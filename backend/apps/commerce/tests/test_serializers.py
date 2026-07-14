from django.test import TestCase
from decimal import Decimal
from datetime import date
from apps.commerce.api.v1.serializers import (
    ProductListSerializer, ProductDetailSerializer, SKUSerializer,
    ProductClassSerializer, CatalogGroupSerializer, ProductCreateUpdateSerializer
)
from apps.commerce.tests.factories import (
    ProductFactory, SKUFactory, ProductClassFactory, CatalogGroupFactory
)
from apps.bridges.tests.factories import (
    ProductMethodFactory, ProductReferenceFactory, ProductCompatibilityFactory
)
from apps.documents.models import Batch, Coa


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


class ProductCreateUpdateSerializerSKUSyncTest(TestCase):
    """方案A（TDD）：保存产品时 SKU 按 id 增量同步，保留既有 SKU id，
    避免 Batch/Coa 因删光重建而级联丢失（COA 报 'SKU does not exist'）。"""

    def _make_product_with_sku_batch_coa(self):
        product = ProductFactory(name='SC8001', catalog_no='SC8001')
        sku = SKUFactory(product=product, sku_code='SC8001-1')
        batch = Batch.objects.create(
            sku=sku, lot_number='SC8001-L1', produced_at=date(2026, 1, 1))
        coa = Coa.objects.create(
            batch=batch, doc_id='COA-SC8001-1',
            product_name='SC8001', catalog_number='SC8001')
        return product, sku, batch, coa

    def test_update_preserves_sku_id_and_cascade_data(self):
        product, sku, batch, coa = self._make_product_with_sku_batch_coa()
        orig_sku_id = sku.id
        orig_batch_id = batch.id
        orig_coa_id = coa.id

        # 前端保存：skus 带 id + 原字段（模拟 saveDraft/publish 的 payload）
        payload = {
            'skus': [{
                'id': orig_sku_id,
                'sku_code': 'SC8001-1',
                'pack_size': '100mg',
                'price': '99.00',
                'currency': 'USD',
                'inventory_status': 'in_stock',
                'concentration': '',
                'lead_time': '',
                'is_default': True,
            }],
        }
        serializer = ProductCreateUpdateSerializer(
            instance=product, data=payload, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        product.refresh_from_db()
        # ① SKU id 必须稳定（被删除重建会变）
        self.assertEqual(product.skus.count(), 1)
        saved_sku = product.skus.first()
        self.assertEqual(saved_sku.id, orig_sku_id)
        # ② Batch / Coa 不得因 SKU 重建而级联删除
        self.assertTrue(Batch.objects.filter(id=orig_batch_id).exists())
        self.assertTrue(Coa.objects.filter(id=orig_coa_id).exists())
        self.assertEqual(Batch.objects.get(id=orig_batch_id).sku_id, orig_sku_id)

    def test_update_removing_sku_deletes_it_and_cascade(self):
        product, sku, batch, coa = self._make_product_with_sku_batch_coa()
        orig_sku_id = sku.id
        orig_batch_id = batch.id
        orig_coa_id = coa.id

        # 前端移除该 SKU（payload skus 为空列表）
        payload = {'skus': []}
        serializer = ProductCreateUpdateSerializer(
            instance=product, data=payload, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        # 移除的 SKU 及其 Batch/Coa 应被级联删除
        self.assertFalse(product.skus.filter(id=orig_sku_id).exists())
        self.assertFalse(Batch.objects.filter(id=orig_batch_id).exists())
        self.assertFalse(Coa.objects.filter(id=orig_coa_id).exists())

    def test_update_adding_new_sku_creates_without_id_collision(self):
        product, sku, batch, coa = self._make_product_with_sku_batch_coa()
        orig_sku_id = sku.id

        # 保留旧 SKU（带 id）+ 新增一个无 id 的 SKU
        payload = {
            'skus': [
                {
                    'id': orig_sku_id,
                    'sku_code': 'SC8001-1',
                    'pack_size': '100mg',
                    'price': '99.00',
                    'currency': 'USD',
                    'inventory_status': 'in_stock',
                    'concentration': '',
                    'lead_time': '',
                    'is_default': True,
                },
                {
                    'sku_code': 'SC8001-2',
                    'pack_size': '500mg',
                    'price': '299.00',
                    'currency': 'USD',
                    'inventory_status': 'in_stock',
                    'concentration': '',
                    'lead_time': '',
                    'is_default': False,
                },
            ],
        }
        serializer = ProductCreateUpdateSerializer(
            instance=product, data=payload, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        product.refresh_from_db()
        self.assertEqual(product.skus.count(), 2)
        self.assertTrue(product.skus.filter(id=orig_sku_id).exists())
        self.assertTrue(product.skus.filter(sku_code='SC8001-2').exists())
