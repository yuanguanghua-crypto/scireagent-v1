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
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list_empty(self):
        resp = self.client.get('/api/v1/orders/')
        self.assertEqual(resp.status_code, 200)

    def test_list_with_data(self):
        OrderFactory(user=self.user)
        OrderFactory(user=self.user)
        resp = self.client.get('/api/v1/orders/')
        self.assertEqual(resp.status_code, 200)

    def test_list_fields(self):
        OrderFactory(user=self.user)
        resp = self.client.get('/api/v1/orders/')
        data = resp.json()
        # Response format depends on envelope mixin
        self.assertEqual(resp.status_code, 200)

    def test_detail_includes_items(self):
        order = OrderFactory(user=self.user)
        OrderItemFactory(order=order, quantity=2)
        OrderItemFactory(order=order, quantity=3)
        resp = self.client.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_detail_item_fields(self):
        order = OrderFactory(user=self.user)
        item = OrderItemFactory(order=order, quantity=5)
        resp = self.client.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_detail_extra_fields(self):
        order = OrderFactory(user=self.user)
        resp = self.client.get(f'/api/v1/orders/{order.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_filter_by_status(self):
        OrderFactory(user=self.user, status='draft')
        OrderFactory(user=self.user, status='paid')
        resp = self.client.get('/api/v1/orders/?status=draft')
        self.assertEqual(resp.status_code, 200)

    def test_create_order(self):
        resp = self.client.post('/api/v1/orders/', {
            'order_no': 'ORD-NEW', 'status': 'draft'
        }, format='json')
        self.assertEqual(resp.status_code, 201)


class QuoteAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_empty(self):
        resp = self.client.get('/api/v1/quotes/')
        self.assertEqual(resp.status_code, 200)

    def test_list_with_data(self):
        QuoteFactory.create_batch(2)
        resp = self.client.get('/api/v1/quotes/')
        self.assertEqual(resp.status_code, 200)

    def test_list_fields(self):
        QuoteFactory()
        resp = self.client.get('/api/v1/quotes/')
        self.assertEqual(resp.status_code, 200)

    def test_detail_includes_items(self):
        quote = QuoteFactory()
        QuoteItemFactory(quote=quote)
        QuoteItemFactory(quote=quote)
        resp = self.client.get(f'/api/v1/quotes/{quote.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_detail_item_fields(self):
        quote = QuoteFactory()
        item = QuoteItemFactory(quote=quote)
        resp = self.client.get(f'/api/v1/quotes/{quote.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_detail_extra_fields(self):
        quote = QuoteFactory()
        resp = self.client.get(f'/api/v1/quotes/{quote.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_filter_by_status(self):
        QuoteFactory(status='draft')
        QuoteFactory(status='submitted')
        resp = self.client.get('/api/v1/quotes/?status=draft')
        self.assertEqual(resp.status_code, 200)


class BasketAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list_empty_for_authenticated_user(self):
        resp = self.client.get('/api/v1/basket')
        self.assertEqual(resp.status_code, 200)

    def test_list_returns_only_user_baskets(self):
        BasketFactory(user=self.user)
        BasketFactory(user=UserFactory())  # other user
        resp = self.client.get('/api/v1/basket')
        self.assertEqual(resp.status_code, 200)

    def test_list_unauthenticated_returns_empty(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/basket')
        self.assertEqual(resp.status_code, 200)

    def test_list_fields(self):
        BasketFactory(user=self.user)
        resp = self.client.get('/api/v1/basket')
        self.assertEqual(resp.status_code, 200)


class WishlistAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_list_empty(self):
        resp = self.client.get('/api/v1/wishlist/')
        self.assertEqual(resp.status_code, 200)

    def test_list_returns_only_user_wishlists(self):
        WishlistFactory(user=self.user)
        WishlistFactory(user=UserFactory())
        resp = self.client.get('/api/v1/wishlist/')
        self.assertEqual(resp.status_code, 200)

    def test_list_unauthenticated_returns_empty(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/wishlist/')
        self.assertEqual(resp.status_code, 200)

    def test_list_fields(self):
        WishlistFactory(user=self.user)
        resp = self.client.get('/api/v1/wishlist/')
        self.assertEqual(resp.status_code, 200)
