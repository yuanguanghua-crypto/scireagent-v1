from django.test import TestCase
from django.db import IntegrityError
from datetime import timedelta
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup
from apps.commerce.tests.factories import (
    ProductFactory, SKUFactory, ProductClassFactory, CatalogGroupFactory
)


class ProductClassModelTest(TestCase):
    def test_create(self):
        pc = ProductClassFactory(name='Nucleotides')
        self.assertEqual(pc.name, 'Nucleotides')

    def test_slug_unique(self):
        ProductClassFactory(slug='nucleotides')
        with self.assertRaises(IntegrityError):
            ProductClassFactory(slug='nucleotides')

    def test_parent_self_fk(self):
        parent = ProductClassFactory(name='Chemistry')
        child = ProductClassFactory(name='Nucleotides', parent=parent)
        self.assertEqual(child.parent_id, parent.id)
        self.assertIn(child, parent.children.all())

    def test_parent_nullable(self):
        pc = ProductClassFactory(parent=None)
        self.assertIsNone(pc.parent)

    def test_str(self):
        pc = ProductClassFactory(name='Nucleotides')
        self.assertEqual(str(pc), 'Nucleotides')

    def test_ordering(self):
        c1 = ProductClassFactory(sort_order=2)
        c2 = ProductClassFactory(sort_order=1)
        classes = list(ProductClass.objects.all())
        self.assertEqual(classes[0].id, c2.id)

    def test_table_name(self):
        self.assertEqual(ProductClass._meta.db_table, 'product_class')


class CatalogGroupModelTest(TestCase):
    def test_create(self):
        cg = CatalogGroupFactory(name='Main Catalog', locale='en')
        self.assertEqual(cg.name, 'Main Catalog')
        self.assertTrue(cg.active)

    def test_slug_unique(self):
        CatalogGroupFactory(slug='main-catalog')
        with self.assertRaises(IntegrityError):
            CatalogGroupFactory(slug='main-catalog')

    def test_active_default(self):
        cg = CatalogGroupFactory()
        self.assertTrue(cg.active)

    def test_locale_default(self):
        cg = CatalogGroupFactory()
        self.assertEqual(cg.locale, 'en')

    def test_str(self):
        cg = CatalogGroupFactory(name='Main Catalog')
        self.assertEqual(str(cg), 'Main Catalog')

    def test_table_name(self):
        self.assertEqual(CatalogGroup._meta.db_table, 'catalog_group')


