"""
TDD Sprint 3.1: Product Graph API
Tests for product subgraph API endpoint.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.tests.factories import ProductFactory


class ProductGraphAPITest(TestCase):
    """Test Product Graph API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name="2'-Azido-dATP",
            catalog_no="SC8047",
            status='active',
        )

    def test_graph_product_returns_nodes(self):
        """Graph API should return nodes for a product."""
        response = self.client.get(f'/api/v1/graph?type=product&id={self.product.id}')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('nodes', data['data'])
        self.assertIsInstance(data['data']['nodes'], list)

    def test_graph_product_returns_edges(self):
        """Graph API should return edges for a product."""
        response = self.client.get(f'/api/v1/graph?type=product&id={self.product.id}')
        data = response.json()

        self.assertIn('edges', data['data'])
        self.assertIsInstance(data['data']['edges'], list)

    def test_graph_product_respects_depth(self):
        """Graph API should respect depth parameter."""
        response = self.client.get(f'/api/v1/graph?type=product&id={self.product.id}&depth=1')
        data = response.json()

        self.assertTrue(data['success'])
        # With depth=1, should have fewer nodes than default
        nodes_depth1 = len(data['data']['nodes'])

        response2 = self.client.get(f'/api/v1/graph?type=product&id={self.product.id}&depth=3')
        data2 = response2.json()

        nodes_depth3 = len(data2['data']['nodes'])
        self.assertGreaterEqual(nodes_depth3, nodes_depth1)

    def test_graph_product_limits_nodes(self):
        """Graph API should limit number of nodes."""
        response = self.client.get(f'/api/v1/graph?type=product&id={self.product.id}&max_nodes=5')
        data = response.json()

        self.assertTrue(data['success'])
        self.assertLessEqual(len(data['data']['nodes']), 5)

    def test_graph_product_node_structure(self):
        """Graph nodes should have id, type, label fields."""
        response = self.client.get(f'/api/v1/graph?type=product&id={self.product.id}')
        data = response.json()

        if data['data']['nodes']:
            node = data['data']['nodes'][0]
            self.assertIn('id', node)
            self.assertIn('type', node)
            self.assertIn('label', node)

    def test_graph_product_edge_structure(self):
        """Graph edges should have source, target fields."""
        response = self.client.get(f'/api/v1/graph?type=product&id={self.product.id}')
        data = response.json()

        if data['data']['edges']:
            edge = data['data']['edges'][0]
            self.assertIn('source', edge)
            self.assertIn('target', edge)

    def test_graph_404_for_nonexistent(self):
        """Graph API should handle nonexistent entities."""
        response = self.client.get('/api/v1/graph?type=product&id=99999')
        # Should return 200 with empty graph or 404
        self.assertIn(response.status_code, [200, 404])

    def test_graph_requires_type_and_id(self):
        """Graph API should return 400 when type and id are missing."""
        response = self.client.get('/api/v1/graph')
        self.assertEqual(response.status_code, 400)
