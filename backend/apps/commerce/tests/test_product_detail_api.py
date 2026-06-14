"""
TDD Tests for Product Detail API endpoint.
Phase 1, Week 3.
"""
import pytest
from rest_framework.test import APIClient
from apps.commerce.tests.factories import ProductFactory, SKUFactory, ProductDocumentFactory
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory,
    ProtocolStepFactory, ReferenceFactory,
)
from apps.bridges.models import ProductMethod, MethodProtocol, ProductReference


@pytest.mark.django_db
class TestProductDetailAPI:
    """T3-17 ~ T3-30: Product detail aggregated endpoint."""

    def setup_method(self):
        self.client = APIClient()

    def test_t3_17_returns_200(self):
        """T3-17: GET /api/v1/products/:id/detail/ returns 200."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        assert resp.status_code == 200

    def test_t3_18_has_product_section(self):
        """T3-18: Response has product section."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'product' in data
        assert data['product']['id'] == product.id

    def test_t3_19_has_applications_section(self):
        """T3-19: Response has applications section."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'applications' in data
        assert isinstance(data['applications'], list)

    def test_t3_20_has_protocols_section(self):
        """T3-20: Response has protocols section."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'protocols' in data
        assert isinstance(data['protocols'], list)

    def test_t3_21_has_references_section(self):
        """T3-21: Response has references section."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'references' in data
        assert isinstance(data['references'], list)

    def test_t3_22_has_related_products_section(self):
        """T3-22: Response has related_products section."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'related_products' in data
        assert isinstance(data['related_products'], list)

    def test_t3_23_has_faq_section(self):
        """T3-23: Response has faq section."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'faq' in data
        assert isinstance(data['faq'], list)

    def test_t3_24_has_compatibility_section(self):
        """T3-24: Response has compatibility section."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'compatibility' in data
        assert isinstance(data['compatibility'], dict)
        assert 'methods' in data['compatibility']
        assert 'protocols' in data['compatibility']
        assert 'products' in data['compatibility']

    def test_t3_25_has_graph_null(self):
        """T3-25: Response has graph section as null."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert 'graph' in data
        assert data['graph'] is None

    def test_t3_26_404_for_nonexistent(self):
        """T3-26: Returns 404 for nonexistent product."""
        resp = self.client.get('/api/v1/products/99999/detail/')
        assert resp.status_code == 404

    def test_t3_27_envelope_format(self):
        """T3-27: Uses Envelope format."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()
        assert data['success'] is True
        assert 'data' in data
        assert 'meta' in data

    def test_t3_28_applications_have_name(self):
        """T3-28: Applications have name field."""
        product = ProductFactory(status='active')
        app = ApplicationFactory(status='active')
        method = MethodFactory(application=app, status='active')
        ProductMethod.objects.create(product=product, method=method)
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert len(data['applications']) >= 1
        assert 'name' in data['applications'][0]

    def test_t3_29_protocols_have_estimated_time(self):
        """T3-29: Protocols have estimated_time_minutes."""
        product = ProductFactory(status='active')
        method = MethodFactory(status='active')
        protocol = ProtocolFactory(method=method, status='published')
        ProtocolStepFactory(protocol=protocol, duration_seconds=120)
        ProductMethod.objects.create(product=product, method=method)
        MethodProtocol.objects.create(method=method, protocol=protocol)
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        assert len(data['protocols']) >= 1
        assert 'estimated_time_minutes' in data['protocols'][0]

    def test_t3_30_compatibility_has_methods_protocols_products(self):
        """T3-30: Compatibility has methods, protocols, products."""
        product = ProductFactory(status='active')
        resp = self.client.get(f'/api/v1/products/{product.id}/detail/')
        data = resp.json()['data']
        compat = data['compatibility']
        assert 'methods' in compat
        assert 'protocols' in compat
        assert 'products' in compat
