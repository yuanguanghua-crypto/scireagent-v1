"""
TDD Tests: Product Serializer with Knowledge Fields
These tests define the expected behavior BEFORE implementation.
"""
from django.test import TestCase
from apps.commerce.models import Product, SKU
from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
from apps.knowledge.models import ResearchGoal, Application, Method, Protocol
from apps.bridges.models import ProductMethod, MethodProtocol
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import (
    ResearchGoalFactory, ApplicationFactory, MethodFactory, ProtocolFactory
)
from apps.bridges.tests.factories import MethodProtocolFactory


class ProductKnowledgeFieldTest(TestCase):
    """ProductCreateUpdateSerializer 支持知识关联字段"""

    def setUp(self):
        self.goal = ResearchGoalFactory(name='RNA Analysis')
        self.app = ApplicationFactory(name='RNA Labeling', research_goal=self.goal)
        self.method1 = MethodFactory(name='CuAAC', application=self.app)
        self.method2 = MethodFactory(name='NHS-Ester', application=self.app)
        self.protocol = ProtocolFactory(name='CuAAC Protocol', method=self.method1)

    def test_serializer_accepts_method_ids(self):
        """Serializer 接受 method_ids 字段"""
        product = ProductFactory()
        data = {'name': product.name, 'method_ids': [self.method1.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn('method_ids', serializer.validated_data)

    def test_serializer_accepts_protocol_ids(self):
        """Serializer 接受 protocol_ids 字段"""
        product = ProductFactory()
        data = {'name': product.name, 'protocol_ids': [self.protocol.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_serializer_accepts_research_goal_ids(self):
        """Serializer 接受 research_goal_ids 字段"""
        product = ProductFactory()
        data = {'name': product.name, 'research_goal_ids': [self.goal.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_serializer_accepts_application_ids(self):
        """Serializer 接受 application_ids 字段"""
        product = ProductFactory()
        data = {'name': product.name, 'application_ids': [self.app.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_creates_product_method_bridges(self):
        """更新产品时创建 ProductMethod 桥接记录"""
        product = ProductFactory()
        data = {'name': product.name, 'method_ids': [self.method1.id, self.method2.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        bridges = ProductMethod.objects.filter(product=product)
        method_ids = list(bridges.values_list('method_id', flat=True))
        self.assertEqual(len(method_ids), 2)
        self.assertIn(self.method1.id, method_ids)
        self.assertIn(self.method2.id, method_ids)

    def test_update_syncs_method_bridges(self):
        """更新产品时同步桥接记录（增量更新，非全量替换）"""
        product = ProductFactory()
        # 先关联 method1
        ProductMethod.objects.create(product=product, method=self.method1)
        # 更新为 method2（应该移除 method1，添加 method2）
        data = {'name': product.name, 'method_ids': [self.method2.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        bridges = ProductMethod.objects.filter(product=product)
        method_ids = list(bridges.values_list('method_id', flat=True))
        self.assertEqual(len(method_ids), 1)
        self.assertIn(self.method2.id, method_ids)
        self.assertNotIn(self.method1.id, method_ids)

    def test_update_preserves_other_fields(self):
        """更新知识字段时不影响产品基础字段"""
        product = ProductFactory(name='Test Product', catalog_no='TEST-001')
        data = {'method_ids': [self.method1.id]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        product.refresh_from_db()
        self.assertEqual(product.name, 'Test Product')
        self.assertEqual(product.catalog_no, 'TEST-001')

    def test_empty_method_ids_clears_bridges(self):
        """空 method_ids 清除所有桥接记录"""
        product = ProductFactory()
        ProductMethod.objects.create(product=product, method=self.method1)
        data = {'name': product.name, 'method_ids': []}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        bridges = ProductMethod.objects.filter(product=product)
        self.assertEqual(bridges.count(), 0)

    def test_no_method_ids_field_preserves_existing(self):
        """不传 method_ids 时保留现有桥接记录"""
        product = ProductFactory()
        ProductMethod.objects.create(product=product, method=self.method1)
        data = {'name': 'New Name'}  # 不传 method_ids
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        bridges = ProductMethod.objects.filter(product=product)
        self.assertEqual(bridges.count(), 1)

    def test_invalid_method_id_ignored(self):
        """无效的 method_id 被忽略"""
        product = ProductFactory()
        data = {'name': product.name, 'method_ids': [99999]}
        serializer = ProductCreateUpdateSerializer(product, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        # 不应该创建桥接记录
        self.assertEqual(ProductMethod.objects.filter(product=product).count(), 0)


class ProductKnowledgeResponseTest(TestCase):
    """产品 API 响应包含知识关联数据"""

    def setUp(self):
        self.goal = ResearchGoalFactory(name='RNA Analysis')
        self.app = ApplicationFactory(name='RNA Labeling', research_goal=self.goal)
        self.method = MethodFactory(name='CuAAC', application=self.app)
        self.protocol = ProtocolFactory(name='CuAAC Protocol', method=self.method)

    def test_product_detail_includes_method_ids(self):
        """产品详情 API 返回 method_ids"""
        product = ProductFactory()
        ProductMethod.objects.create(product=product, method=self.method)
        from apps.commerce.api.v1.serializers import ProductDetailSerializer
        serializer = ProductDetailSerializer(product)
        self.assertIn('method_ids', serializer.data)
        self.assertIn(self.method.id, serializer.data['method_ids'])

    def test_product_detail_includes_protocol_ids(self):
        """产品详情 API 返回 protocol_ids"""
        product = ProductFactory()
        ProductMethod.objects.create(product=product, method=self.method)
        MethodProtocol.objects.create(method=self.method, protocol=self.protocol)
        from apps.commerce.api.v1.serializers import ProductDetailSerializer
        serializer = ProductDetailSerializer(product)
        self.assertIn('protocol_ids', serializer.data)
