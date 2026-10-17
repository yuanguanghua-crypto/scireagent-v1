"""checkout 单号（ORD-YYYYMMDD-NNN）计数器回归测试。

★ 本次修复的缺陷（生产已实际发生）：checkout 用
  `Order.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count() + 1`
  取序号，有两个独立问题：

  ① **口径错**：该 count() 没有区分单据来源。PO 单走
     `apps/transactions/services.py` 的 `PoSubmissionService.submit`，单号是
     `ORD-{uuid8}`（uuid 版），但它同样落在当日窗口内 ⇒ **被计入 checkout 序号**。
     生产实测：2026-07-17 存在 004–007 跳号，而 Order.id 连续 1–16、无任何删除
     ⇒ 跳号只能由"uuid 单污染计数"解释。

  ② **会回退**：count() 在删单后变小 ⇒ 可能生成与已存在单号冲突的编号
     （已实测复现 UNIQUE constraint failed）。

修法：新增专用计数器表 `OrderSequence(biz_date unique, last_number)`，
取号走 `select_for_update() + get_or_create()`，与 uuid 版 PO 单**彻底解耦**。
单号格式 `ORD-YYYYMMDD-NNN` 不变（生产已有单、前端/客服/对账都依赖它）。

────────────────────────────────────────────────────────────────────────
⚠️ sqlite 能验证什么 / 不能验证什么（务必读，不要误读"全绿"）

sqlite 下 `select_for_update()` 是 **no-op**（实发 SQL 不含 FOR UPDATE），
且 sqlite 是整库文件锁 ⇒ 即使"正确"的计数器方案在真并发下也会假失败。
所以本文件只覆盖**纯逻辑不变量**（单调性 / 不冲突 / 跨日重置 / 格式 /
PO 单不污染），**并发互斥性未在本地验证**，见 TestPostgresOnlyConcurrency。

⚠️ 另有已知事实：`config/settings/base.py` 里 sqlite 的 `timeout: 30` 是死代码
（OPTIONS 被后续代码覆盖，实测未生效），因此不要指望它能救并发写。
"""
import re
import threading
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.utils import timezone as dj_tz
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Order
from apps.transactions.services import PoSubmissionService
from apps.transactions.tests.factories import BasketFactory

BIZ = ZoneInfo('Asia/Shanghai')


def _seq_model():
    """局部导入计数器模型。

    ★ 刻意不在模块顶层 import：这样在**修复前**（模型尚不存在）本文件仍能
      collection 成功，让"PO 单污染序号""删单回退"等测试真正跑到断言并**语义红**，
      而不是被一个 ImportError 掩盖。
    """
    from apps.transactions.models import OrderSequence
    return OrderSequence

# 东八区刚过零点、UTC 还在前一天 —— 最恶劣的日切窗口。
FAKE_NOW = datetime(2026, 10, 16, 16, 30, tzinfo=ZoneInfo('UTC'))
FAKE_BIZ_DATE = date(2026, 10, 17)
# 次一业务日，用于"跨日重置"
FAKE_NOW_NEXT = datetime(2026, 10, 17, 16, 30, tzinfo=ZoneInfo('UTC'))
FAKE_BIZ_DATE_NEXT = date(2026, 10, 18)

# 序号版单号格式（格式不可变的守门正则）
SEQ_ORDER_NO_RE = re.compile(r'^ORD-(\d{8})-(\d{3,})$')


# ── helpers ─────────────────────────────────────────────────────────────

def _po_order(user, tag):
    """造一张 **uuid 版 PO 单** —— 走生产同一条路径（PoSubmissionService.submit）。

    ★ 这是本次缺陷的污染源：它落在 Order 表里、当日 created_at 窗口内，
    但单号是 uuid 版，既不该消耗 checkout 序号、也不该被 count() 计入。
    """
    sku = SKUFactory()
    return PoSubmissionService.submit(user, {
        'po_number': f'PO-POLLUTE-{tag}',
        'items': [{'sku_id': sku.id, 'quantity': 1, 'unit_price': '10.00'}],
    })


