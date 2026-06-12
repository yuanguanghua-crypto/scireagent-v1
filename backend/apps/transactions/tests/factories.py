import factory
from decimal import Decimal
from apps.transactions.models import Order, OrderItem, Quote, QuoteItem, Basket, Wishlist
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.accounts.tests.factories import UserFactory


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order
    order_no = factory.Sequence(lambda n: f'ORD-{n:06d}')


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem
    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    sku = factory.SubFactory(SKUFactory)
    quantity = 1
    unit_price = factory.LazyFunction(lambda: Decimal('99.99'))


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
