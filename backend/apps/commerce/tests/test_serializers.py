from django.test import TestCase
from decimal import Decimal
from apps.commerce.api.v1.serializers import (
    ProductListSerializer, ProductDetailSerializer, SKUSerializer,
    ProductClassSerializer, CatalogGroupSerializer
)
from apps.commerce.tests.factories import (
    ProductFactory, SKUFactory, ProductClassFactory, CatalogGroupFactory
)
from apps.bridges.tests.factories import (
    ProductMethodFactory, ProductReferenceFactory, ProductCompatibilityFactory
)


class ProductListSerializerTest(TestCase):
    def test_fields(self):
        product = ProductFactory(name='Cy3-NHS')
        serializer = ProductListSerializer(product)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('cas', data)
        self.assertIn('synonyms', data)
        self.assertIn('sku_summary', data)
        self.assertIn('status', data)
        self.assertIn('research_use_only', data)

    def test_sku_summary_count(self):
        product = ProductFactory()
        SKUFactory(product=product, sku_code='SKU-1')
        SKUFactory(product=product, sku_code='SKU-2')
        serializer = ProductListSerializer(product)
        self.assertEqual(serializer.data['sku_summary']['count'], 2)

    def test_sku_summary_price_range(self):
        product = ProductFactory()
        SKUFactory(product=product, price=Decimal('10.00'), sku_code='SKU-L')
        SKUFactory(product=product, price=Decimal('50.00'), sku_code='SKU-H')
        serializer = ProductListSerializer(product)
        price_range = serializer.data['sku_summary']['price_range']
        self.assertEqual(price_range['min'], '10.00')
        self.assertEqual(price_range['max'], '50.00')

    def test_sku_summary_empty(self):
        product = ProductFactory()
        serializer = ProductListSerializer(product)
        self.assertEqual(serializer.data['sku_summary']['count'], 0)

    def test_sku_summary_statuses(self):
        product = ProductFactory()
        SKUFactory(product=product, inventory_status='in_stock', sku_code='SKU-1')
        SKUFactory(product=product, inventory_status='limited', sku_code='SKU-2')
        serializer = ProductListSerializer(product)
        statuses = serializer.data['sku_summary']['statuses']
        self.assertIn('in_stock', statuses)
        self.assertIn('limited', statuses)


class ProductDetailSerializerTest(TestCase):
    def test_skus_field(self):
        product = ProductFactory()
        SKUFactory(product=product, sku_code='SKU-1')
        serializer = ProductDetailSerializer(product)
        self.assertEqual(len(serializer.data['skus']), 1)

    def test_application_ids(self):
        product = ProductFactory()
        pm = ProductMethodFactory(product=product)
        serializer = ProductDetailSerializer(product)
        self.assertIn(pm.method.application_id, serializer.data['application_ids'])

    def test_method_ids(self):
        product = ProductFactory()
        pm = ProductMethodFactory(product=product)
        serializer = ProductDetailSerializer(product)
        self.assertIn(pm.method_id, serializer.data['method_ids'])

    def test_protocol_ids(self):
        from apps.bridges.tests.factories import MethodProtocolFactory
        product = ProductFactory()
        pm = ProductMethodFactory(product=product)
        mp = MethodProtocolFactory(method=pm.method)
        serializer = ProductDetailSerializer(product)
        self.assertIn(mp.protocol_id, serializer.data['protocol_ids'])

    def test_reference_ids(self):
        product = ProductFactory()
        pr = ProductReferenceFactory(product=product)
        serializer = ProductDetailSerializer(product)
        self.assertIn(pr.reference_id, serializer.data['reference_ids'])

    def test_compatibility_summary(self):
        product = ProductFactory()
        ProductCompatibilityFactory(source_product=product)
        serializer = ProductDetailSerializer(product)
        self.assertEqual(serializer.data['compatibility_summary']['count'], 1)

    def test_empty_bridge_fields(self):
        product = ProductFactory()
        serializer = ProductDetailSerializer(product)
        self.assertEqual(serializer.data['application_ids'], [])
        self.assertEqual(serializer.data['method_ids'], [])
        self.assertEqual(serializer.data['protocol_ids'], [])
        self.assertEqual(serializer.data['reference_ids'], [])
        self.assertEqual(serializer.data['compatibility_summary']['count'], 0)


class SKUSerializerTest(TestCase):
    def test_fields(self):
        sku = SKUFactory(sku_code='SKU-001', pack_size='100mg', price=Decimal('99.99'))
        serializer = SKUSerializer(sku)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_code', data)
        self.assertIn('pack_size', data)
        self.assertIn('price', data)
        self.assertIn('currency', data)
        self.assertIn('inventory_status', data)


class ProductClassSerializerTest(TestCase):
    def test_fields(self):
        pc = ProductClassFactory(name='Nucleotides')
        serializer = ProductClassSerializer(pc)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('parent_id', data)
        self.assertIn('sort_order', data)

    def test_parent_id(self):
        parent = ProductClassFactory(name='Chemistry')
        child = ProductClassFactory(name='Nucleotides', parent=parent)
        serializer = ProductClassSerializer(child)
        self.assertEqual(serializer.data['parent_id'], parent.id)


class CatalogGroupSerializerTest(TestCase):
    def test_fields(self):
        cg = CatalogGroupFactory(name='Main', locale='en', active=True)
        serializer = CatalogGroupSerializer(cg)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('locale', data)
        self.assertIn('active', data)
