# -*- coding: utf-8 -*-
"""下单锁库 / 审核锁库 / 取消释放 / 超时释放 全链路（2026-10-28）。

背景：2026-10-28 之前，下单只做**只读**校验，从不扣减库存 ⇒ 库存 100 时两个客户
各下 100 都能通过（累计超卖）。本轮把「承诺点」改成真实占用：
  · 购物车直购（下单即 CONFIRMED）→ 下单时锁；
  · PO 上传（PO_RECEIVED，意向单）→ 运营 approve 时锁。

⚠️ 这个能力的失效方式**全是静默的**，所以每条都要钉死：
  · 少扣一次 ⇒ 超卖（卖了没有的货）；
  · 少放一次 ⇒ 库存永久泄漏（货锁死，不报错，只是数字慢慢少）；
  · 双扣一次 ⇒ 明明有货却下不了单；
  · 用错 release 语义（发货 vs 取消）⇒ 库存凭空增减。
"""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.inventory.models import Allocation, Inventory, InventoryMovement
from apps.inventory.services import (
    InsufficientInventoryError, InventoryService,
)
from apps.transactions.models import Basket, Order, OrderItem, StatusLog


class ReserveBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='rsv_res', password='x', email='rsv@lab.edu',
            organization=self.org, role='researcher')
        self.proc = User.objects.create_user(
            username='rsv_proc', password='x', organization=self.org, role='procurement')
        self.product = Product.objects.create(name='Pseudo-UTP', slug='pseudo-utp-rsv')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='SC9001-1', price=Decimal('59.00'))
        self.client = APIClient()

    def _stock(self, available, location='WH-A', tracked=True):
        row = Inventory.objects.create(
            sku=self.sku, location=location, available=available)
        if tracked:
            SKU.objects.filter(pk=self.sku.pk).update(is_stock_tracked=True)
            self.sku.refresh_from_db(fields=['is_stock_tracked'])
        return row

    def _basket(self, qty=10):
        Basket.objects.create(user=self.user, product=self.product,
                              sku=self.sku, quantity=qty)

    def _checkout(self):
        self.client.force_authenticate(user=self.user)
        return self.client.post('/api/v1/checkout/', {
            'payment_method': 'purchase_order',
            'po_number': 'PO-RSV-1',
            'shipping_name': 'Buyer',
            'shipping_address': '1 Lab Rd',
            'shipping_email': 'rsv@lab.edu',
        }, format='json')

    def _po(self, qty=10):
        self.client.force_authenticate(user=self.user)
        return self.client.post('/api/v1/orders/po/', {
            'po_number': 'PO-RSV-2',
            'shipping_name': 'Buyer',
            'shipping_address': '1 Lab Rd',
            'shipping_email': 'rsv@lab.edu',
            'items': [{'sku_id': self.sku.id, 'product_id': self.product.id,
                       'quantity': qty}],
        }, format='json')


