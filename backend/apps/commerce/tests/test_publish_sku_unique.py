"""回归测试：发布（PUT 带与现有相同的 sku_code）不应触发 unique 冲突。

bug 复现路径：
  草稿保存 → 创建 SKU（sku_code=X）
  点 Publish → saveDraft 走 PUT，skus=[{sku_code:X}]
  DRF is_valid() 在 ProductCreateUpdateSerializer.update() 的 delete 之前运行
  嵌套 SKUCreateSerializer 的 UniqueValidator，旧 SKU 仍在库中 → 判 unique 冲突 → 400

修复：SKUCreateSerializer.Meta.extra_kwargs 移除 sku_code 自动 UniqueValidator，
唯一性由 update() 内的 instance.skus.all().delete() 保证。
"""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class PublishSkuUniqueTest(TestCase):
    """发布时带相同 sku_code 的 PUT 不应报 unique 冲突"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.staff)

    def _put_payload(self, product, sku_code, status='active'):
        return {
            'name': product.name,
            'slug': product.slug,
            'catalog_no': product.catalog_no or 'SC-PUB-001',
            'cas': '1927-31-7',
            'smiles': 'CCO',
            'status': status,
            'skus': [
                {'sku_code': sku_code, 'pack_size': '100mg',
                 'price': '99.99', 'is_default': True},
            ],
        }

    def test_publish_with_same_sku_code_succeeds(self):
        """单 SKU：草稿→发布，sku_code 与现有一致，应 200"""
        product = ProductFactory(
            name='Publish Test', catalog_no='SC-PUB-001', status='draft',
        )
        SKUFactory(product=product, sku_code='SC-PUB-001-1', is_default=True)

        resp = self.client.put(
            f'/api/v1/products/{product.pk}/',
            self._put_payload(product, 'SC-PUB-001-1'),
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        product.refresh_from_db()
        self.assertEqual(product.status, 'active')
        self.assertEqual(product.skus.count(), 1)
        self.assertEqual(product.skus.first().sku_code, 'SC-PUB-001-1')

    def test_publish_with_multiple_same_sku_codes(self):
        """多 SKU：草稿→发布，所有 sku_code 与现有一致，应 200"""
        product = ProductFactory(
            name='Multi SKU Publish', catalog_no='SC-PUB-002', status='draft',
        )
        SKUFactory(product=product, sku_code='SC-PUB-002-1', is_default=True)
        SKUFactory(product=product, sku_code='SC-PUB-002-2', is_default=False)

        payload = self._put_payload(product, 'SC-PUB-002-1')
        payload['skus'] = [
            {'sku_code': 'SC-PUB-002-1', 'pack_size': '50mg',
             'price': '50.00', 'is_default': True},
            {'sku_code': 'SC-PUB-002-2', 'pack_size': '100mg',
             'price': '90.00', 'is_default': False},
        ]
        resp = self.client.put(
            f'/api/v1/products/{product.pk}/', payload, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        product.refresh_from_db()
        self.assertEqual(product.status, 'active')
        self.assertEqual(product.skus.count(), 2)

    def test_save_draft_with_same_sku_code_succeeds(self):
        """不发布（仍 draft）：PUT 带相同 sku_code 也应成功"""
        product = ProductFactory(
            name='Draft Save', catalog_no='SC-PUB-003', status='draft',
        )
        SKUFactory(product=product, sku_code='SC-PUB-003-1', is_default=True)

        resp = self.client.put(
            f'/api/v1/products/{product.pk}/',
            self._put_payload(product, 'SC-PUB-003-1', status='draft'),
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        product.refresh_from_db()
        self.assertEqual(product.status, 'draft')
