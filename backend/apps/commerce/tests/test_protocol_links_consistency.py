"""Protocol Links 一致性(任务4) 与 排序(任务3) 回归测试。

任务4：保存/恢复产品时刷新 ProductProtocol(link_source=INHERITED) 行，
       使其与当前方法链一致 —— 删孤儿、重写派生行，AUTO 行不动。
任务3：get_protocol_links 排序去掉 tier 优先，全局按相关性降序。
"""
from django.test import TestCase

from apps.commerce.models import Product
from apps.knowledge.models import Protocol, Method
from apps.bridges.models import (
    MethodProtocol, ProductMethod, ProductProtocol,
)


class InheritedBridgeRefreshTest(TestCase):
    def _make_protocol(self, slug, source='curated'):
        return Protocol.objects.create(
            name=slug, slug=slug, status='published', source=source,
        )

    def test_orphan_inherited_pruned_and_derived_written_on_save(self):
        p_good = self._make_protocol('good-proto')
        p_orphan = self._make_protocol('orphan-proto')
        p_auto = self._make_protocol('auto-proto', source='bioprocorpus')

        m = Method.objects.create(name='M', slug='m-refr')
        MethodProtocol.objects.create(
            method=m, protocol=p_good, explicit=True, featured=True,
            status='published', display_order=1,
        )

        prod = Product.objects.create(
            name='P', catalog_no='TEST-REFR-1', slug='test-refr-1', status='draft',
        )
        ProductMethod.objects.create(
            product=prod, method=m, role='reagent', evidence_level='medium',
        )
        # 预置孤儿 INHERITED 行（不在当前方法链派生里）
        ProductProtocol.objects.create(
            product=prod, protocol=p_orphan,
            link_source=ProductProtocol.LinkSource.INHERITED,
            tier=ProductProtocol.Tier.DOCUMENT, relevance_score=0.3,
        )
        # 预置 AUTO 行（应保留不动）
        ProductProtocol.objects.create(
            product=prod, protocol=p_auto,
            link_source=ProductProtocol.LinkSource.AUTO,
            tier=ProductProtocol.Tier.DOCUMENT, relevance_score=0.6,
        )

        from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
        ser = ProductCreateUpdateSerializer(
            instance=prod, data={'method_ids': [m.id], 'name': 'P', 'status': 'draft'},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()

        inherited = set(
            ProductProtocol.objects.filter(
                product=prod, link_source=ProductProtocol.LinkSource.INHERITED,
            ).values_list('protocol_id', flat=True)
        )
        self.assertIn(p_good.id, inherited)       # 派生的被重写
        self.assertNotIn(p_orphan.id, inherited)   # 孤儿被清
        # AUTO 行不受影响
        self.assertTrue(
            ProductProtocol.objects.filter(
                product=prod, protocol=p_auto,
                link_source=ProductProtocol.LinkSource.AUTO,
            ).exists()
        )

    def test_no_orphan_when_method_chain_empty(self):
        p_orphan = self._make_protocol('orphan-only')
        prod = Product.objects.create(
            name='P2', catalog_no='TEST-REFR-2', slug='test-refr-2', status='draft',
        )
        ProductProtocol.objects.create(
            product=prod, protocol=p_orphan,
            link_source=ProductProtocol.LinkSource.INHERITED,
            tier=ProductProtocol.Tier.DOCUMENT, relevance_score=0.3,
        )
        from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
        ser = ProductCreateUpdateSerializer(
            instance=prod, data={'method_ids': [], 'name': 'P2', 'status': 'draft'},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        self.assertFalse(
            ProductProtocol.objects.filter(
                product=prod, link_source=ProductProtocol.LinkSource.INHERITED,
            ).exists()
        )


class ProtocolLinksSortTest(TestCase):
    def test_sort_by_relevance_not_tier(self):
        """去 tier 优先后，高 relevance 的 INHERITED(featured) 应排在
        低 relevance 的 AUTO(document) 之前（tier 优先时顺序相反）。"""
        p_high = Protocol.objects.create(name='High', slug='high', status='published', source='curated')
        p_low = Protocol.objects.create(name='Low', slug='low', status='published', source='bioprocorpus')
        m = Method.objects.create(name='M2', slug='m-sort')
        MethodProtocol.objects.create(
            method=m, protocol=p_high, explicit=True, featured=True,
            status='published', display_order=1,
        )
        prod = Product.objects.create(
            name='P3', catalog_no='TEST-SORT-1', slug='test-sort-1', status='draft',
        )
        ProductMethod.objects.create(product=prod, method=m, role='reagent', evidence_level='medium')
        ProductProtocol.objects.create(
            product=prod, protocol=p_high,
            link_source=ProductProtocol.LinkSource.INHERITED,
            tier=ProductProtocol.Tier.FEATURED, relevance_score=0.9, score_a=0.5,
        )
        ProductProtocol.objects.create(
            product=prod, protocol=p_low,
            link_source=ProductProtocol.LinkSource.AUTO,
            tier=ProductProtocol.Tier.DOCUMENT, relevance_score=0.3, score_a=0.4,
        )
        from apps.commerce.api.v1.serializers import ProductDetailSerializer
        rows = ProductDetailSerializer().get_protocol_links(prod)
        ids = [r['id'] for r in rows]
        self.assertEqual(ids[0], p_high.id)
        self.assertEqual(ids[1], p_low.id)
