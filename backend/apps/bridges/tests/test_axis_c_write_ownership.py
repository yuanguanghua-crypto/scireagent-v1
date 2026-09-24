"""轴C 写权归属（R2，2026-09-24）。

契约：
1. **运行时路径**（未注入 embedding_fn 且本机后端不可用）⇒ **保留**库中 `score_c`，
   **绝不**写 embedding 哨兵 0.5（否则每次产品保存都会抹平离线算好的值）。
   新行则留 `None`，等离线作业补算。
2. **离线路径**（注入 `embedding_fn`）⇒ 计算并写真实 `score_c`。
3. `fuse_relevance` 在 `score_c is None`（缺测）时按可用轴 (A,B) **重归一化**权重；
   而显式 `0.0`（有值且为零）仍参与权重 —— 二者语义不同。
4. `tier` 判定**只看** A/B，与 C 无关（口径与环境无关）。
"""
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.bridges.models import MethodProtocol, ProductMethod, ProductProtocol
from apps.bridges.services.relevance import fuse_relevance
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory

_REL = 'apps.bridges.services.relevance.compute_axis_a'
_AVAIL = 'apps.bridges.services.embedding_backend.embedding_available'


class FuseNoneRenormalizeTest(TestCase):
    def test_c_none_renormalizes_over_ab(self):
        r = fuse_relevance(score_a=0.8, score_b=0.0, score_c=None)
        # (0.70*0.8 + 0.10*0) / 0.80 = 0.70
        self.assertAlmostEqual(r['relevance_score'], 0.70, places=6)
        self.assertIsNone(r['score_c'])

    def test_explicit_zero_c_keeps_weights(self):
        r = fuse_relevance(score_a=0.8, score_b=0.0, score_c=0.0)
        # 0.70*0.8 = 0.56（C 有值且为零，仍占 0.20 权重）
        self.assertAlmostEqual(r['relevance_score'], 0.56, places=6)
        self.assertEqual(r['score_c'], 0.0)

    def test_c_none_is_not_worse_than_zero(self):
        # 缺测不该被当成"语义为零"惩罚
        a = fuse_relevance(score_a=0.8, score_b=0.0, score_c=None)['relevance_score']
        b = fuse_relevance(score_a=0.8, score_b=0.0, score_c=0.0)['relevance_score']
        self.assertGreater(a, b)

    def test_tier_independent_of_c(self):
        for c in (None, 0.0, 0.5, 0.9):
            self.assertEqual(
                fuse_relevance(score_a=0.5, score_b=0.0, score_c=c)['tier'], 'document')
            self.assertEqual(
                fuse_relevance(score_a=0.0, score_b=0.0, score_c=c)['tier'], 'weak')


class RuntimePreservesScoreCTest(TestCase):
    def _chain(self, existing_c=None):
        product = ProductFactory()
        method = MethodFactory()
        protocol = ProtocolFactory()
        ProductMethod.objects.create(product=product, method=method)
        MethodProtocol.objects.create(method=method, protocol=protocol)
        if existing_c is not None:
            ProductProtocol.objects.create(
                product=product, protocol=protocol,
                relevance_score=0.50, score_a=0.5, score_b=0.0, score_c=existing_c,
                tier='document', link_source=ProductProtocol.LinkSource.INHERITED,
            )
        return product

    def test_runtime_preserves_existing_score_c(self):
        product = self._chain(existing_c=0.777)
        with mock.patch(_REL, return_value=0.5), \
                mock.patch(_AVAIL, return_value=False):
            call_command('recompute_protocol_relevance', '--product', str(product.id))
        row = ProductProtocol.objects.get(product=product)
        self.assertAlmostEqual(row.score_c, 0.777, places=6)   # ★ 未被哨兵抹平
        self.assertEqual(row.tier, 'document')

    def test_runtime_leaves_c_null_for_new_row(self):
        product = self._chain(existing_c=None)
        with mock.patch(_REL, return_value=0.5), \
                mock.patch(_AVAIL, return_value=False):
            call_command('recompute_protocol_relevance', '--product', str(product.id))
        row = ProductProtocol.objects.get(product=product)
        self.assertIsNone(row.score_c)                          # 不写假 0.5

    def test_offline_injection_writes_real_c(self):
        product = self._chain(existing_c=0.777)
        with mock.patch(_REL, return_value=0.5):
            call_command('recompute_protocol_relevance', '--product', str(product.id),
                         embedding_fn=lambda p, pr: 0.6)        # score_c=(0.6+1)/2=0.8
        row = ProductProtocol.objects.get(product=product)
        self.assertAlmostEqual(row.score_c, 0.80, places=6)     # 离线路径覆盖为真值

    def test_relevance_consistent_with_stored_c(self):
        # 保留旧 C 后，落库 relevance 必须是**用旧 C** 算的（不能拿哨兵算）
        product = self._chain(existing_c=0.777)
        with mock.patch(_REL, return_value=0.5), \
                mock.patch(_AVAIL, return_value=False):
            call_command('recompute_protocol_relevance', '--product', str(product.id))
        row = ProductProtocol.objects.get(product=product)
        expected = 0.70 * 0.5 + 0.10 * 0.0 + 0.20 * 0.777
        self.assertAlmostEqual(row.relevance_score, expected, places=6)
