import factory
from decimal import Decimal
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup


class ProductClassFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductClass
    name = factory.Sequence(lambda n: f'Class {n}')
    slug = factory.Sequence(lambda n: f'class-{n}')


class CatalogGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CatalogGroup
    name = factory.Sequence(lambda n: f'Catalog {n}')
    slug = factory.Sequence(lambda n: f'catalog-{n}')


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product
    name = factory.Sequence(lambda n: f'Product {n}')
    slug = factory.Sequence(lambda n: f'product-{n}')
    cas = factory.Sequence(lambda n: f'{n:05d}-00-0')
    smiles = 'CCO'


class SKUFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SKU
    product = factory.SubFactory(ProductFactory)
    sku_code = factory.Sequence(lambda n: f'SKU-{n:05d}')
    pack_size = '100mg'
    price = factory.LazyFunction(lambda: Decimal('99.99'))
