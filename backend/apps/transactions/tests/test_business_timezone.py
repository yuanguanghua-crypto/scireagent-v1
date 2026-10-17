"""业务时区（东八区）一致性回归测试。

背景：生产 TIME_ZONE='UTC'，而逾期/账龄/due_date 等"按日历日"的业务语义必须按
settings.BUSINESS_TIME_ZONE（默认 Asia/Shanghai）判定。生产环境 TIME_ZONE 与
BUSINESS_TIME_ZONE 相差 8 小时，因此**本地时间 00:00-07:59 之间，UTC 日期与
业务日期整整差一天** —— 任何用 UTC 日历日的实现都会在这个窗口产生错误。

本文件锁定三条一致性契约：
1. ar_aging() 的 as_of 与分桶基于业务日期；
2. ar_aging() 与 Invoice.is_overdue 对"是否逾期"必须同结论（防语义分裂）；
3. 开票生成的 due_date / invoice_no 年份基于业务日期。

★ 2026-10-17 追加锁定第四类契约（此前 3 处实现漏用 business_today）：
4a. PO 交付日期下限校验必须按业务日历日；
4b. 单号日切序列必须按业务日历日（含 `__date` lookup 时区行为取证）；
4d. business_today 的真相源在 core/，documents 不得跨 app 依赖 transactions。
    （4c SDS 修订日期的用例在其归属目录
     apps/documents/tests/test_business_timezone_sds.py。）

★ 2026-10-17 再追加 4e：上一轮只把 4b 的 **seq 统计窗口**改成了业务日区间，
   却漏改了 checkout 单号**日期前缀**（仍取 UTC 的 `timezone.now().strftime()`），
   导致同一业务日的订单被拆到两个前缀里。4e 用三个用例锁死前缀本身：
跨日窗口 / 跨年窗口 / 与 seq 窗口同源。

伪造时刻统一用「东八区刚过零点、UTC 还在昨天」这一最恶劣窗口。
"""
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone as dj_tz
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import (
    Invoice, InvoiceSequence, Order, OrderItem, business_today,
)
from apps.transactions.services import InvoiceService, PaymentArService
from apps.transactions.tests.factories import BasketFactory

BIZ = ZoneInfo('Asia/Shanghai')

# 伪造时刻：UTC 2026-10-16 16:30 == 东八区 2026-10-17 00:30
#   → UTC 日期 = 2026-10-16，业务日期 = 2026-10-17（差一天）
FAKE_NOW = datetime(2026, 10, 16, 16, 30, tzinfo=ZoneInfo('UTC'))
FAKE_BIZ_DATE = date(2026, 10, 17)
FAKE_UTC_DATE = date(2026, 10, 16)

# 跨年时刻：UTC 2026-12-31 16:30 == 东八区 2027-01-01 00:30
FAKE_NOW_YEAR = datetime(2026, 12, 31, 16, 30, tzinfo=ZoneInfo('UTC'))
FAKE_BIZ_YEAR = 2027


def _order(user, order_no='ORD-TZ-0001', status=Order.Status.DELIVERED):
    order = Order.objects.create(
        user=user, order_no=order_no, status=status,
        po_number=None,  # 显式 None，避免 unique 空串冲突
        subtotal=Decimal('100.00'), grand_total=Decimal('100.00'),
    )
    sku = SKUFactory()
    OrderItem.objects.create(order=order, sku=sku, quantity=1, unit_price=Decimal('100.00'))
    return order


def _invoice(order, invoice_no, due_date, status=Invoice.Status.ISSUED, total='100.00'):
    """直接构造发票，due_date 由调用方显式给定（相对业务日期）。"""
    return Invoice.objects.create(
        order=order, invoice_no=invoice_no, status=status,
        issued_at=dj_tz.now(),
        due_date=due_date,
        subtotal=Decimal(total), grand_total=Decimal(total),
    )


