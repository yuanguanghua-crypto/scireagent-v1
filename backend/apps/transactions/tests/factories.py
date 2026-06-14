import factory
from decimal import Decimal
from datetime import date, timedelta
from apps.transactions.models import (
    Order, OrderItem, Invoice, PaymentRecord, ShippingRecord,
    Quote, QuoteItem, Basket, Wishlist,
)
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.accounts.tests.factories import UserFactory


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order
    order_no = factory.Sequence(lambda n: f'ORD-20260101-{n:04d}')
    status = 'draft'
    payment_method = 'purchase_order'
    po_number = factory.Sequence(lambda n: f'PO-{n:06d}')
    grand_total = factory.LazyFunction(lambda: Decimal('999.99'))


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem
    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    sku = factory.SubFactory(SKUFactory)
    quantity = 1
    unit_price = factory.LazyFunction(lambda: Decimal('99.99'))


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invoice
    order = factory.SubFactory(OrderFactory)
    invoice_no = factory.Sequence(lambda n: f'INV-20260101-{n:04d}')
    status = 'draft'
    due_date = factory.LazyFunction(lambda: date.today() + timedelta(days=30))
    grand_total = factory.LazyFunction(lambda: Decimal('999.99'))


class PaymentRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentRecord
    invoice = factory.SubFactory(InvoiceFactory)
    method = 'wire'
    amount = factory.LazyFunction(lambda: Decimal('999.99'))
    status = 'pending'


class ShippingRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ShippingRecord
    order = factory.SubFactory(OrderFactory)
    status = 'preparing'
    carrier = 'FedEx'
    tracking_number = factory.Sequence(lambda n: f'TRACK-{n:08d}')


class QuoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Quote
    quote_no = factory.Sequence(lambda n: f'QT-{n:06d}')
    contact_name = factory.Faker('name')
    company_name = factory.Faker('company')


class QuoteItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QuoteItem
    quote = factory.SubFactory(QuoteFactory)
    product = factory.SubFactory(ProductFactory)
    sku = factory.SubFactory(SKUFactory)


class BasketFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Basket
    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)
    sku = factory.SubFactory(SKUFactory)
    quantity = 1


class WishlistFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Wishlist
    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f'Wishlist {n}')
