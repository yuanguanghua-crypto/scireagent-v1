"""产品权限与完整度测试。

TDD: ProductViewSet 加 IsAdminOrReadOnly 后的权限验证。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class ProductWritePermissionTest(TestCase):
    """ProductViewSet 写权限测试"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(name='Test Product', catalog_no='SC-TEST-001')
        self.payload = {
            'name': 'New Product',
            'catalog_no': 'SC-TEST-002',
            'status': 'draft',
        }

    def test_anonymous_cannot_create_product(self):
        """匿名用户 → 401/403"""
        resp = self.client.post('/api/v1/products/', self.payload, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anonymous_cannot_update_product(self):
        """匿名用户写 → 401/403"""
        resp = self.client.put(f'/api/v1/products/{self.product.pk}/', self.payload, format='json')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anonymous_can_read_product(self):
        """匿名用户读 → 200"""
        resp = self.client.get(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_staff_cannot_create_product(self):
        """已登录但非 staff → 403"""
        user = UserFactory(is_staff=False)
        self.client.force_authenticate(user=user)
        resp = self.client.post('/api/v1/products/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create_product(self):
        """is_staff 用户 → 201"""
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)
        resp = self.client.post('/api/v1/products/', {
            'name': 'Staff Product Test', 'catalog_no': 'SC-STAFF-001', 'status': 'draft',
            'slug': 'staff-product-test',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_non_staff_cannot_update_product(self):
        """非 staff → 403"""
        user = UserFactory(is_staff=False)
        self.client.force_authenticate(user=user)
        resp = self.client.put(f'/api/v1/products/{self.product.pk}/', self.payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_update_product(self):
        """is_staff → 更新成功"""
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)
        resp = self.client.patch(f'/api/v1/products/{self.product.pk}/', {'name': 'Updated Name'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Updated Name')


class ProductCompletenessTest(TestCase):
    """产品完整度计算逻辑测试"""

    def setUp(self):
        self.client = APIClient()

    def test_complete_product_has_is_complete_true(self):
        """完整产品 → is_complete=True"""
        product = ProductFactory(
            name='Complete', catalog_no='SC-C-001', category_l1='Nucleotides',
            status='active',
        )
        SKUFactory(product=product, is_default=True)
        resp = self.client.get(f'/api/v1/products/{product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertTrue(data['data'].get('is_complete'))

    def test_incomplete_product_has_is_complete_false(self):
        """不完整产品 → is_complete=False, incomplete_items 非空"""
        product = ProductFactory(
            name='Incomplete', catalog_no='', category_l1='',
            status='draft',
        )
        resp = self.client.get(f'/api/v1/products/{product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertFalse(data['data'].get('is_complete'))
        self.assertTrue(len(data['data'].get('incomplete_items', [])) > 0)

    def test_missing_default_sku_is_incomplete(self):
        """有 SKU 但无默认 SKU → 不完整"""
        product = ProductFactory(
            name='NoDefault', catalog_no='SC-ND-001', category_l1='Nucleotides',
        )
        SKUFactory(product=product, is_default=False)
        resp = self.client.get(f'/api/v1/products/{product.pk}/')
        data = resp.json()
        self.assertFalse(data['data'].get('is_complete'))
        self.assertIn('SKU', ''.join(data['data'].get('incomplete_items', [])))
