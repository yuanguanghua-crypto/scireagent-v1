"""S5 RED: 商品级聚合分（仅 non-weak）+ 排序接入。

契约（实现后转 GREEN）：
- relevance.py 新增纯函数 `_aggregate_scores(scores, operator='mean')`：
    mean(默认)/max/top3_mean/logsumexp(t=5)；
    输入为空、或有效分全为 None/NaN -> 返回 None（诚实不冒充 0）。
- relevance.py 新增 `aggregate_product_relevance(pp_rows, operator='mean')`：
    仅聚合 tier != 'weak' 的行的 relevance_score（排除广播/仅语义相似，保区分度）；
    无任何 non-weak 行 -> None；None/NaN 分跳过；operator 透传。
- relevance.py 新增 `update_product_aggregate(product)`：
    聚合该商品非 weak 的 ProductProtocol 行 -> 写入 Product.aggregate_relevance_score；
    无则写 None；幂等可回滚。
- Product 新增字段 `aggregate_relevance_score = FloatField(null=True, blank=True)` + 迁移。
- ProductViewSet.ordering_fields 新增 'aggregate_relevance_score'（商品列表可按聚合分排序）。
- ProductListSerializer.Meta.fields 暴露 'aggregate_relevance_score'。

RED 时应整体 FAIL（函数/字段/排序面/序列化暴露均未实现），直至 S5 实现后转 GREEN。
"""
import math
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.bridges.models import ProductProtocol
from apps.bridges.tests.factories import ProductProtocolFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import ProtocolFactory


# ── 轻量行对象：供 aggregate_product_relevance 单测（无需落库）──
class _Row:
    def __init__(self, tier, relevance_score):
        self.tier = tier
        self.relevance_score = relevance_score


# ── 组 A：_aggregate_scores 纯函数（4 算子 + 边界）──
class AggregateScoresUnitTest(TestCase):
    def test_importable(self):
        from apps.bridges.services.relevance import _aggregate_scores  # noqa: F401

    def test_mean_default(self):
        from apps.bridges.services.relevance import _aggregate_scores
        self.assertAlmostEqual(_aggregate_scores([0.2, 0.4, 0.6]), 0.4, places=9)

    def test_max(self):
        from apps.bridges.services.relevance import _aggregate_scores
        self.assertAlmostEqual(
            _aggregate_scores([0.2, 0.9, 0.6], operator='max'), 0.9, places=9)

    def test_top3_mean(self):
        from apps.bridges.services.relevance import _aggregate_scores
        # [0.9,0.8,0.7,0.1] top3 = (0.9+0.8+0.7)/3 = 0.8
        self.assertAlmostEqual(
            _aggregate_scores([0.9, 0.8, 0.7, 0.1], operator='top3_mean'), 0.8, places=9)

    def test_logsumexp_t5(self):
        from apps.bridges.services.relevance import _aggregate_scores
        # m=0.6; (1/5)*ln(exp(-2)+exp(-1)+1)+0.6 = 0.68148...
        val = _aggregate_scores([0.2, 0.4, 0.6], operator='logsumexp')
        self.assertAlmostEqual(val, 0.681486, places=4)

    def test_empty_returns_none(self):
        from apps.bridges.services.relevance import _aggregate_scores
        self.assertIsNone(_aggregate_scores([]))
        self.assertIsNone(_aggregate_scores(None))

    def test_skips_none_and_nan(self):
        from apps.bridges.services.relevance import _aggregate_scores
        scores = [0.2, None, float('nan'), 0.6]
        # 仅 [0.2, 0.6] 有效 -> mean 0.4
        self.assertAlmostEqual(_aggregate_scores(scores), 0.4, places=9)

    def test_unknown_operator_raises(self):
        from apps.bridges.services.relevance import _aggregate_scores
        with self.assertRaises(ValueError):
            _aggregate_scores([0.2, 0.6], operator='bogus')


# ── 组 B：aggregate_product_relevance（排除 weak / 空->None / None分跳过 / 算子透传）──
class AggregateProductRelevanceTest(TestCase):
    def test_importable(self):
        from apps.bridges.services.relevance import aggregate_product_relevance  # noqa: F401

    def test_excludes_weak(self):
        from apps.bridges.services.relevance import aggregate_product_relevance
        rows = [
            _Row('document', 0.8),
            _Row('weak', 0.99),       # 广播，必须排除
            _Row('literature', 0.5),
        ]
        # (0.8 + 0.5) / 2 = 0.65
        self.assertAlmostEqual(aggregate_product_relevance(rows), 0.65, places=9)

    def test_all_weak_returns_none(self):
        from apps.bridges.services.relevance import aggregate_product_relevance
        rows = [_Row('weak', 0.9), _Row('weak', 0.3)]
        self.assertIsNone(aggregate_product_relevance(rows))

    def test_skips_none_scores(self):
        from apps.bridges.services.relevance import aggregate_product_relevance
        rows = [_Row('document', None), _Row('document', 0.6)]
        self.assertAlmostEqual(aggregate_product_relevance(rows), 0.6, places=9)

    def test_operator_passthrough_max(self):
        from apps.bridges.services.relevance import aggregate_product_relevance
        rows = [_Row('document', 0.2), _Row('literature', 0.9), _Row('document', 0.6)]
        self.assertAlmostEqual(
            aggregate_product_relevance(rows, operator='max'), 0.9, places=9)


