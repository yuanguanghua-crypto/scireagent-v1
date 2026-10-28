"""缺货拦截 + 运营告警台（2026-10-28）。

覆盖三层：
  1. 判定口径 `StockShortageService.is_short` —— 状态驱动 + 有库存记录才校验数量
  2. 两条下单入口（PO 提交 / 购物车结账）被拦时：**不建订单** + **留痕** + 400 带明细
  3. 运营告警台 API：角色矩阵 / 列表计数 / 标记处理 / 重复合并

★ 为什么第 2 层要断言"不建订单"：拦截位置若被误挪到服务层内部（@transaction.atomic），
  抛错时缺货告警行会跟着回滚 ⇒ 运营什么都看不到，且用户会先看到一个已入库的订单。
  这条断言同时守住"没订单"和"有告警"两件事。
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.inventory.models import Inventory, StockShortageAlert
from apps.inventory.services import InventoryService, StockShortageService
from apps.transactions.models import Order


class ShortageBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='short_res', password='x', email='short@lab.edu',
            organization=self.org, role='researcher')
        self.admin = User.objects.create_user(
            username='short_admin', password='x', organization=self.org, role='admin')
        self.proc = User.objects.create_user(
            username='short_proc', password='x', organization=self.org, role='procurement')

        self.product = Product.objects.create(name='Pseudo-UTP', slug='pseudo-utp-short')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='SC8011-1', price=Decimal('59.00'))
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _track(self, available, location='WH-A', tracked=True):
        """建一条库存记录；`tracked=True` 时同时置显式纳管开关。

        ★ 2026-10-28（4a）：纳管判据已从「有没有 Inventory 行」改为
        `SKU.is_stock_tracked` 显式开关 ⇒ 造「已纳管且有多少货」必须两步都做。
        `is_short(self.sku, ...)` 读的是内存对象的字段，故必须 refresh。
        """
        row = Inventory.objects.create(
            sku=self.sku, location=location, available=available)
        if tracked:
            SKU.objects.filter(pk=self.sku.pk).update(is_stock_tracked=True)
            self.sku.refresh_from_db(fields=['is_stock_tracked'])
        return row


class IsShortRuleTest(ShortageBase):
    """判定口径三态：out_of_stock / 有记录比数量 / 无记录不判定。"""

    def test_out_of_stock_enum_blocks_regardless_of_rows(self):
        self.sku.inventory_status = SKU.InventoryStatus.OUT_OF_STOCK
        self.sku.save(update_fields=['inventory_status'])
        short, available, reason = StockShortageService.is_short(self.sku, 1)
        self.assertTrue(short)
        self.assertEqual(reason, StockShortageAlert.Reason.OUT_OF_STOCK)
        self.assertEqual(available, 0)

    def test_untracked_sku_is_not_judged(self):
        """没有任何库存记录 = 尚未纳入库存管理 ⇒ 不判定（否则生产全站无法下单）。"""
        short, available, reason = StockShortageService.is_short(self.sku, 999)
        self.assertFalse(short, '无库存记录不应判缺货')
        self.assertIsNone(available)
        self.assertEqual(reason, '')

    def test_tracked_but_no_rows_at_all_blocks(self):
        """纳管了却一行库存都没有 ⇒ 可用量按 0 算，必须拦。

        ★ 这是 4a 引入的新语义，也是这个字段存在的理由之一：
        旧判据下「没有库存行」= 「不纳管」= 放行，于是「忘了建库存行」
        和「按需生产本来就不设库存」被混为一谈 —— 而前者本该拦。
        """
        self.sku.is_stock_tracked = True
        self.sku.save(update_fields=['is_stock_tracked'])
        short, available, reason = StockShortageService.is_short(self.sku, 1)
        self.assertTrue(short, '已纳管但无任何库存行 = 可用 0，应拦')
        self.assertEqual(available, 0)
        self.assertEqual(reason, StockShortageAlert.Reason.INSUFFICIENT)

    def test_untracked_but_has_rows_passes(self):
        """显式脱管优先于「有库存行」：按需生产的 SKU 有历史库存行也不该被拦。"""
        self._track(100, tracked=False)
        self.assertFalse(self.sku.is_stock_tracked, 'tracked=False 不应被自动置位')
        short, available, reason = StockShortageService.is_short(self.sku, 999)
        self.assertFalse(short)
        self.assertIsNone(available)
        self.assertEqual(reason, '')

    def test_tracked_and_insufficient_blocks(self):
        self._track(5)
        short, available, reason = StockShortageService.is_short(self.sku, 99)
        self.assertTrue(short)
        self.assertEqual(available, 5)
        self.assertEqual(reason, StockShortageAlert.Reason.INSUFFICIENT)

    def test_tracked_and_enough_passes(self):
        self._track(100)
        short, _, _ = StockShortageService.is_short(self.sku, 99)
        self.assertFalse(short)

    def test_tracked_but_zero_available_blocks(self):
        """有记录但可用量 0 —— 这是"已建账且确实没货"，必须拦。"""
        self._track(0)
        short, available, _ = StockShortageService.is_short(self.sku, 1)
        self.assertTrue(short)
        self.assertEqual(available, 0)

    def test_multiple_locations_are_summed(self):
        self._track(40, location='WH-A')
        self._track(60, location='WH-B')
        short, available, _ = StockShortageService.is_short(self.sku, 99)
        self.assertFalse(short, '多库位应求和后再比较')
        self.assertEqual(available, 100)


class PoSubmitBlockedTest(ShortageBase):
    """PO 提交被拦：400 + 明细 + 告警落库 + 没有订单。"""

    def _payload(self, qty=99):
        return {
            'po_number': 'PO-SHORT-1',
            'shipping_name': 'Buyer',
            'shipping_address': '1 Lab Rd',
            'shipping_email': 'short@lab.edu',
            'items': [{'sku_id': self.sku.id, 'product_id': self.product.id, 'quantity': qty}],
        }

    def test_out_of_stock_blocks_submit_and_records_alert(self):
        self.sku.inventory_status = SKU.InventoryStatus.OUT_OF_STOCK
        self.sku.save(update_fields=['inventory_status'])
        self._auth(self.user)

        before_orders = Order.objects.count()
        r = self.client.post('/api/v1/orders/po/', self._payload(), format='json')

        self.assertEqual(r.status_code, 400, r.content[:400])
        body = r.json()
        self.assertFalse(body['success'])
        err = body['meta']['error']
        self.assertEqual(err['code'], 'OUT_OF_STOCK')
        self.assertIn('SC8011-1', err['message'])
        details = err['details']
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]['sku_code'], 'SC8011-1')
        self.assertEqual(details[0]['requested_quantity'], 99)
        self.assertEqual(details[0]['available_quantity'], 0)

        self.assertEqual(Order.objects.count(), before_orders, '被拦时不得产生订单')

        alert = StockShortageAlert.objects.get()
        self.assertEqual(alert.sku_code, 'SC8011-1')
        self.assertEqual(alert.product_name, 'Pseudo-UTP')
        self.assertEqual(alert.user_email, 'short@lab.edu')
        self.assertEqual(alert.requested_quantity, 99)
        self.assertEqual(alert.source, StockShortageAlert.Source.PO_SUBMIT)
        self.assertEqual(alert.status, StockShortageAlert.Status.NEW)

    def test_tracked_insufficient_blocks_submit(self):
        self._track(10)
        self._auth(self.user)
        r = self.client.post('/api/v1/orders/po/', self._payload(99), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['details'][0]['available_quantity'], 10)
        self.assertEqual(StockShortageAlert.objects.count(), 1)

    def test_untracked_sku_passes_submit(self):
        """生产现状：库存表 0 行 ⇒ 下单必须照旧通过（关键回归，防全站禁单）。"""
        self._auth(self.user)
        r = self.client.post('/api/v1/orders/po/', self._payload(99), format='json')
        self.assertEqual(r.status_code, 201, r.content[:400])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(StockShortageAlert.objects.count(), 0)

    def test_enough_stock_passes_submit(self):
        self._track(1000)
        self._auth(self.user)
        r = self.client.post('/api/v1/orders/po/', self._payload(99), format='json')
        self.assertEqual(r.status_code, 201, r.content[:400])
        self.assertEqual(StockShortageAlert.objects.count(), 0)

    def test_repeat_attempts_merge_within_window(self):
        """同一用户同一 SKU 24h 内重复被拦 ⇒ 合并成一条，occurrences 递增。"""
        self._track(0)
        self._auth(self.user)
        for _ in range(3):
            self.client.post('/api/v1/orders/po/', self._payload(3), format='json')
        self.assertEqual(StockShortageAlert.objects.count(), 1)
        self.assertEqual(StockShortageAlert.objects.get().occurrences, 3)


class CheckoutBlockedTest(ShortageBase):
    """购物车结账同样被拦（此前只查 inventory_status 枚举、不看可用量、不留痕）。"""

    def setUp(self):
        super().setUp()
        from apps.transactions.models import Basket
        Basket.objects.create(user=self.user, product=self.product, sku=self.sku, quantity=99)

    def _checkout(self):
        return self.client.post('/api/v1/checkout/', {
            'payment_method': 'purchase_order',
            'po_number': 'PO-CHK-1',
            'shipping_name': 'Buyer',
            'shipping_address': '1 Lab Rd',
            'shipping_email': 'short@lab.edu',
        }, format='json')

    def test_tracked_insufficient_blocks_checkout(self):
        self._track(10)
        self._auth(self.user)
        before = Order.objects.count()
        r = self._checkout()
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'OUT_OF_STOCK')
        self.assertEqual(Order.objects.count(), before)
        alert = StockShortageAlert.objects.get()
        self.assertEqual(alert.source, StockShortageAlert.Source.CHECKOUT)

    def test_untracked_sku_passes_checkout(self):
        self._auth(self.user)
        r = self._checkout()
        self.assertEqual(r.status_code, 201, r.content[:400])
        self.assertEqual(StockShortageAlert.objects.count(), 0)


class ShortageDeskApiTest(ShortageBase):
    """运营告警台 API：角色矩阵 + 列表计数 + 标记处理。"""

    def setUp(self):
        super().setUp()
        self.a1 = StockShortageAlert.objects.create(
            user=self.user, user_name='short_res', user_email='short@lab.edu',
            sku=self.sku, sku_code='SC8011-1', product_name='Pseudo-UTP',
            requested_quantity=99, available_quantity=0,
            reason=StockShortageAlert.Reason.INSUFFICIENT,
            source=StockShortageAlert.Source.PO_SUBMIT,
        )

    def test_anon_401(self):
        r = self.client.get('/api/v1/inventory/shortage-alerts/')
        self.assertEqual(r.status_code, 401, r.content[:200])

    def test_customer_403(self):
        self._auth(self.user)
        r = self.client.get('/api/v1/inventory/shortage-alerts/')
        self.assertEqual(r.status_code, 403, r.content[:200])

    def test_procurement_can_list_with_counts(self):
        self._auth(self.proc)
        r = self.client.get('/api/v1/inventory/shortage-alerts/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        body = r.json()
        self.assertEqual(len(body['data']), 1)
        self.assertEqual(body['data'][0]['sku_code'], 'SC8011-1')
        self.assertEqual(body['data'][0]['user_display'], 'short_res')
        counts = body['meta']['counts']
        self.assertEqual(counts['new'], 1)
        self.assertEqual(counts['restocked'], 0)
        self.assertEqual(body['meta']['pagination']['count'], 1)

    def test_filter_by_status(self):
        self._auth(self.admin)
        r = self.client.get('/api/v1/inventory/shortage-alerts/?status=dismissed')
        self.assertEqual(r.json()['data'], [])

    def test_search_by_sku_and_email(self):
        self._auth(self.admin)
        for q in ('SC8011', 'Pseudo', 'short@lab.edu', 'short_res'):
            r = self.client.get(f'/api/v1/inventory/shortage-alerts/?search={q}')
            self.assertEqual(len(r.json()['data']), 1, f'search={q} 应命中 1 条')

    def test_resolve_marks_handled(self):
        self._auth(self.admin)
        r = self.client.post(
            f'/api/v1/inventory/shortage-alerts/{self.a1.id}/resolve/',
            {'status': 'restocked', 'note': '已补 200 支'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.a1.refresh_from_db()
        self.assertEqual(self.a1.status, StockShortageAlert.Status.RESTOCKED)
        self.assertEqual(self.a1.note, '已补 200 支')
        self.assertEqual(self.a1.handled_by, self.admin)
        self.assertIsNotNone(self.a1.handled_at)

    def test_resolve_rejects_bad_status(self):
        self._auth(self.admin)
        r = self.client.post(
            f'/api/v1/inventory/shortage-alerts/{self.a1.id}/resolve/',
            {'status': 'whatever'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_resolve_can_revert_to_new(self):
        self._auth(self.admin)
        self.client.post(f'/api/v1/inventory/shortage-alerts/{self.a1.id}/resolve/',
                         {'status': 'contacted'}, format='json')
        r = self.client.post(f'/api/v1/inventory/shortage-alerts/{self.a1.id}/resolve/',
                             {'status': 'new'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.a1.refresh_from_db()
        self.assertEqual(self.a1.status, StockShortageAlert.Status.NEW)
        self.assertIsNone(self.a1.handled_at, '撤回时应清掉处理时间')
        self.assertIsNone(self.a1.handled_by)


class OrderListSerializerFieldsTest(ShortageBase):
    """列表接口必须带 grant_code / shipping_method / shipping_name / shipping_address。

    此前缺失 ⇒ 审核台三格恒 undefined ⇒ 模板 `|| '—'` 把**有地址的订单**显示成没地址。
    """

    def test_list_includes_operator_fields(self):
        order = Order.objects.create(
            user=self.user, order_no='ORD-FIELDS01', status=Order.Status.PO_RECEIVED,
            po_number='PO-F1', grant_code='R01-ABC', shipping_method='cold_pack',
            shipping_name='Dr Chen', shipping_address='1 Lab Rd, Ningbo',
            grand_total=Decimal('59.00'),
        )
        self._auth(self.user)
        r = self.client.get('/api/v1/orders/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        rows = [o for o in r.json()['data'] if o['id'] == order.id]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['grant_code'], 'R01-ABC')
        self.assertEqual(row['shipping_method'], 'cold_pack')
        self.assertEqual(row['shipping_name'], 'Dr Chen')
        self.assertEqual(row['shipping_address'], '1 Lab Rd, Ningbo')

class StockTrackingApiTest(ShortageBase):
    """4a：显式「纳入库存管理」开关（`SKU.is_stock_tracked`）+ 缺口清单。

    这个开关的失效方式都是静默的，所以每条都要钉：
      · 关错了（有货却脱管）⇒ 那批货从所有流程里消失；
      · 开了但没行（纳管却 0 库存）⇒ 该 SKU 所有下单被拦，而库存台上看不到它。
    """

    def test_receipt_auto_tracks_sku(self):
        """入库即纳管 —— 这是开关唯一的自动置位路径。"""
        self.assertFalse(self.sku.is_stock_tracked)
        InventoryService.receipt(self.sku.id, 'WH-A', 10, reason='initial')
        self.sku.refresh_from_db(fields=['is_stock_tracked'])
        self.assertTrue(self.sku.is_stock_tracked, '入库后必须自动纳管')

    def test_track_on_then_off(self):
        self._auth(self.proc)
        r = self.client.post('/api/v1/inventory/track/',
                             {'sku_id': self.sku.id, 'tracked': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.assertTrue(r.json()['data']['is_stock_tracked'])
        self.sku.refresh_from_db(fields=['is_stock_tracked'])
        self.assertTrue(self.sku.is_stock_tracked)

        r = self.client.post('/api/v1/inventory/track/',
                             {'sku_id': self.sku.id, 'tracked': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.sku.refresh_from_db(fields=['is_stock_tracked'])
        self.assertFalse(self.sku.is_stock_tracked)

    def test_cannot_untrack_while_holding_stock(self):
        """有货却脱管 ⇒ 货凭空消失。必须 400 且开关不动。"""
        self._track(10)
        self._auth(self.proc)
        r = self.client.post('/api/v1/inventory/track/',
                             {'sku_id': self.sku.id, 'tracked': False}, format='json')
        self.assertEqual(r.status_code, 400, r.content[:400])
        err = r.json()['meta']['error']
        self.assertEqual(err['code'], 'STOCK_NOT_EMPTY')
        self.assertEqual(err['details'][0]['available'], 10)
        self.sku.refresh_from_db(fields=['is_stock_tracked'])
        self.assertTrue(self.sku.is_stock_tracked, '被拒时开关不得改变')

    def test_cannot_untrack_unknown_sku(self):
        self._auth(self.proc)
        r = self.client.post('/api/v1/inventory/track/',
                             {'sku_id': 999999, 'tracked': True}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_tracked_gaps_lists_only_tracked_without_rows(self):
        """纳管 + 无库存行 ⇒ 下单必被拦，必须能在运营侧看见。"""
        self.sku.is_stock_tracked = True
        self.sku.save(update_fields=['is_stock_tracked'])
        SKU.objects.create(product=self.product, sku_code='SC8011-2')  # 未纳管
        self._auth(self.proc)

        r = self.client.get('/api/v1/inventory/tracked-gaps/')
        self.assertEqual(r.status_code, 200, r.content[:400])
        data = r.json()['data']
        codes = [i['sku_code'] for i in data['items']]
        self.assertEqual(data['count'], 1)
        self.assertEqual(codes, ['SC8011-1'])

    def test_tracked_gaps_drops_sku_once_stocked(self):
        self.sku.is_stock_tracked = True
        self.sku.save(update_fields=['is_stock_tracked'])
        self._auth(self.proc)
        self.assertEqual(self.client.get('/api/v1/inventory/tracked-gaps/')
                         .json()['data']['count'], 1)

        InventoryService.receipt(self.sku.id, 'WH-A', 5, reason='initial')
        self.assertEqual(self.client.get('/api/v1/inventory/tracked-gaps/')
                         .json()['data']['count'], 0, '有库存行后不该再出现在缺口清单')

    def test_customer_forbidden(self):
        self._auth(self.user)
        r = self.client.post('/api/v1/inventory/track/',
                             {'sku_id': self.sku.id, 'tracked': True}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_anonymous_denied(self):
        r = self.client.post('/api/v1/inventory/track/',
                             {'sku_id': self.sku.id, 'tracked': True}, format='json')
        self.assertIn(r.status_code, (401, 403))