@pytest.mark.django_db
class TestArAgingBusinessDate:
    """契约 1：ar_aging() 的 as_of 与分桶基于业务日期，不是 UTC 日期。"""

    def test_as_of_uses_business_date_not_utc_date(self):
        """核心断言：东八区已跨日、UTC 未跨日时，as_of 必须是业务日期。"""
        assert FAKE_BIZ_DATE != FAKE_UTC_DATE, '伪造时刻必须落在跨日窗口内，否则本测试无意义'
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            data = PaymentArService.ar_aging()
        assert data['as_of'] == str(FAKE_BIZ_DATE)

    def test_bucket_boundary_shifted_by_business_date(self):
        """due_date == 业务日期-1：应落 '30' 桶。

        若实现仍用 UTC 日期，则 age = 2026-10-16 - 2026-10-16 = 0 → 误落 'current'。
        """
        user = UserFactory()
        order = _order(user, 'ORD-TZ-B1')
        inv = _invoice(order, 'INV-TZ-B1', due_date=FAKE_BIZ_DATE - timedelta(days=1))

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            data = PaymentArService.ar_aging()

        assert data['buckets']['current']['count'] == 0, '逾期发票不应落在 current 桶'
        assert data['buckets']['30']['count'] == 1
        assert data['buckets']['30']['amount'] == 100.0

    def test_due_date_equals_business_date_is_current(self):
        """due_date 恰为业务日期当天：age=0 → 'current'（不算逾期）。"""
        user = UserFactory()
        order = _order(user, 'ORD-TZ-B2')
        _invoice(order, 'INV-TZ-B2', due_date=FAKE_BIZ_DATE)

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            data = PaymentArService.ar_aging()

        assert data['buckets']['current']['count'] == 1
        assert data['buckets']['30']['count'] == 0


@pytest.mark.django_db
class TestArAgingMatchesIsOverdue:
    """契约 2（防回归核心）：ar_aging 与 is_overdue 必须同结论。"""

    @pytest.mark.parametrize('offset_days', [-90, -60, -31, -30, -1, 0, 1, 10])
    def test_bucket_agrees_with_is_overdue(self, offset_days):
        """对每张未付发票：(age>0) 必须等价于 is_overdue。

        age = (business_today - due_date).days；分桶规则 age<=0 → 'current'。
        """
        user = UserFactory()
        order = _order(user, f'ORD-TZ-C{offset_days}')
        inv = _invoice(order, f'INV-TZ-C{offset_days}', due_date=FAKE_BIZ_DATE + timedelta(days=offset_days))

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            data = PaymentArService.ar_aging()
            overdue_flag = inv.is_overdue
            age = (FAKE_BIZ_DATE - inv.due_date).days

        in_current = data['buckets']['current']['count'] == 1
        assert in_current == (age <= 0), f'offset={offset_days} age={age} 分桶与 age 规则不符'
        assert overdue_flag == (age > 0), (
            f'offset={offset_days}: is_overdue={overdue_flag} 与 age={age} 不一致'
        )
        # 二者必须互相推出：is_overdue == not in_current
        assert overdue_flag != in_current, (
            f'offset={offset_days}: is_overdue={overdue_flag} 但 current 桶={in_current} —— 语义分裂'
        )


@pytest.mark.django_db
class TestIssueDueDateBusinessTimezone:
    """契约 3：开票端 due_date 与 invoice_no 年份基于业务日期。"""

    def test_net30_due_date_from_business_date(self):
        """东八区凌晨开票 NET30 → due_date = 业务日期 + 30。"""
        user = UserFactory()
        order = _order(user, 'ORD-TZ-D1')

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            inv = InvoiceService.issue(order, payment_terms=Order.PaymentTerms.NET30, actor=user)

        assert inv.due_date == FAKE_BIZ_DATE + timedelta(days=30)

    def test_net60_due_date_from_business_date(self):
        user = UserFactory()
        order = _order(user, 'ORD-TZ-D2')

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            inv = InvoiceService.issue(order, payment_terms=Order.PaymentTerms.NET60, actor=user)

        assert inv.due_date == FAKE_BIZ_DATE + timedelta(days=60)

    def test_net45_due_date_from_business_date(self):
        user = UserFactory()
        order = _order(user, 'ORD-TZ-D3')

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            inv = InvoiceService.issue(order, payment_terms=Order.PaymentTerms.NET45, actor=user)

        assert inv.due_date == FAKE_BIZ_DATE + timedelta(days=45)

    def test_invoice_no_year_uses_business_year(self):
        """东八区元旦凌晨开票 → 票号年份必须是业务年份（2027），不是 UTC 年份（2026）。"""
        user = UserFactory()
        order = _order(user, 'ORD-TZ-D4')

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW_YEAR):
            inv = InvoiceService.issue(order, payment_terms=Order.PaymentTerms.NET30, actor=user)

        assert FAKE_NOW_YEAR.year != FAKE_BIZ_YEAR, '伪造时刻必须落在跨年窗口内'
        assert inv.invoice_no.startswith(f'INV-{FAKE_BIZ_YEAR}-'), (
            f'票号 {inv.invoice_no} 应使用业务年份 {FAKE_BIZ_YEAR}'
        )
        assert InvoiceSequence.objects.filter(year=FAKE_BIZ_YEAR).exists()

    def test_due_date_does_not_leak_previous_business_year(self):
        """跨年开票：due_date 落在业务年+30，而非 UTC 年+30。"""
        user = UserFactory()
        order = _order(user, 'ORD-TZ-D5')

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW_YEAR):
            inv = InvoiceService.issue(order, payment_terms=Order.PaymentTerms.NET30, actor=user)

        assert inv.due_date == date(FAKE_BIZ_YEAR, 1, 31), f'due_date={inv.due_date}'
        # 序列号未回退到 UTC 年份
        assert not InvoiceSequence.objects.filter(year=FAKE_NOW_YEAR.year).exists()


