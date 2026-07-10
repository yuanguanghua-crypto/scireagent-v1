"""
TDD Sprint 1.1: FAQ Dynamic Generation
Tests for FAQ generation service and API endpoint.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.services.faq_generator import generate_faq, generate_faq_json_ld


class FAQAPITest(TestCase):
    """Test FAQ API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name="2'-Azido-dATP",
            catalog_no="SC8047",
            cas="73449-06-6",
            storage="-20°C",
            purity="≥ 95% (HPLC)",
            overview="A modified dATP for click chemistry labeling.",
            status='active',
        )

    def test_faq_api_returns_4_questions(self):
        """FAQ API should return at least 4 questions for a product."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/faq/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('data', data)
        faqs = data['data']
        self.assertIsInstance(faqs, list)
        self.assertGreaterEqual(len(faqs), 4)

    def test_faq_has_question_and_answer(self):
        """Each FAQ item should have 'question' and 'answer' fields."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/faq/')
        data = response.json()
        faqs = data['data']

        for faq in faqs:
            self.assertIn('question', faq)
            self.assertIn('answer', faq)
            self.assertTrue(len(faq['question']) > 0)
            self.assertTrue(len(faq['answer']) > 0)

    def test_faq_includes_storage_question(self):
        """FAQ should include a storage question when storage is available."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/faq/')
        data = response.json()
        faqs = data['data']

        storage_faqs = [f for f in faqs if 'stored' in f['question'].lower() or 'storage' in f['question'].lower()]
        self.assertGreaterEqual(len(storage_faqs), 1)
        self.assertIn('-20°C', storage_faqs[0]['answer'])

    def test_faq_includes_purity_question(self):
        """FAQ should include a purity question when purity is available."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/faq/')
        data = response.json()
        faqs = data['data']

        purity_faqs = [f for f in faqs if 'purity' in f['question'].lower()]
        self.assertGreaterEqual(len(purity_faqs), 1)
        self.assertIn('95%', purity_faqs[0]['answer'])

    def test_faq_includes_formula_question(self):
        """FAQ should include a formula question when formula is available."""
        self.product.formula = 'C10H15N8O12P3'
        self.product.save()

        response = self.client.get(f'/api/v1/products/{self.product.id}/faq/')
        data = response.json()
        faqs = data['data']

        formula_faqs = [f for f in faqs if 'formula' in f['question'].lower()]
        self.assertGreaterEqual(len(formula_faqs), 1)
        self.assertIn('C10H15N8O12P3', formula_faqs[0]['answer'])

    def test_faq_json_ld_format(self):
        """FAQ API should return valid JSON-LD when requested."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/faq/?json_ld=true')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('json_ld', data)

        json_ld = data['json_ld']
        self.assertEqual(json_ld['@context'], 'https://schema.org')
        self.assertEqual(json_ld['@type'], 'FAQPage')
        self.assertIn('mainEntity', json_ld)
        self.assertGreaterEqual(len(json_ld['mainEntity']), 4)

    def test_faq_404_for_inactive_product(self):
        """FAQ API should return 404 for inactive products."""
        self.product.status = 'draft'
        self.product.save()

        response = self.client.get(f'/api/v1/products/{self.product.id}/faq/')
        self.assertEqual(response.status_code, 404)

    def test_faq_404_for_nonexistent_product(self):
        """FAQ API should return 404 for nonexistent products."""
        response = self.client.get('/api/v1/products/99999/faq/')
        self.assertEqual(response.status_code, 404)


class FAQGeneratorTest(TestCase):
    """Test FAQ generator service directly."""

    def setUp(self):
        self.product = ProductFactory(
            name="Cy3-dUTP",
            catalog_no="SC8018",
            cas="123456-78-9",
            storage="-20°C, protect from light",
            purity="≥ 98% (HPLC)",
            concentration="1 mM",
            formula="C35H42N3O14P3S",
            overview="A fluorescent dUTP analog for RNA labeling.",
            status='active',
        )

    def test_generate_faq_returns_list(self):
        """generate_faq should return a list of dicts."""
        faqs = generate_faq(self.product)
        self.assertIsInstance(faqs, list)
        self.assertGreaterEqual(len(faqs), 4)

    def test_generate_faq_json_ld_structure(self):
        """generate_faq_json_ld should return valid JSON-LD structure."""
        faqs = generate_faq(self.product)
        json_ld = generate_faq_json_ld(self.product, faqs)

        self.assertEqual(json_ld['@context'], 'https://schema.org')
        self.assertEqual(json_ld['@type'], 'FAQPage')
        self.assertIn('mainEntity', json_ld)

        for entity in json_ld['mainEntity']:
            self.assertEqual(entity['@type'], 'Question')
            self.assertIn('name', entity)
            self.assertIn('acceptedAnswer', entity)
            self.assertEqual(entity['acceptedAnswer']['@type'], 'Answer')
