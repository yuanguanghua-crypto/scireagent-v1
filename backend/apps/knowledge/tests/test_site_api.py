from django.test import TestCase
from rest_framework.test import APIClient
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory, ReferenceFactory
)
from apps.commerce.tests.factories import ProductFactory


class SiteHomeAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_home_endpoint(self):
        resp = self.client.get('/api/v1/site/home')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('hero', data['data'])
        self.assertIn('featured_applications', data['data'])

    def test_home_hero_fields(self):
        resp = self.client.get('/api/v1/site/home')
        hero = resp.json()['data']['hero']
        self.assertIn('title', hero)
        self.assertIn('subtitle', hero)

    def test_home_featured_applications(self):
        ApplicationFactory(status='active')
        ApplicationFactory(status='draft')  # should not appear
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        self.assertEqual(len(data['featured_applications']), 1)

    def test_home_featured_methods(self):
        MethodFactory(status='active')
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        self.assertIn('featured_methods', data)
        self.assertEqual(len(data['featured_methods']), 1)

    def test_home_featured_products(self):
        ProductFactory(status='active')
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        self.assertIn('featured_products', data)
        self.assertEqual(len(data['featured_products']), 1)

    def test_home_featured_application_fields(self):
        ApplicationFactory(status='active', name='RNA Labeling')
        resp = self.client.get('/api/v1/site/home')
        app_data = resp.json()['data']['featured_applications'][0]
        self.assertIn('id', app_data)
        self.assertIn('name', app_data)
        self.assertIn('slug', app_data)
        self.assertIn('summary', app_data)

    def test_home_envelope_format(self):
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)


class SiteNavigationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_navigation_endpoint(self):
        resp = self.client.get('/api/v1/site/navigation')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('primary', data['data'])

    def test_navigation_primary_items(self):
        resp = self.client.get('/api/v1/site/navigation')
        primary = resp.json()['data']['primary']
        labels = [item['label'] for item in primary]
        self.assertIn('Home', labels)
        self.assertIn('Applications', labels)
        self.assertIn('Methods', labels)

    def test_navigation_applications(self):
        ApplicationFactory(status='active', name='RNA Labeling')
        ApplicationFactory(status='draft', name='Draft App')
        resp = self.client.get('/api/v1/site/navigation')
        apps = resp.json()['data']['applications']
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['name'], 'RNA Labeling')


class SearchAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_search_empty_query(self):
        resp = self.client.get('/api/v1/search')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_search_products(self):
        ProductFactory(name='Cy3-NHS Ester')
        ProductFactory(name='Cy5-NHS Ester')
        resp = self.client.get('/api/v1/search?q=Cy3')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['type'], 'product')

    def test_search_methods(self):
        MethodFactory(name='Sanger Sequencing')
        MethodFactory(name='PCR Amplification')
        resp = self.client.get('/api/v1/search?q=Sanger')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_applications(self):
        ApplicationFactory(name='RNA Labeling')
        resp = self.client.get('/api/v1/search?q=RNA')
        data = resp.json()
        self.assertTrue(len(data['data']) > 0)
        self.assertEqual(data['data'][0]['type'], 'application')

    def test_search_protocols(self):
        ProtocolFactory(name='DNA Extraction Protocol')
        resp = self.client.get('/api/v1/search?q=Extraction')
        data = resp.json()
        self.assertTrue(len(data['data']) > 0)

    def test_search_references(self):
        ReferenceFactory(title='Nature Paper on CRISPR')
        resp = self.client.get('/api/v1/search?q=CRISPR')
        data = resp.json()
        self.assertTrue(len(data['data']) > 0)

    def test_search_multiple_types(self):
        ProductFactory(name='Cy3-NHS')
        MethodFactory(name='Cy3 Labeling Method')
        resp = self.client.get('/api/v1/search?q=Cy3')
        data = resp.json()
        types = [r['type'] for r in data['data']]
        self.assertIn('product', types)
        self.assertIn('method', types)

    def test_search_no_results(self):
        ProductFactory(name='Cy3-NHS')
        resp = self.client.get('/api/v1/search?q=NonExistent')
        self.assertEqual(resp.json()['data'], [])

    def test_search_meta(self):
        resp = self.client.get('/api/v1/search?q=test')
        meta = resp.json()['meta']
        self.assertIn('query', meta)
        self.assertEqual(meta['query'], 'test')

    def test_search_type_filter(self):
        ProductFactory(name='Cy3-NHS')
        MethodFactory(name='Cy3 Labeling')
        resp = self.client.get('/api/v1/search?q=Cy3&type=product')
        data = resp.json()['data']
        for result in data:
            self.assertEqual(result['type'], 'product')

    def test_search_suggest(self):
        ProductFactory(name='Cy3-NHS')
        resp = self.client.get('/api/v1/search/suggest?q=Cy3')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_search_suggest_short_query(self):
        resp = self.client.get('/api/v1/search/suggest?q=C')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_search_suggest_fields(self):
        ProductFactory(name='Cy3-NHS')
        MethodFactory(name='Cy3 Labeling')
        resp = self.client.get('/api/v1/search/suggest?q=Cy3')
        suggestions = resp.json()['data']
        self.assertTrue(len(suggestions) > 0)
        for s in suggestions:
            self.assertIn('type', s)
            self.assertIn('id', s)
            self.assertIn('text', s)


class SitemapAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_sitemap_xml(self):
        ApplicationFactory(status='active')
        ProductFactory(status='active')
        resp = self.client.get('/api/v1/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('<?xml', content)
        self.assertIn('<urlset', content)
        self.assertIn('</urlset>', content)

    def test_sitemap_contains_applications(self):
        ApplicationFactory(status='active')
        resp = self.client.get('/api/v1/sitemap.xml')
        content = resp.content.decode()
        self.assertIn('/applications/', content)

    def test_sitemap_contains_methods(self):
        MethodFactory(status='active')
        resp = self.client.get('/api/v1/sitemap.xml')
        content = resp.content.decode()
        self.assertIn('/methods/', content)

    def test_sitemap_contains_products(self):
        ProductFactory(status='active')
        resp = self.client.get('/api/v1/sitemap.xml')
        content = resp.content.decode()
        self.assertIn('/products/', content)

    def test_sitemap_contains_protocols(self):
        ProtocolFactory(status='active')
        resp = self.client.get('/api/v1/sitemap.xml')
        content = resp.content.decode()
        self.assertIn('/protocols/', content)

    def test_sitemap_excludes_draft(self):
        ApplicationFactory(status='draft')
        resp = self.client.get('/api/v1/sitemap.xml')
        content = resp.content.decode()
        self.assertNotIn('/applications/', content)

    def test_sitemap_content_type(self):
        resp = self.client.get('/api/v1/sitemap.xml')
        self.assertEqual(resp.get('Content-Type'), 'application/xml')

    def test_sitemap_always_contains_home(self):
        resp = self.client.get('/api/v1/sitemap.xml')
        content = resp.content.decode()
        # Home URL should always be present
        self.assertIn('<url>', content)
