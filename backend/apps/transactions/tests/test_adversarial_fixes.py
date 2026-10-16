"""★ 对抗性自测修复回归 — v4.1 Fix 1/2/3。

Fix 1: quantity max_value=10000（防天量订单）
Fix 2: create_shipment 状态校验（防任意状态挂 shipment）
Fix 3: adjust 不存在库存 ID → 404 而非 500
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.inventory.models import Inventory
from apps.transactions.models import Order, OrderItem
from apps.transactions.services import ShippingService
from apps.transactions.models import InvalidTransitionError


class AdversarialFixTest(TestCase):
    """对抗性自测发现的 3 个安全 bug 的修复验证。"""

    def setUp(self):
        self.org = Organization.objects.create(name='SecLab', org_type='academic')
        self.admin = User.objects.create_user(
            username='sec_admin', password='x', organization=self.org, role='admin')
        self.customer = User.objects.create_user(
            username='sec_cust', password='x', organization=self.org, role='researcher')
        self.procurement = User.objects.create_user(
            username='sec_proc', password='x', organization=self.org, role='procurement')
        product = Product.objects.create(name='SecProduct', slug='sec-prod')
        self.sku = SKU.objects.create(product=product, sku_code='SEC-SKU-001', price=Decimal('10.00'))
        self.client = APIClient()

    # ── Fix 1: quantity max_value ──

    def test_quantity_999999999_rejected(self):
        """quantity=999999999 应被 serializer 的 max_value=10000 拦截为 400。"""
        self.client.force_authenticate(user=self.customer)
        r = self.client.post('/api/v1/orders/po/', {
            'po_number': 'SEC-QTY-MAX', 'shipping_name': 'T', 'shipping_address': 'T',
            'items': [{'sku_id': self.sku.id, 'quantity': 999999999, 'unit_price': '10.00'}],
        }, format='json')
        self.assertEqual(r.status_code, 400, f'Expected 400, got {r.status_code}: {r.content[:200]}')

    def test_quantity_10000_accepted(self):
        """quantity=10000（边界值）应被接受。"""
        self.client.force_authenticate(user=self.customer)
        r = self.client.post('/api/v1/orders/po/', {
            'po_number': 'SEC-QTY-OK', 'shipping_name': 'T', 'shipping_address': 'T',
            'items': [{'sku_id': self.sku.id, 'quantity': 10000, 'unit_price': '10.00'}],
        }, format='json')
        self.assertIn(r.status_code, (200, 201), f'Expected 2xx, got {r.status_code}: {r.content[:200]}')

    # ── Fix 2: create_shipment 状态校验 ──

    def test_shipment_in_wrong_status_rejected(self):
        """po_received 状态的订单不应能创建 shipment（应抛 InvalidTransitionError）。"""
        order = Order.objects.create(
            user=self.customer, organization=self.org,
            order_no='SEC-SHIP-001', po_number=None, status=Order.Status.PO_RECEIVED)
        item = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=1, unit_price=Decimal('10.00'))
        with self.assertRaises(InvalidTransitionError):
            ShippingService.create_shipment(
                order, carrier='FedEx', items=[{'order_item_id': item.id, 'quantity': 1}])

    def test_shipment_in_confirmed_status_ok(self):
        """confirmed 状态的订单应能正常创建 shipment。"""
        order = Order.objects.create(
            user=self.customer, organization=self.org,
            order_no='SEC-SHIP-002', po_number=None, status=Order.Status.CONFIRMED)
        item = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=1, unit_price=Decimal('10.00'))
        shipment = ShippingService.create_shipment(
            order, carrier='FedEx', items=[{'order_item_id': item.id, 'quantity': 1}])
        self.assertIsNotNone(shipment)

    # ── Fix 3: adjust 不存在库存 ID → 404 ──

    def test_adjust_nonexistent_inventory_404(self):
        """调整不存在的库存 ID 应返回 404 而非 500。"""
        self.client.force_authenticate(user=self.procurement)
        r = self.client.post('/api/v1/inventory/99999/adjust/',
                             {'delta': -1, 'reason': 'test'}, format='json')
        self.assertEqual(r.status_code, 404, f'Expected 404, got {r.status_code}: {r.content[:200]}')

    def test_adjust_existing_inventory_200(self):
        """调整存在的库存 ID 应正常返回 200。"""
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=10)
        self.client.force_authenticate(user=self.procurement)
        r = self.client.post(f'/api/v1/inventory/{inv.id}/adjust/',
                             {'delta': -1, 'reason': 'test'}, format='json')
        self.assertEqual(r.status_code, 200)
