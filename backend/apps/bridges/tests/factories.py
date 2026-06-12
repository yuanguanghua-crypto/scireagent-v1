import factory
from apps.bridges.models import ProductMethod, MethodProtocol, ProductReference, ProductCompatibility, ProductProduct
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory, ReferenceFactory, CompatibilityFactory


class ProductMethodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductMethod
    product = factory.SubFactory(ProductFactory)
    method = factory.SubFactory(MethodFactory)
    role = 'reagent'


class MethodProtocolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MethodProtocol
    method = factory.SubFactory(MethodFactory)
    protocol = factory.SubFactory(ProtocolFactory)


class ProductReferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductReference
    product = factory.SubFactory(ProductFactory)
    reference = factory.SubFactory(ReferenceFactory)
    citation_role = 'supporting'


class ProductCompatibilityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductCompatibility
    source_product = factory.SubFactory(ProductFactory)
    target_product = factory.SubFactory(ProductFactory)
    compatibility = factory.SubFactory(CompatibilityFactory)
    verdict = 'compatible'


class ProductProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductProduct
    source_product = factory.SubFactory(ProductFactory)
    target_product = factory.SubFactory(ProductFactory)
    relation_type = 'related'
