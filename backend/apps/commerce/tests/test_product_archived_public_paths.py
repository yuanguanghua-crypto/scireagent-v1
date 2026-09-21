"""S2：公开读路径排除软删产品（archived=True）—— commerce 侧。

逐条锁定：list + ?search= / retrieve {id}/ / {id}/detail/。
并反向锁定 staff 回收站（?archived=1）与 restore 不被过度封锁
（红线：get_queryset 的 archived 分支不得收紧，否则 restore 取不到对象→回收站锁死）。

独立成文件的原因：backend/apps/commerce/tests/test_product_audit.py 是 S1 已固化的文件，
S2 用例不改动它。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory


class S2ArchivedLeakPathsTest(TestCase):
    """S2：公开读路径排除软删产品（archived=True）。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)

    def _archived(self, name, slug):
        p = ProductFactory(name=name, slug=slug, status='active')
        p.archived = True
        p.save(update_fields=['archived'])
        return p

    # ── 路径 1：list + ?search=（旧写法会覆盖 qs、丢失 exclude）──
    def test_list_search_excludes_archived(self):
        archived = self._archived('Zzzsearch Probe Archived', 'zzzsearch-archived')
        live = ProductFactory(name='Zzzsearch Probe Live', slug='zzzsearch-live', status='active')
        resp = self.client.get('/api/v1/products/?search=Zzzsearch')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [p['name'] for p in resp.json()['data']]
        self.assertNotIn(archived.name, names)
        # 回归：搜索仍能命中未归档产品
        self.assertIn(live.name, names)

    # ── 路径 2：retrieve {id}/ ──
    def test_retrieve_archived_404_anonymous(self):
        archived = self._archived('Retrieve Archived', 'retrieve-archived')
        resp = self.client.get(f'/api/v1/products/{archived.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_archived_200_staff(self):
        archived = self._archived('Retrieve Archived Staff', 'retrieve-archived-staff')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get(f'/api/v1/products/{archived.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── 路径 3：{id}/detail/ ──
    def test_detail_archived_404(self):
        archived = self._archived('Detail Archived', 'detail-archived')
        resp = self.client.get(f'/api/v1/products/{archived.pk}/detail/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_active_200_regression(self):
        live = ProductFactory(name='Detail Live', slug='detail-live', status='active')
        resp = self.client.get(f'/api/v1/products/{live.pk}/detail/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── 反向：不得过度封锁（S1 回收站依赖）──
    def test_staff_recycle_bin_still_lists_archived(self):
        archived = self._archived('Recycle Visible', 'recycle-visible')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get('/api/v1/products/?archived=1')
        names = [p['name'] for p in resp.json()['data']]
        self.assertIn(archived.name, names)

    def test_restore_still_works_on_archived(self):
        archived = self._archived('Restore Me', 'restore-me')
        self.client.force_authenticate(user=self.staff)
        resp = self.client.post(f'/api/v1/products/{archived.pk}/restore/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        archived.refresh_from_db()
        self.assertFalse(archived.archived)
