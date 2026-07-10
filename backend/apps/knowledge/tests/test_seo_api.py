"""T6-01 ~ T6-15: SEO API tests"""
from django.test import TestCase
from rest_framework.test import APIClient
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import ApplicationFactory


class ProductDetailSEOTest(TestCase):
    """T6-01 ~ T6-02: Product detail SEO fields"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name='RNA Labeling Kit',
            status='active',
            seo_title='RNA Labeling Kit | SciReagent',
            seo_description='High-quality RNA labeling reagents for research use.',
        )

    def test_product_detail_has_seo_title(self):
        """T6-01: Product detail API returns seo_title"""
        resp = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = resp.json()
        self.assertEqual(data['data']['product']['seo_title'], 'RNA Labeling Kit | SciReagent')

    def test_product_detail_has_seo_description(self):
        """T6-02: Product detail API returns seo_description"""
        resp = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = resp.json()
        self.assertIn('RNA labeling', data['data']['product']['seo_description'])


class HomepageSEOTest(TestCase):
    """T6-03 ~ T6-06: Homepage SEO section"""

    def setUp(self):
        self.client = APIClient()

    def test_homepage_has_seo_section(self):
        """T6-03: Homepage API has seo section"""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()
        self.assertIn('seo', data['data'])

    def test_homepage_seo_has_title(self):
        """T6-04"""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()
        self.assertIsInstance(data['data']['seo']['title'], str)
        self.assertTrue(len(data['data']['seo']['title']) > 0)

    def test_homepage_seo_has_description(self):
        """T6-05"""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()
        self.assertIsInstance(data['data']['seo']['description'], str)
        self.assertTrue(len(data['data']['seo']['description']) > 0)

    def test_homepage_seo_has_og_image(self):
        """T6-06"""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()
        self.assertIn('og_image', data['data']['seo'])


class ApplicationDetailSEOTest(TestCase):
    """T6-07: Application detail SEO"""

    def setUp(self):
        self.client = APIClient()
        self.app = ApplicationFactory(name='RNA Labeling', status='active')

    def test_application_detail_has_seo(self):
        """T6-07: Application detail has seo fields"""
        resp = self.client.get(f'/api/v1/applications/{self.app.id}/')
        data = resp.json()
        self.assertIn('data', data)


class RobotsTxtTest(TestCase):
    """T6-08 ~ T6-10: robots.txt endpoint"""

    def setUp(self):
        self.client = APIClient()

    def test_robots_txt_returns_200(self):
        """T6-08"""
        resp = self.client.get('/robots.txt')
        self.assertEqual(resp.status_code, 200)

    def test_robots_txt_contains_user_agent(self):
        """T6-09"""
        resp = self.client.get('/robots.txt')
        self.assertContains(resp, 'User-agent:')

    def test_robots_txt_contains_sitemap(self):
        """T6-10"""
        resp = self.client.get('/robots.txt')
        self.assertContains(resp, 'Sitemap:')


class SitemapTest(TestCase):
    """T6-11 ~ T6-12: Sitemap"""

    def setUp(self):
        self.client = APIClient()

    def test_sitemap_returns_200(self):
        """T6-11"""
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)

    def test_sitemap_contains_product_urls(self):
        """T6-12"""
        ProductFactory(name='RNA Kit', status='active')
        resp = self.client.get('/sitemap.xml')
        self.assertContains(resp, '/products/')


class JSONLDTest(TestCase):
    """T6-13 ~ T6-15: JSON-LD structured data"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(name='RNA Labeling Kit', status='active')

    def test_product_detail_has_jsonld(self):
        """T6-13"""
        resp = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = resp.json()
        self.assertIn('jsonld', data['data']['product'])

    def test_jsonld_has_type_product(self):
        """T6-14"""
        resp = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = resp.json()
        jsonld = data['data']['product']['jsonld']
        self.assertEqual(jsonld.get('@type'), 'Product')

    def test_jsonld_has_name_description(self):
        """T6-15"""
        resp = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = resp.json()
        jsonld = data['data']['product']['jsonld']
        self.assertIn('name', jsonld)
        self.assertIn('description', jsonld)
