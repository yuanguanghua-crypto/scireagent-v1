"""
TDD RED: 三轴融合打分 + recompute 命令（§14 + 决策 Q4 轴C离线持久化）。

运行时应 FAIL（relevance 服务模块 / fuse_relevance / recompute 命令尚未实现），
直至 #353 实现后转 GREEN。

核心契约：
- fuse_relevance(S_A, S_B, S_C) = 0.70*S_A + 0.10*S_B + 0.20*S_C  （权重和=1）
- 轴B 硬上限：wB=0.10，S_B 再高，其对总分的贡献封顶 0.10（#338 稀疏实证不喧宾夺主）
- relevance_basis 映射：S_B>0 & S_A>0→combined；S_B>0 & S_A==0→bioz_aligned；
                       S_A>0 & S_B==0→vendor_only；二者皆0→embedding_break
- tier 映射：S_B>0→literature；S_A>0→document；二者皆0→weak（S4 起，原 featured）
- recompute_protocol_relevance 命令：为产品落/更新 ProductProtocol 行；幂等；
  轴C(score_c) 离线持久化（embedding 经由可注入 embedding_fn 计算，便于测试）
"""
from django.test import TestCase
from django.core.management import call_command

from apps.bridges.models import ProductProtocol
from apps.bridges.tests.factories import ProductProtocolFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory


def _make_product_with_usage(usage):
    """轴A 地基（docx 厂商声称用途）在 §13 决策中仍冻结未落库，Product 尚无 usage 字段。

    测试仅验证轴A 的「用途×协议领域词」重叠检测逻辑，故在内存实例上挂载 usage
    属性（compute_axis_a 经 getattr 读取，无字段时返回 None 诚实不冒充），
    不触及 Product schema（避免与冻结决策冲突）。
    """
    p = ProductFactory()
    p.usage = usage
    return p


class FuseRelevanceTest(TestCase):
    def test_importable(self):
        from apps.bridges.services import relevance  # noqa: F401

    def test_formula_pure_weights(self):
        """0.70*A + 0.10*B + 0.20*C 精确值。"""
        from apps.bridges.services.relevance import fuse_relevance
        r = fuse_relevance(score_a=0.50, score_b=0.0, score_c=0.20)
        # 0.70*0.5 + 0.10*0 + 0.20*0.2 = 0.35 + 0.0 + 0.04 = 0.39
        self.assertAlmostEqual(r['relevance_score'], 0.39, places=6)
        self.assertAlmostEqual(r['score_a'], 0.50)
        self.assertAlmostEqual(r['score_b'], 0.0)
        self.assertAlmostEqual(r['score_c'], 0.20)

    def test_weights_sum_to_one(self):
        from apps.bridges.services.relevance import WEIGHTS
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0, places=6)

    def test_axis_b_hard_cap(self):
        """S_B 即便=1（文献数远超上限），对总分贡献封顶 0.10。"""
        from apps.bridges.services.relevance import fuse_relevance
        r = fuse_relevance(score_a=0.0, score_b=1.0, score_c=0.0)
        # 0.10*1.0 = 0.10，绝不超过
        self.assertAlmostEqual(r['relevance_score'], 0.10, places=6)
        self.assertAlmostEqual(r['score_b'], 1.0)  # 分量仍如实记录
        self.assertLessEqual(r['relevance_score'], 0.10 + 1e-9)

    def test_basis_combined(self):
        from apps.bridges.services.relevance import fuse_relevance
        r = fuse_relevance(score_a=0.4, score_b=0.2, score_c=0.1)
        self.assertEqual(r['relevance_basis'], 'combined')
        self.assertEqual(r['tier'], 'literature')

    def test_basis_bioz_aligned(self):
        from apps.bridges.services.relevance import fuse_relevance
        r = fuse_relevance(score_a=0.0, score_b=0.3, score_c=0.0)
        self.assertEqual(r['relevance_basis'], 'bioz_aligned')
        self.assertEqual(r['tier'], 'literature')

    def test_basis_vendor_only(self):
        from apps.bridges.services.relevance import fuse_relevance
        r = fuse_relevance(score_a=0.6, score_b=0.0, score_c=0.0)
        self.assertEqual(r['relevance_basis'], 'vendor_only')
        self.assertEqual(r['tier'], 'document')

    def test_basis_embedding_break(self):
        from apps.bridges.services.relevance import fuse_relevance
        r = fuse_relevance(score_a=0.0, score_b=0.0, score_c=0.3)
        self.assertEqual(r['relevance_basis'], 'embedding_break')
        self.assertEqual(r['tier'], 'weak')

    def test_no_signal(self):
        from apps.bridges.services.relevance import fuse_relevance
        r = fuse_relevance(score_a=0.0, score_b=0.0, score_c=0.0)
        self.assertAlmostEqual(r['relevance_score'], 0.0)
        self.assertEqual(r['tier'], 'weak')