@pytest.mark.django_db
class TestBusinessTodayHelper:
    """business_today() 自身：不能等价于 timezone.localdate()。"""

    def test_business_today_shifted_in_early_hours(self):
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            assert business_today() == FAKE_BIZ_DATE

    def test_business_today_matches_localtime(self):
        """正常时段：业务日期 == 系统本地日期（本机为 UTC+8）。"""
        assert business_today() == datetime.now(BIZ).date()


@pytest.mark.django_db
class TestPoDeliveryDateBusinessTimezone:
    """契约 4a：PO 交付日期下限校验必须用 business_today()，不是 date.today()。

    ⚠️ 关键测试前提：`date.today()` 取的是**进程操作系统时区**。本机恰好是 UTC+8，
    于是本机上 `date.today()` 恰好等于业务日期，缺陷被掩盖、测试假绿。
    生产容器 TZ 为 UTC ⇒ `date.today()` 等于 UTC 日期。
    因此本类用 `_patch_process_date_today` 把**被测模块内**的 `date.today()`
    固定为 UTC 日期，精确复现生产行为（刻意不 patch 全局 `datetime.date`，
    避免污染 DRF 的日期解析）。
    """

    def _submit(self, delivery_date_str):
        from apps.transactions.api.v1.serializers import PoSubmitSerializer
        sku = SKUFactory()
        data = {
            'requested_delivery_date': delivery_date_str,
            'items': [{
                'sku_id': sku.pk,
                'quantity': 1,
                'unit_price': '10.00',
            }],
        }
        s = PoSubmitSerializer(data=data)
        valid = s.is_valid()
        return valid, s

    def test_process_today_is_utc_in_production_like_env(self):
        """前置自检：确认模拟环境成立，否则后续断言无意义。

        修复后 serializers 已不再引用 date.today()，此时该属性不存在 ⇒
        说明"进程本地日期"这条错误路径已被彻底移除，本用例自动跳过模拟。
        """
        from apps.transactions.api.v1 import serializers as ser
        if not hasattr(ser, 'date'):
            pytest.skip('serializers 已不再引用 date.today()（缺陷路径已移除）')
        with _patch_process_date_today(ser, FAKE_UTC_DATE):
            assert ser.date.today() == FAKE_UTC_DATE
            assert ser.date.today() != FAKE_BIZ_DATE

    def test_yesterday_in_biz_tz_must_be_rejected(self):
        """东八区凌晨：'昨天'（= UTC 今天）已属过去，必须拒绝。"""
        from apps.transactions.api.v1 import serializers as ser
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW), \
                _patch_process_date_today(ser, FAKE_UTC_DATE, soft=True):
            valid, s = self._submit((FAKE_BIZ_DATE - timedelta(days=1)).isoformat())
        assert valid is False, (
            '东八区凌晨提交"昨天"的交付日期必须被拒绝'
            f'（date.today()={FAKE_UTC_DATE} 会错误放行）'
        )
        assert 'past' in str(s.errors).lower()

    def test_utc_today_in_biz_tz_is_rejected_even_if_utc_today(self):
        """核心边界断言：UTC 今天（= 业务昨天）必须被拒。

        若实现用 UTC 日期做下限，value == UTC 今天 会通过校验 —— 这正是缺陷。
        """
        assert FAKE_UTC_DATE == FAKE_BIZ_DATE - timedelta(days=1)
        from apps.transactions.api.v1 import serializers as ser
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW), \
                _patch_process_date_today(ser, FAKE_UTC_DATE, soft=True):
            valid, s = self._submit(FAKE_UTC_DATE.isoformat())
        assert valid is False, 'UTC 今天在东八区属昨天，必须拒绝'

    def test_biz_today_itself_is_accepted(self):
        """交付日期 == 业务日期当天：应通过（边界不误杀）。"""
        from apps.transactions.api.v1 import serializers as ser
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW), \
                _patch_process_date_today(ser, FAKE_UTC_DATE, soft=True):
            valid, s = self._submit(FAKE_BIZ_DATE.isoformat())
        assert valid is True, f'交付日期=业务日期应通过，实际错误：{s.errors}'


