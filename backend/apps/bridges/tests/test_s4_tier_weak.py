"""S4 RED: tier 语义修正 + 广播沉底。

契约（实现后转 GREEN）：
- `Tier` 枚举新增 `WEAK='weak'`（label '弱相关'）；`FEATURED` 保留为历史值，
  但不再自动派生、也不再是字段默认。
- `ProductProtocol.tier` 字段默认 `FEATURED → WEAK`。
- `fuse_relevance` 兜底桶（S_A=0 且 S_B=0，仅语义相似）返回 `'weak'`
  （原为 `'featured'`，那个"编辑精选"徽标是虚假的）。
- 数据迁移：所有 `tier='featured'` 行重标 `'weak'`（dev 实测 974 行），零删除（铁律①）。
- 排序：`weak` 恒沉底——任何 relevance 都排最后；其余按相关性降序。
- 序列化回退 `tier` 由 `featured → weak`。

运行时应 FAIL（Tier 无 WEAK / 默认仍为 featured / fuse 仍回 featured /
relabel 服务与排序 helper 尚未实现），直至 S4 实现后转 GREEN。
"""
from django.test import TestCase

from apps.bridges.models import ProductProtocol
from apps.bridges.services.relevance import fuse_relevance


class TierWeakEnumTest(TestCase):
    def test_weak_member_exists(self):
        self.assertTrue(hasattr(ProductProtocol.Tier, 'WEAK'))
        self.assertEqual(ProductProtocol.Tier.WEAK.value, 'weak')
        self.assertEqual(ProductProtocol.Tier.WEAK.label, '弱相关')

    def test_featured_still_legacy_value(self):
        # FEATURED 保留为历史值（已落库数据/回退兼容），但不在新派生里出现
        self.assertTrue(hasattr(ProductProtocol.Tier, 'FEATURED'))
        self.assertEqual(ProductProtocol.Tier.FEATURED.value, 'featured')

    def test_model_default_is_weak(self):
        f = ProductProtocol._meta.get_field('tier')
        self.assertEqual(f.default, ProductProtocol.Tier.WEAK)


class FuseRelevanceWeakTest(TestCase):
    def test_broadcast_bucket_is_weak(self):
        # S_A=0 & S_B=0（仅语义相似）-> weak（原 featured）
        r = fuse_relevance(score_a=0.0, score_b=0.0, score_c=0.3)
        self.assertEqual(r['tier'], 'weak')
        r2 = fuse_relevance(score_a=0.0, score_b=0.0, score_c=0.0)
        self.assertEqual(r2['tier'], 'weak')

    def test_document_and_literature_unchanged(self):
        self.assertEqual(
            fuse_relevance(score_a=0.6, score_b=0.0, score_c=0.0)['tier'], 'document')
        self.assertEqual(
            fuse_relevance(score_a=0.0, score_b=0.3, score_c=0.0)['tier'], 'literature')


class RelabelWeakServiceTest(TestCase):
    def _make(self, tier, score_a=0.0, score_b=0.0):
        from apps.commerce.models import Product
        from apps.knowledge.models import Protocol, Method
        from apps.bridges.models import ProductMethod, MethodProtocol
        p = Product.objects.create(
            name='P', catalog_no='S4-' + tier, slug='s4-' + tier, status='draft')
        proto = Protocol.objects.create(
            name='X', slug='x-' + tier, status='published', source='curated')
        m = Method.objects.create(name='M', slug='m-' + tier)
        MethodProtocol.objects.create(
            method=m, protocol=proto, explicit=True, featured=True,
            status='published', display_order=1)
        ProductMethod.objects.create(product=p, method=m)
        return ProductProtocol.objects.create(
            product=p, protocol=proto, tier=tier,
            relevance_score=0.2, score_a=score_a, score_b=score_b,
            link_source=ProductProtocol.LinkSource.INHERITED)

    def test_relabel_featured_to_weak_only(self):
        from apps.bridges.services.tier_relabel import relabel_featured_to_weak
        self._make('featured')
        self._make('document')
        self._make('literature')
        n = relabel_featured_to_weak()
        self.assertEqual(n, 1)  # 仅 featured 被重标
        self.assertEqual(ProductProtocol.objects.filter(tier='weak').count(), 1)
        self.assertEqual(ProductProtocol.objects.filter(tier='featured').count(), 0)
        self.assertEqual(ProductProtocol.objects.filter(tier='document').count(), 1)
        self.assertEqual(ProductProtocol.objects.filter(tier='literature').count(), 1)

    def test_relabel_idempotent(self):
        from apps.bridges.services.tier_relabel import relabel_featured_to_weak
        self._make('featured')
        relabel_featured_to_weak()
        n2 = relabel_featured_to_weak()
        self.assertEqual(n2, 0)  # 第二次零影响（幂等，零删除）
        self.assertEqual(ProductProtocol.objects.filter(tier='weak').count(), 1)
        # 零删除：总行数不变（仅 1 行 featured）
        self.assertEqual(ProductProtocol.objects.count(), 1)


class WeakSinkSortTest(TestCase):
    def test_weak_sinks_below_higher_relevance_nonweak(self):
        from apps.bridges.services.relevance import protocol_link_sort_key
        weak = {'tier': 'weak', 'relevance_score': 0.99, 'score_c': 0.9, 'id': 1}
        doc = {'tier': 'document', 'relevance_score': 0.30, 'score_c': 0.2, 'id': 2}
        rows = [weak, doc]
        rows.sort(key=protocol_link_sort_key)
        # 即便 weak 的 relevance 远高于 document，weak 仍沉底
        self.assertEqual(rows[0]['tier'], 'document')
        self.assertEqual(rows[1]['tier'], 'weak')

    def test_weak_internal_sorted_by_relevance_desc(self):
        from apps.bridges.services.relevance import protocol_link_sort_key
        w1 = {'tier': 'weak', 'relevance_score': 0.9, 'score_c': 0.1, 'id': 1}
        w2 = {'tier': 'weak', 'relevance_score': 0.3, 'score_c': 0.2, 'id': 2}
        rows = [w1, w2]
        rows.sort(key=protocol_link_sort_key)
        self.assertEqual([r['id'] for r in rows], [1, 2])

    def test_weak_sinks_in_serializer_protocol_links(self):
        from apps.commerce.api.v1.serializers import ProductDetailSerializer
        from apps.commerce.tests.factories import ProductFactory
        from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory
        from apps.bridges.models import ProductMethod, MethodProtocol
        product = ProductFactory()
        method = MethodFactory()
        ProductMethod.objects.create(product=product, method=method)
        weak_proto = ProtocolFactory(name='WeakProto')
        doc_proto = ProtocolFactory(name='DocProto')
        MethodProtocol.objects.create(method=method, protocol=weak_proto)
        MethodProtocol.objects.create(method=method, protocol=doc_proto)
        ProductProtocol.objects.create(
            product=product, protocol=weak_proto,
            tier='weak', relevance_score=0.99, score_c=0.9,
            link_source='inherited', relevance_basis='embedding_break')
        ProductProtocol.objects.create(
            product=product, protocol=doc_proto,
            tier='document', relevance_score=0.30, score_c=0.2,
            link_source='inherited', relevance_basis='vendor_only')
        rows = ProductDetailSerializer(product).get_protocol_links(product)
        tiers = [r['tier'] for r in rows]
        self.assertEqual(tiers[0], 'document')
        self.assertEqual(tiers[-1], 'weak')
