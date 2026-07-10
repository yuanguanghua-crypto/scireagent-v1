from django.test import TestCase
from rest_framework.test import APIClient
from apps.commerce.tests.factories import (
    ProductFactory, SKUFactory, ProductClassFactory, CatalogGroupFactory
)
from apps.bridges.tests.factories import ProductMethodFactory, ProductReferenceFactory


class ProductAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_empty(self):
        resp = self.client.get('/api/v1/products/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data'], [])

    def test_list_with_data(self):
        ProductFactory.create_batch(3)
        resp = self.client.get('/api/v1/products/')
        self.assertEqual(len(resp.json()['data']), 3)

    def test_list_envelope_format(self):
        ProductFactory()
        resp = self.client.get('/api/v1/products/')
        data = resp.json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_list_has_sku_summary(self):
        product = ProductFactory()
        SKUFactory(product=product, price=10.00, sku_code='SKU-A')
        SKUFactory(product=product, price=20.00, sku_code='SKU-B')
        resp = self.client.get('/api/v1/products/')
        data = resp.json()['data'][0]
        self.assertIn('sku_summary', data)
        self.assertEqual(data['sku_summary']['count'], 2)

    def test_list_sku_summary_price_range(self):
        product = ProductFactory()
        SKUFactory(product=product, price=10.00, sku_code='SKU-L')
        SKUFactory(product=product, price=50.00, sku_code='SKU-H')
        resp = self.client.get('/api/v1/products/')
        data = resp.json()['data'][0]
        self.assertEqual(data['sku_summary']['price_range']['min'], '10.00')
        self.assertEqual(data['sku_summary']['price_range']['max'], '50.00')

    def test_detail_includes_skus(self):
        product = ProductFactory()
        SKUFactory(product=product, sku_code='TEST-001')
        SKUFactory(product=product, sku_code='TEST-002')
        resp = self.client.get(f'/api/v1/products/{product.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(len(data['skus']), 2)

    def test_detail_sku_fields(self):
        product = ProductFactory()
        sku = SKUFactory(product=product, sku_code='TEST-001', pack_size='100mg', price=99.99)
        resp = self.client.get(f'/api/v1/products/{product.id}/')
        sku_data = resp.json()['data']['skus'][0]
        self.assertEqual(sku_data['sku_code'], 'TEST-001')
        self.assertEqual(sku_data['pack_size'], '100mg')
        self.assertIn('price', sku_data)
        self.assertIn('inventory_status', sku_data)

    def test_detail_includes_bridge_fields(self):
        product = ProductFactory()
        resp = self.client.get(f'/api/v1/products/{product.id}/')
        data = resp.json()['data']
        self.assertIn('method_ids', data)
        self.assertIn('reference_ids', data)
        self.assertIn('compatibility_summary', data)
        self.assertIn('application_ids', data)
        self.assertIn('protocol_ids', data)

    def test_detail_method_ids_populated(self):
        product = ProductFactory()
        pm = ProductMethodFactory(product=product)
        resp = self.client.get(f'/api/v1/products/{product.id}/')
        data = resp.json()['data']
        self.assertIn(pm.method_id, data['method_ids'])

    def test_detail_reference_ids_populated(self):
        product = ProductFactory()
        pr = ProductReferenceFactory(product=product)
        resp = self.client.get(f'/api/v1/products/{product.id}/')
        data = resp.json()['data']
        self.assertIn(pr.reference_id, data['reference_ids'])

    def test_detail_compatibility_summary(self):
        product = ProductFactory()
        resp = self.client.get(f'/api/v1/products/{product.id}/')
        data = resp.json()['data']
        self.assertIn('count', data['compatibility_summary'])

    def test_filter_by_product_class_id(self):
        pc = ProductClassFactory()
        ProductFactory(product_class=pc)
        ProductFactory()  # different class
        resp = self.client.get(f'/api/v1/products/?product_class_id={pc.id}')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_status(self):
        ProductFactory(status='active')
        ProductFactory(status='draft')
        resp = self.client.get('/api/v1/products/?status=active')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_by_name(self):
        ProductFactory(name='Cy3-NHS Ester')
        ProductFactory(name='Cy5-NHS Ester')
        resp = self.client.get('/api/v1/products/?search=Cy3')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_by_cas(self):
        ProductFactory(cas='12345-67-8')
        ProductFactory(cas='99999-00-0')
        resp = self.client.get('/api/v1/products/?search=12345')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_json_ld_endpoint(self):
        product = ProductFactory(name='Test Product')
        resp = self.client.get(f'/api/v1/products/{product.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@type', jsonld)

    def test_detail_not_found(self):
        resp = self.client.get('/api/v1/products/99999/')
        self.assertEqual(resp.status_code, 404)


class SKUAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        SKUFactory.create_batch(3)
        resp = self.client.get('/api/v1/skus/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 3)

    def test_list_fields(self):
        SKUFactory()
        resp = self.client.get('/api/v1/skus/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_code', data)
        self.assertIn('pack_size', data)
        self.assertIn('price', data)
        self.assertIn('inventory_status', data)

    def test_filter_by_product_id(self):
        product = ProductFactory()
        SKUFactory(product=product, sku_code='SKU-A')
        SKUFactory(sku_code='SKU-B')  # different product
        resp = self.client.get(f'/api/v1/skus/?product_id={product.id}')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_inventory_status(self):
        SKUFactory(inventory_status='in_stock', sku_code='SKU-A')
        SKUFactory(inventory_status='out_of_stock', sku_code='SKU-B')
        resp = self.client.get('/api/v1/skus/?inventory_status=in_stock')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_detail(self):
        sku = SKUFactory(sku_code='SKU-001', pack_size='100mg')
        resp = self.client.get(f'/api/v1/skus/{sku.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['sku_code'], 'SKU-001')


class ProductClassAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        ProductClassFactory.create_batch(2)
        resp = self.client.get('/api/v1/product-classes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        ProductClassFactory()
        resp = self.client.get('/api/v1/product-classes/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('parent_id', data)

    def test_detail(self):
        pc = ProductClassFactory(name='Nucleotides')
        resp = self.client.get(f'/api/v1/product-classes/{pc.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['name'], 'Nucleotides')


class CatalogGroupAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        CatalogGroupFactory.create_batch(2)
        resp = self.client.get('/api/v1/catalog-groups/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_only_active(self):
        CatalogGroupFactory(active=True, slug='active-group')
        CatalogGroupFactory(active=False, slug='inactive-group')
        resp = self.client.get('/api/v1/catalog-groups/')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_list_fields(self):
        CatalogGroupFactory()
        resp = self.client.get('/api/v1/catalog-groups/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('locale', data)
        self.assertIn('active', data)