class CheckoutReserveTest(ReserveBase):
    """购物车直购 = 承诺 ⇒ 下单就锁库。"""

    def test_checkout_locks_stock(self):
        inv = self._stock(100)
        self._basket(10)
        r = self._checkout()
        self.assertEqual(r.status_code, 201, r.content[:400])

        inv.refresh_from_db()
        self.assertEqual(inv.available, 90, '下单必须真的扣减可分配量')
        self.assertEqual(inv.allocated, 10, '扣掉的量必须落到 allocated')

        order = Order.objects.get()
        alloc = Allocation.objects.get(order_item__order=order)
        self.assertEqual(alloc.quantity, 10)
        self.assertEqual(alloc.status, Allocation.Status.RESERVED)
        self.assertEqual(alloc.inventory_id, inv.id)

        mv = InventoryMovement.objects.get(kind=InventoryMovement.Kind.ALLOCATE)
        self.assertEqual(mv.delta_available, -10)
        self.assertEqual(mv.delta_allocated, 10)
        self.assertTrue(mv.reason.startswith('checkout:'), mv.reason)

    def test_checkout_splits_across_locations(self):
        """一个 SKU 多库位：按 available 从多到少摊开，跨库位拆成多条占用。"""
        a = self._stock(30, location='WH-A')
        b = self._stock(50, location='WH-B')
        self._basket(60)
        r = self._checkout()
        self.assertEqual(r.status_code, 201, r.content[:400])

        allocs = Allocation.objects.all().order_by('-quantity')
        self.assertEqual(len(allocs), 2, '60 件应从两个库位各取一部分')
        self.assertEqual([x.quantity for x in allocs], [50, 10])
        # 贪心：先吃 50 的 WH-B，再吃 WH-A 的 10
        self.assertEqual(allocs[0].inventory_id, b.id)
        self.assertEqual(allocs[1].inventory_id, a.id)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.available, b.available), (20, 0))

    def test_insufficient_rolls_back_whole_order(self):
        """锁库失败 ⇒ 整单回滚：没有订单、没有明细、库存分文未动、购物车还在。"""
        inv = self._stock(5)
        self._basket(10)
        r = self._checkout()
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'OUT_OF_STOCK')

        self.assertEqual(Order.objects.count(), 0, '失败不得留下订单')
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(Allocation.objects.count(), 0)
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (5, 0))
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 1,
                         '回滚后购物车不能被清空')

    def test_untracked_sku_is_not_locked(self):
        """未纳管（按需生产）的 SKU：不锁，也不因为"没有库存行"而失败。"""
        self._basket(999)
        r = self._checkout()
        self.assertEqual(r.status_code, 201, r.content[:400])
        self.assertEqual(Allocation.objects.count(), 0)

    def test_repeat_reserve_does_not_double_deduct(self):
        """幂等：同一订单再锁一次不得双扣（否则明明有货却下不了单）。"""
        inv = self._stock(100)
        self._basket(10)
        self.assertEqual(self._checkout().status_code, 201)
        order = Order.objects.get()

        InventoryService.reserve_for_order(order)
        inv.refresh_from_db()
        self.assertEqual(inv.available, 90, '第二次 reserve 不得再扣')
        self.assertEqual(Allocation.objects.count(), 1)


class CancelReleaseTest(ReserveBase):
    """取消 / 拒单必须把占用退回可用量（不是发货语义）。"""

    def _order_with_lock(self, qty=10, stock=100):
        inv = self._stock(stock)
        self._basket(qty)
        self.assertEqual(self._checkout().status_code, 201)
        return Inventory.objects.get(pk=inv.pk), Order.objects.get()

    def test_cancel_returns_stock_to_available(self):
        inv, order = self._order_with_lock(10, 100)
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (90, 10))

        self.client.force_authenticate(user=self.proc)
        r = self.client.post(f'/api/v1/orders/{order.pk}/cancel/',
                             {'reason': 'customer changed mind'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:400])

        inv.refresh_from_db()
        self.assertEqual(inv.available, 100, '取消必须把货退回可分配量')
        self.assertEqual(inv.allocated, 0, '取消必须清掉占用量')

        alloc = Allocation.objects.get()
        self.assertEqual(alloc.status, Allocation.Status.RELEASED)

        mv = InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.RELEASE).get()
        self.assertEqual(mv.delta_available, 10, '取消是 available +10')
        self.assertEqual(mv.delta_allocated, -10)

    def test_reject_returns_stock(self):
        inv = self._stock(100)
        po = self._po(10)          # PO 上传不锁库
        self.assertEqual(po.status_code, 201, po.content[:400])
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (100, 0),
                         'PO 上传是意向单，此时不该锁库')

        order = Order.objects.get()
        self.client.force_authenticate(user=self.proc)
        r = self.client.post(f'/api/v1/orders/{order.pk}/reject/',
                             {'reason': 'no budget'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:400])
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (100, 0))

    def test_cancel_is_idempotent(self):
        """已经取消过的订单再释放一次不得把库存加两次。"""
        inv, order = self._order_with_lock(10, 100)
        self.client.force_authenticate(user=self.proc)
        self.client.post(f'/api/v1/orders/{order.pk}/cancel/', {'reason': 'x'}, format='json')
        inv.refresh_from_db()
        self.assertEqual(inv.available, 100)

        InventoryService.release_for_order(order, reason='again')
        inv.refresh_from_db()
        self.assertEqual(inv.available, 100, '重复释放不得再加库存')


