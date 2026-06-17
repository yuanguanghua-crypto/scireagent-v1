"""
TDD Sprint 4.1: SEO Metadata
Tests for SEO features: sitemap, robots.txt, JSON-LD, meta tags.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.tests.factories import ProductFactory


class SEOTest(TestCase):
    """Test SEO features."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name="2'-Azido-dATP",
            catalog_no="SC8047",
            cas="73449-06-6",
            status='active',
            seo_title="Buy 2'-Azido-dATP | SciReagent",
            seo_description="High purity 2'-Azido-dATP for click chemistry labeling. CAS: 73449-06-6.",
        )

    def test_sitemap_returns_200(self):
        """Sitemap should return 200 with XML content."""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('urlset', response.content.decode())

    def test_sitemap_includes_products(self):
        """Sitemap should include product URLs."""
        response = self.client.get('/sitemap.xml')
        content = response.content.decode()
        self.assertIn('/products/', content)

    def test_robots_txt_returns_200(self):
        """Robots.txt should return 200."""
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('User-agent', content)
        self.assertIn('Sitemap', content)

    def test_robots_txt_disallows_admin(self):
        """Robots.txt should disallow admin pages."""
        response = self.client.get('/robots.txt')
        content = response.content.decode()
        self.assertIn('Disallow: /admin/', content)

    def test_product_json_ld_endpoint(self):
        """Product JSON-LD endpoint should return structured data."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/json-ld/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        # JSON-LD is nested inside 'data' field
        json_ld = data.get('data', data)
        self.assertIn('@context', json_ld)

    def test_product_json_ld_has_name(self):
        """Product JSON-LD should include product name."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/json-ld/')
        data = response.json()
        json_ld = data.get('data', data)

        self.assertIn('name', json_ld)
        self.assertEqual(json_ld['name'], "2'-Azido-dATP")

    def test_product_json_ld_has_type(self):
        """Product JSON-LD should include @type."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/json-ld/')
        data = response.json()
        json_ld = data.get('data', data)

        self.assertIn('@type', json_ld)

    def test_product_detail_api_includes_seo_fields(self):
        """Product detail API should include SEO fields."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        product = data['data']['product']
        self.assertIn('seo_title', product)
        self.assertIn('seo_description', product)

    def test_homepage_api_includes_seo(self):
        """Homepage API should include SEO metadata."""
        response = self.client.get('/api/v1/site/home')
        data = response.json()

        self.assertIn('seo', data['data'])
        seo = data['data']['seo']
        self.assertIn('title', seo)
        self.assertIn('description', seo)
