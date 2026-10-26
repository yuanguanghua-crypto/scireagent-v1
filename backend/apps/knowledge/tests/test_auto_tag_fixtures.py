"""写入时自动标记测试夹具（is_test_fixture）。

背景（2026-10-26 线上事故）：
E2E 通过**生产 API** 建了 9 条 `__e2e_goals_*`，而当时唯一标记手段是**事后**跑
`mark_test_fixtures` 命令。忘了跑 ⇒ 脏数据以 `is_test_fixture=False` 混进正常数据，
只能靠每个查询记得调 `.public()` 过滤 —— 首页漏了一处，测试垃圾就占了首屏 5/6。

本测试锁住新契约：**API 写入时按名称前缀自动打标**，脏数据从诞生就是脏的。

同时锁住一个不能退让的边界：**不改变 factory 的行为**。`test_test_fixture_isolation.py`
依赖「factory 创建时 is_test_fixture 仍为 False，须跑 mark 命令才变 True」这一前提，
所以标记逻辑必须留在 ViewSet 层，不能下沉到 model.save()。

## 迁移状态说明

存量 9 条（id 34-42）在本修复之前就以 `is_test_fixture=True` 存在（靠
`test_test_fixture_isolation.py` 里记录的 `mark_test_fixtures` 命令补标），
id 很小 ⇒ 会排在首页 `[:6]` 之外。所以「自动打标」对存量是补充，
真正的修复是 `site_views.py` 的 `.public()` 过滤。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.models import Application, Method, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    MethodFactory,
    ResearchGoalFactory,
)


class AutoTagOnCreateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(UserFactory(is_staff=True))

    def test_goal_with_prefix_is_marked(self):
        r = self.client.post('/api/v1/research-goals/', {
            'name': '__e2e_goals_1783689956152__',
            'slug': 'e2e-goals-1783689956152',
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        g = ResearchGoal.objects.get(name='__e2e_goals_1783689956152__')
        self.assertTrue(g.is_test_fixture, '以 __ 开头创建时必须自动标记')

    def test_goal_without_prefix_not_marked(self):
        r = self.client.post('/api/v1/research-goals/', {
            'name': 'RNA Labeling & Detection',
            'slug': 'rna-labeling-detection',
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        g = ResearchGoal.objects.get(name='RNA Labeling & Detection')
        self.assertFalse(g.is_test_fixture, '正常命名不能被误标')

    def test_application_with_prefix_is_marked(self):
        goal = ResearchGoalFactory()
        r = self.client.post('/api/v1/applications/', {
            'name': '__e2e_apps_1783689956152__',
            'slug': 'e2e-apps-1783689956152',
            'research_goal': goal.pk,
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        self.assertTrue(Application.objects.get(name='__e2e_apps_1783689956152__').is_test_fixture)

    def test_method_with_prefix_is_marked(self):
        r = self.client.post('/api/v1/methods/', {
            'name': '__curl_test_method__',
            'slug': 'curl-test-method',
        }, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        self.assertTrue(Method.objects.get(name='__curl_test_method__').is_test_fixture)


class AutoTagOnUpdateTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(UserFactory(is_staff=True))

    def test_rename_to_prefix_marks(self):
        g = ResearchGoalFactory(name='Normal Goal')
        self.assertFalse(g.is_test_fixture)
        r = self.client.patch(f'/api/v1/research-goals/{g.pk}/',
                              {'name': '__e2e_renamed__'}, format='json')
        self.assertIn(r.status_code, (200, 204), r.content[:300])
        g.refresh_from_db()
        self.assertTrue(g.is_test_fixture, '改名为 __ 开头后应自动标记')

    def test_rename_away_does_not_unmark(self):
        """取消标记是人工判断（可能还有关联数据），不该由一次改名决定。

        ⚠️ 必须带 `?include_test_fixtures=1`：`apply_public_visibility` 让测试夹具
        对所有身份默认不可见（含 staff），不加这个参数 PATCH 会 404。
        这本身也是隔离机制在正常工作的证据。
        """
        g = ResearchGoalFactory(name='__e2e_already__', is_test_fixture=True)
        r = self.client.patch(f'/api/v1/research-goals/{g.pk}/?include_test_fixtures=1',
                              {'name': 'Now A Real Name'}, format='json')
        self.assertIn(r.status_code, (200, 204), r.content[:300])
        g.refresh_from_db()
        self.assertTrue(g.is_test_fixture, '改名不应自动取消标记')


class FactoryBehaviourUnchangedTest(TestCase):
    """关键边界：factory 走 ORM 直接 create，**不经过 ViewSet**，必须保持 False。"""

    def test_factory_still_creates_unmarked(self):
        g = ResearchGoalFactory(name='__e2e_goals_1783689956152__')
        self.assertFalse(g.is_test_fixture,
                         'factory 行为不能变 —— test_test_fixture_isolation 依赖这个前提')

    def test_factory_app_and_method_unmarked(self):
        app = ApplicationFactory(name='__e2e_apps_x__')
        m = MethodFactory(name='__e2e_methods_x__')
        self.assertFalse(app.is_test_fixture)
        self.assertFalse(m.is_test_fixture)
