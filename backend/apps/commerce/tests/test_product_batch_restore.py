"""S5.2：批量恢复端点 `POST /api/v1/products/batch-restore/` + **幂等**。

设计要点：
- 幂等：对已 `archived=False` 的对象再调用 **不产生重复 RESTORE 审计**。
- 容错：不存在的 id 记入 `not_found`，不让整批失败。
- 取证时机沿用 S3：`AuditLog.log()` 必须在置 `archived=False` **之前**调用。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import AuditLog
from apps.commerce.tests.factories import ProductFactory

URL = '/api/v1/products/batch-restore/'


class BatchRestoreTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.p1 = self._archived('R1')
        self.p2 = self._archived('R2')
        self.live = ProductFactory(name='Live One', status='active')

    @staticmethod
    def _archived(name):
        p = ProductFactory(name=name, status='active')
        p.archived = True
        p.save()
        return p

    def _post(self, ids):
        self.client.force_authenticate(user=self.staff)
        return self.client.post(URL, {'ids': ids}, format='json')

    def test_restores_all_given_ids(self):
        resp = self._post([self.p1.pk, self.p2.pk])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()['data']
        self.assertEqual(data['restored'], 2)
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertFalse(self.p1.archived)
        self.assertFalse(self.p2.archived)

    def test_writes_restore_audit_per_restored_product(self):
        self._post([self.p1.pk, self.p2.pk])
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.ACTION_RESTORE).count(), 2)

    def test_second_call_is_idempotent_and_writes_no_duplicate_audit(self):
        """幂等：重复批量恢复不得产生重复审计。"""
        self._post([self.p1.pk])
        before = AuditLog.objects.filter(action=AuditLog.ACTION_RESTORE).count()
        resp = self._post([self.p1.pk])
        data = resp.json()['data']
        self.assertEqual(data['restored'], 0)
        self.assertEqual(data['skipped'], 1)
        after = AuditLog.objects.filter(action=AuditLog.ACTION_RESTORE).count()
        self.assertEqual(after, before, '重复恢复产生了重复审计，破坏幂等')

    def test_reports_missing_ids_without_failing_the_batch(self):
        resp = self._post([self.p1.pk, 99999999])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()['data']
        self.assertEqual(data['restored'], 1)
        self.assertIn(99999999, data['not_found'])

    def test_empty_ids_rejected(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(URL, {'ids': []}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_cannot_batch_restore(self):
        resp = self.client.post(URL, {'ids': [self.p1.pk]}, format='json')
        self.assertIn(resp.status_code,
                      [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        self.p1.refresh_from_db()
        self.assertTrue(self.p1.archived, '匿名不得恢复')
