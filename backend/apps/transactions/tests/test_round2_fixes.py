"""★ 第二轮对抗性自测修复 — sku_id 校验 + unit_price 服务端覆盖。"""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order, OrderItem


class Round2FixTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='R2Lab', org_type='academic')
        self.customer = User.objects.create_user(
            username='r2_cust', password='x', organization=self.org, role='researcher')
        product = Product.objects.create(name='R2Product', slug='r2-prod')
        self.sku = SKU.objects.create(product=product, sku_code='R2-SKU-001', price=Decimal('25.00'))
        self.client = APIClient()

    def test_nonexistent_sku_400(self):
        """sku_id=999999（不存在）应 400 而非 500。"""
        self.client.force_authenticate(user=self.customer)
        r = self.client.post('/api/v1/orders/po/', {
            'po_number': 'R2-TEST', 'shipping_name': 'T', 'shipping_address': 'T',
            'items': [{'sku_id': 999999, 'quantity': 1, 'unit_price': '10.00'}],
        }, format='json')
        self.assertEqual(r.status_code, 400, f'Expected 400, got {r.status_code}')

    def test_unit_price_server_overrides_client(self):
        """客户端提交 unit_price=0.01 应被服务端覆盖为 SKU 现价 25.00。"""
        self.client.force_authenticate(user=self.customer)
        r = self.client.post('/api/v1/orders/po/', {
            'po_number': 'R2-PRICE', 'shipping_name': 'T', 'shipping_address': 'T',
            'items': [{'sku_id': self.sku.id, 'quantity': 2, 'unit_price': '0.01'}],
        }, format='json')
        self.assertIn(r.status_code, (200, 201))
        order = Order.objects.get(po_number='R2-PRICE')
        item = OrderItem.objects.get(order=order)
        self.assertEqual(item.unit_price, Decimal('25.00'), f'Expected 25.00, got {item.unit_price}')
        self.assertEqual(order.grand_total, Decimal('50.00'), f'Expected 50.00, got {order.grand_total}')