@pytest.mark.django_db
class TestOrderNoSequenceBusinessDate:
    """契约 4b：单号日切必须按业务日历日（含 __date lookup 的时区行为取证）。"""

    def _order_at(self, user, order_no, moment):
        o = Order.objects.create(
            user=user, order_no=order_no, status=Order.Status.CONFIRMED,
            po_number=None, subtotal=Decimal('1.00'), grand_total=Decimal('1.00'),
        )
        Order.objects.filter(pk=o.pk).update(created_at=moment)
        return o

    def test_date_lookup_basis_is_settings_timezone_not_business_tz(self):
        """★ 取证：Django `created_at__date=` 按 settings.TIME_ZONE(UTC) 截断。

        两条订单分别落在业务日 10-17（UTC 10-16 16:30）与业务日 10-16（UTC 10-16 15:30）。
        按 UTC 日期查 → 两条都命中；按业务日期查 → 只命中第一条。
        这证明生产 TIME_ZONE='UTC' 时 `__date=` 不能直接用来做业务日切。
        """
        from django.conf import settings
        assert settings.TIME_ZONE == 'UTC', '本取证前提：settings.TIME_ZONE 为 UTC'

        user = UserFactory()
        self._order_at(user, 'ORD-BIZDAY-0001', datetime(2026, 10, 16, 16, 30, tzinfo=ZoneInfo('UTC')))
        self._order_at(user, 'ORD-BIZPREV-0001', datetime(2026, 10, 16, 15, 30, tzinfo=ZoneInfo('UTC')))

        by_utc_date = set(Order.objects.filter(
            order_no__startswith='ORD-BIZ',
            created_at__date=FAKE_UTC_DATE,
        ).values_list('order_no', flat=True))
        assert by_utc_date == {'ORD-BIZDAY-0001', 'ORD-BIZPREV-0001'}, (
            f'__date=UTC日期 应命中两条，实际 {by_utc_date}'
        )

        start, end = business_day_bounds_probe(FAKE_BIZ_DATE)
        by_biz_date = set(Order.objects.filter(
            order_no__startswith='ORD-BIZ',
            created_at__gte=start, created_at__lt=end,
        ).values_list('order_no', flat=True))
        assert by_biz_date == {'ORD-BIZDAY-0001'}, (
            f'显式业务日区间应只命中业务日 10-17 的订单，实际 {by_biz_date}'
        )

    def test_checkout_seq_resets_on_business_day_boundary(self):
        """东八区 00:30 checkout：单号序号必须接着"业务日 10-17"的既有进度。

        已存在 1 张业务日 10-17 的checkout 单⇒ 新单 seq 必须是 002。
        改前按 UTC 日期（10-16）统计，会把业务日 10-16 的订单也算进去 ⇒ seq 错位。

        ★ 2026-10-17：取号改为专用计数器 OrderSequence 后，"当日已发到第几号"
          的真相源是计数器行而非 `count()`（旧 count() 会把 uuid 版 PO 单也计入，
          生产 2026-07-17 因此出现 004-007 跳号）。
          故此处显式把计数器置为 1 来表达"当日已发出 1 单"，并保留业务日 10-16
          的订单作为"不得串号"的反例 —— 跨业务日不得串号这条契约不变。
        """
        from apps.transactions.models import OrderSequence

        client = APIClient()
        user = UserFactory()
        client.force_authenticate(user)
        product = ProductFactory()
        sku = SKUFactory(product=product, price=Decimal('100.00'))
        BasketFactory(user=user, product=product, sku=sku, quantity=1)

        # 业务日 10-16 的订单（UTC 10-16 15:30）——不该计入 10-17 的序号
        self._order_at(user, 'ORD-PREV-0001', datetime(2026, 10, 16, 15, 30, tzinfo=ZoneInfo('UTC')))
        # 业务日 10-17 的订单（UTC 10-16 16:30）——应计入
        self._order_at(user, 'ORD-CURR-0001', datetime(2026, 10, 16, 16, 30, tzinfo=ZoneInfo('UTC')))
        # 计数器：业务日 10-17 已发到 001；业务日 10-16 另有一桶更高进度，
        # 用于反证"取号只看自己的业务日桶，不受相邻日影响"
        OrderSequence.objects.create(biz_date=FAKE_BIZ_DATE, last_number=1)
        OrderSequence.objects.create(biz_date=FAKE_BIZ_DATE - timedelta(days=1), last_number=7)

        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            resp = client.post('/api/v1/checkout/', {
                'payment_method': 'purchase_order',
                'po_number': 'PO-TZ-0001',
                'shipping_name': 'Test',
                'shipping_address': '123 Main St',
            }, format='json')
        assert resp.status_code == 201, f'checkout 失败：{resp.data}'

        created = Order.objects.get(order_no=resp.data['order_no'])
        seq = created.order_no.rsplit('-', 1)[1]
        assert seq == '002', (
            f'业务日 10-17 计数器已到 001，新单序号应为 002，实际 {created.order_no}'
        )
        # 相邻业务日的计数器不得被本次取号改动
        prev_row = OrderSequence.objects.get(biz_date=FAKE_BIZ_DATE - timedelta(days=1))
        assert prev_row.last_number == 7, '相邻业务日的计数器不得被污染'

    def _checkout(self, user, po_number):
        client = APIClient()
        client.force_authenticate(user)
        product = ProductFactory()
        sku = SKUFactory(product=product, price=Decimal('100.00'))
        BasketFactory(user=user, product=product, sku=sku, quantity=1)
        resp = client.post('/api/v1/checkout/', {
            'payment_method': 'purchase_order',
            'po_number': po_number,
            'shipping_name': 'Test',
            'shipping_address': '123 Main St',
        }, format='json')
        assert resp.status_code == 201, f'checkout 失败：{resp.data}'
        return Order.objects.get(order_no=resp.data['order_no'])

    def test_order_no_date_prefix_uses_business_date_not_utc_date(self):
        """★ 本次缺陷：单号日期段曾直接取 UTC 的 `timezone.now().strftime()`。

        东八区 00:30（UTC 还在前一天 16:30）checkout ⇒ 日期段必须是业务日 10-17，
        而不是 UTC 日期 10-16。否则同一业务日的订单被拆到两个前缀里，
        与按业务日做的 seq 统计窗口错位。
        """
        assert FAKE_UTC_DATE.strftime('%Y%m%d') != FAKE_BIZ_DATE.strftime('%Y%m%d'), \
            '伪造时刻必须落在跨日窗口内，否则本测试无意义'

        user = UserFactory()
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            order = self._checkout(user, 'PO-TZP-0001')
        assert order.order_no.startswith(f'ORD-{FAKE_BIZ_DATE.strftime("%Y%m%d")}-'), (
            f'单号 {order.order_no} 的日期段应为业务日 {FAKE_BIZ_DATE}'
        )
        assert not order.order_no.startswith(f'ORD-{FAKE_UTC_DATE.strftime("%Y%m%d")}-'), (
            f'单号 {order.order_no} 的日期段回落成了 UTC 日期 {FAKE_UTC_DATE}'
        )

    def test_order_no_date_prefix_uses_business_year_not_utc_year(self):
        """跨年窗口：东八区元旦凌晨（UTC 12-31）⇒ 年份必须是 2027 而非 2026。"""
        user = UserFactory()
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW_YEAR):
            order = self._checkout(user, 'PO-TZP-0002')
        assert FAKE_NOW_YEAR.year != FAKE_BIZ_YEAR, '伪造时刻必须落在跨年窗口内'
        assert order.order_no.startswith(f'ORD-{FAKE_BIZ_YEAR}0101-'), (
            f'单号 {order.order_no} 的年份应为业务年 {FAKE_BIZ_YEAR}，不是 UTC 年 {FAKE_NOW_YEAR.year}'
        )

    def test_date_prefix_and_seq_window_share_one_business_day(self):
        """★ 前缀与 seq 统计窗口必须出自**同一个**业务日变量。

        锁住"同源"这条契约：单号前缀的日期段 == seq 过滤窗口左端点所在的业务日。
        否则会出现"seq 按业务日统计、前缀按另一套日期"的错位（本次修复前的状态）。
        """
        day_start, day_end = business_day_bounds_probe(FAKE_BIZ_DATE)
        user = UserFactory()
        with patch.object(dj_tz, 'now', return_value=FAKE_NOW):
            order = self._checkout(user, 'PO-TZP-0003')
        assert order.order_no.split('-')[1] == day_start.strftime('%Y%m%d'), (
            f'前缀日期段应与 seq 窗口左端点 {day_start} 同日，'
            f'实际单号 {order.order_no}，窗口 [{day_start}, {day_end})'
        )


