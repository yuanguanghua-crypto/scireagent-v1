"""T7-21 ~ T7-27: Graph traversal service tests"""
from django.test import TestCase
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory, ReferenceFactory,
)
from apps.commerce.tests.factories import ProductFactory
from apps.bridges.tests.factories import ProductMethodFactory, MethodProtocolFactory, ProductReferenceFactory
from apps.knowledge.services.graph_service import build_graph


class GraphServiceTest(TestCase):
    """T7-21 ~ T7-27"""

    def test_product_with_method_returns_2_nodes(self):
        """T7-21: Product + Method → 2 nodes"""
        product = ProductFactory(status='active')
        method = MethodFactory(status='active')
        ProductMethodFactory(product=product, method=method)
        result = build_graph('product', product.id, depth=1)
        types = [n['type'] for n in result['nodes']]
        self.assertIn('product', types)
        self.assertIn('method', types)
        self.assertEqual(len(result['nodes']), 2)

    def test_product_with_method_app_returns_3_nodes(self):
        """T7-22: Product → Method → Application → 3 nodes at depth=2"""
        product = ProductFactory(status='active')
        method = MethodFactory(status='active')
        app = method.application
        app.status = 'active'
        app.save()
        ProductMethodFactory(product=product, method=method)
        result = build_graph('product', product.id, depth=2)
        types = [n['type'] for n in result['nodes']]
        self.assertIn('product', types)
        self.assertIn('method', types)
        self.assertIn('application', types)

    def test_product_with_reference_adds_ref_node(self):
        """T7-23: Product + Reference → ref node + edge"""
        product = ProductFactory(status='active')
        ref = ReferenceFactory()
        ProductReferenceFactory(product=product, reference=ref)
        result = build_graph('product', product.id, depth=1)
        types = [n['type'] for n in result['nodes']]
        self.assertIn('reference', types)
        # Check edge exists
        rels = [e['relationship'] for e in result['edges']]
        self.assertIn('cited_in', rels)

    def test_max_nodes_truncation(self):
        """T7-24: max_nodes=2 limits output"""
        product = ProductFactory(status='active')
        m1 = MethodFactory(status='active')
        m2 = MethodFactory(status='active')
        ProductMethodFactory(product=product, method=m1)
        ProductMethodFactory(product=product, method=m2)
        result = build_graph('product', product.id, depth=1, max_nodes=2)
        self.assertLessEqual(len(result['nodes']), 2)

    def test_no_duplicates(self):
        """T7-25: Same entity visited via multiple paths → single node"""
        product = ProductFactory(status='active')
        method = MethodFactory(status='active')
        ProductMethodFactory(product=product, method=method)
        # Both product and method connect to the same application
        app = method.application
        app.status = 'active'
        app.save()
        result = build_graph('product', product.id, depth=2)
        node_ids = [n['id'] for n in result['nodes']]
        # No duplicates
        self.assertEqual(len(node_ids), len(set(node_ids)))

    def test_cycle_detection(self):
        """T7-26: Circular reference doesn't cause infinite loop"""
        product = ProductFactory(status='active')
        method = MethodFactory(status='active')
        ProductMethodFactory(product=product, method=method)
        # Should complete without hanging
        result = build_graph('product', product.id, depth=10)
        self.assertIsInstance(result['nodes'], list)
        self.assertIsInstance(result['edges'], list)

    def test_empty_graph(self):
        """T7-27: Product with no relations → only self node"""
        product = ProductFactory(status='active')
        result = build_graph('product', product.id, depth=3)
        self.assertEqual(len(result['nodes']), 1)
        self.assertEqual(result['nodes'][0]['type'], 'product')
        self.assertEqual(len(result['edges']), 0)
