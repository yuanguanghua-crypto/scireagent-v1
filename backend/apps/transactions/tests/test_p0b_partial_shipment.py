"""
P0-B 红/绿测试：部分发货时占用被整额释放。

缺陷：ShippingService.mark_shipped 的释放循环里，`remaining` 只决定何时停止遍历，
不决定释放多少；而 `InventoryService.release(alloc)` 释放 `allocation.quantity` 整额。
⇒ 占用 10、发货 5，`Inventory.allocated` 直接归零（账面 10 件实际只出5 件）。

修法：Allocation 增加 `released_quantity` 累计释放量字段；部分释放时只减实际发货量、
流水 delta_allocated 按实发量写、`status` 保持 RESERVED 直到released==quantity 才转 SHIPPED。

注意：本文件在修复前必须失败（红），修复后必须通过（绿）。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.inventory.models import Allocation, Inventory, InventoryMovement
from apps.inventory.services import InventoryService
from apps.transactions.models import Order, OrderItem, ShippingRecord
from apps.transactions.services import ShippingService

User = get_user_model()


class PartialShipmentAllocationTest(TestCase):
    """占用 10 / 发货 5 ⇒ allocated 必须剩 5，status 仍 RESERVED。"""

    def setUp(self):
        self.org = Organization.objects.create(name='Lab-P0B', org_type='academic')
        self.user = User.objects.create_user(
            username='p0b_u', email='p0b_u@example.com', password='x',
            role='researcher', organization=self.org,
        )
        product = Product.objects.create(name='ReagentP0B', slug='reagent-p0b')
        self.sku = SKU.objects.create(
            product=product, sku_code='SKU-P0B-001', price=Decimal('10.00'))
        self.inv = Inventory.objects.create(
            sku=self.sku, location='MAIN', available=20, allocated=0)

    def _make_order_with_allocation(self, qty=10):
        order = Order.objects.create(
            user=self.user, organization=self.org, order_no='P0B-ORD-001',
            po_number='PO-P0B-001', status=Order.Status.CONFIRMED)
        oi = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=qty, unit_price=Decimal('10.00'))
        alloc = InventoryService.allocate(oi, self.inv.id, qty)
        return order, oi, alloc

    def test_partial_shipment_leaves_remaining_allocation(self):
        order, oi, alloc = self._make_order_with_allocation(10)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.available, 10)
        self.assertEqual(self.inv.allocated, 10)

        shipment = ShippingService.create_shipment(
            order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 5}])
        ShippingService.mark_shipped(shipment.id)

        self.inv.refresh_from_db()
        alloc.refresh_from_db()
        #★ 核心断言：只释放实发的 5，剩 5 仍被占用
        self.assertEqual(
            self.inv.available, 10,
            'available 不应变化（实物已出，不是回库）')
        self.assertEqual(
            self.inv.allocated, 5,
            f'部分发货只应释放实发量5，实际 allocated={self.inv.allocated}')

    def test_partial_shipment_allocation_stays_reserved(self):
        order, oi, alloc = self._make_order_with_allocation(10)
        shipment = ShippingService.create_shipment(
            order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 5}])
        ShippingService.mark_shipped(shipment.id)

        alloc.refresh_from_db()
        self.assertEqual(
            alloc.status, Allocation.Status.RESERVED,
            '部分发货后占用未全部释放，status 应保持 RESERVED')

    def test_partial_shipment_movement_records_actual_amount(self):
        """InventoryMovement 流水金额必须按实际释放量写，不能按 alloc 整额。"""
        order, oi, alloc = self._make_order_with_allocation(10)
        shipment = ShippingService.create_shipment(
            order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 5}])
        ShippingService.mark_shipped(shipment.id)

        mv = InventoryMovement.objects.filter(
            inventory=self.inv, kind=InventoryMovement.Kind.SHIP).latest('id')
        self.assertEqual(mv.delta_allocated, -5, '流水应记录 -5')
        self.assertEqual(mv.quantity, 5, '流水数量应为5')

    def test_partial_then_full_second_shipment_drains_allocation(self):
        """先发5 再发 5（第二批）⇒ allocated 归零、status 转 SHIPPED。"""
        order, oi, alloc = self._make_order_with_allocation(10)
        s1 = ShippingService.create_shipment(
            order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 5}])
        ShippingService.mark_shipped(s1.id)

        self.inv.refresh_from_db()
        self.assertEqual(self.inv.allocated, 5)

        s2 = ShippingService.create_shipment(
            order, 'DHL', [{'order_item_id': oi.id, 'quantity': 5}])
        ShippingService.mark_shipped(s2.id)

        self.inv.refresh_from_db()
        alloc.refresh_from_db()
        self.assertEqual(self.inv.allocated, 0, '两批发完占用应归零')
        self.assertEqual(
            alloc.status, Allocation.Status.SHIPPED,
            '全部发完 status 应转 SHIPPED')

    # ── 回归：全量发货路径行为必须与修复前完全一致 ──

    def test_full_shipment_regression(self):
        """发货 10 / 占用 10 ⇒ allocated=0、status=SHIPPED、流水 -10。"""
        order, oi, alloc = self._make_order_with_allocation(10)
        shipment = ShippingService.create_shipment(
            order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 10}])
        ShippingService.mark_shipped(shipment.id)

        self.inv.refresh_from_db()
        alloc.refresh_from_db()
        self.assertEqual(self.inv.available, 10)
        self.assertEqual(self.inv.allocated, 0, '全量发货占用应归零')
        self.assertEqual(alloc.status, Allocation.Status.SHIPPED)

        mv = InventoryMovement.objects.filter(
            inventory=self.inv, kind=InventoryMovement.Kind.SHIP).latest('id')
        self.assertEqual(mv.delta_allocated, -10, '全量发货流水应为 -10')
        self.assertEqual(mv.quantity, 10)

    def test_full_shipment_exceeds_allocation_is_bounded(self):
        """发货数量 > 占用数量时不得把 allocated 减成负数。

        ★ 2026-10-28 调整构造方式：`create_shipment` 现在会拒绝
          「累计发货量 > 下单量」（跨批次超发守卫，放开 shipped 补发后必须加）。
          所以不能再靠「下单 10 却发 15」来构造 —— 那种请求已在建单阶段被 400 挡掉。
          改为 **下单 15、只占用 10、发 15**：释放被 `min(实发量, 剩余占用)` 限到 10。
          断言意图不变：`InventoryService.release` 的有界性，allocated 不得为负。
        """
        order = Order.objects.create(
            user=self.user, organization=self.org, order_no='P0B-ORD-OVER',
            po_number='PO-P0B-OVER', status=Order.Status.CONFIRMED)
        oi = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=15, unit_price=Decimal('10.00'))
        InventoryService.allocate(oi, self.inv.id, 10)      # 只占用 10 < 下单 15

        shipment = ShippingService.create_shipment(
            order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 15}])
        ShippingService.mark_shipped(shipment.id)

        self.inv.refresh_from_db()
        self.assertGreaterEqual(self.inv.allocated, 0, 'allocated 不得为负')
        self.assertEqual(self.inv.allocated, 0, '占用 10 全被释放后应为 0')

    def test_over_shipment_beyond_ordered_is_rejected(self):
        """跨批次累计发货量 > 下单量 ⇒ 建单阶段必须拒绝（2026-10-28 新守卫）。"""
        order, oi, _alloc = self._make_order_with_allocation(10)
        ShippingService.create_shipment(
            order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 4}])
        # 再建 7 件 ⇒ 累计 11 > 下单 10，必须拒
        with self.assertRaises(ValueError) as ctx:
            ShippingService.create_shipment(
                order, 'FedEx', [{'order_item_id': oi.id, 'quantity': 7}])
        self.assertIn('超出下单量', str(ctx.exception))

    def test_release_quantity_service_unchanged(self):
        """回归：InventoryService.release_quantity 直接调用仍按传入量释放。"""
        order, oi, alloc = self._make_order_with_allocation(10)
        InventoryService.release_quantity(self.inv.id, 4)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.allocated, 6)
        alloc.refresh_from_db()
        self.assertEqual(
            alloc.status, Allocation.Status.RESERVED,
            'release_quantity 不应改Allocation.status')