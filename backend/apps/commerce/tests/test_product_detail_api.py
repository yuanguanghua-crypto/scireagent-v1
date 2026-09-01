"""
TDD Sprint 1.3: Product Detail API Complete
Tests for product detail API endpoint with all required sections.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import ReagentClass
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory
from apps.bridges.tests.factories import (
    ProductMethodFactory, ProductMethodRelationFactory,
    ProductProtocolFactory, MethodProtocolFactory,
)


class ProductDetailAPITest(TestCase):
    """Test Product Detail API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name="2'-Azido-dATP",
            catalog_no="SC8047",
            cas="73449-06-6",
            storage="-20°C",
            purity="≥ 95% (HPLC)",
            concentration="100 mM",
            formula="C10H15N8O12P3",
            molecular_weight=532.2,
            overview="A modified dATP for click chemistry labeling.",
            smiles="C1=NC(=C2C(=N1)N(C=N2)[C@H]3...",
            status='active',
            category_l1='nucleotides_nucleosides',
        )

    def test_product_detail_returns_200(self):
        """Product detail API should return 200 for active products."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        self.assertEqual(response.status_code, 200)

    def test_product_detail_includes_product(self):
        """Product detail should include product information."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('product', data['data'])
        product = data['data']['product']
        self.assertEqual(product['name'], "2'-Azido-dATP")
        self.assertEqual(product['catalog_no'], 'SC8047')

    def test_product_detail_includes_applications(self):
        """Product detail should include related applications."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('applications', data['data'])
        self.assertIsInstance(data['data']['applications'], list)

    def test_product_detail_includes_protocols(self):
        """Product detail should include related protocols."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('protocols', data['data'])
        self.assertIsInstance(data['data']['protocols'], list)

    def test_product_detail_includes_faq(self):
        """Product detail should include FAQ questions."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('faq', data['data'])
        faq = data['data']['faq']
        self.assertIsInstance(faq, list)
        self.assertGreaterEqual(len(faq), 4)

    def test_product_detail_includes_related_products(self):
        """Product detail should include related products."""
        # Create some related products
        for i in range(3):
            ProductFactory(
                catalog_no=f'SC{i+1}',
                status='active',
                category_l1='nucleotides_nucleosides',
            )

        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('related_products', data['data'])
        related = data['data']['related_products']
        self.assertIsInstance(related, list)
        self.assertLessEqual(len(related), 4)

    def test_product_detail_includes_references(self):
        """Product detail should include references."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('references', data['data'])
        self.assertIsInstance(data['data']['references'], list)

    def test_product_detail_includes_compatibility(self):
        """Product detail should include compatibility information."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        self.assertIn('compatibility', data['data'])

    def test_product_detail_404_for_inactive(self):
        """Product detail should return 404 for inactive products."""
        self.product.status = 'draft'
        self.product.save()

        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        self.assertEqual(response.status_code, 404)

    def test_product_detail_404_for_nonexistent(self):
        """Product detail should return 404 for nonexistent products."""
        response = self.client.get('/api/v1/products/99999/detail/')
        self.assertEqual(response.status_code, 404)

    def test_product_detail_faq_has_questions_and_answers(self):
        """FAQ items should have question and answer fields."""
        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        faq = data['data']['faq']
        for item in faq:
            self.assertIn('question', item)
            self.assertIn('answer', item)
            self.assertTrue(len(item['question']) > 0)
            self.assertTrue(len(item['answer']) > 0)

    def test_product_detail_related_excludes_self(self):
        """Related products should not include the product itself."""
        # Create some related products
        for i in range(3):
            ProductFactory(
                catalog_no=f'SC{i+1}',
                status='active',
                category_l1='nucleotides_nucleosides',
            )

        response = self.client.get(f'/api/v1/products/{self.product.id}/detail/')
        data = response.json()

        related = data['data']['related_products']
        related_ids = [p['id'] for p in related]
        self.assertNotIn(self.product.id, related_ids)


class ProductDetailReadThroughTest(TestCase):
    """P0#3 方案A「读端打通」：详情 API 从 ProductProtocol 直接表 + PMR derived 边读取。

    覆盖四条核心路径：
    1. ProductProtocol 行 → 顶层 protocols 非空且排序符合 tier/relevance 优先级（weak 沉底）
    2. PMR derived 边 → methods 包含该 derived 方法（含 source_type 标记）
    3. 仅旧 ProductMethod 桥 → 不报错且 fallback 生效（仍能看到方法）
    4. 仅 MethodProtocol 桥（无 PP 行）→ protocols 回退派生链路不丢数据
    """

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name='Read Through Product',
            catalog_no='SC8120',
            cas='99999-00-0',
            status='active',
            category_l1='nucleotides_nucleosides',
        )

    def _get_detail(self):
        return self.client.get(f'/api/v1/products/{self.product.id}/detail/')

    def test_detail_protocols_read_from_product_protocol_sorted_by_tier(self):
        """PP 行 → 顶层 protocols 非空，排序 tier 优先（featured 在 weak 之前）。"""
        featured = ProtocolFactory(status='published')
        weak = ProtocolFactory(status='published')
        ProductProtocolFactory(
            product=self.product, protocol=featured,
            tier='featured', relevance_score=0.8, link_source='inherited',
        )
        ProductProtocolFactory(
            product=self.product, protocol=weak,
            tier='weak', relevance_score=0.5, link_source='inherited',
        )
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        protocols = response.json()['data']['protocols']
        self.assertEqual(len(protocols), 2)
        self.assertEqual(protocols[0]['id'], featured.id)
        self.assertEqual(protocols[1]['id'], weak.id)

    def test_detail_derived_methods_from_pmr_edge(self):
        """PMR derived 边 → methods 含该方法，product.derived_methods 含 source_type 标记。"""
        method = MethodFactory(status='active')
        rc = ReagentClass.objects.create(
            id_code='RC-PMR-T', name='PMR Test RC', slug='pmr-test-rc',
            behavior_type='method_specific',
        )
        ProductMethodRelationFactory(
            product=self.product, method=method,
            relation_type='derived_relevance',
            source_reagent_class=rc,
            status='active',
        )
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        # compatibility.methods 已合并 PMR derived 方法
        method_ids = [m['id'] for m in data['compatibility']['methods']]
        self.assertIn(method.id, method_ids)
        # product.derived_methods 输出含透明来源标记 source_type='derived'
        derived = data['product']['derived_methods']
        dm = next((d for d in derived if d['id'] == method.id), None)
        self.assertIsNotNone(dm)
        self.assertEqual(dm['source_type'], 'derived')

    def test_detail_fallback_to_legacy_product_method_bridge(self):
        """仅旧 ProductMethod 桥 → 不报错且 fallback 生效（仍能看到方法）。"""
        method = MethodFactory(status='active')
        ProductMethodFactory(product=self.product, method=method)
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        method_ids = [m['id'] for m in data['compatibility']['methods']]
        self.assertIn(method.id, method_ids)
        self.assertEqual(data['product']['derived_methods'], [])

    def test_detail_protocols_fallback_to_method_protocol_bridge(self):
        """仅 MethodProtocol 桥（无 PP 行）→ protocols 回退派生链路不丢数据。"""
        method = MethodFactory(status='active')
        protocol = ProtocolFactory(status='published')
        ProductMethodFactory(product=self.product, method=method)
        MethodProtocolFactory(method=method, protocol=protocol)
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        protocols = response.json()['data']['protocols']
        self.assertEqual(len(protocols), 1)
        self.assertEqual(protocols[0]['id'], protocol.id)

    def test_detail_derived_draft_method_passes_status_filter(self):
        """P2-1：PMR derived 边关联的 draft method 必须出现在 methods 列表。

        全库 derived 边关联的 method 均为 draft 状态，原 status='active' 过滤
        将其全部滤掉（公开详情页 methods 看不到 derived 方法）——本用例守卫放行。
        """
        method = MethodFactory(status='draft')
        rc = ReagentClass.objects.create(
            id_code='RC-PMR-D', name='PMR Draft RC', slug='pmr-draft-rc',
            behavior_type='method_specific',
        )
        ProductMethodRelationFactory(
            product=self.product, method=method,
            relation_type='derived_relevance',
            source_reagent_class=rc,
            status='active',
        )
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        method_ids = [m['id'] for m in response.json()['data']['compatibility']['methods']]
        self.assertIn(method.id, method_ids)

    def test_detail_deprecated_method_still_filtered(self):
        """P2-1 边界：只放行 draft，deprecated 已弃用方法仍被滤出 methods 列表。"""
        method = MethodFactory(status='deprecated')
        ProductMethodFactory(product=self.product, method=method)
        response = self._get_detail()
        self.assertEqual(response.status_code, 200)
        method_ids = [m['id'] for m in response.json()['data']['compatibility']['methods']]
        self.assertNotIn(method.id, method_ids)
