"""
TDD RED: ProductDetailSerializer.protocol_links 排序 + 内联摘要（#355）。

定义编辑页/详情页所需的数据契约：
- ProductDetailSerializer 新增 `protocol_links`，为派生协议集按
  tier(literature>document>featured) → relevance_score 降 → score_c 降 排序后的
  内联摘要列表：
  [{id, name, slug, relevance_score, score_a, score_b, score_c,
    relevance_basis, link_source, tier, literature_count}]
- 铁律①：即便产品尚无 ProductProtocol 行（recompute 未跑），也必须返回全部派生协议
  （回退 tier='weak' [S4]、relevance_score=0、link_source='inherited'、basis=''），不得丢数据。
- `protocol_ids` 保持向后兼容（仍为 id 列表）。

运行时应 FAIL（serializer 尚无 protocol_links 字段 / 排序未实现），
直至 #355 实现后转 GREEN。
"""
from django.test import TestCase

from apps.commerce.api.v1.serializers import ProductDetailSerializer
from apps.commerce.models import Product
from apps.bridges.models import ProductMethod, MethodProtocol, ProductProtocol
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory


def _build_product_with_protocols(n=3):
    product = ProductFactory()
    method = MethodFactory()
    ProductMethod.objects.create(product=product, method=method)
    protocols = []
    for i in range(n):
        p = ProtocolFactory(name=f"Protocol {i}")
        MethodProtocol.objects.create(method=method, protocol=p)
        protocols.append(p)
    return product, protocols


