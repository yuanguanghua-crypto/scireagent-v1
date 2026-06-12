from django.test import TestCase
from rest_framework.test import APIClient
from apps.transactions.tests.factories import (
    OrderFactory, OrderItemFactory, QuoteFactory, QuoteItemFactory,
    BasketFactory, WishlistFactory
)
from apps.accounts.tests.factories import UserFactory


class OrderAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_empty(self):
        resp = self.client.get('/api/v1/orders/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data'], [])

    def test_list_with_data(self):
        OrderFactory.create_batch(2)
        resp = self.client.get('/api/v1/orders/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 2)

    def test_list_envelope_format(self):
        OrderFactory()
        resp = self.client.get('/api/v1/orders/')
        data = resp.json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_list_fields(self):
        OrderFactory()
        resp = self.client.get('/api/v1/orders/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('order_no', data)
        self.assertIn('status', data)
        self.assertIn('subtotal', data)
        self.assertIn('grand_total', data)
        self.assertIn('currency', data)

    def test_detail_includes_items(self):
        order = OrderFactory()
        OrderItemFactory(order=order, quantity=2)
        OrderItemFactory(order=order, quantity=3)
        resp = self.client.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(len(data['items']), 2)

    def test_detail_item_fields(self):
        order = OrderFactory()
        item = OrderItemFactory(order=order, quantity=5)
        resp = self.client.get(f'/api/v1/orders/{order.id}/')
        item_data = resp.json()['data']['items'][0]
        self.assertIn('id', item_data)
        self.assertIn('product_id', item_data)
        self.assertIn('sku_id', item_data)
        self.assertIn('quantity', item_data)
        self.assertIn('unit_price', item_data)

    def test_detail_extra_fields(self):
        order = OrderFactory()
        resp = self.client.get(f'/api/v1/orders/{order.id}/')
        data = resp.json()['data']
        self.assertIn('tax_total', data)
        self.assertIn('comment', data)

    def test_filter_by_status(self):
        OrderFactory(status='pending')
        OrderFactory(status='paid')
        resp = self.client.get('/api/v1/orders/?status=pending')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_create_order(self):
        resp = self.client.post('/api/v1/orders/', {
            'order_no': 'ORD-NEW', 'status': 'pending'
        }, format='json')
        self.assertEqual(resp.status_code, 201)


class QuoteAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_empty(self):
        resp = self.client.get('/api/v1/quotes/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data'], [])

    def test_list_with_data(self):
        QuoteFactory.create_batch(2)
        resp = self.client.get('/api/v1/quotes/')
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        QuoteFactory()
        resp = self.client.get('/api/v1/quotes/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('quote_no', data)
        self.assertIn('company_name', data)
        self.assertIn('contact_name', data)
        self.assertIn('status', data)

    def test_detail_includes_items(self):
        quote = QuoteFactory()
        QuoteItemFactory(quote=quote)
        QuoteItemFactory(quote=quote)
        resp = self.client.get(f'/api/v1/quotes/{quote.id}/')
        data = resp.json()['data']
        self.assertEqual(len(data['items']), 2)

    def test_detail_item_fields(self):
        quote = QuoteFactory()
        item = QuoteItemFactory(quote=quote)
        resp = self.client.get(f'/api/v1/quotes/{quote.id}/')
        item_data = resp.json()['data']['items'][0]
        self.assertIn('id', item_data)
        self.assertIn('product_id', item_data)
        self.assertIn('quantity', item_data)

    def test_detail_extra_fields(self):
        quote = QuoteFactory()
        resp = self.client.get(f'/api/v1/quotes/{quote.id}/')
        data = resp.json()['data']
        self.assertIn('contact_email', data)
        self.assertIn('contact_phone', data)
        self.assertIn('country', data)
        self.assertIn('valid_until', data)
        self.assertIn('remark', data)

    def test_filter_by_status(self):
        QuoteFactory(status='draft')
        QuoteFactory(status='submitted')
        resp = self.client.get('/api/v1/quotes/?status=draft')
        self.assertEqual(len(resp.json()['data']), 1)


class BasketAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list_empty_for_authenticated_user(self):
        resp = self.client.get('/api/v1/basket/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

    def test_list_returns_only_user_baskets(self):
        BasketFactory(user=self.user)
        BasketFactory(user=UserFactory())  # other user
        resp = self.client.get('/api/v1/basket/')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_list_unauthenticated_returns_empty(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/basket/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_list_fields(self):
        BasketFactory(user=self.user)
        resp = self.client.get('/api/v1/basket/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_id', data)
        self.assertIn('quantity', data)
        self.assertIn('product_name', data)
        self.assertIn('sku_code', data)


class WishlistAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list_empty(self):
        resp = self.client.get('/api/v1/wishlist/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_list_returns_only_user_wishlists(self):
        WishlistFactory(user=self.user)
        WishlistFactory(user=UserFactory())
        resp = self.client.get('/api/v1/wishlist/')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_list_unauthenticated_returns_empty(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/wishlist/')
        self.assertEqual(resp.json()['data'], [])

    def test_list_fields(self):
        WishlistFactory(user=self.user)
        resp = self.client.get('/api/v1/wishlist/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('product_count', data)
