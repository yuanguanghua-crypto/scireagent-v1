"""业务时区（东八区）一致性回归测试。

背景：生产 TIME_ZONE='UTC'，而逾期/账龄/due_date 等"按日历日"的业务语义必须按
settings.BUSINESS_TIME_ZONE（默认 Asia/Shanghai）判定。生产环境 TIME_ZONE 与
BUSINESS_TIME_ZONE 相差 8 小时，因此**本地时间 00:00-07:59 之间，UTC 日期与
业务日期整整差一天** —— 任何用 UTC 日历日的实现都会在这个窗口产生错误。

本文件锁定三条一致性契约：
1. ar_aging() 的 as_of 与分桶基于业务日期；
2. ar_aging() 与 Invoice.is_overdue 对"是否逾期"必须同结论（防语义分裂）；
3. 开票生成的 due_date / invoice_no 年份基于业务日期。

伪造时刻统一用「东八区刚过零点、UTC 还在昨天」这一最恶劣窗口。
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone as dj_tz

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import SKUFactory
from apps.transactions.models import (
    Invoice, InvoiceSequence, Order, OrderItem, business_today,
)
from apps.transactions.services import InvoiceService, PaymentArService

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