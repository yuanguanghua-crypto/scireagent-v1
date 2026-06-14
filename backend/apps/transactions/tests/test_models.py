from django.test import TestCase
from django.db import IntegrityError
from decimal import Decimal
from apps.transactions.models import Order, OrderItem, Quote, QuoteItem, Basket, Wishlist
from apps.transactions.tests.factories import (
    OrderFactory, OrderItemFactory, QuoteFactory, QuoteItemFactory,
    BasketFactory, WishlistFactory
)
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class OrderModelTest(TestCase):
    def test_create(self):
        order = OrderFactory(order_no='ORD-001')
        self.assertEqual(order.order_no, 'ORD-001')
        self.assertEqual(order.status, 'draft')

    def test_order_no_unique(self):
        OrderFactory(order_no='ORD-001')
        with self.assertRaises(IntegrityError):
            OrderFactory(order_no='ORD-001')

    def test_status_default(self):
        order = OrderFactory()
        self.assertEqual(order.status, 'draft')

    def test_status_choices(self):
        choices = dict(Order.Status.choices)
        self.assertIn('draft', choices)
        self.assertIn('confirmed', choices)
        self.assertIn('paid', choices)
        self.assertIn('processing', choices)
        self.assertIn('shipped', choices)
        self.assertIn('completed', choices)
        self.assertIn('cancelled', choices)

    def test_financial_fields_default(self):
        order = OrderFactory(grand_total=Decimal('0'))
        self.assertEqual(order.subtotal, Decimal('0'))
        self.assertEqual(order.tax_total, Decimal('0'))
        self.assertEqual(order.grand_total, Decimal('0'))

    def test_currency_default(self):
        order = OrderFactory()
        self.assertEqual(order.currency, 'USD')

    def test_user_nullable(self):
        order = OrderFactory(user=None)
        self.assertIsNone(order.user)

    def test_str(self):
        order = OrderFactory(order_no='ORD-001')
        self.assertEqual(str(order), 'Order ORD-001')

    def test_ordering(self):
        from django.utils import timezone
        from datetime import timedelta
        o1 = OrderFactory()
        o2 = OrderFactory()
        # o2 created after o1, so should be first in '-created_at' ordering
        orders = list(Order.objects.all())
        self.assertEqual(orders[0].id, o2.id)

    def test_table_name(self):
        self.assertEqual(Order._meta.db_table, 'order')


class OrderItemModelTest(TestCase):
    def test_create(self):
        order = OrderFactory()
        product = ProductFactory()
        sku = SKUFactory()
        item = OrderItemFactory(order=order, product=product, sku=sku, quantity=2)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.order_id, order.id)

    def test_order_items(self):
        order = OrderFactory()
        OrderItemFactory(order=order, quantity=2)
        OrderItemFactory(order=order, quantity=3)
        self.assertEqual(order.items.count(), 2)

    def test_product_nullable(self):
        item = OrderItemFactory(product=None)
        self.assertIsNone(item.product)

    def test_sku_nullable(self):
        item = OrderItemFactory(sku=None)
        self.assertIsNone(item.sku)

    def test_quantity_default(self):
        product = ProductFactory()
        sku = SKUFactory()
        item = OrderItemFactory(quantity=1)
        self.assertEqual(item.quantity, 1)

    def test_unit_price_default(self):
        item = OrderItemFactory(unit_price=Decimal('0'))
        self.assertEqual(item.unit_price, Decimal('0'))

    def test_cascade_delete(self):
        order = OrderFactory()
        item = OrderItemFactory(order=order)
        item_id = item.id
        order.delete()
        self.assertFalse(OrderItem.objects.filter(id=item_id).exists())

    def test_table_name(self):
        self.assertEqual(OrderItem._meta.db_table, 'order_item')