@pytest.mark.django_db
class TestSharedHelperPlacement:
    """契约 4d：business_today 的真相源在 core/，两个 app 都不该跨 app 依赖。

    documents（合规文档域）不得为了拿一个日期助手而 import 交易域的 models，
    否则形成 documents → transactions 的架构倒置。
    """

    def test_business_today_lives_in_core(self):
        from core.business_time import business_today as core_bt
        assert core_bt is business_today, 'transactions.models 应转发 core 的实现'

    def test_documents_workflow_does_not_import_transactions(self):
        """架构守卫：documents 服务层不得 import transactions。"""
        import apps.documents.services.workflow as wf
        src = Path(wf.__file__).read_text(encoding='utf-8')
        offenders = [
            ln.strip() for ln in src.splitlines()
            if 'transactions' in ln and ln.strip().startswith(('import ', 'from '))
        ]
        assert not offenders, f'workflow.py 出现了对 transactions 的 import：{offenders}'

    def test_documents_workflow_uses_business_today(self):
        """documents 必须走 core 的共享助手。"""
        import apps.documents.services.workflow as wf
        assert wf.business_today is business_today


@contextmanager
def _patch_process_date_today(module, fixed, soft=False):
    """把被测模块里 `date.today()` 固定为 `fixed`，模拟生产容器 TZ=UTC。

    为什么必须这么做：`date.today()` 读的是**操作系统进程时区**，既不是 Django 的
    TIME_ZONE 也不是 BUSINESS_TIME_ZONE。本机 OS 时区恰为 UTC+8 ⇒ `date.today()`
    恰好等于业务日期，用 `date.today()` 的实现在本机测试下会**假绿**。
    生产容器 TZ=UTC 时才会暴露该缺陷。

    实现：给模块注入一个 today() 被固定的 date 子类，覆盖模块自己的命名空间 ——
      · `from datetime import date`（serializers）→ 替换模块属性 `date`
      · `import datetime` + `datetime.date.today()`（workflow）→ 替换模块属性 `datetime`
    只影响被测模块自己；**刻意不 patch 全局 `datetime.date`**，否则 Django 的
    DateField.to_python 会因 `parse_date` 拿到非 str 而炸
    （实测 TypeError: fromisoformat: argument must be str）。

    :param soft: True 时，若模块已不再持有该名字（缺陷路径已移除）则静默跳过，
                 让"行为断言"继续成立而不是因 AttributeError 误报失败。
    """
    assert fixed is not None

    class _FixedTodayDate(date):
        @classmethod
        def today(cls):
            return fixed

    class _DatetimeProxy:
        """代理真 datetime 模块，仅把 .date 换成 today() 固定的子类。"""

        def __getattr__(self, name):
            if name == 'date':
                return _FixedTodayDate
            return getattr(datetime, name)

    uses_datetime_module = hasattr(module, 'datetime') and not hasattr(module, 'date')
    if soft and not uses_datetime_module and not hasattr(module, 'date'):
        yield  # 该模块已不再走 date.today()，无需模拟
        return

    if uses_datetime_module:
        with patch.object(module, 'datetime', _DatetimeProxy()):
            yield
    else:
        with patch.object(module, 'date', _FixedTodayDate):
            yield


def business_day_bounds_probe(day):
    """局部辅助：显式构造业务日 [00:00, 次日00:00) aware 区间。

    刻意不复用生产代码，避免"用被测实现验证被测实现"的循环论证。
    """
    tz = ZoneInfo('Asia/Shanghai')
    start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    return start, start + timedelta(days=1)