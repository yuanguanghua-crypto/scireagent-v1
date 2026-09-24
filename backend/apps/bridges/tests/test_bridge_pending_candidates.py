"""★ P1-a′ 回归闸门（2026-09-24）：桥回退候选的**打分**与**公开路径隔离**。

背景（全部为实测事实）：
- 产品 `ProductProtocol` 表为 0 行时，`build_protocol_links` 走 **MethodProtocol 桥回退**
  （`tier='weak'`、`score=0`）⇒ 编辑页第 5 节所有候选**全无分数**，无法按匹配度排序。
- 实测（dev 夹具，753 条桥）：strong=0 而 weak=753 ⇒ 前端只渲染 `None`，
  753 条全在默认收起的「弱相关」里（P0 已修文案；本闸门锁 P1-a′ 的分与排序）。

P1-a′ 的设计约束（本文件逐条锁死）：
1. **默认关闭**：`build_protocol_links(product)` 必须**保持原行为**（全 weak、无 pending）
   —— 因为 `ProductDetailAPIView`（公开聚合详情）与 v2 序列化器都用默认参数 ⇒ 公开页零变化。
2. **只有编辑页开启**：`ProductDetailSerializer.get_protocol_links` 传 `compute_pending=True`。
3. **只读**：绝不写 `ProductProtocol`（落库与否由 `367e5f4` 的证据口径管，本函数不越界）。
4. **诚实标注**：升级行必须带 `pending=True`（前端据此显示"候选 · 未落库"），
   因为 `P` 的取法（`usage` 空时回退 `name`）与 `compute_axis_a` 的正式口径不完全一致。
5. **无命中即无操作**：`P` 为空（品名/usage 未命中词表）⇒ 返回 `{}` ⇒ 行为与改动前逐字相同。
"""
from django.test import TestCase

from apps.bridges.models import MethodProtocol, ProductMethod, ProductProtocol
from apps.bridges.services.relevance import build_protocol_links
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Method, Protocol

LINK = ProductProtocol.LinkSource
TIER = ProductProtocol.Tier


class BridgePendingCandidatesTest(TestCase):
    """`compute_pending` 的开关语义与只读性。"""

    def setUp(self):
        # 品名命中词表（`pcr` 在 domain_vocab 里）⇒ P 非空
        self.product = ProductFactory(name='PCR primer labeling kit', catalog_no='E2E-P1A-1')
        self.method = Method.objects.create(name='P1A Method', slug='p1a-method', status='active')
        # 协议侧文本也命中 `pcr` ⇒ Q 非空、P∩Q 非空 ⇒ S_A > 0
        self.protocol = Protocol.objects.create(
            name='PCR amplification protocol', slug='p1a-protocol', status='published',
            objective='pcr primer extension',
        )
        ProductMethod.objects.create(product=self.product, method=self.method)
        MethodProtocol.objects.create(method=self.method, protocol=self.protocol)

    # ── 约束 1：默认关闭必须与改动前一致 ──────────────────────────────
    def test_default_off_keeps_all_weak_and_no_pending(self):
        rows = build_protocol_links(self.product)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r['tier'], TIER.WEAK)
        self.assertEqual(r['relevance_score'], 0.0)
        self.assertIsNone(r['score_a'])
        self.assertNotIn('pending', r)

    # ── 约束 2/4：开启后升级为 document 且标注 pending ────────────────
    def test_compute_pending_upgrades_matching_row(self):
        rows = build_protocol_links(self.product, compute_pending=True)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r['tier'], TIER.DOCUMENT, 'P∩Q 非空 ⇒ 轴A 有值 ⇒ 应为 document')
        self.assertTrue(r['pending'], '升级行必须带 pending=True（候选·未落库）')
        self.assertGreater(r['score_a'] or 0.0, 0.0)
        self.assertGreater(r['relevance_score'] or 0.0, 0.0)
        self.assertEqual(r['relevance_basis'], 'vendor_only')

    # ── 约束 5：P 为空 ⇒ 完全不动 ─────────────────────────────────────
    def test_compute_pending_noop_when_name_has_no_vocab_term(self):
        p2 = ProductFactory(name='ZZZ unknown thing', catalog_no='E2E-P1A-2')
        ProductMethod.objects.create(product=p2, method=self.method)
        rows = build_protocol_links(p2, compute_pending=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tier'], TIER.WEAK)
        self.assertNotIn('pending', rows[0])

    # ── 约束 3：只读，绝不写 ProductProtocol ──────────────────────────
    def test_does_not_write_productprotocol(self):
        self.assertEqual(ProductProtocol.objects.filter(product=self.product).count(), 0)
        build_protocol_links(self.product, compute_pending=True)
        self.assertEqual(
            ProductProtocol.objects.filter(product=self.product).count(), 0,
            'P1-a′ 只展示、绝不落库',
        )

    # ── 契约：PP 表非空时回退分支不介入（既有"只回落库真实行"口径不变）──
    def test_pp_rows_present_path_untouched(self):
        ProductProtocol.objects.create(
            product=self.product, protocol=self.protocol, link_source=LINK.AUTO,
            relevance_score=0.83, score_a=0.9, score_b=0.0, score_c=0.5,
            tier=TIER.DOCUMENT, relevance_basis='vendor_only', literature_count=0,
        )
        rows = build_protocol_links(self.product, compute_pending=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['relevance_score'], 0.83)
        self.assertEqual(rows[0]['link_source'], 'auto')
        self.assertNotIn('pending', rows[0], 'PP>0 ⇒ 走主源，不标 pending')

    # ── 编辑页序列化器确实开了；公开视图保持默认（源码级锁定）──────────
    def test_edit_serializer_enables_and_public_view_does_not(self):
        import inspect

        from apps.commerce.api.v1 import serializers as S
        from apps.commerce.api.v1 import views as V

        src_ser = inspect.getsource(S.ProductDetailSerializer.get_protocol_links)
        self.assertIn('compute_pending=True', src_ser, '编辑页序列化器必须开启候选打分')

        src_view = inspect.getsource(V.ProductDetailAPIView.get)
        self.assertIn('build_protocol_links(product)', src_view,
                      '公开聚合详情必须用默认参数（不开候选打分）')
        self.assertNotIn('compute_pending', src_view, '公开聚合详情不得开启候选打分')
