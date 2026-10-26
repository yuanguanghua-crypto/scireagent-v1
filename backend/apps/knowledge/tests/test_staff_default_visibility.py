"""staff 默认只见公开态（方案 B，2026-10-26 用户拍板）。

## 为什么要改

此前 `apply_public_visibility` 让 **staff 无条件绕过 status 过滤**。结果同一个
staff 用户在两个页面看到矛盾数字：

| 页面 | 数字 | 来源 |
|---|---|---|
| 首页 "Methods" 卡片 | **93** | `site_views.py` 写死 `filter(status='active')` |
| 点 "Browse 93 →" 进 `/methods` | **47,927** | staff 绕过过滤，含 47,834 个 draft |

访客视角两边都是 93（一致），但 staff 视角差 47,834 —— 看起来像故障。

现在改为 **staff 也默认过滤 status**，需显式 `?include_unpublished=1` 才看全量。
理由：默认行为应对齐"访客看到什么"，例外（管理视角）必须是显式动作。

## 注意后端的两段过滤顺序

`apply_public_visibility`（按公开态）在前，DjangoFilterBackend 的 `?status=`
在后。所以「看 draft」必须**同时**传 `include_unpublished=1`，否则先被筛成
active、再按 draft 筛成空。前端 `buildParams()` 已按此处理。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory

METHODS = '/api/v1/methods/'
PROTOCOLS = '/api/v1/protocols/'


class StaffDefaultVisibilityTest(TestCase):
    def setUp(self):
        # 1 条公开 + 2 条草稿
        self.pub_method = MethodFactory(name='Active Method', status='active')
        self.draft1 = MethodFactory(name='Draft Method 1', status='draft')
        self.draft2 = MethodFactory(name='Draft Method 2', status='draft')

        self.staff = APIClient()
        self.staff.force_authenticate(UserFactory(is_staff=True))
        self.anon = APIClient()

    def _count(self, client, path, **params):
        return (client.get(path, params).json().get('meta') or {}) \
            .get('pagination', {}).get('count')

    def test_staff_sees_only_public_by_default(self):
        """核心断言：staff 默认与访客同口径（93 而非 47,927 的那条规则）。"""
        self.assertEqual(self._count(self.staff, METHODS), 1,
                         'staff 默认应只见 active，否则会与首页统计矛盾')

    def test_staff_with_optin_sees_all(self):
        self.assertEqual(self._count(self.staff, METHODS, include_unpublished=1), 3,
                         '显式 opt-in 才能看全量（管理视角）')

    def test_staff_can_filter_draft_with_optin(self):
        """看 draft 必须同时带 include_unpublished，否则会被公开态过滤先筛空。"""
        self.assertEqual(self._count(self.staff, METHODS, include_unpublished=1, status='draft'), 2)

    def test_anonymous_unaffected(self):
        self.assertEqual(self._count(self.anon, METHODS), 1)

    def test_anonymous_cannot_escalate_with_param(self):
        """`include_unpublished` 对非 staff 一律无效 —— 不能让匿名用户绕过。"""
        self.assertEqual(self._count(self.anon, METHODS, include_unpublished=1), 1)
        self.assertEqual(self._count(self.anon, METHODS, include_unpublished=1, status='draft'), 0)

    def test_homepage_matches_list_for_staff(self):
        """首页 methods 数字必须等于 staff 默认列表的 count —— 这就是本 bug 的判据。"""
        home = self.anon.get('/api/v1/site/home').json()
        home = home.get('data') or home
        home_methods = (home.get('knowledge') or {}).get('methods')
        staff_list = self._count(self.staff, METHODS)
        self.assertEqual(home_methods, staff_list,
                         f'首页 {home_methods} ≠ staff 列表 {staff_list}')


class ProtocolDefaultVisibilityTest(TestCase):
    def setUp(self):
        ProtocolFactory(name='Published Protocol', status='published')
        ProtocolFactory(name='Draft Protocol', status='draft')
        self.staff = APIClient()
        self.staff.force_authenticate(UserFactory(is_staff=True))
        self.anon = APIClient()

    def _count(self, client, path, **params):
        return (client.get(path, params).json().get('meta') or {}) \
            .get('pagination', {}).get('count')

    def test_staff_default_only_published(self):
        self.assertEqual(self._count(self.staff, PROTOCOLS), 1)

    def test_staff_optin_sees_all(self):
        self.assertEqual(self._count(self.staff, PROTOCOLS, include_unpublished=1), 2)

    def test_anonymous_unaffected(self):
        self.assertEqual(self._count(self.anon, PROTOCOLS), 1)
