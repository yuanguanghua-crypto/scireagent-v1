# -*- coding: utf-8 -*-
"""收敛类聚合 API 测试（双层结构 Step 2）。

契约要点（对应「收敛类聚合 API」需求）：
1. 静态 JSON 可加载且 total_classes == 851。
2. list：默认按 size 降序；group/source 精确过滤；search 大小写不敏感子串过滤；
   分页 page/page_size 边界回退（page_size 超上限/非法、page<1 均回退默认）。
3. detail：合法 class_id 返回类信息 + members；成员 n 计数口径
   （RG→Count('protocols')、AP→Count('research_goal_collections')）；
   不存在的 class_id → 404 信封。
4. 可见性：匿名/普通用户成员仅 ACTIVE；staff 全量；is_test_fixture=True
   对所有身份（含 staff + include_test_fixtures=1）都不可见。
5. 文件缺失兜底：monkeypatch 服务 JSON 路径 → list 返回空 data，不抛 500。

测试数据策略：静态 JSON 里的 class（如 rg_c001 → 实体 33）在空测试 DB 中
不一定存在实体行，因此凡涉及"成员命中 DB 行"的用例，通过 patch 服务层
get_class 返回指向测试实体的合成类 dict，成员查询仍走真实 DB。
"""
import json
from unittest import mock

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.models import Application, ResearchGoal
from apps.knowledge.services import convergence_service
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    ProtocolFactory,
    ResearchGoalFactory,
)


def _sample_class(class_id='rg_c001', group='rg', name='RNA Analysis',
                  source='curated', quality='pass', entity_ids=None, avg_cos=None):
    """构造与静态 JSON 结构一致的类 dict（测试用合成类）。

    注意：与 service.get_class 的输出契约对齐——带 size 计算字段
    （真实 service 在返回前会装饰出 size/avg_cos）。
    """
    entity_ids = entity_ids or []
    cls = {
        'class_id': class_id,
        'group': group,
        'name': name,
        'source': source,
        'quality': quality,
        'representative_id': entity_ids[0] if entity_ids else None,
        'entity_ids': entity_ids,
        'size': len(entity_ids),
    }
    if avg_cos is not None:
        cls['avg_cos'] = avg_cos
    return cls


def _patch_class(sample):
    """patch 服务层 get_class，让 detail 端点命中测试合成类。"""
    return mock.patch.object(convergence_service, 'get_class', return_value=sample)


class ConvergenceClassStaticJsonTest(TestCase):
    """静态 JSON 可加载契约（total_classes == 851）。"""

    def test_json_file_loadable_with_851_classes(self):
        path = settings.BASE_DIR / 'data' / 'convergence_classes.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['meta']['total_classes'], 851)
        self.assertEqual(len(data['classes']), 851)

    def test_service_loads_851_classes(self):
        classes = convergence_service.list_classes()
        self.assertEqual(len(classes), 851)
        # 每个类都带计算字段 size
        self.assertTrue(all('size' in c and c['size'] == len(c['entity_ids']) for c in classes))


