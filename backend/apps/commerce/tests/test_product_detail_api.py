"""
TDD Sprint 1.3: Product Detail API Complete
Tests for product detail API endpoint with all required sections.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory


class ProductDetailAPITest(TestCase):
    """Test Product Detail API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name="2'-Azido-dATP",
            catalog_no="SC8047",
            cas="73449-06-6",
            storage="-20°C",
            purity="≥ 95% (HPLC)",
            concentration="100 mM",
            formula="C10H15N8O12P3",
            molecular_weight=532.2,
            overview="A modified dATP for click chemistry labeling.",
            smiles="C1=NC(=C2C(=N1)N(C=N2)[C@H]3...",
            status='active',
            category_l1='nucleotides_nucleosides',
        )

    def test_product_detail_returns_200(self):
        """Product detail API should return 200 for active products."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        self.assertEqual(response.status_code, 200)

    def test_product_detail_includes_product(self):
        """Product detail should include product information."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('product', data['data'])
        product = data['data']['product']
        self.assertEqual(product['name'], "2'-Azido-dATP")
        self.assertEqual(product['catalog_no'], 'SC8047')

    def test_product_detail_includes_applications(self):
        """Product detail should include related applications."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('applications', data['data'])
        self.assertIsInstance(data['data']['applications'], list)

    def test_product_detail_includes_protocols(self):
        """Product detail should include related protocols."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('protocols', data['data'])
        self.assertIsInstance(data['data']['protocols'], list)

    def test_product_detail_includes_faq(self):
        """Product detail should include FAQ questions."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('faq', data['data'])
        faq = data['data']['faq']
        self.assertIsInstance(faq, list)
        self.assertGreaterEqual(len(faq), 4)

    def test_product_detail_includes_related_products(self):
        """Product detail should include related products."""
        # Create some related products
        for i in range(3):
            ProductFactory(
                catalog_no=f'SC{i+1}',
                status='active',
                category_l1='nucleotides_nucleosides',
            )

        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('related_products', data['data'])
        related = data['data']['related_products']
        self.assertIsInstance(related, list)
        self.assertLessEqual(len(related), 4)

    def test_product_detail_includes_references(self):
        """Product detail should include references."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('references', data['data'])
        self.assertIsInstance(data['data']['references'], list)

    def test_product_detail_includes_compatibility(self):
        """Product detail should include compatibility information."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('compatibility', data['data'])

    def test_product_detail_404_for_inactive(self):
        """Product detail should return 404 for inactive products."""
        self.product.status = 'draft'
        self.product.save()

        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        self.assertEqual(response.status_code, 404)

    def test_product_detail_404_for_nonexistent(self):
        """Product detail should return 404 for nonexistent products."""
        response = self.client.get('/api/v1/products/99999/detail/')
        self.assertEqual(response.status_code, 404)

    def test_product_detail_faq_has_questions_and_answers(self):
        """FAQ items should have question and answer fields."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        faq = data['data']['faq']
        for item in faq:
            self.assertIn('question', item)
            self.assertIn('answer', item)
            self.assertTrue(len(item['question']) > 0)
            self.assertTrue(len(item['answer']) > 0)

    def test_product_detail_related_excludes_self(self):
        """Related products should not include the product itself."""
        # Create some related products
        for i in range(3):
            ProductFactory(
                catalog_no=f'SC{i+1}',
                status='active',
                category_l1='nucleotides_nucleosides',
            )

        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        related = data['data']['related_products']
        related_ids = [p['id'] for p in related]
        self.assertNotIn(self.product.id, related_ids)
