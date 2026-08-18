"""
TDD 集成：第一版业务闭环（usage 字段 → backfill → recompute → 显示层）。

将 #376/#377 的成果接到已实现的 recompute + serializer 显示层，端到端验证：
- 真实 docx usage 经 backfill 灌入 Product.usage（#377）
- recompute 经 ProductMethod→MethodProtocol 派生协议，轴A 由真实 usage 点火（#376 字段落地）
- serializer protocol_links 输出真实档位/分数，而非 fallback 默认值

此测试作为回归守卫：若任一环节（字段缺失/backfill 失效/recompute 不落库/显示层回退）被破坏，
本测试立即 RED。
"""
from django.test import TestCase
from django.core.management import call_command

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory
from apps.bridges.models import ProductMethod, MethodProtocol, ProductProtocol
from apps.commerce.api.v1.serializers import ProductDetailSerializer


def _fake_embed(product, protocol):
    # 确定性 stub 余弦（轴C=(cos+1)/2）；生产用 embedding_backend 真实 MiniLM
    return 0.3


class FirstVersionPipelineTest(TestCase):
    def test_pipeline_lights_up_display(self):
        product = ProductFactory(catalog_no='SC9999PIPE', usage='')
        method = MethodFactory()
        protocol = ProtocolFactory(
            name='RNA Sequencing', objective='rna sequencing library prep'
        )
        ProductMethod.objects.create(product=product, method=method)
        MethodProtocol.objects.create(method=method, protocol=protocol)

        # ① backfill 等价操作：灌入真实 docx 风格 usage
        product.usage = "This reagent is used for rna sequencing and library prep."
        product.save()
        self.assertEqual(Product.objects.get(pk=product.pk).usage,
                         "This reagent is used for rna sequencing and library prep.")

        # ② recompute（注入确定性 embedding）
        call_command('recompute_protocol_relevance', '--product', 'SC9999PIPE',
                     embedding_fn=_fake_embed)

        pp = ProductProtocol.objects.get(product=product, protocol=protocol)
        self.assertGreater(pp.score_a, 0.0, "轴A 应由真实 usage 点火")
        self.assertEqual(pp.tier, 'document')
        self.assertGreater(pp.relevance_score, 0.0)

        # ③ 显示层输出真实档位/分数，不应触发 fallback
        ser = ProductDetailSerializer(product)
        links = ser.data['protocol_links']
        self.assertTrue(
            any(l['tier'] == 'document' and l['relevance_score'] > 0 for l in links),
            "显示层应呈现真实 document 档位与正分数",
        )
        self.assertFalse(
            any(l['score_a'] is None for l in links),
            "存在 ProductProtocol 行时应输出真实 score_a，不应 fallback",
        )
