"""
TDD RED: ProductProtocol 模型（§14.3 三轴融合持久化）。

这些测试在「实现前」定义 ProductProtocol 的期望行为；运行时应全部 FAIL
（ImportError / 无表 / 字段缺失），直到 #352 实现模型 + 迁移后转 GREEN。

期望 schema（来自设计稿 §14.3 + 决策 Q2 link_source）：
- product / protocol FK，related_name 分别为 protocol_links / product_protocols
- relevance_score FloatField(db_index=True)  三轴融合总分（驱动排序/TopN）
- score_a / score_b / score_c FloatField(null=True)  三轴分量（UI 透明 + 闸门）
- relevance_basis CharField  'vendor_only' | 'bioz_aligned' | 'embedding_break' | 'combined'
- link_source CharField     'explicit' | 'inherited' | 'auto'
- tier CharField            'document' | 'literature' | 'featured'(历史) | 'weak'(S4 默认/广播桶)
- literature_count IntegerField(default=0)   文献×N 徽标
- computed_at DateTimeField(auto_now=True)
- Meta: db_table='product_protocol'; unique_together=[('product','protocol')]
"""
from django.test import TestCase
from django.db import IntegrityError

from apps.bridges.tests.factories import ProductProtocolFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import ProtocolFactory


class ProductProtocolModelTest(TestCase):
    def test_model_importable(self):
        """ProductProtocol 模型必须存在且可导入（RED→GREEN 的导入闸门）。"""
        from apps.bridges.models import ProductProtocol  # noqa: F401

    def test_create_with_all_fields(self):
        from apps.bridges.models import ProductProtocol
        product = ProductFactory()
        protocol = ProtocolFactory()
        pp = ProductProtocol.objects.create(
            product=product,
            protocol=protocol,
            relevance_score=0.42,
            score_a=0.50,
            score_b=0.10,
            score_c=0.20,
            relevance_basis='vendor_only',
            link_source='inherited',
            tier='document',
            literature_count=0,
        )
        self.assertEqual(pp.product, product)
        self.assertEqual(pp.protocol, protocol)
        self.assertAlmostEqual(pp.relevance_score, 0.42)
        self.assertAlmostEqual(pp.score_a, 0.50)
        self.assertAlmostEqual(pp.score_b, 0.10)
        self.assertAlmostEqual(pp.score_c, 0.20)
        self.assertEqual(pp.relevance_basis, 'vendor_only')
        self.assertEqual(pp.link_source, 'inherited')
        self.assertEqual(pp.tier, 'document')
        self.assertEqual(pp.literature_count, 0)

    def test_unique_together_product_protocol(self):
        from apps.bridges.models import ProductProtocol
        product = ProductFactory()
        protocol = ProtocolFactory()
        ProductProtocol.objects.create(product=product, protocol=protocol,
                                      relevance_score=0.1)
        with self.assertRaises(IntegrityError):
            ProductProtocol.objects.create(product=product, protocol=protocol,
                                          relevance_score=0.2)

    def test_factory_builds(self):
        pp = ProductProtocolFactory()
        self.assertIsNotNone(pp.pk)
        self.assertIsNotNone(pp.product_id)
        self.assertIsNotNone(pp.protocol_id)

    def test_defaults(self):
        from apps.bridges.models import ProductProtocol
        product = ProductFactory()
        protocol = ProtocolFactory()
        pp = ProductProtocol.objects.create(product=product, protocol=protocol)
        # 未提供时：relevance_score 应有默认 0，link_source 默认 inherited，tier 默认 weak（S4）
        self.assertAlmostEqual(pp.relevance_score, 0.0)
        self.assertEqual(pp.link_source, 'inherited')
        self.assertEqual(pp.tier, 'weak')
        self.assertEqual(pp.literature_count, 0)
        self.assertIsNone(pp.score_a)
        self.assertIsNone(pp.score_b)
        self.assertIsNone(pp.score_c)

    def test_link_source_choices(self):
        from apps.bridges.models import ProductProtocol
        choices = dict(ProductProtocol.LinkSource.choices)
        self.assertIn('explicit', choices)
        self.assertIn('inherited', choices)
        self.assertIn('auto', choices)

    def test_tier_choices(self):
        from apps.bridges.models import ProductProtocol
        choices = dict(ProductProtocol.Tier.choices)
        self.assertIn('document', choices)
        self.assertIn('literature', choices)
        self.assertIn('featured', choices)

    def test_basis_choices(self):
        from apps.bridges.models import ProductProtocol
        choices = dict(ProductProtocol.Basis.choices)
        self.assertIn('vendor_only', choices)
        self.assertIn('bioz_aligned', choices)
        self.assertIn('embedding_break', choices)
        self.assertIn('combined', choices)

    def test_relevance_score_indexed(self):
        from apps.bridges.models import ProductProtocol
        indexed = [i for i in ProductProtocol._meta.indexes
                   if any(f == 'relevance_score' for f in i.fields)]
        self.assertTrue(len(indexed) >= 1, "relevance_score 必须建索引以驱动排序")

    def test_related_name_product(self):
        from apps.bridges.models import ProductProtocol
        product = ProductFactory()
        protocol = ProtocolFactory()
        ProductProtocol.objects.create(product=product, protocol=protocol)
        self.assertEqual(product.protocol_links.count(), 1)

    def test_related_name_protocol(self):
        from apps.bridges.models import ProductProtocol
        product = ProductFactory()
        protocol = ProtocolFactory()
        ProductProtocol.objects.create(product=product, protocol=protocol)
        self.assertEqual(protocol.product_protocols.count(), 1)

    def test_table_name(self):
        from apps.bridges.models import ProductProtocol
        self.assertEqual(ProductProtocol._meta.db_table, 'product_protocol')

    def test_str_contains_protocol(self):
        from apps.bridges.models import ProductProtocol
        product = ProductFactory()
        protocol = ProtocolFactory(name='RNA Probe Protocol')
        pp = ProductProtocol.objects.create(product=product, protocol=protocol)
        self.assertIn('RNA Probe Protocol', str(pp))
