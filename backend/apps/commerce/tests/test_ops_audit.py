"""审计日志查询 —— 权限、筛选、快照、覆盖范围元信息。

背景：`AuditLog` 此前**只写不读**（全仓只有 `AuditLog.log()`），
要追溯"谁删了哪个产品、删之前是什么值"只能进容器跑 shell。
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import AuditLog, Product
from apps.commerce.tests.factories import ProductFactory

URL = '/api/v1/ops/audit-logs/'


class AuditLogTestBase(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True, username='auditadmin')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.ct = ContentType.objects.get_for_model(Product)
        self.p1 = ProductFactory(catalog_no='SC8801', name='Alpha Probe')
        self.p2 = ProductFactory(catalog_no='SC8802', name='Beta Probe')

    def _mk(self, action, product, snapshot=None, user=None):
        return AuditLog.objects.create(
            user=user or self.admin,
            action=action,
            content_type=self.ct,
            object_id=product.pk,
            object_repr=product.name,
            snapshot=snapshot or {},
        )


class AuditLogPermissionTest(AuditLogTestBase):
    def test_anonymous_denied(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    def test_researcher_denied(self):
        c = APIClient()
        c.force_authenticate(UserFactory(is_staff=False, role='researcher'))
        self.assertIn(c.get(URL).status_code, (401, 403))

    def test_procurement_denied(self):
        """审计日志含操作人与字段快照，procurement 不该看。"""
        c = APIClient()
        c.force_authenticate(UserFactory(is_staff=False, role='procurement'))
        self.assertIn(c.get(URL).status_code, (401, 403))

    def test_staff_allowed(self):
        self.assertEqual(self.client.get(URL).status_code, 200)


class AuditLogQueryTest(AuditLogTestBase):
    def test_rows_and_shape(self):
        self._mk(AuditLog.ACTION_DELETE, self.p1)
        rows = self.client.get(URL).json()['data']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for f in ('id', 'timestamp', 'action', 'action_display', 'model',
                  'object_id', 'object_repr', 'username', 'has_snapshot'):
            self.assertIn(f, row)
        self.assertEqual(row['model'], 'product')
        self.assertEqual(row['username'], 'auditadmin')
        self.assertEqual(row['action_display'], '软删除(归档)')

    def test_filter_by_action(self):
        self._mk(AuditLog.ACTION_DELETE, self.p1)
        self._mk(AuditLog.ACTION_RESTORE, self.p2)
        rows = self.client.get(URL, {'action': 'restore'}).json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['action'], 'RESTORE', 'action 参数应大小写不敏感')

    def test_filter_by_username(self):
        other = UserFactory(username='someone-else')
        self._mk(AuditLog.ACTION_UPDATE, self.p1, user=self.admin)
        self._mk(AuditLog.ACTION_UPDATE, self.p2, user=other)
        rows = self.client.get(URL, {'username': 'auditadmin'}).json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['username'], 'auditadmin')

    def test_search_object_repr(self):
        self._mk(AuditLog.ACTION_DELETE, self.p1)
        self._mk(AuditLog.ACTION_DELETE, self.p2)
        rows = self.client.get(URL, {'search': 'Alpha'}).json()['data']
        self.assertEqual(len(rows), 1)
        self.assertIn('Alpha', rows[0]['object_repr'])

    def test_filter_by_date_range(self):
        self._mk(AuditLog.ACTION_DELETE, self.p1)
        today = timezone.localdate().isoformat()
        self.assertEqual(len(self.client.get(URL, {'since': today}).json()['data']), 1)
        self.assertEqual(len(self.client.get(URL, {'until': '2000-01-01'}).json()['data']), 0)

    def test_newest_first(self):
        self._mk(AuditLog.ACTION_CREATE, self.p1)
        self._mk(AuditLog.ACTION_DELETE, self.p2)
        rows = self.client.get(URL).json()['data']
        self.assertEqual(rows[0]['action'], 'DELETE', '默认按时间倒序')

    def test_coverage_meta_is_honest(self):
        """必须如实告知"只覆盖产品"，否则会被当成全局审计。"""
        self._mk(AuditLog.ACTION_DELETE, self.p1)   # models 列表由实际数据推导
        meta = self.client.get(URL).json()['meta']
        self.assertIn('coverage', meta)
        # 必须是去重后的列表 —— 曾经因为 Meta.ordering 干扰 DISTINCT
        # 返回 123 个重复的 'product'
        self.assertEqual(meta['coverage']['models'], ['product'])
        self.assertIn('只记录产品', meta['coverage']['note'])


class AuditLogDetailTest(AuditLogTestBase):
    def test_detail_includes_snapshot(self):
        snap = {'before': {'name': 'Alpha Probe', 'status': 'active'},
                'after': {'name': 'Alpha Probe', 'status': 'archived'}}
        log = self._mk(AuditLog.ACTION_UPDATE, self.p1, snapshot=snap)
        d = self.client.get(f'{URL}{log.pk}/').json()['data']
        self.assertEqual(d['snapshot']['before']['status'], 'active')
        self.assertEqual(d['snapshot']['after']['status'], 'archived')
        self.assertTrue(d['has_snapshot'])

    def test_detail_without_snapshot(self):
        log = self._mk(AuditLog.ACTION_DELETE, self.p1)
        d = self.client.get(f'{URL}{log.pk}/').json()['data']
        self.assertEqual(d['snapshot'], {})
        self.assertFalse(d['has_snapshot'])

    def test_unknown_id_404(self):
        self.assertEqual(self.client.get(f'{URL}999999/').status_code, 404)
