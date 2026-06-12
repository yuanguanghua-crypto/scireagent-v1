from django.test import TestCase
from decimal import Decimal
from apps.transactions.api.v1.serializers import (
    OrderListSerializer, OrderDetailSerializer, OrderItemSerializer,
    QuoteListSerializer, QuoteDetailSerializer, QuoteItemSerializer,
    BasketSerializer, WishlistSerializer
)
from apps.transactions.tests.factories import (
    OrderFactory, OrderItemFactory, QuoteFactory, QuoteItemFactory,
    BasketFactory, WishlistFactory
)


class OrderListSerializerTest(TestCase):
    def test_fields(self):
        order = OrderFactory(order_no='ORD-001')
        serializer = OrderListSerializer(order)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('order_no', data)
        self.assertIn('status', data)
        self.assertIn('subtotal', data)
        self.assertIn('grand_total', data)
        self.assertIn('currency', data)
        self.assertIn('created_at', data)


class OrderDetailSerializerTest(TestCase):
    def test_items_field(self):
        order = OrderFactory()
        OrderItemFactory(order=order, quantity=2)
        OrderItemFactory(order=order, quantity=3)
        serializer = OrderDetailSerializer(order)
        self.assertEqual(len(serializer.data['items']), 2)

    def test_extra_fields(self):
        order = OrderFactory()
        serializer = OrderDetailSerializer(order)
        data = serializer.data
        self.assertIn('tax_total', data)
        self.assertIn('comment', data)
        self.assertIn('user_id', data)


class OrderItemSerializerTest(TestCase):
    def test_fields(self):
        item = OrderItemFactory(quantity=5, unit_price=Decimal('19.99'))
        serializer = OrderItemSerializer(item)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_id', data)
        self.assertIn('quantity', data)
        self.assertIn('unit_price', data)


class QuoteListSerializerTest(TestCase):
    def test_fields(self):
        quote = QuoteFactory(quote_no='QT-001')
        serializer = QuoteListSerializer(quote)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('quote_no', data)
        self.assertIn('company_name', data)
        self.assertIn('contact_name', data)
        self.assertIn('status', data)
        self.assertIn('grand_total', data)


class QuoteDetailSerializerTest(TestCase):
    def test_items_field(self):
        quote = QuoteFactory()
        QuoteItemFactory(quote=quote)
        serializer = QuoteDetailSerializer(quote)
        self.assertEqual(len(serializer.data['items']), 1)

    def test_extra_fields(self):
        quote = QuoteFactory()
        serializer = QuoteDetailSerializer(quote)
        data = serializer.data
        self.assertIn('contact_email', data)
        self.assertIn('contact_phone', data)
        self.assertIn('country', data)
        self.assertIn('valid_until', data)
        self.assertIn('remark', data)


class QuoteItemSerializerTest(TestCase):
    def test_fields(self):
        item = QuoteItemFactory()
        serializer = QuoteItemSerializer(item)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_id', data)
        self.assertIn('quantity', data)
        self.assertIn('unit_price', data)
        self.assertIn('note', data)


class BasketSerializerTest(TestCase):
    def test_fields(self):
        basket = BasketFactory()
        serializer = BasketSerializer(basket)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_id', data)
        self.assertIn('quantity', data)
        self.assertIn('product_name', data)
        self.assertIn('sku_code', data)

    def test_product_name_source(self):
        basket = BasketFactory()
        serializer = BasketSerializer(basket)
        self.assertEqual(serializer.data['product_name'], basket.product.name)

    def test_sku_code_source(self):
        basket = BasketFactory()
        serializer = BasketSerializer(basket)
        self.assertEqual(serializer.data['sku_code'], basket.sku.sku_code)


class WishlistSerializerTest(TestCase):
    def test_fields(self):
        wishlist = WishlistFactory(name='My List')
        serializer = WishlistSerializer(wishlist)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('product_count', data)

    def test_product_count(self):
        from apps.commerce.tests.factories import ProductFactory
        wishlist = WishlistFactory()
        p1 = ProductFactory()
        p2 = ProductFactory()
        wishlist.products.add(p1, p2)
        serializer = WishlistSerializer(wishlist)
        self.assertEqual(serializer.data['product_count'], 2)

    def test_product_count_empty(self):
        wishlist = WishlistFactory()
        serializer = WishlistSerializer(wishlist)
        self.assertEqual(serializer.data['product_count'], 0)
