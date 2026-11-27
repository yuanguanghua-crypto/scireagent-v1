"""S8 批次一：/checkout 的 PO 号冲突（A-145）与 PO 提交响应里的订单 id（A-149）。

## A-145 钉住什么
`Order.po_number` 上有 `uniq_order_po_number_nonempty`（非空才唯一），而购物车结账
视图此前**完全不判重** ⇒ 撞号时是 `IntegrityError` 从 atomic 里冒出来，DRF 兜不住，
客户看到通用 500 + "Action failed"（QA Batch 15）。
同一张 PO 号走 `/po/submit` 却能得到 "PO number already exists: …" ——
两条下单路径对同一件事必须说同一句话。

## A-149 钉住什么
PO 提交成功后前端要跳订单详情，而响应此前只有 `order_no`、没有 `id` ⇒ 无处可跳。
补 `id` 是纯增量，既有键不变。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import Basket, Order

User = get_user_model()


class CheckoutPoConflictTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='A145 Org', org_type='academic')
        self.user = User.objects.create_user(
            username='a145_user', password='testpass123',
            email='a145@example.com', role='researcher',
            email_verified=True, organization=self.org,
        )
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(
            name='A145 Reagent', slug='a145-reagent', catalog_no='A145-1', status='active')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='A145-1-10', pack_size='10 mg',
            price=Decimal('10.00'), currency='USD', is_default=True)
        Basket.objects.create(user=self.user, product=self.product,
                             sku=self.sku, quantity=1)
        # 已存在一张用了该 PO 号的单
        Order.objects.create(
            user=self.user, organization=self.org, order_no='ORD-A145-EXIST',
            status=Order.Status.CONFIRMED, payment_method='purchase_order',
            po_number='PO-A145-DUP', grand_total=Decimal('10.00'),
        )

    def _checkout(self, po_number):
        return self.client.post('/api/v1/checkout/', {
            'payment_method': 'purchase_order',
            'po_number': po_number,
            'shipping_name': 'Recipient',
            'shipping_address': '1 Test St',
        }, format='json')

    def test_duplicate_po_returns_409_with_clear_message(self):
        r = self._checkout('PO-A145-DUP')
        self.assertEqual(r.status_code, 409, r.content[:300])
        err = r.json()['meta']['error']
        self.assertEqual(err['code'], 'PO_NUMBER_CONFLICT')
        # 与 /po/submit 同一句话（含冲突的号码本身）
        self.assertIn('PO number already exists', err['message'])
        self.assertIn('PO-A145-DUP', err['message'])

    def test_duplicate_po_does_not_create_order_nor_clear_basket(self):
        before = Order.objects.count()
        self._checkout('PO-A145-DUP')
        self.assertEqual(Order.objects.count(), before, '冲突时不得建单')
        self.assertEqual(Basket.objects.filter(user=self.user).count(), 1,
                         '冲突时不得清空购物车（客户还要改号重提）')

    def test_unique_po_still_succeeds(self):
        r = self._checkout('PO-A145-NEW')
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertEqual(Order.objects.filter(po_number='PO-A145-NEW').count(), 1)


class PoSubmitResponseIncludesIdTest(TestCase):
    """A-149：`/po/submit` 的 201 响应必须带 `id`，前端才跳得动。"""

    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='A149 Org', org_type='academic')
        self.user = User.objects.create_user(
            username='a149_user', password='testpass123',
            email='a149@example.com', role='researcher',
            email_verified=True, organization=self.org,
        )
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(
            name='A149 Reagent', slug='a149-reagent', catalog_no='A149-1', status='active')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='A149-1-10', pack_size='10 mg',
            price=Decimal('20.00'), currency='USD', is_default=True)

    def test_response_has_id_and_order_no(self):
        r = self.client.post('/api/v1/orders/po/', {
            'po_number': 'PO-A149-PROBE',
            'shipping_name': 'Recipient',
            'shipping_address': '1 Test St',
            'items': [{
                'product_id': self.product.id,
                'sku_id': self.sku.id,
                'quantity': 1,
                'unit_price': '20.00',
            }],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content[:400])
        data = r.json()['data']
        self.assertIn('id', data)
        self.assertIn('order_no', data)
        order = Order.objects.get(pk=data['id'])
        self.assertEqual(order.order_no, data['order_no'])
