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
    """删除动作（Plan B：默认软归档，不物理删除）"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.product = ProductFactory(name='Delete Me', status='active')

    def test_staff_delete_soft_archives(self):
        """staff DELETE -> 200，产品软归档（仍在 DB，archived=True）"""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.product.refresh_from_db()
        self.assertTrue(self.product.archived)

    def test_soft_delete_keeps_skus(self):
        """软删不级联物理删 SKU（行为变更：不再 CASCADE 硬删）"""
        sku = SKUFactory(product=self.product, sku_code='KEPT-SKU')
        self.client.force_authenticate(user=self.staff)
        self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertTrue(SKU.objects.filter(pk=sku.pk).exists())

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


class ProductRestoreOnCreateTest(TestCase):
    """软删除（archived=True）商品仍占 catalog_no；重新创建同名目录号应恢复而非冲突。

    删除审计铁律下 DELETE 仅置 archived=True，行仍在库、catalog_no 仍受唯一约束占用。
    修复：POST 创建时若 catalog_no 仅命中 archived 行，则 un-archive 并用新数据更新该商品。
    """

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)

    def _post_create(self, payload):
        self.client.force_authenticate(user=self.staff)
        return self.client.post('/api/v1/products/', payload, format='json')

    def test_create_with_archived_catalog_no_restores(self):
        """POST 同名 catalog_no（仅 archived 命中）→ 201，恢复同 id、archived=False、字段更新。"""
        p = ProductFactory(catalog_no='SC-RESTORE-1', name='Old Name', status='active')
        p.archived = True
        p.save()
        resp = self._post_create({
            'name': 'New Restored', 'catalog_no': 'SC-RESTORE-1', 'slug': 'new-sc-restore-1', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()['data']['id'], p.id)
        p.refresh_from_db()
        self.assertFalse(p.archived)
        self.assertEqual(p.name, 'New Restored')

    def test_create_with_archived_catalog_no_preserves_skus_when_none_sent(self):
        """恢复时若未带 skus，归档商品原有 SKU 不应被误删。"""
        p = ProductFactory(catalog_no='SC-RESTORE-2', name='Has Sku', status='active')
        sku = SKUFactory(product=p, sku_code='KEEP-ME')
        p.archived = True
        p.save()
        resp = self._post_create({
            'name': 'Restored', 'catalog_no': 'SC-RESTORE-2', 'slug': 'new-sc-restore-2', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        p.refresh_from_db()
        self.assertFalse(p.archived)
        self.assertTrue(SKU.objects.filter(pk=sku.pk).exists())

    def test_create_with_active_duplicate_still_conflicts(self):
        """若 catalog_no 命中未归档（active）行，仍走唯一约束正常报 400（真重复）。"""
        ProductFactory(catalog_no='SC-DUP-1', name='Existing', status='active')
        resp = self._post_create({
            'name': 'Clash', 'catalog_no': 'SC-DUP-1', 'slug': 'new-sc-dup-1', 'status': 'draft',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


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
