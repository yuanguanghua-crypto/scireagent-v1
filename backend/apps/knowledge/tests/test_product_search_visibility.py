"""S1 选项 A：Product 搜索可见性（复用既有 archived 回收站机制）。

v2 方案误判「Product 0/256 零污染」，实际有 131 个 e2e 残骸（前缀 E2E / E2E-，
全部 archived=True）。公开 Product list/detail 已由 views.py 排除 archived，但 search
三个端点查 Product 时漏了 archived 过滤——这正是 S1 要修的「search 无可见性过滤」类
泄漏。本测试锁定该契约：archived Product 不得出现在任何 search 读取面。

守铁律①：全程零删除，仅复用 archived 字段语义。
"""
from rest_framework.test import APIClient
from django.test import TestCase
from apps.commerce.tests.factories import ProductFactory


class ProductSearchArchivedVisibilityTest(TestCase):
    """archived=True 的 Product 在 search / suggest / grouped 三个端点不可见。"""

    def setUp(self):
        self.client = APIClient()
        self.archived = ProductFactory(
            name='Archived E2E zzz probe', archived=True, status='draft'
        )
        self.active = ProductFactory(
            name='Active E2E zzz probe', archived=False, status='active'
        )

    # ---------- 辅助 ----------
    def _search_product_names(self, resp):
        rows = resp.json()['data']
        return [r.get('name') for r in rows if r.get('type') == 'product']

    def _suggest_product_texts(self, resp):
        rows = resp.json()['data']
        return [r.get('text') for r in rows if r.get('type') == 'product']

    # ---------- search ----------
    def test_search_excludes_archived_product(self):
        resp = self.client.get('/api/v1/search?q=zzz')
        names = self._search_product_names(resp)
        self.assertNotIn(self.archived.name, names)
        self.assertIn(self.active.name, names)

    # ---------- search/suggest ----------
    def test_search_suggest_excludes_archived_product(self):
        resp = self.client.get('/api/v1/search/suggest?q=zzz')
        texts = self._suggest_product_texts(resp)
        self.assertNotIn(self.archived.name, texts)
        self.assertIn(self.active.name, texts)

    # ---------- search/grouped ----------
    def test_search_grouped_excludes_archived_product(self):
        resp = self.client.get('/api/v1/search/grouped?q=zzz')
        names = [r['name'] for r in resp.json()['data']['products']]
        self.assertNotIn(self.archived.name, names)
        self.assertIn(self.active.name, names)