def _checkout(user, po_suffix):
    """走真实 HTTP 路径 checkout，返回新建的 Order。"""
    client = APIClient()
    client.force_authenticate(user)
    product = ProductFactory()
    sku = SKUFactory(product=product, price=Decimal('100.00'))
    BasketFactory(user=user, product=product, sku=sku, quantity=1)
    resp = client.post('/api/v1/checkout/', {
        'payment_method': 'purchase_order',
        'po_number': f'PO-SEQ-{po_suffix}',
        'shipping_name': 'Test',
        'shipping_address': '123 Main St',
    }, format='json')
    assert resp.status_code == 201, f'checkout 失败：{resp.data}'
    return Order.objects.get(order_no=resp.data['order_no'])


# ── 不变量 ①（★核心）：PO uuid 单不得计入 checkout 序号 ────────────────────

@pytest.mark.django_db
class TestPoOrderDoesNotPolluteCheckoutSequence:
    """★ 本次修复的核心目标：计数器只数 checkout 单，PO uuid 单不再污染序号。

    改前：4 张 uuid PO 单 + 1 次 checkout ⇒ seq = 4+1 = 5（跳号）。
    改后：同样场景 ⇒ seq = 1。
    """

    def test_four_uuid_po_orders_then_checkout_still_gets_001(self, monkeypatch):
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        user = UserFactory()

        # 先造 4 张 uuid 版 PO 单（生产实测正是这个形态）
        po_orders = [_po_order(user, i) for i in range(4)]
        for o in po_orders:
            assert not SEQ_ORDER_NO_RE.match(o.order_no), (
                f'PO 单应是 uuid 版单号，实际 {o.order_no}'
            )

        order = _checkout(user, 'POLL1')
        assert order.order_no.endswith('-001'), (
            f'4 张 uuid PO 单不得消耗 checkout 序号，新单应为 -001，'
            f'实际 {order.order_no}（这就是生产 004-007 跳号的成因）'
        )

    def test_uuid_po_orders_do_not_advance_counter_row(self):
        """计数器行只被 checkout 推进；PO 单提交后计数器不应出现/变化。"""
        OrderSequence = _seq_model()
        user = UserFactory()
        before = OrderSequence.objects.count()

        _po_order(user, 'CTR1')
        _po_order(user, 'CTR2')

        assert OrderSequence.objects.count() == before, (
            'PO 单（uuid 版）不得触碰 OrderSequence 计数器'
        )

    def test_interleaved_po_and_checkout_sequence_is_dense(self):
        """PO 单与 checkout 交错时，checkout 序号必须是 001,002,003（无空洞）。"""
        user = UserFactory()
        got = []
        for i in range(3):
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(dj_tz, 'now', lambda: FAKE_NOW)
                _po_order(user, f'MIX{i}')          # uuid 单
                got.append(_checkout(user, f'MIX{i}').order_no.rsplit('-', 1)[1])
        assert got == ['001', '002', '003'], f'序号应连续无空洞，实际 {got}'


# ── 不变量 ②：单调性 —— 删光订单后计数器绝不回退 ──────────────────────────

@pytest.mark.django_db
class TestSequenceMonotonicity:
    """删单后序号只能前进。改前 count() 会回退 ⇒ 撞已存在单号。"""

    def test_counter_does_not_rewind_after_all_orders_deleted(self, monkeypatch):
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        user = UserFactory()

        first = _checkout(user, 'MONO1').order_no     # 001
        second = _checkout(user, 'MONO2').order_no    # 002
        assert first.endswith('-001') and second.endswith('-002')

        # 删光当日全部订单 —— 改前 count() 归零，下一单会重新拿到 001
        Order.objects.all().delete()
        assert Order.objects.count() == 0

        third = _checkout(user, 'MONO3').order_no
        assert third.endswith('-003'), (
            f'删光订单后计数器不得回退，应继续 003，实际 {third}'
        )

        OrderSequence = _seq_model()
        row = OrderSequence.objects.get(biz_date=FAKE_BIZ_DATE)
        assert row.last_number == 3, f'计数器应停在 3，实际 {row.last_number}'

    def test_deleting_a_middle_order_does_not_free_its_number(self, monkeypatch):
        """删中间一张（-002）后，下一单必须是 -003，不能复用 -002。"""
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        user = UserFactory()

        _checkout(user, 'MID1')                              # 001
        victim = _checkout(user, 'MID2')                     # 002
        c = _checkout(user, 'MID3')                          # 003
        assert victim.order_no.endswith('-002')
        assert c.order_no.endswith('-003')

        victim.delete()
        d = _checkout(user, 'MID4')
        assert d.order_no.endswith('-004'), (
            f'删中间单后应拿到 -004（计数器继续前进），实际 {d.order_no}'
        )
        assert d.order_no != c.order_no, '不得复用已删单占用的编号'


