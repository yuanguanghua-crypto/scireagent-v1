"""P0 — status 可见性统一收口。

契约（用户拍板 2026-09-07，D1=甲/AP 详情 draft 完全隐藏，D2=graph 一律公开口径）：

1. 公开读（匿名/非 staff）在任何读取面都不可见 draft：
   search / search-suggest / search-grouped / protocols 列表与详情 /
   AP 详情 methods / graph 起点与邻居。
2. staff 在 API 读面（list/retrieve/search）看全量（含 draft），便于后台管理。
3. 公开态映射：ResearchGoal/Application/Method → active；Protocol → published；
   Product → active/published（且非 archived）；Reference 无 status 字段不过滤。
4. graph 端点一律公开口径（即使 staff 也不放行 draft，图谱是公开展示组件）。
5. 真实（公开态）实体零回归。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.bridges.tests.factories import MethodProtocolFactory, ProductMethodFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    MethodFactory,
    ProtocolFactory,
)

ACTIVE = 'active'
PUBLISHED = 'published'
DRAFT = 'draft'


class PublicVisibilitySearchTest(TestCase):
    """契约 1/2：search / suggest / grouped 三个端点的 draft 隔离。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)

        # Method：draft（默认）vs active
        self.draft_method = MethodFactory(name='zzz draft method')
        self.active_method = MethodFactory(name='zzz real method', status=ACTIVE)
        # Application：draft vs active
        self.draft_app = ApplicationFactory(name='zzz draft app')
        self.active_app = ApplicationFactory(name='zzz real app', status=ACTIVE)
        # Protocol：draft（默认）vs published
        self.draft_protocol = ProtocolFactory(name='zzz draft protocol')
        self.published_protocol = ProtocolFactory(name='zzz real protocol', status=PUBLISHED)
        # Product：draft vs active
        self.draft_product = ProductFactory(name='zzz draft product', status=DRAFT)
        self.active_product = ProductFactory(name='zzz real product', status=ACTIVE)

    # ---------- /api/v1/search ----------
    def test_search_anonymous_hides_all_drafts(self):
        resp = self.client.get('/api/v1/search?q=zzz')
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()['data']
        names = [r.get('name', '') for r in rows]
        self.assertNotIn(self.draft_method.name, names)
        self.assertNotIn(self.draft_app.name, names)
        self.assertNotIn(self.draft_protocol.name, names)
        self.assertNotIn(self.draft_product.name, names)
        # 公开态实体仍在
        self.assertIn(self.active_method.name, names)
        self.assertIn(self.active_app.name, names)
        self.assertIn(self.published_protocol.name, names)
        self.assertIn(self.active_product.name, names)

    def test_search_staff_sees_drafts(self):
        self.client.force_authenticate(user=self.staff)
        rows = self.client.get('/api/v1/search?q=zzz').json()['data']
        names = [r.get('name', '') for r in rows]
        self.assertIn(self.draft_method.name, names)
        self.assertIn(self.draft_app.name, names)
        self.assertIn(self.draft_protocol.name, names)
        self.assertIn(self.draft_product.name, names)

    # ---------- /api/v1/search/suggest ----------
    def test_suggest_anonymous_hides_drafts(self):
        resp = self.client.get('/api/v1/search/suggest?q=zzz')
        texts = [r.get('text', '') for r in resp.json()['data']]
        self.assertNotIn(self.draft_method.name, texts)
        self.assertNotIn(self.draft_product.name, texts)
        self.assertIn(self.active_method.name, texts)
        self.assertIn(self.active_product.name, texts)

    def test_suggest_staff_sees_drafts(self):
        self.client.force_authenticate(user=self.staff)
        texts = [r.get('text', '') for r in
                 self.client.get('/api/v1/search/suggest?q=zzz').json()['data']]
        self.assertIn(self.draft_method.name, texts)
        self.assertIn(self.draft_product.name, texts)

    # ---------- /api/v1/search/grouped ----------
    def test_grouped_anonymous_hides_drafts(self):
        data = self.client.get('/api/v1/search/grouped?q=zzz').json()['data']
        self.assertNotIn(self.draft_app.name, [r['name'] for r in data['applications']])
        self.assertNotIn(self.draft_method.name, [r['name'] for r in data['methods']])
        self.assertNotIn(self.draft_protocol.name, [r['name'] for r in data['protocols']])
        self.assertNotIn(self.draft_product.name, [r['name'] for r in data['products']])
        self.assertIn(self.active_app.name, [r['name'] for r in data['applications']])
        self.assertIn(self.published_protocol.name, [r['name'] for r in data['protocols']])
        self.assertIn(self.active_product.name, [r['name'] for r in data['products']])

    def test_grouped_staff_sees_drafts(self):
        self.client.force_authenticate(user=self.staff)
        data = self.client.get('/api/v1/search/grouped?q=zzz').json()['data']
        self.assertIn(self.draft_method.name, [r['name'] for r in data['methods']])
        self.assertIn(self.draft_protocol.name, [r['name'] for r in data['protocols']])