class ConvergenceClassListAPITest(TestCase):
    """list 端点：GET /api/v1/convergence-classes/。"""

    def setUp(self):
        self.client = APIClient()

    def test_default_returns_sorted_by_size_desc(self):
        resp = self.client.get('/api/v1/convergence-classes')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['total'], 851)
        items = data['data']['items']
        self.assertEqual(len(items), 20)  # 默认 page_size=20
        sizes = [it['size'] for it in items]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        # 最大类 ap_k011(size=334) 应排第一
        self.assertEqual(items[0]['class_id'], 'ap_k011')
        self.assertEqual(items[0]['size'], 334)
        # 列表项字段白名单：class_id/group/name/source/quality/size/avg_cos
        self.assertEqual(
            set(items[0].keys()),
            {'class_id', 'group', 'name', 'source', 'quality', 'size', 'avg_cos'},
        )

    def test_group_filter(self):
        resp = self.client.get('/api/v1/convergence-classes', {'group': 'rg'})
        self.assertEqual(resp.status_code, 200)
        items = resp.json()['data']['items']
        self.assertTrue(items)
        self.assertTrue(all(it['group'] == 'rg' for it in items))
        self.assertEqual(resp.json()['data']['total'], 414)

    def test_trailing_slash_url_reachable(self):
        """带尾斜杠 URL 必须可达（与 DefaultRouter 端点约定一致）。"""
        resp = self.client.get('/api/v1/convergence-classes/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_invalid_group_returns_empty_items(self):
        """group 非法值：无匹配类，返回空 items + total=0，不抛错。"""
        resp = self.client.get('/api/v1/convergence-classes/', {'group': 'bogus'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['items'], [])
        self.assertEqual(data['data']['total'], 0)

    def test_source_filter(self):
        resp = self.client.get('/api/v1/convergence-classes', {'source': 'kmeans'})
        self.assertEqual(resp.status_code, 200)
        items = resp.json()['data']['items']
        self.assertTrue(items)
        self.assertTrue(all(it['source'] == 'kmeans' for it in items))
        # kmeans 类必有 avg_cos
        self.assertTrue(all(it['avg_cos'] is not None for it in items))
        self.assertEqual(resp.json()['data']['total'], 476)

    def test_avg_cos_null_for_non_kmeans(self):
        resp = self.client.get('/api/v1/convergence-classes', {'source': 'curated'})
        items = resp.json()['data']['items']
        self.assertTrue(items)
        self.assertTrue(all(it['avg_cos'] is None for it in items))

    def test_search_filter_case_insensitive(self):
        # 'rna' 大小写不敏感命中约 40 类（rg_c001 在其中但 size=1 排后），
        # 用 page_size=100 拉全量验证命中集合，而不受默认分页截断影响
        resp = self.client.get(
            '/api/v1/convergence-classes', {'search': 'rna', 'page_size': '100'},
        )
        self.assertEqual(resp.status_code, 200)
        items = resp.json()['data']['items']
        self.assertTrue(items)
        self.assertTrue(all('rna' in it['name'].lower() for it in items))
        # rg_c001 名为 RNA Analysis，应被命中
        self.assertIn('rg_c001', {it['class_id'] for it in items})

    def test_page_size_cap_and_fallback(self):
        # page_size 超上限(100) → 回退默认 20
        resp = self.client.get('/api/v1/convergence-classes', {'page_size': '1000'})
        self.assertEqual(len(resp.json()['data']['items']), 20)
        self.assertEqual(resp.json()['meta']['page_size'], 20)
        # page_size 非法 → 回退 20
        resp = self.client.get('/api/v1/convergence-classes', {'page_size': 'abc'})
        self.assertEqual(len(resp.json()['data']['items']), 20)
        self.assertEqual(resp.json()['meta']['page_size'], 20)
        # page<1 非法 → 回退 1
        resp = self.client.get('/api/v1/convergence-classes', {'page': '0'})
        self.assertEqual(resp.json()['meta']['page'], 1)

    def test_pagination_slice_no_overlap(self):
        resp1 = self.client.get('/api/v1/convergence-classes', {'page': '1', 'page_size': '100'})
        resp2 = self.client.get('/api/v1/convergence-classes', {'page': '2', 'page_size': '100'})
        ids1 = {it['class_id'] for it in resp1.json()['data']['items']}
        ids2 = {it['class_id'] for it in resp2.json()['data']['items']}
        self.assertEqual(len(ids1), 100)
        self.assertEqual(len(ids2), 100)
        self.assertFalse(ids1 & ids2)


class ConvergenceClassDetailAPITest(TestCase):
    """detail 端点：GET /api/v1/convergence-classes/<class_id>/。"""

    def setUp(self):
        self.client = APIClient()

    def test_detail_existing_class(self):
        resp = self.client.get('/api/v1/convergence-classes/rg_c001')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        d = data['data']
        self.assertEqual(d['class_id'], 'rg_c001')
        self.assertEqual(d['group'], 'rg')
        self.assertEqual(d['name'], 'RNA Analysis')
        self.assertIsInstance(d['members'], list)
        self.assertEqual(set(d.keys()),
                         {'class_id', 'group', 'name', 'source', 'quality',
                          'size', 'avg_cos', 'members'})
        self.assertIn('member_total', data['meta'])
        self.assertIn('page', data['meta'])
        self.assertIn('page_size', data['meta'])

    def test_detail_trailing_slash_url_reachable(self):
        """detail 带尾斜杠 URL 必须可达。"""
        resp = self.client.get('/api/v1/convergence-classes/rg_c001/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_detail_member_pagination_boundaries(self):
        """成员分页边界：page_size 超上限回退默认 20；page 超总页返回空 members。"""
        goals = [ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE) for _ in range(25)]
        sample = _sample_class(
            class_id='rg_paging', group='rg', entity_ids=[g.id for g in goals],
        )
        with _patch_class(sample):
            # page_size=1000 超上限 → 回退默认 20（首页返回 20 条成员）
            resp = self.client.get(
                f'/api/v1/convergence-classes/{sample["class_id"]}/',
                {'page_size': '1000'},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['meta']['page_size'], 20)
            self.assertEqual(resp.json()['meta']['member_total'], 25)
            self.assertEqual(len(resp.json()['data']['members']), 20)
            # page 超总页（25 条 / page_size=20 → 最多 2 页）→ members 为空
            resp = self.client.get(
                f'/api/v1/convergence-classes/{sample["class_id"]}/',
                {'page': '10', 'page_size': '20'},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['meta']['member_total'], 25)
            self.assertEqual(resp.json()['data']['members'], [])

    def test_members_n_count_rg(self):
        """造 1 个 RG + 2 个 Protocol 并关联，验证成员 n == 2。"""
        goal = ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE)
        p1 = ProtocolFactory()
        p2 = ProtocolFactory()
        goal.protocols.add(p1, p2)
        sample = _sample_class(class_id='rg_test', group='rg', entity_ids=[goal.id])
        with _patch_class(sample):
            resp = self.client.get(f'/api/v1/convergence-classes/{sample["class_id"]}')
        self.assertEqual(resp.status_code, 200)
        d = resp.json()['data']
        self.assertEqual(d['size'], 1)
        self.assertEqual(resp.json()['meta']['member_total'], 1)
        members = d['members']
        self.assertEqual(len(members), 1)
        m = members[0]
        self.assertEqual(m['id'], goal.id)
        self.assertEqual(m['name'], goal.name)
        self.assertEqual(m['slug'], goal.slug)
        self.assertEqual(m['origin'], goal.origin)
        self.assertEqual(m['n'], 2)

    def test_members_n_count_ap(self):
        """Application 口径：n == Count('research_goal_collections')（M2M 反向）。"""
        app = ApplicationFactory(status=Application.Status.ACTIVE)
        rg1 = ResearchGoalFactory()
        rg2 = ResearchGoalFactory()
        rg1.application_collection.add(app)
        rg2.application_collection.add(app)
        sample = _sample_class(class_id='ap_test', group='ap', entity_ids=[app.id])
        with _patch_class(sample):
            resp = self.client.get(f'/api/v1/convergence-classes/{sample["class_id"]}')
        self.assertEqual(resp.status_code, 200)
        members = resp.json()['data']['members']
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]['id'], app.id)
        self.assertEqual(members[0]['n'], 2)

    def test_detail_not_found(self):
        resp = self.client.get('/api/v1/convergence-classes/rg_does_not_exist')
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIsNone(data['data'])
        self.assertIn('error', data['meta'])
        self.assertIn('code', data['meta']['error'])
        self.assertIn('message', data['meta']['error'])