# ── 不变量 ③：删除后不产生 unique 冲突 ───────────────────────────────────

@pytest.mark.django_db
class TestNoUniqueConflictAfterDelete:
    """改前已实测复现 UNIQUE constraint failed；改后由单调计数器保证不冲突。"""

    def test_no_unique_violation_after_bulk_delete(self, monkeypatch):
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        user = UserFactory()

        for i in range(5):
            _checkout(user, f'DEL{i}')
        Order.objects.all().delete()

        # 改前：这里必然 UNIQUE constraint failed（计数器回到 0）
        for i in range(5, 8):
            o = _checkout(user, f'DEL{i}')
            assert o.order_no.endswith(f'-{i + 1:03d}')

        assert len(set(Order.objects.values_list('order_no', flat=True))) == 3, \
            '不应出现重复单号'


# ── 不变量 ④：跨日重置（新业务日从 001 开始） ─────────────────────────────

@pytest.mark.django_db
class TestSequenceResetsPerBusinessDay:
    """计数器按业务日分桶；新业务日的第一单必须是 -001。"""

    def test_new_business_day_starts_at_001(self, monkeypatch):
        OrderSequence = _seq_model()
        user = UserFactory()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(dj_tz, 'now', lambda: FAKE_NOW)
            day1 = _checkout(user, 'D1A')
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(dj_tz, 'now', lambda: FAKE_NOW_NEXT)
            day2 = _checkout(user, 'D2A')

        assert day1.order_no == 'ORD-20261017-001', day1.order_no
        assert day2.order_no == 'ORD-20261018-001', (
            f'新业务日应从 001 重新开始，实际 {day2.order_no}'
        )
        assert OrderSequence.objects.filter(
            biz_date__in=[FAKE_BIZ_DATE, FAKE_BIZ_DATE_NEXT]).count() == 2

    def test_counter_is_keyed_by_business_date_not_utc_date(self, monkeypatch):
        """★ 业务日分桶必须用 business_today()，不是 UTC 日期。

        东八区 00:30（UTC 16:30前一天）checkout ⇒ 计数器行的 biz_date 是
        业务日 10-17，且**不得**为 UTC 的 10-16 建行。
        """
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        OrderSequence = _seq_model()
        user = UserFactory()
        order = _checkout(user, 'TZKEY')

        assert order.order_no.startswith('ORD-20261017-'), order.order_no
        assert OrderSequence.objects.filter(biz_date=date(2026, 10, 17)).exists()
        assert not OrderSequence.objects.filter(biz_date=date(2026, 10, 16)).exists(), (
            '不得按 UTC 日期建计数器行'
        )


# ── 不变量 ⑤：单号格式不变 ───────────────────────────────────────────────

@pytest.mark.django_db
class TestOrderNoFormatUnchanged:
    """ORD-YYYYMMDD-NNN 必须保持 —— 生产已有单、前端/客服/对账都依赖。"""

    def test_first_order_of_day_is_three_digit_001(self, monkeypatch):
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        user = UserFactory()
        order = _checkout(user, 'FMT1')
        assert re.match(r'^ORD-20261017-\d{3}$', order.order_no), order.order_no
        assert order.order_no.endswith('-001')

    def test_seq_crosses_999_without_breaking_format(self, monkeypatch):
        """序号超过 999 后格式仍需可解析（不得截断/加前缀）。"""
        OrderSequence = _seq_model()
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        OrderSequence.objects.create(biz_date=FAKE_BIZ_DATE, last_number=998)
        user = UserFactory()
        o1 = _checkout(user, 'BIG1')
        o2 = _checkout(user, 'BIG2')
        assert o1.order_no == 'ORD-20261017-999', o1.order_no
        assert o2.order_no == 'ORD-20261017-1000', o2.order_no
        assert SEQ_ORDER_NO_RE.match(o2.order_no), o2.order_no

    def test_generated_order_no_always_matches_seq_pattern(self, monkeypatch):
        monkeypatch.setattr(dj_tz, 'now', lambda: FAKE_NOW)
        user = UserFactory()
        for i in range(4):
            o = _checkout(user, f'PAT{i}')
            m = SEQ_ORDER_NO_RE.match(o.order_no)
            assert m, f'单号 {o.order_no} 不符合 ORD-YYYYMMDD-NNN'


