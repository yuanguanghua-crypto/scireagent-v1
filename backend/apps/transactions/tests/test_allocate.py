"""补 P1-1 的 allocate 端点（`POST /orders/{id}/allocate/`）测试。

背景：`InventoryService.allocate_for_order` 服务层已实现，但缺 HTTP 端点；
备货台（节点 B）无法通过 API 锁定库存。本文件按 TDD 补端点 + 回归。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.inventory.models import Inventory, Allocation
from apps.transactions.models import Order, OrderItem

User = get_user_model()


class AllocateTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.proc = User.objects.create_user(
            username='proc', email='p@e.com', password='x',
            role='procurement', organization=self.org,
        )
        self.researcher = User.objects.create_user(
            username='rsr', email='r@e.com', password='x',
            role='researcher', organization=self.org,
        )
        product = Product.objects.create(name='Reagent', slug='reagent')
        self.sku = SKU.objects.create(product=product, sku_code='SKU-INV-001', price=Decimal('10.00'))
        self.inventory = Inventory.objects.create(sku=self.sku, available=10, allocated=0)
        self.order = Order.objects.create(
            user=self.researcher, organization=self.org,
            order_no='ORD-INV-001', po_number=None, status=Order.Status.CONFIRMED,
        )
        self.item = OrderItem.objects.create(
            order=self.order, sku=self.sku, quantity=3, unit_price=Decimal('10.00'),
        )

    def _allocate(self, user, lines):
        c = APIClient()
        c.force_authenticate(user)
        return c.post(f'/api/v1/orders/{self.order.id}/allocate/', {'lines': lines}, format='json')

    def test_procurement_can_allocate(self):
        r = self._allocate(self.proc, [
            {'order_item_id': self.item.id, 'inventory_id': self.inventory.id, 'quantity': 3}
        ])
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.available, 7, '锁定后可分配量应减少')
        self.assertEqual(self.inventory.allocated, 3, '锁定后占用量应增加')
        self.assertTrue(
            Allocation.objects.filter(order_item=self.item, status=Allocation.Status.RESERVED).exists()
        )

    def test_missing_lines_returns_400(self):
        r = self._allocate(self.proc, [])
        self.assertEqual(r.status_code, 400)

    def test_order_item_not_in_order_returns_400(self):
        other = Order.objects.create(
            user=self.researcher, order_no='ORD-OTHER', po_number=None,
            status=Order.Status.CONFIRMED,
        )
        other_item = OrderItem.objects.create(
            order=other, sku=self.sku, quantity=1, unit_price=Decimal('10.00'),
        )
        r = self._allocate(self.proc, [
            {'order_item_id': other_item.id, 'inventory_id': self.inventory.id, 'quantity': 1}
        ])
        self.assertEqual(r.status_code, 400)

    def test_over_commit_returns_400(self):
        r = self._allocate(self.proc, [
            {'order_item_id': self.item.id, 'inventory_id': self.inventory.id, 'quantity': 99}
        ])
        self.assertEqual(r.status_code, 400, '超卖应 400')

    def test_order_not_confirmed_returns_400(self):
        self.order.status = Order.Status.PO_RECEIVED
        self.order.save(update_fields=['status'])
        r = self._allocate(self.proc, [
            {'order_item_id': self.item.id, 'inventory_id': self.inventory.id, 'quantity': 1}
        ])
        self.assertEqual(r.status_code, 400, '未确认的订单不得锁定库存')

    def test_non_procurement_forbidden(self):
        r = self._allocate(self.researcher, [
            {'order_item_id': self.item.id, 'inventory_id': self.inventory.id, 'quantity': 1}
        ])
        self.assertEqual(r.status_code, 403)

    def test_order_detail_includes_sku_available(self):
        """审核台展示库存所需：订单详情（detail）的每个 item 应带 sku_available。"""
        c = APIClient()
        c.force_authenticate(self.researcher)  # 归属人 retrieve 自己的订单（非 staff 只能看自己的）
        r = c.get(f'/api/v1/orders/{self.order.id}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        items = r.json()['data']['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['sku_available'], 10, '应返回该 SKU 的可分配量')
