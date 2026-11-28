"""A-046：上架（active）的产品必须至少有一个默认 SKU。

## 改前
编辑页把默认 SKU 那行的 ✕ 点掉（当时无确认框）保存后，产品仍能保持 active，
但没有任何默认 SKU。`_is_product_complete()` 只把它算进"完整性提示"（发布弹窗展示），
**不阻断保存** —— 所以 `is_complete=false` 的产品照样能是 active。

## 口径（三点，别收紧）
① 只要求**至少一个**默认 SKU，不要求"恰好一个" —— 生产存在同时挂两个
   `is_default=true` 的历史数据，收紧成唯一会打回存量。
② 只在**涉及上架或本次提交了 skus** 时判：active 产品改个描述不该被顶回来。
③ 没有 SKU 的产品不在此条拦（那是"没建规格"，与"有规格但没指定默认"是两件事）。
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.commerce.models import Product, SKU


class ActiveRequiresDefaultSkuTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='a046_admin', password='x', email='a046@lab.edu',
            role='admin', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.p = Product.objects.create(
            name='A046 Probe', slug='a046-probe', catalog_no='A046-1',
            status='active', research_use_only=True)
        self.s1 = SKU.objects.create(product=self.p, sku_code='A046-1-A',
                                     pack_size='1 mg', price=Decimal('10'),
                                     is_default=True)
        self.s2 = SKU.objects.create(product=self.p, sku_code='A046-1-B',
                                     pack_size='5 mg', price=Decimal('20'),
                                     is_default=False)

    def _patch_skus(self, flags):
        skus = []
        for sku, flag in zip((self.s1, self.s2), flags):
            skus.append({
                'id': sku.id, 'sku_code': sku.sku_code,
                'pack_size': sku.pack_size, 'price': str(sku.price),
                'is_default': flag,
            })
        return self.client.patch(f'/api/v1/products/{self.p.id}/',
                                 {'status': 'active', 'skus': skus}, format='json')

    def test_active_with_no_default_sku_rejected(self):
        r = self._patch_skus([False, False])
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertIn('skus', str(r.json()))

    def test_active_with_one_default_ok(self):
        r = self._patch_skus([True, False])
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_active_with_two_defaults_ok(self):
        """存量存在双默认，不能收紧成唯一。"""
        r = self._patch_skus([True, True])
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_active_product_can_update_other_fields(self):
        """没提交 skus 的普通编辑不该被这条拦住。"""
        r = self.client.patch(f'/api/v1/products/{self.p.id}/',
                              {'summary': '改个描述'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_draft_with_no_default_sku_still_allowed(self):
        """草稿允许没有默认 SKU（还没定规格）。"""
        r = self.client.patch(f'/api/v1/products/{self.p.id}/',
                              {'status': 'draft',
                               'skus': [{'id': self.s1.id, 'sku_code': self.s1.sku_code,
                                         'pack_size': self.s1.pack_size,
                                         'price': str(self.s1.price), 'is_default': False},
                                        {'id': self.s2.id, 'sku_code': self.s2.sku_code,
                                         'pack_size': self.s2.pack_size,
                                         'price': str(self.s2.price), 'is_default': False}]},
                              format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
