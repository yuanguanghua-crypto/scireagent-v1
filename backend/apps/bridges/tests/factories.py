import factory
from apps.bridges.models import (
    ProductMethod, MethodProtocol, ProductReference, ProductCompatibility,
    ProductProduct, ProductProtocol, ProductMethodRelation,
)
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory, ReferenceFactory, CompatibilityFactory


class ProductMethodRelationFactory(factory.django.DjangoModelFactory):
    """PMR 工厂（双 edge）。

    默认造一条 REVIEW 草稿（verified_applicability + source_reagent_class=None），
    豁免 PMR-01 分支 2（仅 ACTIVE verified 强约束 evidence 三件套），可直接落库。
    derived_relevance 场景需显式传 relation_type + source_reagent_class（且 evidence 全空）。
    """
    class Meta:
        model = ProductMethodRelation

    product = factory.SubFactory(ProductFactory)
    method = factory.SubFactory(MethodFactory)
    relation_type = 'verified_applicability'
    source_reagent_class = None
    evidence_type = ''
    evidence_reference = None
    evidence_strength = ''
    evidence_note = ''
    curator = ''
    status = 'review'


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


class ProductProtocolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductProtocol
    product = factory.SubFactory(ProductFactory)
    protocol = factory.SubFactory(ProtocolFactory)
    relevance_score = 0.0
    link_source = 'inherited'
    tier = 'featured'
