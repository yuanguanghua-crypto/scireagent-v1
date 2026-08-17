"""S1 — 测试夹具实体隔离（is_test_fixture 标记法）

契约（对应「知识实体链路-可行实施方案与步骤计划-v2」S1）：

1. ResearchGoal / Application / Method 三模型带 ``is_test_fixture`` 布尔字段，默认 False。
2. 管理命令 ``mark_test_fixtures`` 按名称前缀标记，**永不删除任何数据行**（铁律①）。
3. 防护栏：被标记的实体即便 ``status=ACTIVE``，也不得出现在任何对外读取面
   （列表 / 详情 / search / search-suggest / search-grouped / site-navigation）。
   —— 这是关键：现网 22 个脏实体恰好是 draft，靠 status 侥幸挡住了列表端点，
   但 search 系列端点根本没有 status 过滤。本测试用 ACTIVE 夹具证伪该侥幸。
4. 逃生口：staff + ``?include_test_fixtures=1`` 可看到，用于人工清理。
5. 真实实体零回归。
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.models import Application, Method, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    MethodFactory,
    ResearchGoalFactory,
)

ACTIVE = 'active'


class TestFixtureFieldTest(TestCase):
    """契约 1：三模型有 is_test_fixture 字段，默认 False。"""

    def test_research_goal_has_is_test_fixture_default_false(self):
        goal = ResearchGoalFactory()
        self.assertFalse(goal.is_test_fixture)

    def test_application_has_is_test_fixture_default_false(self):
        app = ApplicationFactory()
        self.assertFalse(app.is_test_fixture)

    def test_method_has_is_test_fixture_default_false(self):
        method = MethodFactory()
        self.assertFalse(method.is_test_fixture)

    def test_field_is_queryable(self):
        ResearchGoalFactory(name='__e2e_x__', is_test_fixture=True)
        ResearchGoalFactory(name='Real Goal')
        self.assertEqual(ResearchGoal.objects.filter(is_test_fixture=True).count(), 1)
        self.assertEqual(ResearchGoal.objects.filter(is_test_fixture=False).count(), 1)


class MarkTestFixturesCommandTest(TestCase):
    """契约 2：管理命令按前缀标记，零删除，幂等，不误伤。"""

    def setUp(self):
        self.dirty = [
            ResearchGoalFactory(name='__e2e_goals_1783689956152__'),
            ResearchGoalFactory(name='__curl_test_goal__'),
        ]
        self.dirty_app = ApplicationFactory(name='__e2e_apps_1783692845767__')
        self.dirty_method = MethodFactory(name='__e2e_methods_1783690055811__')
        self.real_goal = ResearchGoalFactory(name='RNA Analysis')
        self.real_app = ApplicationFactory(name='RNA Fluorescent Labeling')
        self.real_method = MethodFactory(name='CuAAC Click Chemistry')

    def _counts(self):
        return (
            ResearchGoal.objects.count(),
            Application.objects.count(),
            Method.objects.count(),
        )

    def test_dry_run_does_not_write(self):
        before = self._counts()
        out = StringIO()
        call_command('mark_test_fixtures', '--dry-run', stdout=out)
        self.assertEqual(self._counts(), before)
        self.assertEqual(ResearchGoal.objects.filter(is_test_fixture=True).count(), 0)
        self.assertEqual(Application.objects.filter(is_test_fixture=True).count(), 0)
        self.assertEqual(Method.objects.filter(is_test_fixture=True).count(), 0)
        # dry-run 仍应报告将要标记的数量
        self.assertIn('2', out.getvalue())

    def test_marks_prefixed_entities(self):
        call_command('mark_test_fixtures', stdout=StringIO())
        self.assertEqual(ResearchGoal.objects.filter(is_test_fixture=True).count(), 2)
        self.assertEqual(Application.objects.filter(is_test_fixture=True).count(), 1)
        self.assertEqual(Method.objects.filter(is_test_fixture=True).count(), 1)

    def test_does_not_touch_real_entities(self):
        call_command('mark_test_fixtures', stdout=StringIO())
        self.real_goal.refresh_from_db()
        self.real_app.refresh_from_db()
        self.real_method.refresh_from_db()
        self.assertFalse(self.real_goal.is_test_fixture)
        self.assertFalse(self.real_app.is_test_fixture)
        self.assertFalse(self.real_method.is_test_fixture)

    def test_deletes_nothing(self):
        """铁律①：数据零删除。"""
        before = self._counts()
        call_command('mark_test_fixtures', stdout=StringIO())
        self.assertEqual(self._counts(), before)

    def test_idempotent(self):
        call_command('mark_test_fixtures', stdout=StringIO())
        first = (
            ResearchGoal.objects.filter(is_test_fixture=True).count(),
            Application.objects.filter(is_test_fixture=True).count(),
            Method.objects.filter(is_test_fixture=True).count(),
        )
        call_command('mark_test_fixtures', stdout=StringIO())
        second = (
            ResearchGoal.objects.filter(is_test_fixture=True).count(),
            Application.objects.filter(is_test_fixture=True).count(),
            Method.objects.filter(is_test_fixture=True).count(),
        )
        self.assertEqual(first, second)

    def test_unmark_restores_flag(self):
        """支持回滚：--unmark 把标记清回 False（仍不删数据）。"""
        call_command('mark_test_fixtures', stdout=StringIO())
        before = self._counts()
        call_command('mark_test_fixtures', '--unmark', stdout=StringIO())
        self.assertEqual(ResearchGoal.objects.filter(is_test_fixture=True).count(), 0)
        self.assertEqual(self._counts(), before)

    def test_custom_prefix(self):
        ResearchGoalFactory(name='ZZTMP_probe')
        call_command('mark_test_fixtures', '--prefix', 'ZZTMP_', stdout=StringIO())
        self.assertEqual(
            ResearchGoal.objects.filter(is_test_fixture=True, name='ZZTMP_probe').count(), 1
        )
        # 默认前缀的脏实体不应被这次调用标记
        self.assertFalse(ResearchGoal.objects.get(name='__curl_test_goal__').is_test_fixture)


class TestFixtureReadSurfaceIsolationTest(TestCase):
    """契约 3/4：被标记实体在所有读取面不可见（即使 status=ACTIVE）。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)

        # 关键：夹具设为 ACTIVE，证明隔离不依赖 status 侥幸
        self.fx_goal = ResearchGoalFactory(
            name='__e2e_goals_zzz__', status=ACTIVE, is_test_fixture=True
        )
        self.fx_app = ApplicationFactory(
            name='__e2e_apps_zzz__', status=ACTIVE, is_test_fixture=True,
            research_goal=self.fx_goal, summary='fixture summary zzz',
        )
        self.fx_method = MethodFactory(
            name='__e2e_methods_zzz__', status=ACTIVE, is_test_fixture=True,
            application=self.fx_app, purpose='fixture purpose zzz',
        )

        self.real_goal = ResearchGoalFactory(name='Real Goal zzz', status=ACTIVE)
        self.real_app = ApplicationFactory(
            name='Real App zzz', status=ACTIVE, research_goal=self.real_goal,
            summary='real summary zzz',
        )
        self.real_method = MethodFactory(
            name='Real Method zzz', status=ACTIVE, application=self.real_app,
            purpose='real purpose zzz',
        )

    # ---------- 列表端点 ----------
    def _names(self, resp):
        return [row['name'] for row in resp.json()['data']]

    def test_research_goal_list_anonymous_excludes_fixture(self):
        names = self._names(self.client.get('/api/v1/research-goals/'))
        self.assertNotIn(self.fx_goal.name, names)
        self.assertIn(self.real_goal.name, names)

    def test_research_goal_list_staff_excludes_fixture_by_default(self):
        self.client.force_authenticate(user=self.staff)
        names = self._names(self.client.get('/api/v1/research-goals/'))
        self.assertNotIn(self.fx_goal.name, names)
        self.assertIn(self.real_goal.name, names)

    def test_application_list_excludes_fixture(self):
        names = self._names(self.client.get('/api/v1/applications/'))
        self.assertNotIn(self.fx_app.name, names)
        self.assertIn(self.real_app.name, names)

    def test_method_list_excludes_fixture(self):
        names = self._names(self.client.get('/api/v1/methods/'))
        self.assertNotIn(self.fx_method.name, names)
        self.assertIn(self.real_method.name, names)

    # ---------- 逃生口 ----------
    def test_staff_can_opt_in_to_see_fixtures(self):
        self.client.force_authenticate(user=self.staff)
        names = self._names(
            self.client.get('/api/v1/research-goals/?include_test_fixtures=1')
        )
        self.assertIn(self.fx_goal.name, names)

    def test_anonymous_cannot_opt_in(self):
        names = self._names(
            self.client.get('/api/v1/research-goals/?include_test_fixtures=1')
        )
        self.assertNotIn(self.fx_goal.name, names)

    # ---------- 详情端点 ----------
    def test_detail_of_fixture_is_404_for_anonymous(self):
        resp = self.client.get(f'/api/v1/research-goals/{self.fx_goal.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_detail_of_fixture_visible_to_staff_with_optin(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get(
            f'/api/v1/research-goals/{self.fx_goal.id}/?include_test_fixtures=1'
        )
        self.assertEqual(resp.status_code, 200)

    # ---------- search 系列（现状零 status 过滤，真实泄漏点）----------
    def test_search_excludes_fixture(self):
        resp = self.client.get('/api/v1/search?q=zzz')
        names = [r.get('name', '') for r in resp.json()['data']]
        self.assertNotIn(self.fx_app.name, names)
        self.assertNotIn(self.fx_method.name, names)
        self.assertIn(self.real_app.name, names)

    def test_search_suggest_excludes_fixture(self):
        resp = self.client.get('/api/v1/search/suggest?q=zzz')
        texts = [r.get('text', '') for r in resp.json()['data']]
        self.assertNotIn(self.fx_method.name, texts)
        self.assertIn(self.real_method.name, texts)

    def test_search_grouped_excludes_fixture(self):
        resp = self.client.get('/api/v1/search/grouped?q=zzz')
        data = resp.json()['data']
        app_names = [r['name'] for r in data['applications']]
        method_names = [r['name'] for r in data['methods']]
        self.assertNotIn(self.fx_app.name, app_names)
        self.assertNotIn(self.fx_method.name, method_names)
        self.assertIn(self.real_app.name, app_names)

    # ---------- 站点导航 ----------
    def test_site_navigation_excludes_fixture(self):
        resp = self.client.get('/api/v1/site/navigation')
        payload = resp.json()
        blob = str(payload)
        self.assertNotIn(self.fx_app.name, blob)
        self.assertNotIn(self.fx_method.name, blob)

    # ---------- 图谱 ----------
    def test_graph_of_fixture_returns_404(self):
        resp = self.client.get(
            f'/api/v1/graph?type=application&id={self.fx_app.id}'
        )
        self.assertEqual(resp.status_code, 404)

    def test_graph_of_real_entity_still_works(self):
        resp = self.client.get(
            f'/api/v1/graph?type=application&id={self.real_app.id}'
        )
        self.assertEqual(resp.status_code, 200)