# ── 组 C：update_product_aggregate（落库，仅 non-weak）──
class UpdateProductAggregateTest(TestCase):
    def _make_product_with_pp(self, specs):
        """specs = [(tier, relevance_score), ...]；返回 product。"""
        p = ProductFactory()
        for tier, score in specs:
            proto = ProtocolFactory()
            ProductProtocolFactory(
                product=p, protocol=proto, tier=tier, relevance_score=score,
                link_source=ProductProtocol.LinkSource.INHERITED,
            )
        return p

    def test_persists_excluding_weak(self):
        from apps.bridges.services.relevance import update_product_aggregate
        p = self._make_product_with_pp([
            ('document', 0.8), ('literature', 0.5), ('weak', 0.99),
        ])
        update_product_aggregate(p)
        p.refresh_from_db()
        # (0.8 + 0.5) / 2 = 0.65；weak 0.99 不计入
        self.assertAlmostEqual(p.aggregate_relevance_score, 0.65, places=9)

    def test_none_when_only_weak(self):
        from apps.bridges.services.relevance import update_product_aggregate
        p = self._make_product_with_pp([('weak', 0.9)])
        update_product_aggregate(p)
        p.refresh_from_db()
        self.assertIsNone(p.aggregate_relevance_score)

    def test_idempotent(self):
        from apps.bridges.services.relevance import update_product_aggregate
        p = self._make_product_with_pp([('document', 0.4), ('literature', 0.8)])
        update_product_aggregate(p)
        p.refresh_from_db()
        first = p.aggregate_relevance_score
        # 改一行后再算，应当反映新值（幂等=可重复，结果随数据更新）
        ProductProtocol.objects.filter(product=p, tier='document').update(relevance_score=0.2)
        update_product_aggregate(p)
        p.refresh_from_db()
        second = p.aggregate_relevance_score
        self.assertNotEqual(first, second)
        # (0.2 + 0.8) / 2 = 0.5
        self.assertAlmostEqual(second, 0.5, places=9)


# ── 组 D：ProductViewSet.ordering_fields 含聚合分面 ──
class OrderingFieldTest(TestCase):
    def test_ordering_field_present(self):
        from apps.commerce.api.v1.views import ProductViewSet
        self.assertIn('aggregate_relevance_score', ProductViewSet.ordering_fields)


# ── 组 E：ProductListSerializer 暴露聚合分 ──
class SerializerExposesAggregateTest(TestCase):
    def test_serializer_field_present(self):
        from apps.commerce.api.v1.serializers import ProductListSerializer
        self.assertIn('aggregate_relevance_score', ProductListSerializer.Meta.fields)


# ── 组 F：端到端 API 排序（?ordering=aggregate_relevance_score 升序）──
class ApiOrderingTest(TestCase):
    def _seed(self, score):
        from apps.bridges.services.relevance import update_product_aggregate
        p = ProductFactory(status='active')
        proto = ProtocolFactory()
        ProductProtocolFactory(
            product=p, protocol=proto, tier='document', relevance_score=score,
            link_source=ProductProtocol.LinkSource.INHERITED,
        )
        update_product_aggregate(p)
        return p

    def test_ordering_query_sorts_ascending(self):
        from django.test import Client
        from django.urls import reverse
        # 三个商品，聚合分 0.9 / 0.2 / 0.6（均 non-weak，无 null 排序歧义）
        self._seed(0.9)
        self._seed(0.2)
        self._seed(0.6)

        User = get_user_model()
        staff = User.objects.create_user(
            username='s5_staff', password='x', is_staff=True, is_superuser=False)
        client = Client()
        client.force_login(staff)

        resp = client.get(reverse('product-list') + '?ordering=aggregate_relevance_score')
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()['data']
        scores = [r['aggregate_relevance_score'] for r in rows]
        # 升序：0.2, 0.6, 0.9
        self.assertEqual(scores, sorted(scores))
        self.assertEqual(scores, [0.2, 0.6, 0.9])