class ApproveReserveTest(ReserveBase):
    """PO 上传不锁；运营 approve 时才锁。"""

    def test_po_submit_does_not_lock(self):
        inv = self._stock(100)
        r = self._po(10)
        self.assertEqual(r.status_code, 201, r.content[:400])
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (100, 0))
        self.assertEqual(Allocation.objects.count(), 0)

    def test_approve_locks_stock(self):
        inv = self._stock(100)
        self.assertEqual(self._po(10).status_code, 201)
        order = Order.objects.get()

        self.client.force_authenticate(user=self.proc)
        r = self.client.post(f'/api/v1/orders/{order.pk}/approve/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:400])

        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (90, 10))
        alloc = Allocation.objects.get()
        self.assertEqual(alloc.status, Allocation.Status.RESERVED)
        self.assertTrue(InventoryMovement.objects.get(
            kind=InventoryMovement.Kind.ALLOCATE).reason.startswith('approve:'))

    def test_approve_fails_and_rolls_back_status(self):
        """审核时库存不够 ⇒ 400，且订单**不能**停在 CONFIRMED（否则就是"已确认但没货"）。

        必须构造「提交时够、审核时不够」：PO 提交本身有只读预检（10 > 5 会当场被拦，
        根本走不到审核）。所以提交后把库存调低，模拟"这段时间被别人买走了"。
        """
        inv = self._stock(10)
        self.assertEqual(self._po(10).status_code, 201)
        Inventory.objects.filter(pk=inv.pk).update(available=5)
        order = Order.objects.get()

        self.client.force_authenticate(user=self.proc)
        r = self.client.post(f'/api/v1/orders/{order.pk}/approve/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'OUT_OF_STOCK')

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PO_RECEIVED, '状态必须回滚')
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (5, 0),
                         '失败的审核不得留下任何占用')
        self.assertEqual(Allocation.objects.count(), 0)

    def test_manual_allocate_rejected_when_already_locked(self):
        """下单/审核已锁库后手点 Allocate ⇒ 400（否则同一批货占两次）。"""
        self._stock(100)
        self.assertEqual(self._po(10).status_code, 201)
        order = Order.objects.get()
        self.client.force_authenticate(user=self.proc)
        self.client.post(f'/api/v1/orders/{order.pk}/approve/', {}, format='json')

        oi = OrderItem.objects.get(order=order)
        inv = Inventory.objects.get(sku=self.sku)
        r = self.client.post(f'/api/v1/orders/{order.pk}/allocate/', {
            'lines': [{'order_item_id': oi.pk, 'inventory_id': inv.pk, 'quantity': 10}],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'ALREADY_ALLOCATED')
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (90, 10), '不得再扣一次')


class ExpiredReleaseCommandTest(ReserveBase):
    """超时释放：只还库存，不取消订单；正在备货的订单不碰。"""

    def _locked_order(self, status, age_hours):
        inv = self._stock(100)
        self._basket(10)
        self.assertEqual(self._checkout().status_code, 201)
        order = Order.objects.get()
        order.status = status
        order.save(update_fields=['status'])
        Order.objects.filter(pk=order.pk).update(
            updated_at=timezone.now() - timedelta(hours=age_hours))
        order.refresh_from_db()
        return Inventory.objects.get(pk=inv.pk), order

    def test_releases_confirmed_order_and_keeps_status(self):
        inv, order = self._locked_order(Order.Status.CONFIRMED, 100)
        call_command('release_expired_reservations', '--hours', '72', verbosity=0)

        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (100, 0))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED,
                         '只释放占用，不得取消客户订单')
        self.assertEqual(Allocation.objects.get().status, Allocation.Status.RELEASED)
        self.assertTrue(StatusLog.objects.filter(
            order=order, note__contains='auto-released').exists(),
            '时间线要留痕，否则运营不知道为什么库存回来了')

    def test_does_not_touch_in_production(self):
        """正在备货的占用是"正在用"的，释放会导致后续发货静默不扣减。"""
        inv, order = self._locked_order(Order.Status.IN_PRODUCTION, 100)
        call_command('release_expired_reservations', '--hours', '72', verbosity=0)
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (90, 10))
        self.assertEqual(Allocation.objects.get().status, Allocation.Status.RESERVED)

    def test_does_not_touch_fresh_order(self):
        inv, order = self._locked_order(Order.Status.CONFIRMED, 1)
        call_command('release_expired_reservations', '--hours', '72', verbosity=0)
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (90, 10))

    def test_dry_run_changes_nothing(self):
        inv, order = self._locked_order(Order.Status.CONFIRMED, 100)
        call_command('release_expired_reservations', '--hours', '72',
                     '--dry-run', verbosity=0)
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (90, 10))
        self.assertEqual(Allocation.objects.get().status, Allocation.Status.RESERVED)


