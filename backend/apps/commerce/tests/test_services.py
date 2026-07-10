from django.test import TestCase
from decimal import Decimal
from apps.commerce.services.commerce_service import CommerceService
from apps.commerce.models import Product, SKU
from apps.commerce.tests.factories import ProductClassFactory


class CommerceServiceCreateProductTest(TestCase):
    def test_create_product(self):
        validated_data = {
            'name': 'Cy3-NHS',
            'slug': 'cy3-nhs',
            'cas': '12345-67-8',
        }
        product = CommerceService.create_product(validated_data)
        self.assertEqual(product.name, 'Cy3-NHS')
        self.assertEqual(product.cas, '12345-67-8')
        self.assertTrue(Product.objects.filter(id=product.id).exists())

    def test_create_product_with_skus(self):
        validated_data = {
            'name': 'Cy3-NHS',
            'slug': 'cy3-nhs-sku',
            'cas': '12345-67-8',
        }
        skus_data = [
            {'sku_code': 'SKU-001', 'pack_size': '100mg', 'price': Decimal('99.99')},
            {'sku_code': 'SKU-002', 'pack_size': '500mg', 'price': Decimal('399.99')},
        ]
        product = CommerceService.create_product(validated_data, skus_data)
        self.assertEqual(product.skus.count(), 2)

    def test_create_product_skus_prices(self):
        validated_data = {
            'name': 'Cy5-NHS',
            'slug': 'cy5-nhs',
        }
        skus_data = [
            {'sku_code': 'SKU-CY5-1', 'pack_size': '100mg', 'price': Decimal('149.99')},
        ]
        product = CommerceService.create_product(validated_data, skus_data)
        sku = product.skus.first()
        self.assertEqual(sku.price, Decimal('149.99'))

    def test_create_product_without_skus(self):
        validated_data = {
            'name': 'Test Product',
            'slug': 'test-product-no-skus',
        }
        product = CommerceService.create_product(validated_data)
        self.assertEqual(product.skus.count(), 0)

    def test_create_product_with_class(self):
        pc = ProductClassFactory()
        validated_data = {
            'name': 'Classified Product',
            'slug': 'classified-product',
            'product_class': pc,
        }
        product = CommerceService.create_product(validated_data)
        self.assertEqual(product.product_class_id, pc.id)

    def test_search_products(self):
        from apps.commerce.tests.factories import ProductFactory
        ProductFactory(name='Cy3-NHS')
        ProductFactory(name='Cy5-NHS')
        results = CommerceService.search_products('Cy3')
        self.assertEqual(results.count(), 1)
