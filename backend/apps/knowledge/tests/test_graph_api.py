"""T7-01 ~ T7-20, T8-01 ~ T8-03: Graph API tests"""
from django.test import TestCase
from rest_framework.test import APIClient
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory, ReferenceFactory,
)
from apps.commerce.tests.factories import ProductFactory
from apps.bridges.tests.factories import (
    ProductMethodFactory, MethodProtocolFactory, ProductReferenceFactory,
)


class GraphAPITest(TestCase):
    """T7-01 ~ T7-20"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(status='active')
        self.method = MethodFactory(status='active')
        ProductMethodFactory(product=self.product, method=self.method)

    def test_returns_200(self):
        """T7-01"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        self.assertEqual(resp.status_code, 200)

    def test_has_nodes_key(self):
        """T7-02"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        data = resp.json()
        self.assertIsInstance(data['data']['nodes'], list)

    def test_has_edges_key(self):
        """T7-03"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        data = resp.json()
        self.assertIsInstance(data['data']['edges'], list)

    def test_envelope_format(self):
        """T7-04"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_includes_product_node(self):
        """T7-05"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        nodes = resp.json()['data']['nodes']
        types = [n['type'] for n in nodes]
        self.assertIn('product', types)

    def test_includes_method_nodes(self):
        """T7-06"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        nodes = resp.json()['data']['nodes']
        types = [n['type'] for n in nodes]
        self.assertIn('method', types)

    def test_includes_application_nodes(self):
        """T7-07: depth=3 should reach application"""
        app = self.method.application
        app.status = 'active'
        app.save()
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id, 'depth': 3})
        nodes = resp.json()['data']['nodes']
        types = [n['type'] for n in nodes]
        self.assertIn('application', types)

    def test_edge_product_to_method(self):
        """T7-08"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        edges = resp.json()['data']['edges']
        source_targets = [(e['source'], e['target']) for e in edges]
        product_node = f'product_{self.product.id}'
        method_node = f'method_{self.method.id}'
        self.assertIn((product_node, method_node), source_targets)

    def test_edge_method_to_application(self):
        """T7-09"""
        app = self.method.application
        app.status = 'active'
        app.save()
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id, 'depth': 3})
        edges = resp.json()['data']['edges']
        rels = [e['relationship'] for e in edges]
        self.assertIn('belongs_to', rels)

    def test_node_has_required_fields(self):
        """T7-10"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        node = resp.json()['data']['nodes'][0]
        self.assertIn('id', node)
        self.assertIn('type', node)
        self.assertIn('label', node)

    def test_edge_has_required_fields(self):
        """T7-11"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        edges = resp.json()['data']['edges']
        if edges:
            edge = edges[0]
            self.assertIn('id', edge)
            self.assertIn('source', edge)
            self.assertIn('target', edge)
            self.assertIn('relationship', edge)

    def test_max_nodes_limit(self):
        """T7-12"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id, 'max_nodes': 50})
        nodes = resp.json()['data']['nodes']
        self.assertLessEqual(len(nodes), 50)

    def test_max_edges_limit(self):
        """T7-13"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id, 'max_edges': 100})
        edges = resp.json()['data']['edges']
        self.assertLessEqual(len(edges), 100)

    def test_depth_1_returns_only_direct(self):
        """T7-14: depth=1 → only direct neighbors"""
        app = self.method.application
        app.status = 'active'
        app.save()
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id, 'depth': 1})
        nodes = resp.json()['data']['nodes']
        types = [n['type'] for n in nodes]
        # depth=1: product + method only (not application)
        self.assertIn('product', types)
        self.assertIn('method', types)
        self.assertNotIn('application', types)

    def test_default_depth_is_3(self):
        """T7-15"""
        app = self.method.application
        app.status = 'active'
        app.save()
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': self.product.id})
        nodes = resp.json()['data']['nodes']
        types = [n['type'] for n in nodes]
        # Default depth=3 should reach application
        self.assertIn('application', types)

    def test_from_application(self):
        """T7-16"""
        app = self.method.application
        app.status = 'active'
        app.save()
        resp = self.client.get('/api/v1/graph', {'type': 'application', 'id': app.id})
        self.assertEqual(resp.status_code, 200)
        nodes = resp.json()['data']['nodes']
        self.assertTrue(len(nodes) >= 1)

    def test_from_method(self):
        """T7-17"""
        resp = self.client.get('/api/v1/graph', {'type': 'method', 'id': self.method.id})
        self.assertEqual(resp.status_code, 200)
        nodes = resp.json()['data']['nodes']
        self.assertTrue(len(nodes) >= 1)

    def test_missing_params_returns_400(self):
        """T7-18"""
        resp = self.client.get('/api/v1/graph', {'type': 'product'})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_type_returns_400(self):
        """T7-19"""
        resp = self.client.get('/api/v1/graph', {'type': 'invalid', 'id': 1})
        self.assertEqual(resp.status_code, 400)

    def test_nonexistent_id_returns_404(self):
        """T7-20"""
        resp = self.client.get('/api/v1/graph', {'type': 'product', 'id': 99999})
        self.assertEqual(resp.status_code, 404)

class HomepageGraphPreviewRemovedTest(TestCase):
    """T8-01~03 的契约反转（2026-10-30）。

    用户明确要求「图谱部分不展示，没有作用，而且很杂乱」，首页不再返回
    graph_preview。实测该字段的唯一消费方是 KnowledgeGraphPreview.vue，
    而那条前端链（Preview → KnowledgeGraph → useGraph → api/graph.js）
    在接入首页之前**全仓零引用**；每次首页请求还要多跑一次 depth=2 的 BFS
    （build_graph），纯浪费。

    这里锁的是「首页响应里不再出现该字段」。
    `/api/v1/graph` 端点本身**保留**（GraphAPITest 仍覆盖），删的只是首页预览。
    """

    def setUp(self):
        self.client = APIClient()

    def test_homepage_no_graph_preview(self):
        ApplicationFactory(status='active', display_priority=10)
        data = self.client.get('/api/v1/site/home').json()['data']
        self.assertNotIn('graph_preview', data)

    def test_graph_endpoint_still_available(self):
        """删的只是首页预览，/api/v1/graph 端点必须仍然可用。"""
        app = ApplicationFactory(status='active', display_priority=10)
        resp = self.client.get(f'/api/v1/graph?type=application&id={app.id}')
        self.assertEqual(resp.status_code, 200)
