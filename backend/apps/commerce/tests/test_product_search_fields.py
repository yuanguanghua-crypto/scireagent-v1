"""产品搜索字段覆盖 —— 2026-10-28 修「按货号搜不到」回归。

## 缺陷

`ProductViewSet.search_fields` 配了 6 个字段，但 `get_queryset()` 实际走
`selectors.filter_products()`，而后者只搜 4 个 ⇒ **`catalog_no` / `formula`
在配置里存在、运行时从不生效**。

生产实测：
```
GET /api/v1/products/?search=SC8023  → 0 条   （该产品确实存在：active 未归档）
GET /api/v1/products/?search=5-Iodo  → 1 条
```

货号是采购/报价/对账时最常用的检索方式，影响 `/po/submit` 明细行搜索、
前台搜索框等所有 `GET /products/?search=` 的调用方。

## 本测试守两件事

1. 6 个字段都能搜到（含 `catalog_no` / `formula`）
2. **两处配置不能再漂移** —— `selectors.PRODUCT_SEARCH_FIELDS` 必须等于
   `ProductViewSet.search_fields`，否则又是"配了不生效"。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.api.v1.views import ProductViewSet
from apps.commerce.models import Product
from apps.commerce.selectors import PRODUCT_SEARCH_FIELDS
from apps.commerce.tests.factories import ProductFactory

URL = '/api/v1/products/'


class ProductSearchFieldsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.p = ProductFactory(
            name='5-Iodo-dUTP',
            catalog_no='SC8023',
            cas='105931-58-9',
            formula='C9H13IN3O14P3',
            status='active',
        )

    def _search(self, q):
        r = self.client.get(URL, {'search': q})
        self.assertEqual(r.status_code, 200, r.content[:200])
        rows = r.json().get('data') or []
        return [x['id'] for x in rows]

    # ── 核心回归：货号 ──────────────────────────────────────────────
    def test_search_by_catalog_no_exact(self):
        """按完整货号能搜到 —— 这是本次修复的主目标。"""
        self.assertIn(self.p.id, self._search('SC8023'))

    def test_search_by_catalog_no_prefix(self):
        self.assertIn(self.p.id, self._search('SC802'))

    def test_search_by_catalog_no_case_insensitive(self):
        self.assertIn(self.p.id, self._search('sc8023'), 'icontains 应大小写不敏感')

    # ── formula（同一批漏掉的字段）─────────────────────────────────
    def test_search_by_formula(self):
        self.assertIn(self.p.id, self._search('C9H13IN3O14P3'))

    # ── 原有字段不能回归 ──────────────────────────────────────────
    def test_search_by_name_still_works(self):
        self.assertIn(self.p.id, self._search('5-Iodo'))

    def test_search_by_cas_still_works(self):
        self.assertIn(self.p.id, self._search('105931-58-9'))

    def test_unknown_term_returns_empty(self):
        self.assertEqual(self._search('ZZZ-NOT-EXIST-9999'), [])

    # ── 配置一致性守卫：防止"配了不生效"再次发生 ─────────────────
    def test_search_fields_consistent_with_viewset(self):
        """`PRODUCT_SEARCH_FIELDS` 必须等于 `ProductViewSet.search_fields`。

        `search_fields` 只对 DRF `SearchFilter` 生效，而本视图走自定义 selectors，
        所以真正生效的是前者。两者任一侧新增字段而另一侧没跟上，就会出现
        "配置里有、搜不到"——本次 bug 正是这样来的。
        """
        view_fields = list(ProductViewSet.search_fields)
        self.assertEqual(
            sorted(PRODUCT_SEARCH_FIELDS), sorted(view_fields),
            f'两处搜索字段不一致：selectors={sorted(PRODUCT_SEARCH_FIELDS)} '
            f'vs search_fields={sorted(view_fields)}。'
            f'新增字段时必须同时改两处（或统一由 PRODUCT_SEARCH_FIELDS 派生）。',
        )