class PublicVisibilityProtocolViewSetTest(TestCase):
    """契约 1/2：ProtocolViewSet 列表与详情（published 口径）。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.draft = ProtocolFactory(name='D Proto zzz')
        self.published = ProtocolFactory(name='P Proto zzz', status=PUBLISHED)
        self.superseded = ProtocolFactory(name='S Proto zzz', status='superseded')

    def test_list_anonymous_only_published(self):
        names = [r['name'] for r in self.client.get('/api/v1/protocols/').json()['data']]
        self.assertIn(self.published.name, names)
        self.assertNotIn(self.draft.name, names)
        self.assertNotIn(self.superseded.name, names)

    def test_list_staff_sees_all(self):
        self.client.force_authenticate(user=self.staff)
        names = [r['name'] for r in self.client.get('/api/v1/protocols/').json()['data']]
        self.assertIn(self.published.name, names)
        self.assertIn(self.draft.name, names)
        self.assertIn(self.superseded.name, names)

    def test_retrieve_draft_404_anonymous(self):
        resp = self.client.get(f'/api/v1/protocols/{self.draft.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_retrieve_published_200_anonymous(self):
        resp = self.client.get(f'/api/v1/protocols/{self.published.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_draft_200_staff(self):
        self.client.force_authenticate(user=self.staff)
        resp = self.client.get(f'/api/v1/protocols/{self.draft.id}/')
        self.assertEqual(resp.status_code, 200)


class PublicVisibilityApplicationDetailTest(TestCase):
    """契约 1/D1-甲：AP 详情 methods 区只展示 active（draft 完全隐藏，对 staff 亦然）。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.app = ApplicationFactory(name='Detail App zzz', status=ACTIVE)
        self.active_method = MethodFactory(
            name='Active M zzz', status=ACTIVE, application=self.app)
        self.draft_method = MethodFactory(
            name='Draft M zzz', status=DRAFT, application=self.app)

    def _method_names(self):
        data = self.client.get(f'/api/v1/applications/{self.app.id}/').json()['data']
        return [m['name'] for m in data['methods']]

    def test_anonymous_methods_exclude_draft(self):
        names = self._method_names()
        self.assertIn(self.active_method.name, names)
        self.assertNotIn(self.draft_method.name, names)

    def test_staff_methods_also_exclude_draft(self):
        """D1-甲：完全隐藏（staff 查看 draft 走 /methods/ 端点，不在展示面）。"""
        self.client.force_authenticate(user=self.staff)
        names = self._method_names()
        self.assertIn(self.active_method.name, names)
        self.assertNotIn(self.draft_method.name, names)


class PublicVisibilityGraphTest(TestCase):
    """契约 1/4：graph 起点与邻居一律公开口径（staff 亦不放行）。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)

        self.draft_method = MethodFactory(name='G draft method', status=DRAFT)
        self.active_method = MethodFactory(name='G active method', status=ACTIVE)
        self.published_protocol = ProtocolFactory(name='G pub protocol', status=PUBLISHED)
        self.draft_protocol = ProtocolFactory(name='G draft protocol', status=DRAFT)
        self.active_app = ApplicationFactory(name='G active app', status=ACTIVE)
        self.active_product = ProductFactory(name='G active product', status=ACTIVE)
        self.draft_product = ProductFactory(name='G draft product', status=DRAFT)

        # 桥：published 协议 ↔ draft 方法（邻居过滤点）
        MethodProtocolFactory(method=self.draft_method, protocol=self.published_protocol)
        # active 产品 ↔ draft 方法（邻居过滤点）
        ProductMethodFactory(product=self.active_product, method=self.draft_method)
        # active AP ↔ draft 方法（既有过滤点的回归保护）
        self.draft_method.application = self.active_app
        self.draft_method.save()
        self.active_method.application = self.active_app
        self.active_method.save()

    def _node_ids(self, resp):
        self.assertEqual(resp.status_code, 200)
        return set(n['id'] for n in resp.json()['data']['nodes'])

    def test_draft_method_start_404(self):
        resp = self.client.get(f'/api/v1/graph?type=method&id={self.draft_method.id}')
        self.assertEqual(resp.status_code, 404)

    def test_draft_protocol_start_404(self):
        resp = self.client.get(f'/api/v1/graph?type=protocol&id={self.draft_protocol.id}')
        self.assertEqual(resp.status_code, 404)

    def test_draft_product_start_404(self):
        resp = self.client.get(f'/api/v1/graph?type=product&id={self.draft_product.id}')
        self.assertEqual(resp.status_code, 404)

    def test_staff_also_blocked_on_graph_drafts(self):
        """契约 4：D2 一律公开口径。"""
        self.client.force_authenticate(user=self.staff)
        for t, obj in (('method', self.draft_method), ('protocol', self.draft_protocol)):
            resp = self.client.get(f'/api/v1/graph?type={t}&id={obj.id}')
            self.assertEqual(resp.status_code, 404)

    def test_published_protocol_graph_hides_draft_method_neighbor(self):
        ids = self._node_ids(
            self.client.get(f'/api/v1/graph?type=protocol&id={self.published_protocol.id}'))
        self.assertIn(f'protocol_{self.published_protocol.id}', ids)
        self.assertNotIn(f'method_{self.draft_method.id}', ids)

    def test_active_product_graph_hides_draft_method_neighbor(self):
        ids = self._node_ids(
            self.client.get(f'/api/v1/graph?type=product&id={self.active_product.id}'))
        self.assertIn(f'product_{self.active_product.id}', ids)
        self.assertNotIn(f'method_{self.draft_method.id}', ids)

    def test_active_application_graph_keeps_active_method_regression(self):
        """既有过滤点（application→method active）零回归。"""
        ids = self._node_ids(
            self.client.get(f'/api/v1/graph?type=application&id={self.active_app.id}'))
        self.assertIn(f'method_{self.active_method.id}', ids)
        self.assertNotIn(f'method_{self.draft_method.id}', ids)
