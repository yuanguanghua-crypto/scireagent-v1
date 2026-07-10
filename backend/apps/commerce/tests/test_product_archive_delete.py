"""产品下架（archive）与删除（destroy）测试。

- archive @action：staff 下架产品，status -> archived，前台不可见，可恢复。
- destroy：物理删除，SKU 级联删除。
- 前台过滤：非 staff 请求只看 active，下架/草稿不进列表且无法用 status 参数绕过。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import Product, SKU
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class ProductArchiveTest(TestCase):
    """下架动作"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.product = ProductFactory(name='Archive Me', status='active')

    def test_staff_can_archive_product(self):
        """staff POST archive -> 200，status 变 archived"""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/archive/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ARCHIVED)

    def test_anonymous_cannot_archive(self):
        """匿名下架 -> 401/403，status 不变"""
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/archive/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ACTIVE)

    def test_non_staff_cannot_archive(self):
        """非 staff 下架 -> 403"""
        self.client.force_authenticate(user=UserFactory(is_staff=False))
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/archive/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ProductDestroyTest(TestCase):
    """删除动作"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.product = ProductFactory(name='Delete Me', status='active')

    def test_staff_can_delete_product(self):
        """staff DELETE -> 200，产品消失"""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_delete_cascades_to_skus(self):
        """删除产品连带删除其 SKU（CASCADE）"""
        sku = SKUFactory(product=self.product, sku_code='TO-BE-CASCADED')
        self.client.force_authenticate(user=self.staff)
        self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertFalse(SKU.objects.filter(pk=sku.pk).exists())

    def test_anonymous_cannot_delete(self):
        """匿名删除 -> 401/403"""
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_non_staff_cannot_delete(self):
        """非 staff 删除 -> 403"""
        self.client.force_authenticate(user=UserFactory(is_staff=False))
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ProductPublicStatusFilterTest(TestCase):
    """前台列表状态过滤隐患修复"""

    def setUp(self):
        self.client = APIClient()
        # 公开列表只应看到 active 这一条
        ProductFactory(name='Active', status='active')
        ProductFactory(name='Draft', status='draft')
        ProductFactory(name='Archived', status='archived')
        ProductFactory(name='Deprecated', status='deprecated')

    def test_anonymous_list_only_active(self):
        """匿名列表只返回 active 产品"""
        resp = self.client.get('/api/v1/products/')
        names = [p['name'] for p in resp.json()['data']]
        self.assertEqual(names, ['Active'])

    def test_anonymous_cannot_bypass_with_status_param(self):
        """匿名 ?status=draft 也无法绕过，仍只返回 active"""
        resp = self.client.get('/api/v1/products/?status=draft')
        names = [p['name'] for p in resp.json()['data']]
        self.assertEqual(names, ['Active'])

    def test_staff_sees_all_statuses(self):
        """staff 不受过滤，可见全部状态"""
        self.client.force_authenticate(user=UserFactory(is_staff=True))
        resp = self.client.get('/api/v1/products/')
        names = {p['name'] for p in resp.json()['data']}
        self.assertEqual(names, {'Active', 'Draft', 'Archived', 'Deprecated'})
