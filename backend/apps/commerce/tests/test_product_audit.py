"""Plan B：产品删除审计 + 默认软归档（回收站式）。

- DELETE /products/{pk}/  → 软归档（archived=True，不物理删）+ AuditLog(DELETE)。
- POST  /products/{pk}/restore/  → 取消归档 + AuditLog(UPDATE)。
- POST  /products/{pk}/hard-delete/ → 物理删除 + AuditLog(HARD_DELETE)，仅超管。
- 默认列表 exclude(archived=True)；staff 加 ?archived=1 可见回收站。
- create / update 也写 AuditLog（全程可追溯）。
"""
from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import Product, SKU, AuditLog
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class ProductSoftDeleteTest(TestCase):
    """DELETE 改为软归档（回收站），不物理删除。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.product = ProductFactory(name='Soft Delete Me', status='active')

    def test_staff_delete_soft_archives_not_physically_removes(self):
        """staff DELETE -> 200，产品仍在 DB，archived=True（软删）"""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.product.refresh_from_db()
        self.assertTrue(self.product.archived)

    def test_soft_deleted_excluded_from_default_list_anonymous(self):
        """匿名默认列表看不到已软删产品"""
        self.product.archived = True
        self.product.save()
        resp = self.client.get('/api/v1/products/')
        names = [p['name'] for p in resp.json()['data']]
        self.assertNotIn('Soft Delete Me', names)

    def test_soft_deleted_excluded_from_default_list_staff(self):
        """staff 默认列表也看不到（回收站默认隐藏）"""
        self.product.archived = True
        self.product.save()
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get('/api/v1/products/')
        names = [p['name'] for p in resp.json()['data']]
        self.assertNotIn('Soft Delete Me', names)

    def test_staff_can_see_archived_via_param(self):
        """staff 加 ?archived=1 可见回收站"""
        self.product.archived = True
        self.product.save()
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get('/api/v1/products/?archived=1')
        names = [p['name'] for p in resp.json()['data']]
        self.assertIn('Soft Delete Me', names)

    def test_restore_unarchives(self):
        """restore action 取消归档，产品回到列表"""
        self.product.archived = True
        self.product.save()
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/restore/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertFalse(self.product.archived)

    def test_soft_delete_does_not_cascade_skus(self):
        """软删不级联物理删 SKU（产品仍在，SKU 自然保留）"""
        sku = SKUFactory(product=self.product, sku_code='KEEP-ME')
        self.client.force_authenticate(user=self.staff)
        self.client.delete(f'/api/v1/products/{self.product.pk}/')
        self.assertTrue(SKU.objects.filter(pk=sku.pk).exists())


class ProductDeleteAuditTest(TestCase):
    """删除/创建/硬删全程审计。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.admin = UserFactory(is_superuser=True, is_staff=True)
        self.product = ProductFactory(name='Audit Me', status='active')

    def _ct(self):
        return ContentType.objects.get_for_model(Product)

    def test_delete_creates_audit_log(self):
        """DELETE 写一条 AuditLog(DELETE)，含操作人/对象repr"""
        self.client.force_authenticate(user=self.staff)
        self.client.delete(f'/api/v1/products/{self.product.pk}/')
        logs = AuditLog.objects.filter(content_type=self._ct(), object_id=self.product.pk)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.action, AuditLog.ACTION_DELETE)
        self.assertEqual(log.user, self.staff)
        self.assertEqual(log.object_repr, 'Audit Me')

    def test_create_creates_audit_log(self):
        """POST 创建产品写 AuditLog(CREATE)"""
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post('/api/v1/products/', {
            'name': 'Create Audit', 'slug': 'create-audit', 'status': 'draft',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        prod = Product.objects.get(slug='create-audit')
        log = AuditLog.objects.get(content_type=self._ct(), object_id=prod.pk)
        self.assertEqual(log.action, AuditLog.ACTION_CREATE)
        self.assertEqual(log.user, self.staff)

    def test_hard_delete_creates_audit_log_and_removes(self):
        """超管 hard-delete 物理删除 + AuditLog(HARD_DELETE)"""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/hard-delete/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        log = AuditLog.objects.get(content_type=self._ct(), object_id=self.product.pk)
        self.assertEqual(log.action, AuditLog.ACTION_HARD_DELETE)
        self.assertEqual(log.user, self.admin)

    def test_hard_delete_forbidden_for_non_superuser(self):
        """非超管（含普通 staff）禁止 hard-delete"""
        self.client.force_authenticate(user=self.staff)  # staff 非 superuser
        resp = self.client.post(f'/api/v1/products/{self.product.pk}/hard-delete/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())


class ProductUpdateAuditTest(TestCase):
    """更新也写审计。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.product = ProductFactory(name='Before', status='active')

    def test_update_creates_audit_log(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.patch(f'/api/v1/products/{self.product.pk}/', {
            'overview': 'changed overview',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ct = ContentType.objects.get_for_model(Product)
        log = AuditLog.objects.get(content_type=ct, object_id=self.product.pk)
        self.assertEqual(log.action, AuditLog.ACTION_UPDATE)
        self.assertEqual(log.user, self.staff)


class DashboardExcludesArchivedTest(TestCase):
    """工作台统计不计入软删(回收站)产品。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        ProductFactory(name='Live One', status='active')
        p = ProductFactory(name='Soft Deleted', status='draft')
        p.archived = True
        p.save()

    def test_dashboard_total_excludes_archived(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get('/api/v1/admin/dashboard-stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()['data']
        # 总数只算 live（1 条），软删的不计入
        self.assertEqual(data['total_products'], 1)
        self.assertEqual(data['draft_products'], 0)
