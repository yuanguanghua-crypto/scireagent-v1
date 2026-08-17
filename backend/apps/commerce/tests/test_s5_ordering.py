"""S5 前端接入 — 商品级知识关联分排序（含 nulls_last 修正）。

验证：
1. ?ordering=-aggregate_relevance_score 降序：高分在前、NULL(无关联)沉底。
2. ?ordering=aggregate_relevance_score  升序：低分在前、NULL 沉底。
3. 字段在列表响应中暴露。
"""
from django.test import TestCase
from rest_framework.test import APIClient
from apps.commerce.tests.factories import ProductFactory


class S5AggregateOrderingTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # 高关联 / 低关联 / 无关联(NULL) 三个商品
        self.high = ProductFactory(aggregate_relevance_score=0.90, status='active')
        self.low = ProductFactory(aggregate_relevance_score=0.40, status='active')
        self.none = ProductFactory(aggregate_relevance_score=None, status='active')

    def _scores(self, ordering):
        resp = self.client.get('/api/v1/products/', {'ordering': ordering})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()['data']
        return [(r['id'], r.get('aggregate_relevance_score')) for r in rows]

    def test_field_exposed_in_list(self):
        rows = self._scores('-aggregate_relevance_score')
        ids = [r[0] for r in rows]
        self.assertIn(self.high.id, ids)
        # 取值与设定一致
        by_id = {r[0]: r[1] for r in rows}
        self.assertAlmostEqual(by_id[self.high.id], 0.90)
        self.assertIsNone(by_id[self.none.id])

    def test_desc_nulls_last(self):
        rows = self._scores('-aggregate_relevance_score')
        ids = [r[0] for r in rows]
        # 高分在前，无关联沉底（最后）
        self.assertEqual(ids[0], self.high.id)
        self.assertEqual(ids[-1], self.none.id)
        # 中间是低分
        self.assertEqual(ids[1], self.low.id)

    def test_asc_nulls_last(self):
        rows = self._scores('aggregate_relevance_score')
        ids = [r[0] for r in rows]
        # 低分在前，无关联沉底（最后）
        self.assertEqual(ids[0], self.low.id)
        self.assertEqual(ids[1], self.high.id)
        self.assertEqual(ids[-1], self.none.id)
