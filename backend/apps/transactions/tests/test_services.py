from django.test import TestCase
from decimal import Decimal
from apps.transactions.services import TransactionService
from apps.transactions.models import Order, OrderItem, Basket
from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class TransactionServiceCreateOrderTest(TestCase):
    def test_create_order(self):
        user = UserFactory()
        product = ProductFactory()
        sku = SKUFactory(product=product)
        items_data = [
            {'product': product, 'sku': sku, 'quantity': 2, 'unit_price': Decimal('99.99')},
        ]
        order = TransactionService.create_order(user, items_data)
        self.assertTrue(Order.objects.filter(id=order.id).exists())
        self.assertEqual(order.user_id, user.id)

    def test_create_order_generates_order_no(self):
        user = UserFactory()
        product = ProductFactory()
        sku = SKUFactory(product=product)
        items_data = [
            {'product': product, 'sku': sku, 'quantity': 1, 'unit_price': Decimal('50.00')},
        ]
        order = TransactionService.create_order(user, items_data)
        self.assertTrue(order.order_no.startswith('ORD-'))
        self.assertTrue(len(order.order_no) > 4)

    def test_create_order_calculates_totals(self):
        user = UserFactory()
        product = ProductFactory()
        sku1 = SKUFactory(product=product, sku_code='SKU-A')
        sku2 = SKUFactory(product=product, sku_code='SKU-B')
        items_data = [
            {'product': product, 'sku': sku1, 'quantity': 2, 'unit_price': Decimal('50.00')},
            {'product': product, 'sku': sku2, 'quantity': 1, 'unit_price': Decimal('100.00')},
        ]
        order = TransactionService.create_order(user, items_data)
        order.refresh_from_db()
        self.assertEqual(order.subtotal, Decimal('200.00'))
        self.assertEqual(order.grand_total, Decimal('200.00'))

    def test_create_order_creates_items(self):
        user = UserFactory()
        product = ProductFactory()
        sku = SKUFactory(product=product)
        items_data = [
            {'product': product, 'sku': sku, 'quantity': 3, 'unit_price': Decimal('25.00')},
        ]
        order = TransactionService.create_order(user, items_data)
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.unit_price, Decimal('25.00'))

    def test_create_order_no_items(self):
        user = UserFactory()
        order = TransactionService.create_order(user, [])
        self.assertEqual(order.items.count(), 0)
        self.assertEqual(order.subtotal, Decimal('0'))
        self.assertEqual(order.grand_total, Decimal('0'))

    def test_create_order_status_pending(self):
        user = UserFactory()
        order = TransactionService.create_order(user, [])
        self.assertEqual(order.status, 'draft')


class TransactionServiceAddToBasketTest(TestCase):
    def test_add_to_basket(self):
        user = UserFactory()
        product = ProductFactory()
        sku = SKUFactory(product=product)
        basket = TransactionService.add_to_basket(user, product.id, sku.id, 2)
        self.assertEqual(basket.quantity, 2)
        self.assertEqual(basket.user_id, user.id)

    def test_add_to_basket_creates(self):
        user = UserFactory()
        product = ProductFactory()
        sku = SKUFactory(product=product)
        TransactionService.add_to_basket(user, product.id, sku.id)
        self.assertTrue(Basket.objects.filter(user=user, sku=sku).exists())

    def test_add_to_basket_updates_existing(self):
        user = UserFactory()
        product = ProductFactory()
        sku = SKUFactory(product=product)
        TransactionService.add_to_basket(user, product.id, sku.id, 1)
        TransactionService.add_to_basket(user, product.id, sku.id, 5)
        basket = Basket.objects.get(user=user, sku=sku)
        self.assertEqual(basket.quantity, 5)

    def test_add_to_basket_default_quantity(self):
        user = UserFactory()
        product = ProductFactory()
        sku = SKUFactory(product=product)
        basket = TransactionService.add_to_basket(user, product.id, sku.id)
        self.assertEqual(basket.quantity, 1)