class AxisAFeatureTest(TestCase):
    """轴A：docx 用途(P) × 协议领域词(Q) F-score（§4/§14.1）。"""

    def test_axis_a_extracts_overlap(self):
        """产品用途含 rna/sequencing，协议名含 sequencing → S_A>0。"""
        from apps.bridges.services.relevance import compute_axis_a
        product = _make_product_with_usage(
            "This reagent is used for rna sequencing and library prep.")
        protocol = ProtocolFactory(name="RNA Sequencing Protocol",
                                   objective="sequencing of rna and ngs library prep")
        s_a = compute_axis_a(product, protocol)
        self.assertGreater(s_a, 0.0)
        self.assertLessEqual(s_a, 1.0)

    def test_axis_a_no_usage_is_none(self):
        from apps.bridges.services.relevance import compute_axis_a
        product = ProductFactory()  # usage 为空
        protocol = ProtocolFactory(name="RNA Sequencing")
        self.assertIsNone(compute_axis_a(product, protocol))


class AxisBTypicalityTest(TestCase):
    """轴B：Bioz 协议级对齐（B1 修复）；count 经上限归一，贡献封顶。"""

    def test_axis_b_zero_when_no_bioz(self):
        from apps.bridges.services.relevance import compute_axis_b
        product = ProductFactory()
        protocol = ProtocolFactory()
        s_b, lit_n = compute_axis_b(product, protocol, bioz_lits=[])
        self.assertEqual(s_b, 0.0)
        self.assertEqual(lit_n, 0)

    def test_axis_b_capped_at_one(self):
        from apps.bridges.services.relevance import compute_axis_b, BIOZ_TYP_CAP
        product = ProductFactory()
        protocol = ProtocolFactory(name="RNA Sequencing Protocol",
                                   objective="rna sequencing and ngs")
        # 10 条均含 rna/sequencing 的文献；超过 BIOZ_TYP_CAP(=5) 应封顶为 1
        lits = [{"article_title": "study of rna sequencing",
                 "techniques": "rna sequencing",
                 "long": "", "medium": "", "short": ""} for _ in range(10)]
        s_b, lit_n = compute_axis_b(product, protocol, bioz_lits=lits)
        self.assertEqual(lit_n, 10)
        self.assertAlmostEqual(s_b, 1.0)
        self.assertLessEqual(s_b, 1.0)


class RecomputeCommandTest(TestCase):
    """recompute_protocol_relevance 命令：落/更新 ProductProtocol，幂等，轴C 持久化。"""

    def test_command_runs_and_creates_rows(self):
        product = ProductFactory()
        method = MethodFactory()
        protocol = ProtocolFactory(method=method)
        from apps.bridges.models import ProductMethod, MethodProtocol
        ProductMethod.objects.create(product=product, method=method)
        MethodProtocol.objects.create(method=method, protocol=protocol)

        # 注入确定性 embedding_fn：返回基于 (product_id, protocol_id) 的稳定值
        def fake_embed(product, protocol):
            return ((product.id * 7 + protocol.id * 13) % 100) / 100.0

        call_command('recompute_protocol_relevance',
                     '--product', product.catalog_no or str(product.id),
                     embedding_fn=fake_embed)

        pp = ProductProtocol.objects.filter(product=product, protocol=protocol).first()
        self.assertIsNotNone(pp, "recompute 应为派生协议落 ProductProtocol 行")


class RecomputeIdempotentTest(TestCase):
    def test_recompute_idempotent(self):
        product = ProductFactory()
        method = MethodFactory()
        protocol = ProtocolFactory(method=method)
        from apps.bridges.models import ProductMethod, MethodProtocol
        ProductMethod.objects.create(product=product, method=method)
        MethodProtocol.objects.create(method=method, protocol=protocol)

        def fake_embed(product, protocol):
            return 0.33

        for _ in range(2):
            call_command('recompute_protocol_relevance',
                         '--product', str(product.id),
                         embedding_fn=fake_embed)

        # 幂等：唯一对约束，不应出现重复行
        count = ProductProtocol.objects.filter(product=product).count()
        self.assertEqual(count, 1)
