"""
TDD Sprint 1.2: RelatedProducts
Tests for related products service and API endpoint.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Method
from apps.bridges.models import ProductMethod


class RelatedProductsAPITest(TestCase):
    """Test Related Products API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name="2'-Azido-dATP",
            catalog_no="SC8047",
            status='active',
            category_l1='nucleotides_nucleosides',
        )

    def test_related_returns_4_products(self):
        """Related API should return at most 4 products."""
        # Create some related products
        for i in range(6):
            ProductFactory(
                catalog_no=f'SC{i+1}',
                status='active',
                category_l1='nucleotides_nucleosides',
            )

        response = self.client.get(f'/api/v1/products/{self.product.id}/related/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('data', data)
        related = data['data']
        self.assertIsInstance(related, list)
        self.assertLessEqual(len(related), 4)

    def test_related_excludes_self(self):
        """Related products should not include the product itself."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/related/')
        data = response.json()
        related = data['data']

        related_ids = [p['id'] for p in related]
        self.assertNotIn(self.product.id, related_ids)

    def test_related_returns_empty_for_single_product(self):
        """Related API should return empty list when no other products exist."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/related/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        related = data['data']
        self.assertEqual(len(related), 0)

    def test_related_prioritizes_same_method(self):
        """Products sharing methods should be prioritized."""
        # Use an existing method from the database
        method = Method.objects.first()
        if not method:
            self.skipTest('No methods in database')

        # Create a product with the same method
        related_product = ProductFactory(
            catalog_no='SC_RELATED',
            status='active',
            category_l1='nucleotides_nucleosides',
        )
        ProductMethod.objects.create(
            product=self.product,
            method=method,
            role='reagent',
        )
        ProductMethod.objects.create(
            product=related_product,
            method=method,
            role='reagent',
        )

        # Create a product without the method (same category only)
        category_product = ProductFactory(
            catalog_no='SC_CATEGORY',
            status='active',
            category_l1='nucleotides_nucleosides',
        )

        response = self.client.get(f'/api/v1/products/{self.product.id}/related/')
        data = response.json()
        related = data['data']

        # The method-sharing product should be first
        self.assertGreaterEqual(len(related), 1)
        self.assertEqual(related[0]['catalog_no'], 'SC_RELATED')

    def test_related_falls_back_to_category(self):
        """When no method match, products in same category should be returned."""
        # Create products in same category
        for i in range(3):
            ProductFactory(
                catalog_no=f'SC_CAT{i}',
                status='active',
                category_l1='nucleotides_nucleosides',
            )

        # Create product in different category
        ProductFactory(
            catalog_no='SC_OTHER',
            status='active',
            category_l1='click_chemistry',
        )

        response = self.client.get(f'/api/v1/products/{self.product.id}/related/')
        data = response.json()
        related = data['data']

        # Should return same-category products
        self.assertGreaterEqual(len(related), 1)
        catalog_nos = [p['catalog_no'] for p in related]
        self.assertIn('SC_CAT0', catalog_nos)

    def test_related_404_for_inactive_product(self):
        """Related API should return 404 for inactive products."""
        self.product.status = 'draft'
        self.product.save()

        response = self.client.get(f'/api/v1/products/{self.product.id}/related/')
        self.assertEqual(response.status_code, 404)
