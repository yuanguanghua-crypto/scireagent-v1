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

    def test_t1_08_featured_solutions_removed(self):
        """T1-08（契约变更，2026-10-30）：首页不再返回 featured_solutions。

        原来这条区块的选取条件是 `display_priority > 0`，而实测全库
        28,566 个 active Application 的 display_priority **全部是 0**
        —— 运营置顶功能从未使用 ⇒ 该字段恒为 []，前端也从未渲染。
        留着只是每次首页多跑一条跨三层的 COUNT 聚合。
        用户 2026-10-30 拍板删除，「精选应用」改用 featured_applications，
        所以这里锁住「不再出现」，防止有人把它加回来又变回空区块。
        """
        ApplicationFactory(status='active', display_priority=100)
        data = self.client.get('/api/v1/site/home').json()['data']
        assert 'featured_solutions' not in data

    def test_t1_09_featured_applications_carry_counts(self):
        """T1-09（原 featured_solutions 的 methods/products 计数契约迁移到此）：
        精选应用必须带 methods_count / products_count，供首页卡片显示
        「N methods · M products」。"""
        app = ApplicationFactory(status='active', display_priority=100)
        m1 = MethodFactory(application=app, status='active')
        MethodFactory(application=app, status='active')
        product = ProductFactory(status='active')
        ProductMethod.objects.create(product=product, method=m1)

        data = self.client.get('/api/v1/site/home').json()['data']
        item = next(a for a in data['featured_applications'] if a['id'] == app.id)
        assert item['methods_count'] == 2
        assert item['products_count'] >= 1
        assert 'references_count' not in item

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

    def test_t1_16_graph_preview_removed(self):
        """T1-16（契约变更，2026-10-30）：首页不再返回 graph_preview。

        用户要求「图谱部分不展示，没有作用，而且很杂乱」。原来这条断言的是
        「返回 null」，但后来 `_build_homepage_graph()` 让它变成 20 节点图，
        断言就一直是红的/靠空库侥幸通过 —— 现在两边一起删掉。
        """
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert 'graph_preview' not in data

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
        # 2026-10-30：featured_solutions（恒空）与 graph_preview（用户要求去掉）均已删除
        required = ['hero', 'stats', 'featured_applications', 'featured_methods',
                    'featured_products', 'research_goals', 'references']
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
        assert 'featured_solutions' not in data  # 2026-10-30 已删除（恒空区块）
        assert isinstance(data['research_goals'], list)
        assert isinstance(data['references'], list)

    def test_t2_07_featured_products_limit_20(self):
        """T2-10: Featured products limited to 20."""
        for i in range(25):
            ProductFactory(status='active', display_priority=i + 1)
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        assert len(data['featured_products']) <= 20
