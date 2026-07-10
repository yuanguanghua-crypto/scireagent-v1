"""Phase 2 测试：CategoryTreeView 重写为 DB 驱动。

验证响应结构与旧硬编码版逐键兼容，前端 ProductLayout.vue 无需改动。
"""
import pytest
from rest_framework.test import APIClient

from apps.commerce.models import Product, ProductClass
from apps.commerce.tests.factories import ProductFactory, ProductClassFactory


@pytest.mark.django_db
class TestCategoryTreeView:
    """GET /api/v1/categories"""

    def _get(self):
        return APIClient().get('/api/v1/categories').json()

    def _make_tree(self):
        l1 = ProductClassFactory(name='Nucleotides & Nucleosides', slug='nucleotides_nucleosides')
        l2a = ProductClassFactory(name='Fluorescent Nucleotides', slug='fluorescent', parent=l1)
        l2b = ProductClassFactory(name='Cyclic Nucleotides', slug='cyclic', parent=l1)
        l3 = ProductClassFactory(name='5-Formyl', slug='5-formyl', parent=l2a)
        return l1, l2a, l2b, l3

    def test_l1_with_products_returns_count(self):
        l1, l2a, l2b, l3 = self._make_tree()
        ProductFactory(product_class=l1)
        ProductFactory(product_class=l2a)
        data = self._get()
        assert data['nucleotides_nucleosides']['count'] == 2

    def test_l2_children_list_from_db(self):
        l1, l2a, l2b, l3 = self._make_tree()
        data = self._get()
        children = data['nucleotides_nucleosides']['children']
        assert 'Fluorescent Nucleotides' in children
        assert 'Cyclic Nucleotides' in children

    def test_l2_counts_excludes_zero(self):
        l1, l2a, l2b, l3 = self._make_tree()
        ProductFactory(product_class=l2a)  # 只 l2a 有产品
        data = self._get()
        l2_counts = data['nucleotides_nucleosides']['l2_counts']
        assert 'Fluorescent Nucleotides' in l2_counts
        assert 'Cyclic Nucleotides' not in l2_counts

    def test_l2_counts_has_id_and_children(self):
        l1, l2a, l2b, l3 = self._make_tree()
        ProductFactory(product_class=l2a)
        data = self._get()
        entry = data['nucleotides_nucleosides']['l2_counts']['Fluorescent Nucleotides']
        assert entry['id'] == l2a.id
        assert '5-Formyl' in entry['children']

    def test_no_envelope(self):
        # 顶层直接是 dict，不是 {success, data, meta}
        self._make_tree()
        resp = APIClient().get('/api/v1/categories')
        data = resp.json()
        assert 'success' not in data
        assert isinstance(data, dict)

    def test_l1_count_includes_l2_l3_descendants(self):
        l1, l2a, l2b, l3 = self._make_tree()
        ProductFactory(product_class=l2a)
        ProductFactory(product_class=l3)
        data = self._get()
        # l2a 直接 + l3 直接，都算 l1 后代
        assert data['nucleotides_nucleosides']['count'] == 2
