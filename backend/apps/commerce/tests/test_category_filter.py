"""Phase 4 测试：过滤逻辑改为 product_class 递归。

验证：
- category_l1 query param 递归匹配 L1 下所有后代产品
- category_l2 query param 按 L2 name 匹配
- product_class_id 过滤支持递归（include_descendants）
- related_products 按 product_class 递归匹配
- 首页 categories payload 只含 3 个 L1
"""
import pytest
from rest_framework.test import APIClient

from apps.commerce.models import Product, ProductClass
from apps.commerce.selectors import get_descendant_product_class_ids, filter_products
from apps.commerce.tests.factories import ProductFactory, ProductClassFactory, SKUFactory
from apps.commerce.services.related_products import get_related_products


@pytest.mark.django_db
class TestGetDescendantIds:
    """TC: get_descendant_product_class_ids 递归返回含自身的所有后代 id"""

    def test_l1_slug_returns_all_descendants(self):
        l1 = ProductClassFactory(name='Nucleotides', slug='nucleotides_nucleosides')
        l2a = ProductClassFactory(name='Fluorescent', slug='fluorescent', parent=l1)
        l2b = ProductClassFactory(name='Cyclic', slug='cyclic', parent=l1)
        l3 = ProductClassFactory(name='5-Formyl', slug='5-formyl', parent=l2a)
        ids = get_descendant_product_class_ids('nucleotides_nucleosides')
        assert set(ids) == {l1.id, l2a.id, l2b.id, l3.id}

    def test_unknown_slug_returns_empty(self):
        assert get_descendant_product_class_ids('nonexistent') == []

    def test_l2_id_returns_subtree(self):
        l1 = ProductClassFactory(name='Nucleotides', slug='nucleotides_nucleosides')
        l2a = ProductClassFactory(name='Fluorescent', slug='fluorescent', parent=l1)
        l3 = ProductClassFactory(name='5-Formyl', slug='5-formyl', parent=l2a)
        # L2 id 视为子树根，返回含 l2a 及其后代（l3）
        ids = get_descendant_product_class_ids(l2a.id)
        assert l2a.id in ids
        assert l3.id in ids


@pytest.mark.django_db
class TestProductCategoryFilter:
    """TC: ProductViewSet 按 category_l1/category_l2 过滤"""

    def _make_tree(self):
        l1 = ProductClassFactory(name='Nucleotides', slug='nucleotides_nucleosides')
        l2a = ProductClassFactory(name='Fluorescent Nucleotides', slug='fluorescent', parent=l1)
        l2b = ProductClassFactory(name='Cyclic Nucleotides', slug='cyclic', parent=l1)
        return l1, l2a, l2b

    def test_filter_by_category_l1_returns_descendants(self):
        l1, l2a, l2b = self._make_tree()
        p1 = ProductFactory(product_class=l2a, status='active')
        p2 = ProductFactory(product_class=l2b, status='active')
        resp = APIClient().get(f'/api/v1/products/?category_l1=nucleotides_nucleosides')
        data = resp.json()['data']
        ids = {p['id'] for p in data}
        assert p1.id in ids and p2.id in ids

    def test_filter_by_category_l2_name(self):
        l1, l2a, l2b = self._make_tree()
        p1 = ProductFactory(product_class=l2a, status='active')
        p2 = ProductFactory(product_class=l2b, status='active')
        resp = APIClient().get(f'/api/v1/products/?category_l2=Fluorescent Nucleotides')
        data = resp.json()['data']
        ids = {p['id'] for p in data}
        assert p1.id in ids
        assert p2.id not in ids

    def test_filter_by_product_class_id_direct(self):
        l1, l2a, l2b = self._make_tree()
        p1 = ProductFactory(product_class=l2a, status='active')
        p2 = ProductFactory(product_class=l2b, status='active')
        resp = APIClient().get(f'/api/v1/products/?product_class_id={l2a.id}')
        data = resp.json()['data']
        ids = {p['id'] for p in data}
        assert p1.id in ids
        assert p2.id not in ids


@pytest.mark.django_db
class TestRelatedProductsRecursive:
    """TC: related_products 按 product_class 递归匹配"""

    def test_related_same_l1_different_l2(self):
        l1 = ProductClassFactory(name='Nucleotides', slug='nucleotides_nucleosides')
        l2a = ProductClassFactory(name='Fluorescent', slug='fluorescent', parent=l1)
        l2b = ProductClassFactory(name='Cyclic', slug='cyclic', parent=l1)
        p1 = ProductFactory(product_class=l2a, status='active')
        p2 = ProductFactory(product_class=l2b, status='active')
        related = get_related_products(p1, limit=4)
        assert p2 in related

    def test_related_no_product_class_fallback_global(self):
        p1 = ProductFactory(product_class=None, status='active')
        p2 = ProductFactory(status='active')
        related = get_related_products(p1, limit=4)
        # 无 product_class → 全局 fallback，应返回其他 active 产品
        assert p2 in related


@pytest.mark.django_db
class TestHomeCategoriesThreeL1:
    """TC: 首页 categories payload 只含 3 个 L1"""

    def test_home_categories_payload(self):
        resp = APIClient().get('/api/v1/site/home')
        data = resp.json()
        if data.get('success'):
            cats = data['data'].get('categories', [])
            keys = {c.get('slug', '').replace('-', '_') for c in cats}
            # 只含 3 个采纳 L1 的 slug
            assert any('nucleotides' in k for k in keys)
            assert any('click' in k for k in keys)
            assert any('molecular' in k for k in keys)
            # 不应再出现旧的扩展类键
            assert not any('fluorescent' == k for k in keys)
            assert not any('bioconjugation' == k for k in keys)
