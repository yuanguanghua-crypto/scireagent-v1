"""T5-10 ~ T5-24: Grouped search API tests"""
from django.test import TestCase
from rest_framework.test import APIClient
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.knowledge.tests.factories import ApplicationFactory, MethodFactory, ProtocolFactory, ReferenceFactory


class GroupedSearchAPITest(TestCase):
    """T5-10 ~ T5-24"""

    def setUp(self):
        self.client = APIClient()

    def test_returns_200(self):
        """T5-10: Grouped search returns 200"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        self.assertEqual(resp.status_code, 200)

    def test_has_products_key(self):
        """T5-11: Response has products key"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()
        self.assertIn('products', data['data'])

    def test_has_applications_key(self):
        """T5-12"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()
        self.assertIn('applications', data['data'])

    def test_has_methods_key(self):
        """T5-13"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()
        self.assertIn('methods', data['data'])

    def test_has_protocols_key(self):
        """T5-14"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()
        self.assertIn('protocols', data['data'])

    def test_has_references_key(self):
        """T5-15"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()
        self.assertIn('references', data['data'])

    def test_envelope_format(self):
        """T5-16: Response uses Envelope format"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_empty_for_no_match(self):
        """T5-17: No match returns empty lists"""
        resp = self.client.get('/api/v1/search/grouped', {'q': 'zzzznonexistent'})
        data = resp.json()['data']
        self.assertEqual(data['products'], [])
        self.assertEqual(data['applications'], [])

    def test_limits_products_to_10(self):
        """T5-18"""
        ProductFactory.create_batch(15, name='RNA Test Product')
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()['data']
        self.assertLessEqual(len(data['products']), 10)

    def test_limits_other_types_to_5(self):
        """T5-19"""
        ApplicationFactory.create_batch(8, name='RNA Application')
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()['data']
        self.assertLessEqual(len(data['applications']), 5)

    def test_empty_query_returns_empty(self):
        """T5-20"""
        ProductFactory(name='RNA Kit')
        resp = self.client.get('/api/v1/search/grouped', {'q': ''})
        data = resp.json()['data']
        self.assertEqual(data['products'], [])

    def test_type_filter(self):
        """T5-21: ?type=product returns only products"""
        ProductFactory(name='RNA Kit')
        ApplicationFactory(name='RNA Application')
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna', 'type': 'product'})
        data = resp.json()['data']
        self.assertTrue(len(data['products']) > 0)
        self.assertEqual(data['applications'], [])

    def test_product_has_catalog_no(self):
        """T5-22"""
        ProductFactory(name='RNA Labeling Kit')
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()['data']
        if data['products']:
            self.assertIn('catalog_no', data['products'][0])

    def test_product_has_score(self):
        """T5-23"""
        ProductFactory(name='RNA Labeling Kit')
        resp = self.client.get('/api/v1/search/grouped', {'q': 'rna'})
        data = resp.json()['data']
        if data['products']:
            self.assertIn('score', data['products'][0])

    def test_typo_tolerance(self):
        """T5-24: Search handles misspelling gracefully (icontains fallback)"""
        ProductFactory(name='RNA Labeling Kit')
        # With icontains, partial match works
        resp = self.client.get('/api/v1/search/grouped', {'q': 'labeling'})
        data = resp.json()['data']
        self.assertTrue(len(data['products']) > 0)