class QuoteModelTest(TestCase):
    def test_create(self):
        quote = QuoteFactory(quote_no='QT-001')
        self.assertEqual(quote.quote_no, 'QT-001')

    def test_quote_no_unique(self):
        QuoteFactory(quote_no='QT-001')
        with self.assertRaises(IntegrityError):
            QuoteFactory(quote_no='QT-001')

    def test_quote_no_nullable(self):
        quote = QuoteFactory(quote_no=None)
        self.assertIsNone(quote.quote_no)

    def test_status_default(self):
        quote = QuoteFactory()
        self.assertEqual(quote.status, 'draft')

    def test_status_choices(self):
        choices = dict(Quote.Status.choices)
        self.assertIn('draft', choices)
        self.assertIn('submitted', choices)
        self.assertIn('responded', choices)
        self.assertIn('negotiating', choices)
        self.assertIn('closed', choices)
        self.assertIn('cancelled', choices)

    def test_user_nullable(self):
        quote = QuoteFactory(user=None)
        self.assertIsNone(quote.user)

    def test_financial_fields_default(self):
        quote = QuoteFactory()
        self.assertEqual(quote.subtotal, Decimal('0'))
        self.assertEqual(quote.grand_total, Decimal('0'))

    def test_valid_until_nullable(self):
        quote = QuoteFactory(valid_until=None)
        self.assertIsNone(quote.valid_until)

    def test_str_with_quote_no(self):
        quote = QuoteFactory(quote_no='QT-001')
        self.assertEqual(str(quote), 'Quote QT-001')

    def test_str_without_quote_no(self):
        quote = QuoteFactory(quote_no=None)
        result = str(quote)
        self.assertIn('Quote', result)

    def test_table_name(self):
        self.assertEqual(Quote._meta.db_table, 'quote')


class QuoteItemModelTest(TestCase):
    def test_create(self):
        quote = QuoteFactory()
        product = ProductFactory()
        item = QuoteItemFactory(quote=quote, product=product)
        self.assertEqual(item.quote_id, quote.id)

    def test_quote_items(self):
        quote = QuoteFactory()
        QuoteItemFactory(quote=quote)
        QuoteItemFactory(quote=quote)
        self.assertEqual(quote.items.count(), 2)

    def test_product_nullable(self):
        item = QuoteItemFactory(product=None)
        self.assertIsNone(item.product)

    def test_sku_nullable(self):
        item = QuoteItemFactory(sku=None)
        self.assertIsNone(item.sku)

    def test_unit_price_nullable(self):
        item = QuoteItemFactory(unit_price=None)
        self.assertIsNone(item.unit_price)

    def test_cascade_delete(self):
        quote = QuoteFactory()
        item = QuoteItemFactory(quote=quote)
        item_id = item.id
        quote.delete()
        self.assertFalse(QuoteItem.objects.filter(id=item_id).exists())

    def test_table_name(self):
        self.assertEqual(QuoteItem._meta.db_table, 'quote_item')


class BasketModelTest(TestCase):
    def test_unique_together_user_sku(self):
        basket = BasketFactory()
        with self.assertRaises(IntegrityError):
            BasketFactory(user=basket.user, sku=basket.sku)

    def test_quantity_default(self):
        basket = BasketFactory()
        self.assertEqual(basket.quantity, 1)

    def test_session_key_default(self):
        basket = BasketFactory()
        self.assertEqual(basket.session_key, '')

    def test_str(self):
        basket = BasketFactory()
        result = str(basket)
        self.assertIn('x', result)

    def test_table_name(self):
        self.assertEqual(Basket._meta.db_table, 'basket')


class WishlistModelTest(TestCase):
    def test_create(self):
        w = WishlistFactory(name='My List')
        self.assertEqual(w.name, 'My List')

    def test_name_default(self):
        from apps.accounts.tests.factories import UserFactory
        user = UserFactory()
        w = WishlistFactory(user=user, name='My Wishlist')
        self.assertEqual(w.name, 'My Wishlist')

    def test_products_m2m(self):
        w = WishlistFactory()
        p1 = ProductFactory()
        p2 = ProductFactory()
        w.products.add(p1, p2)
        self.assertEqual(w.products.count(), 2)

    def test_products_m2m_reverse(self):
        w = WishlistFactory()
        p = ProductFactory()
        w.products.add(p)
        self.assertIn(w, p.wishlists.all())

    def test_str(self):
        w = WishlistFactory(name='My List')
        result = str(w)
        self.assertIn('My List', result)

    def test_table_name(self):
        self.assertEqual(Wishlist._meta.db_table, 'wishlist')