class ConvergenceClassVisibilityTest(TestCase):
    """成员实体可见性：匿名仅 ACTIVE；staff 全量；is_test_fixture 对所有身份不可见。"""

    def setUp(self):
        self.client = APIClient()

    def test_anonymous_only_active(self):
        active = ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE)
        draft = ResearchGoalFactory(status=ResearchGoal.Status.DRAFT)
        with _patch_class(_sample_class(entity_ids=[active.id, draft.id])):
            resp = self.client.get('/api/v1/convergence-classes/rg_vis')
        self.assertEqual(resp.status_code, 200)
        members = resp.json()['data']['members']
        # 成员顺序保持 entity_ids 顺序，草稿实体被过滤
        self.assertEqual([m['id'] for m in members], [active.id])
        self.assertEqual(resp.json()['meta']['member_total'], 1)

    def test_staff_sees_all_statuses(self):
        staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=staff)
        active = ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE)
        draft = ResearchGoalFactory(status=ResearchGoal.Status.DRAFT)
        with _patch_class(_sample_class(entity_ids=[active.id, draft.id])):
            resp = self.client.get('/api/v1/convergence-classes/rg_vis')
        self.assertEqual(resp.status_code, 200)
        members = resp.json()['data']['members']
        self.assertEqual({m['id'] for m in members}, {active.id, draft.id})
        self.assertEqual(resp.json()['meta']['member_total'], 2)

    def test_test_fixture_invisible_to_anonymous_and_staff(self):
        """is_test_fixture=True 对所有身份都不返回（含 staff + include_test_fixtures=1）。"""
        staff = UserFactory(is_staff=True)
        fixture = ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE, is_test_fixture=True)
        real = ResearchGoalFactory(status=ResearchGoal.Status.ACTIVE)
        with _patch_class(_sample_class(entity_ids=[fixture.id, real.id])):
            # 匿名
            anon = self.client.get('/api/v1/convergence-classes/rg_vis')
            self.assertEqual(
                [m['id'] for m in anon.json()['data']['members']], [real.id],
            )
            # staff + include_test_fixtures=1 也不可见
            self.client.force_authenticate(user=staff)
            staff_resp = self.client.get(
                '/api/v1/convergence-classes/rg_vis', {'include_test_fixtures': '1'},
            )
            self.assertEqual(
                [m['id'] for m in staff_resp.json()['data']['members']], [real.id],
            )