class ProductModelTest(TestCase):
    def test_create(self):
        product = ProductFactory(name='Cy3-NHS', cas='12345-67-8')
        self.assertEqual(product.name, 'Cy3-NHS')
        self.assertEqual(product.cas, '12345-67-8')

    def test_slug_unique(self):
        ProductFactory(slug='cy3-nhs')
        with self.assertRaises(IntegrityError):
            ProductFactory(slug='cy3-nhs')

    def test_synonyms_jsonfield_default(self):
        product = ProductFactory()
        self.assertEqual(product.synonyms, [])

    def test_shelf_life_durationfield(self):
        product = ProductFactory(shelf_life=timedelta(days=365))
        self.assertEqual(product.shelf_life, timedelta(days=365))

    def test_shelf_life_nullable(self):
        product = ProductFactory(shelf_life='')
        self.assertEqual(product.shelf_life, '')

    def test_research_use_only_default(self):
        product = ProductFactory()
        self.assertTrue(product.research_use_only)

    def test_inventory_status_in_stock(self):
        product = ProductFactory()
        SKUFactory(product=product, inventory_status='in_stock')
        self.assertEqual(product.inventory_status, 'in_stock')

    def test_inventory_status_limited(self):
        product = ProductFactory()
        SKUFactory(product=product, inventory_status='limited')
        self.assertEqual(product.inventory_status, 'limited')

    def test_inventory_status_preorder(self):
        product = ProductFactory()
        SKUFactory(product=product, inventory_status='preorder')
        self.assertEqual(product.inventory_status, 'preorder')

    def test_inventory_status_out_of_stock(self):
        product = ProductFactory()
        SKUFactory(product=product, inventory_status='out_of_stock')
        self.assertEqual(product.inventory_status, 'out_of_stock')

    def test_inventory_status_default_when_no_skus(self):
        product = ProductFactory()
        self.assertEqual(product.inventory_status, 'out_of_stock')

    def test_inventory_status_priority_in_stock_over_limited(self):
        """in_stock takes priority over limited"""
        product = ProductFactory()
        SKUFactory(product=product, inventory_status='limited', sku_code='SKU-L-1')
        SKUFactory(product=product, inventory_status='in_stock', sku_code='SKU-I-1')
        self.assertEqual(product.inventory_status, 'in_stock')

    def test_slug_index(self):
        indexes = Product._meta.indexes
        slug_indexes = [i for i in indexes if i.name == 'product_slug_idx']
        self.assertEqual(len(slug_indexes), 1)

    def test_cas_index(self):
        indexes = Product._meta.indexes
        cas_indexes = [i for i in indexes if i.name == 'product_cas_idx']
        self.assertEqual(len(cas_indexes), 1)

    def test_name_index(self):
        indexes = Product._meta.indexes
        name_indexes = [i for i in indexes if i.name == 'product_name_idx']
        self.assertEqual(len(name_indexes), 1)

    def test_str(self):
        product = ProductFactory(name='Cy3-NHS')
        self.assertEqual(str(product), 'Cy3-NHS')

    def test_product_class_fk_nullable(self):
        product = ProductFactory(product_class=None)
        self.assertIsNone(product.product_class)

    def test_catalog_group_fk_nullable(self):
        product = ProductFactory(catalog_group=None)
        self.assertIsNone(product.catalog_group)

    def test_status_default(self):
        product = ProductFactory()
        self.assertEqual(product.status, 'draft')

    def test_related_skus(self):
        product = ProductFactory()
        SKUFactory(product=product, sku_code='SKU-1')
        SKUFactory(product=product, sku_code='SKU-2')
        self.assertEqual(product.skus.count(), 2)

    def test_table_name(self):
        self.assertEqual(Product._meta.db_table, 'product')


class SKUModelTest(TestCase):
    def test_create(self):
        sku = SKUFactory(sku_code='SKU-001', pack_size='100mg', price=99.99)
        self.assertEqual(sku.sku_code, 'SKU-001')
        self.assertEqual(sku.pack_size, '100mg')

    def test_sku_code_unique(self):
        SKUFactory(sku_code='SKU-001')
        with self.assertRaises(IntegrityError):
            SKUFactory(sku_code='SKU-001')

    def test_belongs_to_product(self):
        product = ProductFactory()
        sku = SKUFactory(product=product)
        self.assertEqual(sku.product_id, product.id)

    def test_inventory_status_choices(self):
        choices = dict(SKU.InventoryStatus.choices)
        self.assertIn('in_stock', choices)
        self.assertIn('limited', choices)
        self.assertIn('preorder', choices)
        self.assertIn('out_of_stock', choices)

    def test_inventory_status_default(self):
        sku = SKUFactory()
        self.assertEqual(sku.inventory_status, 'in_stock')

    def test_currency_default(self):
        sku = SKUFactory()
        self.assertEqual(sku.currency, 'USD')

    def test_price_default(self):
        product = ProductFactory()
        sku = SKUFactory(product=product, price=0)
        self.assertEqual(sku.price, 0)

    def test_str(self):
        sku = SKUFactory(sku_code='SKU-001', pack_size='100mg')
        result = str(sku)
        self.assertIn('SKU-001', result)
        self.assertIn('100mg', result)

    def test_ordering(self):
        product = ProductFactory()
        s2 = SKUFactory(product=product, price=199.99, sku_code='SKU-H')
        s1 = SKUFactory(product=product, price=99.99, sku_code='SKU-L')
        skus = list(SKU.objects.all())
        self.assertEqual(skus[0].sku_code, 'SKU-L')

    def test_table_name(self):
        self.assertEqual(SKU._meta.db_table, 'sku')
