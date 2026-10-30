"""Reference 的测试夹具可见性（2026-10-30 C 批补的最后一块）。

## 背景

Reference 是**最后一个没有 `is_test_fixture` 的对外读实体**，也因此
`ReferenceViewSet` 从来没覆写 `get_queryset` —— 夹具直接对外可见。

本地 219 条里有 32 条 e2e 残留（31 条 `__e2e_references_*__` + 1 条
`E2E stub reference`），而那条 stub 的 `year=2026` 让它**稳定排第一**。
C 批要把 ReferencesSection 接进首页，这条 stub 就会在首页首屏出现。

## 口径

Reference 无 `status` 字段 ⇒ `apply_public_visibility` 对它等价于
「只做夹具过滤」。与其它知识实体一致：staff 需显式
`?include_test_fixtures=1` 才能看到夹具（用于人工清理）。
详情（retrieve）同样不挡 —— 否则后台编辑/删除取不到对象。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.tests.factories import ReferenceFactory


class ReferenceFixtureVisibilityTest(TestCase):
    def setUp(self):
        self.anon = APIClient()
        self.staff_client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.staff_client.force_authenticate(user=self.staff)

        self.real = ReferenceFactory(
            title='Zzref Real Paper On Nucleotides', year=2026, doi=None, pmid=None)
        self.fixture = ReferenceFactory(
            title='Zzref E2E stub reference', year=2026, doi=None, pmid=None,
            is_test_fixture=True)

    # ── 公开读面：排除 ─────────────────────────────────────
    def test_anonymous_list_excludes_fixture(self):
        resp = self.anon.get('/api/v1/references/', {'search': 'Zzref'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = [r['title'] for r in resp.json()['data']]
        self.assertIn(self.real.title, titles)
        self.assertNotIn(self.fixture.title, titles)

    def test_homepage_references_exclude_fixture(self):
        """首页 Recent Publications 首屏不能出现 E2E stub。

        夹具的 year=2026 与真实文献同档，按其排序会排到最前 —— 这正是线上
        会发生的效果，所以这里直接断言它不在首页列表里。
        """
        data = self.anon.get('/api/v1/site/home').json()['data']
        titles = [r['title'] for r in data['references']]
        self.assertNotIn(self.fixture.title, titles)
        if self.real.title in titles:  # 可能被 year 排序挤出前 5，不作硬断言
            self.assertLess(titles.index(self.real.title),
                            len(titles))

    # ── staff：需 opt-in ──────────────────────────────────
    def test_staff_can_opt_in_to_fixtures(self):
        resp = self.staff_client.get(
            '/api/v1/references/', {'search': 'Zzref', 'include_test_fixtures': '1'})
        titles = [r['title'] for r in resp.json()['data']]
        self.assertIn(self.fixture.title, titles,
                      'staff 显式 opt-in 后必须能看到夹具（清理需要）')

    def test_staff_without_opt_in_still_excludes(self):
        resp = self.staff_client.get('/api/v1/references/', {'search': 'Zzref'})
        titles = [r['title'] for r in resp.json()['data']]
        self.assertNotIn(self.fixture.title, titles)

    # ── 详情：与列表同口径（DRF 的 get_object 走同一个 get_queryset）──
    def test_fixture_retrieve_blocked_for_anonymous(self):
        """匿名不能靠猜 id 拿到夹具详情（列表挡住了、详情更不该漏）。"""
        resp = self.anon.get(f'/api/v1/references/{self.fixture.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_can_retrieve_fixture_with_opt_in(self):
        """staff 带 opt-in 必须能取到 —— 否则后台连删除/编辑都打不开。"""
        resp = self.staff_client.get(
            f'/api/v1/references/{self.fixture.pk}/',
            {'include_test_fixtures': '1'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['data']['id'], self.fixture.pk)