class ProtocolLinksSerializerTest(TestCase):
    def test_protocol_links_field_present(self):
        product, _ = _build_product_with_protocols()
        data = ProductDetailSerializer(product).data
        self.assertIn('protocol_links', data)

    def test_protocol_links_is_list_of_dicts_with_keys(self):
        product, protocols = _build_product_with_protocols()
        data = ProductDetailSerializer(product).data
        links = data['protocol_links']
        self.assertIsInstance(links, list)
        self.assertEqual(len(links), len(protocols))
        keys = {'id', 'name', 'slug', 'relevance_score', 'score_a', 'score_b',
                'score_c', 'relevance_basis', 'link_source', 'tier'}
        for item in links:
            self.assertTrue(keys.issubset(set(item.keys())),
                            f"缺少字段: {keys - set(item.keys())}")

    def test_fallback_when_no_productprotocol_rows(self):
        """recompute 未跑：仍返回全部派生协议，回退 weak/inherited/score=0（S4 默认 weak）。"""
        product, protocols = _build_product_with_protocols()
        self.assertEqual(ProductProtocol.objects.filter(product=product).count(), 0)
        data = ProductDetailSerializer(product).data
        links = data['protocol_links']
        self.assertEqual(len(links), len(protocols))  # 铁律①不丢数据
        for item in links:
            self.assertEqual(item['tier'], 'weak')
            self.assertEqual(item['link_source'], 'inherited')
            self.assertAlmostEqual(item['relevance_score'], 0.0)
            self.assertEqual(item['relevance_basis'], '')

    def test_sort_by_tier_then_relevance(self):
        """literature 档位恒排 document/featured 之前；同档内按 relevance_score 降。"""
        product, protocols = _build_product_with_protocols(3)
        # 手工写三档：p0 literature(高)、p1 document(中)、p2 featured(0)
        ProductProtocol.objects.create(
            product=product, protocol=protocols[0],
            relevance_score=0.9, tier='literature', link_source='inherited',
            relevance_basis='combined')
        ProductProtocol.objects.create(
            product=product, protocol=protocols[1],
            relevance_score=0.5, tier='document', link_source='inherited',
            relevance_basis='vendor_only')
        ProductProtocol.objects.create(
            product=product, protocol=protocols[2],
            relevance_score=0.0, tier='featured', link_source='inherited',
            relevance_basis='')
        data = ProductDetailSerializer(product).data
        order = [item['tier'] for item in data['protocol_links']]
        self.assertEqual(order, ['literature', 'document', 'featured'])

    def test_same_tier_sorted_by_relevance_desc(self):
        product, protocols = _build_product_with_protocols(2)
        ProductProtocol.objects.create(
            product=product, protocol=protocols[0],
            relevance_score=0.3, tier='document', link_source='inherited',
            relevance_basis='vendor_only')
        ProductProtocol.objects.create(
            product=product, protocol=protocols[1],
            relevance_score=0.8, tier='document', link_source='inherited',
            relevance_basis='vendor_only')
        data = ProductDetailSerializer(product).data
        scores = [item['relevance_score'] for item in data['protocol_links']]
        self.assertEqual(scores, [0.8, 0.3])

    def test_protocol_ids_backward_compatible(self):
        product, protocols = _build_product_with_protocols()
        data = ProductDetailSerializer(product).data
        self.assertIn('protocol_ids', data)
        self.assertIsInstance(data['protocol_ids'], list)
        self.assertEqual(set(data['protocol_ids']), {p.id for p in protocols})

    def test_literature_count_present_and_reflects_model(self):
        """#369：序列化行必须带 literature_count，且等于 ProductProtocol 模型值。"""
        product, protocols = _build_product_with_protocols(1)
        ProductProtocol.objects.create(
            product=product, protocol=protocols[0],
            relevance_score=0.6, tier='literature', link_source='explicit',
            relevance_basis='bioz_aligned', literature_count=5)
        data = ProductDetailSerializer(product).data
        item = data['protocol_links'][0]
        self.assertIn('literature_count', item)
        self.assertEqual(item['literature_count'], 5)

    def test_fallback_literature_count_zero(self):
        """recompute 未跑（无 ProductProtocol 行）：literature_count 回退 0。"""
        product, protocols = _build_product_with_protocols(2)
        self.assertEqual(ProductProtocol.objects.filter(product=product).count(), 0)
        data = ProductDetailSerializer(product).data
        for item in data['protocol_links']:
            self.assertEqual(item['literature_count'], 0)

    def test_auto_links_unioned_with_inherited(self):
        """#403 落地回归：AUTO 自动匹配链接必须并入 protocol_links（与继承链并集，不裁剪）。"""
        product, protocols = _build_product_with_protocols(2)
        ProductProtocol.objects.create(
            product=product, protocol=protocols[0],
            relevance_score=0.6, tier='document', link_source='inherited',
            relevance_basis='vendor_only')
        # 一个不在继承链中的 AUTO 自动匹配协议
        auto_proto = ProtocolFactory(name="Auto BioProCorpus Protocol")
        ProductProtocol.objects.create(
            product=product, protocol=auto_proto,
            relevance_score=0.9, tier='document', link_source='auto',
            relevance_basis='vendor_only')
        data = ProductDetailSerializer(product).data
        links = data['protocol_links']
        ids = {item['id'] for item in links}
        self.assertIn(auto_proto.id, ids)            # AUTO 已并入
        self.assertIn(protocols[0].id, ids)          # 继承链仍在（铁律①不删链）
        auto_item = next(it for it in links if it['id'] == auto_proto.id)
        self.assertEqual(auto_item['link_source'], 'auto')
        self.assertAlmostEqual(auto_item['relevance_score'], 0.9)

    def test_sort_tertiary_by_score_c(self):
        """#357 回归：同档、同 relevance 时，按 score_c 降序（第三级排序键）。"""
        product, protocols = _build_product_with_protocols(2)
        # 同档 document、同 relevance 0.5，仅 score_c 不同
        ProductProtocol.objects.create(
            product=product, protocol=protocols[0],
            relevance_score=0.5, score_c=0.2, tier='document',
            link_source='inherited', relevance_basis='vendor_only')
        ProductProtocol.objects.create(
            product=product, protocol=protocols[1],
            relevance_score=0.5, score_c=0.9, tier='document',
            link_source='inherited', relevance_basis='vendor_only')
        data = ProductDetailSerializer(product).data
        links = data['protocol_links']
        self.assertEqual([item['id'] for item in links], [protocols[1].id, protocols[0].id])
        self.assertEqual([item['score_c'] for item in links], [0.9, 0.2])

    def test_auto_only_product_returns_auto_links(self):
        """FIX：AUTO-only 产品（无 ProductMethod 链）必须返回 AUTO 链接，
        不得被 `if not method_ids: return []` 旧 gate 吞掉（#18 产品不可见）。"""
        product = ProductFactory()
        self.assertEqual(ProductMethod.objects.filter(product=product).count(), 0)
        auto_proto = ProtocolFactory(name="Auto BioProCorpus Protocol")
        ProductProtocol.objects.create(
            product=product, protocol=auto_proto,
            relevance_score=0.9, tier='document', link_source='auto',
            relevance_basis='vendor_only')
        data = ProductDetailSerializer(product).data
        links = data['protocol_links']
        self.assertEqual(len(links), 1)                       # 不再吞掉 AUTO
        self.assertEqual(links[0]['id'], auto_proto.id)
        self.assertEqual(links[0]['link_source'], 'auto')
        self.assertAlmostEqual(links[0]['relevance_score'], 0.9)

    def test_pure_explicit_or_inherited_pp_rows_included(self):
        """P2-2：纯 EXPLICIT/INHERITED PP 行（无任何 ProductMethod/MethodProtocol 桥链）必须出现在
        protocol_links。旧 get_protocol_links 仅由 MethodProtocol 桥 ∪ PP AUTO 推导 protocol_ids，
        会丢弃这类纯 PP 行（丢数据缺陷）；收敛到 build_protocol_links（PP 主源）后应可见。"""
        product = ProductFactory()
        explicit_proto = ProtocolFactory(name='Explicit-only Protocol')
        inherited_proto = ProtocolFactory(name='Inherited-only Protocol')
        ProductProtocol.objects.create(
            product=product, protocol=explicit_proto,
            relevance_score=0.8, tier='document', link_source='explicit',
            relevance_basis='vendor_only')
        ProductProtocol.objects.create(
            product=product, protocol=inherited_proto,
            relevance_score=0.7, tier='document', link_source='inherited',
            relevance_basis='vendor_only')
        self.assertEqual(ProductMethod.objects.filter(product=product).count(), 0)
        data = ProductDetailSerializer(product).data
        by_id = {item['id']: item for item in data['protocol_links']}
        self.assertIn(explicit_proto.id, by_id)
        self.assertIn(inherited_proto.id, by_id)
        self.assertEqual(by_id[explicit_proto.id]['link_source'], 'explicit')
        self.assertEqual(by_id[inherited_proto.id]['link_source'], 'inherited')

    def test_sort_full_realistic_ordering(self):
        """#357 回归：真实数据层面跨三档的完整 (-relevance, -score_c, id) 排序断言。"""
        product, protocols = _build_product_with_protocols(5)
        # 制造确定性全键：p0 literature/0.9/0.1, p1 literature/0.7/0.9,
        # p2 literature/0.7/0.4, p3 document/0.6/0.5, p4 featured/0.99/0.99
        spec = [
            (0, 0.9, 0.1, 'literature'),
            (1, 0.7, 0.9, 'literature'),
            (2, 0.7, 0.4, 'literature'),
            (3, 0.6, 0.5, 'document'),
            (4, 0.99, 0.99, 'featured'),
        ]
        for idx, rel, sc, tier in spec:
            ProductProtocol.objects.create(
                product=product, protocol=protocols[idx],
                relevance_score=rel, score_c=sc, tier=tier,
                link_source='inherited', relevance_basis='combined')
        data = ProductDetailSerializer(product).data
        links = data['protocol_links']
        # 去 tier 优先后，全局按 (-relevance, -score_c, id) 排序：
        # p4(0.99) > p0(0.9) > p1(0.7,sc0.9) > p2(0.7,sc0.4) > p3(0.6)
        expected_ids = [protocols[i].id for i in (4, 0, 1, 2, 3)]
        self.assertEqual([item['id'] for item in links], expected_ids)
        # relevance 降序（等 relevance 时按 score_c 降序）
        self.assertEqual([item['relevance_score'] for item in links], [0.99, 0.9, 0.7, 0.7, 0.6])
        self.assertEqual([item['score_c'] for item in links], [0.99, 0.1, 0.9, 0.4, 0.5])
        # tier 字段仍正确保留（仅不再决定顺序）
        expected_tiers = ['featured', 'literature', 'literature', 'literature', 'document']
        self.assertEqual([item['tier'] for item in links], expected_tiers)