class ConvergenceClassFileMissingTest(TestCase):
    """文件缺失兜底：JSON 不存在时 list 返回空 data，不抛 500。"""

    def setUp(self):
        self.client = APIClient()

    def _patch_missing_json(self):
        missing = settings.BASE_DIR / 'data' / 'no_such_convergence_classes.json'
        return mock.patch.object(convergence_service, '_JSON_PATH', missing)

    def test_list_endpoint_empty_when_json_missing(self):
        with self._patch_missing_json():
            convergence_service._load_classes.cache_clear()
            try:
                resp = self.client.get('/api/v1/convergence-classes')
            finally:
                convergence_service._load_classes.cache_clear()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['items'], [])
        self.assertEqual(data['data']['total'], 0)

    def test_service_list_empty_when_json_missing(self):
        with self._patch_missing_json():
            convergence_service._load_classes.cache_clear()
            try:
                classes = convergence_service.list_classes()
            finally:
                convergence_service._load_classes.cache_clear()
        self.assertEqual(classes, [])


class ConvergenceClassCorruptJsonTest(TestCase):
    """JSON 结构损坏兜底：classes 非 list → 返回空列表，不抛 500（绝不抛异常契约）。"""

    def setUp(self):
        self.client = APIClient()

    def _patch_corrupt_content(self):
        # 让 json.load 读到 {"meta": {}, "classes": "oops"}（classes 被误写成字符串）
        return mock.patch.object(
            convergence_service.json, 'load',
            return_value={'meta': {}, 'classes': 'oops'},
        )

    def test_list_endpoint_empty_when_classes_not_list(self):
        with self._patch_corrupt_content():
            convergence_service._load_classes.cache_clear()
            try:
                resp = self.client.get('/api/v1/convergence-classes/')
            finally:
                convergence_service._load_classes.cache_clear()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['items'], [])
        self.assertEqual(data['data']['total'], 0)

    def test_detail_endpoint_404_not_500_when_classes_corrupt(self):
        """结构损坏时 detail 不抛 500：无任何类 → 404 信封。"""
        with self._patch_corrupt_content():
            convergence_service._load_classes.cache_clear()
            try:
                resp = self.client.get('/api/v1/convergence-classes/rg_c001/')
            finally:
                convergence_service._load_classes.cache_clear()
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.json()['success'])

    def test_service_list_empty_when_classes_corrupt(self):
        with self._patch_corrupt_content():
            convergence_service._load_classes.cache_clear()
            try:
                classes = convergence_service.list_classes()
            finally:
                convergence_service._load_classes.cache_clear()
        self.assertEqual(classes, [])
