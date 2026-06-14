"""
TDD Tests for Homepage API extension.
Phase 1, Week 1-2.
"""
import pytest
from rest_framework.test import APIClient
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory, ReferenceFactory
)
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.bridges.models import ProductMethod, MethodProtocol, ProductReference


@pytest.mark.django_db
class TestHomepageAPI:
    """T1-07 ~ T1-20, T2-01 ~ T2-10: Homepage API extension."""

    def setup_method(self):
        self.client = APIClient()

    def test_t1_07_hero_suggested_searches(self):
        """T1-07: Homepage returns hero.suggested_searches."""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert 'suggested_searches' in data['hero']
        assert isinstance(data['hero']['suggested_searches'], list)
        assert len(data['hero']['suggested_searches']) > 0

    def test_t1_08_featured_solutions_exists(self):
        """T1-08: Homepage returns featured_solutions list."""
        app = ApplicationFactory(status='active', display_priority=100)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert 'featured_solutions' in data
        assert isinstance(data['featured_solutions'], list)

    def test_t1_09_featured_solution_has_methods_count(self):
        """T1-09: Featured solution has methods_count."""
        app = ApplicationFactory(status='active', display_priority=100)
        MethodFactory(application=app, status='active')
        MethodFactory(application=app, status='active')
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        sol = data['featured_solutions'][0]
        assert 'methods_count' in sol
        assert sol['methods_count'] == 2

    def test_t1_10_featured_solution_has_products_count(self):
        """T1-10: Featured solution has products_count."""
        app = ApplicationFactory(status='active', display_priority=100)
        method = MethodFactory(application=app, status='active')
        product = ProductFactory(status='active')
        ProductMethod.objects.create(product=product, method=method)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        sol = data['featured_solutions'][0]
        assert 'products_count' in sol
        assert sol['products_count'] >= 1

    def test_t1_11_no_references_count(self):
        """T1-11: Featured solution does NOT have references_count."""
        app = ApplicationFactory(status='active', display_priority=100)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        if data['featured_solutions']:
            assert 'references_count' not in data['featured_solutions'][0]

    def test_t1_12_research_goals_exists(self):
        """T1-12: Homepage returns research_goals list."""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert 'research_goals' in data
        assert isinstance(data['research_goals'], list)

    def test_t1_13_research_goal_has_applications_count(self):
        """T1-13: Research goal has applications_count."""
        from apps.knowledge.tests.factories import ResearchGoalFactory
        goal = ResearchGoalFactory()
        ApplicationFactory(research_goal=goal, status='active')
        ApplicationFactory(research_goal=goal, status='active')
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        # Find our goal in the list
        found = [g for g in data['research_goals'] if g['id'] == goal.id]
        assert len(found) == 1
        assert found[0]['applications_count'] == 2

    def test_t1_14_references_exists(self):
        """T1-14: Homepage returns references list."""
        ref = ReferenceFactory()
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert 'references' in data
        assert isinstance(data['references'], list)

    def test_t1_15_reference_has_fields(self):
        """T1-15: Reference has title/journal/year/doi."""
        ref = ReferenceFactory()
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        if data['references']:
            r = data['references'][0]
            assert 'title' in r
            assert 'journal' in r
            assert 'year' in r
            assert 'doi' in r

    def test_t1_16_graph_preview_null(self):
        """T1-16: Homepage returns graph_preview as null."""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert 'graph_preview' in data
        assert data['graph_preview'] is None

    def test_t1_17_featured_products_use_display_priority(self):
        """T1-17: Featured products with display_priority > 0 appear first."""
        p_low = ProductFactory(status='active', display_priority=10, name='Low Priority')
        p_high = ProductFactory(status='active', display_priority=100, name='High Priority')
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        featured = data['featured_products']
        # High priority should come first
        if len(featured) >= 2:
            assert featured[0]['display_priority'] >= featured[1]['display_priority']

    def test_t1_18_featured_products_exclude_draft(self):
        """T1-18: No draft products in featured."""
        ProductFactory(status='active', display_priority=100)
        ProductFactory(status='draft', display_priority=200)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        for p in data['featured_products']:
            assert p['status'] != 'draft'

    def test_t1_19_featured_applications_use_display_priority(self):
        """T1-19: Featured applications with display_priority > 0 appear first."""
        a_low = ApplicationFactory(status='active', display_priority=10)
        a_high = ApplicationFactory(status='active', display_priority=100)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        featured = data['featured_applications']
        if len(featured) >= 2:
            assert featured[0].get('display_priority', 0) >= featured[1].get('display_priority', 0)

    def test_t1_20_featured_methods_have_products_count(self):
        """T1-20: Featured methods have products_count."""
        method = MethodFactory(status='active')
        product = ProductFactory(status='active')
        ProductMethod.objects.create(product=product, method=method)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        found = [m for m in data['featured_methods'] if m['id'] == method.id]
        assert len(found) == 1
        assert 'products_count' in found[0]

    def test_t2_01_all_sections_present(self):
        """T2-01: Homepage response has all 9 sections."""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        required = ['hero', 'stats', 'featured_applications', 'featured_methods',
                     'featured_products', 'featured_solutions', 'research_goals',
                     'references', 'graph_preview']
        for key in required:
            assert key in data, f'Missing section: {key}'

    def test_t2_02_envelope_format(self):
        """T2-02: Homepage response uses Envelope format."""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()
        assert 'success' in data
        assert data['success'] is True
        assert 'data' in data
        assert 'meta' in data

    def test_t2_03_featured_products_have_catalog_no(self):
        """T2-03: Featured products have catalog_no."""
        ProductFactory(status='active', catalog_no='SC8047', display_priority=10)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        found = [p for p in data['featured_products'] if p.get('catalog_no') == 'SC8047']
        assert len(found) == 1

    def test_t2_04_featured_products_have_formula(self):
        """T2-04: Featured products have formula."""
        ProductFactory(status='active', formula='C10H14N5O12P3', display_priority=10)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        found = [p for p in data['featured_products'] if p.get('formula') == 'C10H14N5O12P3']
        assert len(found) == 1

    def test_t2_05_featured_applications_have_summary(self):
        """T2-07: Featured applications have summary (not description)."""
        ApplicationFactory(status='active', summary='Test summary', display_priority=10)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        found = [a for a in data['featured_applications'] if a.get('summary') == 'Test summary']
        assert len(found) == 1
        # Should NOT have 'description' field
        if data['featured_applications']:
            assert 'description' not in data['featured_applications'][0]

    def test_t2_06_empty_database(self):
        """T2-09: Empty database returns empty lists, no errors."""
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert isinstance(data['featured_products'], list)
        assert isinstance(data['featured_applications'], list)
        assert isinstance(data['featured_methods'], list)
        assert isinstance(data['featured_solutions'], list)
        assert isinstance(data['research_goals'], list)
        assert isinstance(data['references'], list)

    def test_t2_07_featured_products_limit_8(self):
        """T2-10: Featured products limited to 8."""
        for i in range(10):
            ProductFactory(status='active', display_priority=i + 1)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert len(data['featured_products']) <= 8