class SeedPlaceholderCommandTest(ReserveBase):
    """占位库存：可识别、可清、只清干净的行、不覆盖真实数据。"""

    def setUp(self):
        super().setUp()
        # seed 命令只处理「上架产品」（`status='active', archived=False`）——
        # 未上架的 SKU 客户买不到，灌库存没有意义。Product.status 默认是 draft，
        # 所以这里必须显式置 active，否则命令会一条都不处理（测试假绿的反面）。
        self.product.status = 'active'
        self.product.save(update_fields=['status'])

    def test_seed_creates_rows_and_tracks(self):
        sku2 = SKU.objects.create(product=self.product, sku_code='SC9002-1')
        self.assertFalse(self.sku.is_stock_tracked)
        call_command('seed_inventory_placeholder', '--qty', '100', verbosity=0)

        for s in (self.sku, sku2):
            inv = Inventory.objects.get(sku=s)
            self.assertEqual(inv.available, 100)
            s.refresh_from_db()
            self.assertTrue(s.is_stock_tracked, '入库即纳管')
        mv = InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.RECEIPT).first()
        self.assertEqual(mv.reason, 'PLACEHOLDER:100', '必须留可识别的标记')

    def test_seed_skips_sku_that_already_has_stock(self):
        self._stock(7)
        call_command('seed_inventory_placeholder', '--qty', '100', verbosity=0)
        self.assertEqual(Inventory.objects.get(sku=self.sku).available, 7,
                         '有真实库存的 SKU 绝不能被覆盖')

    def test_purge_removes_clean_rows_and_untracks(self):
        call_command('seed_inventory_placeholder', '--qty', '100', verbosity=0)
        self.assertTrue(Inventory.objects.filter(sku=self.sku).exists())

        call_command('seed_inventory_placeholder', '--purge', verbosity=0)
        self.assertFalse(Inventory.objects.filter(sku=self.sku).exists())
        self.sku.refresh_from_db()
        self.assertFalse(self.sku.is_stock_tracked,
                         'purge 后必须脱管，否则该 SKU 所有下单被拦')

    def test_purge_skips_rows_already_used(self):
        """灌完之后卖过一部分 ⇒ 这行不能删（删了就把真实业务数据带走了）。"""
        call_command('seed_inventory_placeholder', '--qty', '100', verbosity=0)
        inv = Inventory.objects.get(sku=self.sku)
        inv.available = 90
        inv.allocated = 10
        inv.save(update_fields=['available', 'allocated'])

        call_command('seed_inventory_placeholder', '--purge', verbosity=0)
        self.assertTrue(Inventory.objects.filter(pk=inv.pk).exists(),
                        '已被使用的占位行不得删除')
        self.sku.refresh_from_db()
        self.assertTrue(self.sku.is_stock_tracked)

    def test_purge_does_not_touch_real_stock(self):
        """真实库存（reason 不以 PLACEHOLDER 开头）永远不受 purge 影响。"""
        InventoryService.receipt(self.sku.id, 'WH-A', 30, reason='real count')
        call_command('seed_inventory_placeholder', '--purge', verbosity=0)
        inv = Inventory.objects.get(sku=self.sku)
        self.assertEqual(inv.available, 30)
