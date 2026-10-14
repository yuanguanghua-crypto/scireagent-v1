"""PO 号可空（不强制）—— 口径落地回归。

背景：用户口径「PO 号不强制、提示输入、不输入也能过」。但此前 PoSubmitSerializer（CharField
默认 required=True）与服务层（`if not po_number: raise ValueError`）都强制必填，与口径矛盾。
本文件钉住「空 PO 号应能提交，且多单空 PO 号不冲突」。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order

User = get_user_model()


class PoNumberOptionalTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='u', email='u@example.com', password='x',
            role='researcher', organization=self.org,
        )
        product = Product.objects.create(name='Reagent', slug='reagent')
        self.sku = SKU.objects.create(product=product, sku_code='SKU-OPT-001', price=Decimal('10.00'))

    def _submit(self, po_number=None):
        c = APIClient()
        c.force_authenticate(self.user)
        payload = {
            'shipping_name': 'Lab', 'shipping_address': '1 Oxford St',
            'items': [{'sku_id': self.sku.id, 'quantity': 1, 'unit_price': '10.00'}],
        }
        if po_number is not None:
            payload['po_number'] = po_number
        return c.post('/api/v1/orders/po/', payload, format='json')

    def test_submit_without_po_number_succeeds(self):
        r = self._submit()  # 不传 po_number
        self.assertEqual(r.status_code, 201, r.content[:300])
        order = Order.objects.latest('id')
        self.assertIn(order.po_number, (None, ''), '空 PO 号应落为空/None')

    def test_two_orders_without_po_number_both_succeed(self):
        r1 = self._submit()
        r2 = self._submit()
        self.assertEqual(r1.status_code, 201, r1.content[:300])
        self.assertEqual(r2.status_code, 201, r2.content[:300])

    def test_submit_with_po_number_still_succeeds(self):
        r = self._submit('PO-OPT-0001')
        self.assertEqual(r.status_code, 201, r.content[:300])
        order = Order.objects.get(po_number='PO-OPT-0001')
        self.assertEqual(order.po_number, 'PO-OPT-0001')

    def test_duplicate_po_number_still_conflicts(self):
        self._submit('PO-OPT-DUP')
        r = self._submit('PO-OPT-DUP')
        self.assertEqual(r.status_code, 409, '非空 PO 号仍应唯一')