# ── 回填（数据迁移）逻辑 ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestBackfillLogic:
    r"""存量回填：从既有 order_no 反推每个业务日已用的最大序号。

    ★ 为什么取 max 而不是 count：生产 2026-07-17 已有 004-007 跳号，
      count 会低估 ⇒ 新单会撞已存在单号。必须按 max 回填。
    ★ 为什么 uuid 单天然被排除：uuid 版单号无第二个 '-'
      （`ORD-{8位HEX}`），正则 `^ORD-(\d{8})-(\d{3,})$` 匹配不上。
    """

    SEQ_RE = re.compile(r'^ORD-(\d{8})-(\d{3,})$')

    def _parse(self, order_no):
        m = self.SEQ_RE.match(order_no or '')
        if not m:
            return None
        d = datetime.strptime(m.group(1), '%Y%m%d').date()
        return d, int(m.group(2))

    def test_regex_excludes_uuid_orders(self):
        for uuid_no in ('ORD-A1B2C3D4', 'ORD-0000ABCD', 'ORD-12345678'):
            assert self._parse(uuid_no) is None, f'{uuid_no} 不应被解析为序号版单号'

    def test_backfill_uses_max_not_count(self):
        user = UserFactory()
        for seq in ('001', '002', '003', '008'):
            Order.objects.create(
                user=user, order_no=f'ORD-20260717-{seq}',
                status=Order.Status.CONFIRMED, po_number=None,
                subtotal=Decimal('1.00'), grand_total=Decimal('1.00'),
            )
        parsed = [self._parse(o) for o in
                  Order.objects.values_list('order_no', flat=True)]
        assert all(p is not None for p in parsed)
        assert max(p[1] for p in parsed) == 8, (
            '必须取 max（008），count 会得 4 ⇒ 新单 005 撞已存在单号'
        )


# ── ⚠️ 需 Postgres 环境的并发互斥验证（本地不跑、不声称通过） ──────────────

@pytest.mark.django_db(transaction=True)
class TestPostgresOnlyConcurrency:
    """⚠️ **并发互斥性未在本地验证。**

    sqlite 下 `select_for_update()` 是 no-op 且整库文件锁 ⇒ 本地跑必假失败
    （已实测：3 线程真并发抽出重复号1,2,1）。真实验证必须在 Postgres 上进行：

        DB_ENGINE=postgres python -m pytest \\
            apps/transactions/tests/test_order_sequence.py::TestPostgresOnlyConcurrency -q

    断言的性质：N 个并发 checkout 抽出的序号**两两不同**且**恰好覆盖 1..N**。
    """

    def test_concurrent_checkout_numbers_are_unique_and_dense(self):
        if connection.vendor != 'postgresql':
            pytest.skip(
                '需 Postgres：sqlite 下 select_for_update 为 no-op + 整库文件锁，'
                '本地无法验证并发互斥（sqlite 结果为假红）'
            )

        user = UserFactory()
        # 预建各用户购物车，避免并发期创建 Product/SKU 干扰
        products = []
        for i in range(8):
            p = ProductFactory()
            s = SKUFactory(product=p, price=Decimal('100.00'))
            BasketFactory(user=user, product=p, sku=s, quantity=1)
            products.append((p, s))

        results, errors = [], []
        lock = threading.Lock()
        barrier = threading.Barrier(len(products))

        def worker(i):
            try:
                c = APIClient()
                c.force_authenticate(user)
                barrier.wait(timeout=30)
                r = c.post('/api/v1/checkout/', {
                    'payment_method': 'purchase_order',
                    'po_number': f'PO-CONC-{i}',
                    'shipping_name': 'T', 'shipping_address': 'A',
                }, format='json')
                with lock:
                    if r.status_code == 201:
                        results.append(r.data['order_no'])
                    else:
                        errors.append(r.status_code)
            except Exception as e:            # noqa: BLE001
                with lock:
                    errors.append(repr(e))

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(len(products))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert not errors, f'并发 checkout 出现失败：{errors}'
        assert len(results) == len(products), f'成功数不符：{results}'
        assert len(set(results)) == len(results), f'出现重复单号：{sorted(results)}'
        seqs = sorted(int(r.rsplit('-', 1)[1]) for r in results)
        assert seqs == list(range(1, len(products) + 1)), f'序号非稠密 1..N：{seqs}'