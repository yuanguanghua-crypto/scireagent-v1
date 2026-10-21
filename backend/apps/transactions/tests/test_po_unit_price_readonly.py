"""F5 回归 — `PoSubmitItemSerializer.unit_price` 可写，唯一防线在服务层。

现状（已核实）：`unit_price` 是客户端可提交字段，安全性**只靠**
`PoSubmissionService` 用 `sku.price` 强制覆盖（services.py:132-141）。
这是**单点防御** —— 任何人新增一个复用该序列化器的写端点、或改动服务层，
价格篡改立刻敞开。

本文件钉住两道防线：
1. 序列化器层：`PoSubmitItemSerializer` 的 `validated_data` **不含** `unit_price`
   （证明它真的被 read_only 忽略，而不是被接受）
2. 服务层回归：带 1% 篡改价提交 PO → 201，但落库 `OrderItem.unit_price` 与
   `order.grand_total` 都按 `sku.price` 计算（证明第二道防线仍在）
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order, OrderItem
from apps.transactions.api.v1.serializers import PoSubmitItemSerializer

from django.contrib.auth import get_user_model

User = get_user_model()


class PoUnitPriceReadonlyTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='buyer', email='buyer@example.com', password='x',
            role='researcher', organization=self.org)
        product = Product.objects.create(name='Reagent', slug='reagent')
        self.sku = SKU.objects.create(
            product=product, sku_code='SKU-PRICE-001', price=Decimal('100.00'))
        # 真实价 100 元，篡改价 1 元（1%）
        self.tampered_price = '1.00'

    # ── 1. 序列化器层：unit_price 必须在 validated_data 中被丢弃 ──
    def test_serializer_ignores_client_unit_price(self):
        s = PoSubmitItemSerializer(data={
            'sku_id': self.sku.id,
            'quantity': 2,
            'unit_price': self.tampered_price,  # 故意传
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn('unit_price', s.validated_data,
                         'unit_price 必须是 read_only —— validated_data 不应含它')
        self.assertEqual(s.validated_data['sku_id'], self.sku.id)
        self.assertEqual(s.validated_data['quantity'], 2)

    # ── 2. 服务层回归：篡改价不影响落库与总额 ──
    def test_tampered_unit_price_overridden_by_sku_price(self):
        c = APIClient()
        c.force_authenticate(self.user)
        resp = c.post('/api/v1/orders/po/', {
            'shipping_name': 'Lab', 'shipping_address': '1 Oxford St',
            'items': [{
                'sku_id': self.sku.id,
                'quantity': 2,
                'unit_price': self.tampered_price,  # 1% 真实价
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content[:400])

        order = Order.objects.latest('id')
        item = OrderItem.objects.get(order=order)
        self.assertEqual(item.unit_price, Decimal('100.00'),
                         '落库单价必须等于 sku.price，不能被客户端篡改')
        self.assertEqual(order.grand_total, Decimal('200.00'),
                         '总额必须按 sku.price × 2 计算')
        self.assertNotEqual(order.grand_total, Decimal('2.00'))
