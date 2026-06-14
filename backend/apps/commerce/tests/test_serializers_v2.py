"""
TDD Tests for V1.2 Serializers.
Phase 1, Week 3.
"""
import pytest
from decimal import Decimal
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory,
    ProtocolStepFactory, ReferenceFactory,
)


@pytest.mark.django_db
class TestApplicationBriefSerializer:
    """T3-01 ~ T3-02."""

    def test_t3_01_fields(self):
        """T3-01: ApplicationBriefSerializer fields are id, name, slug, summary."""
        from apps.commerce.api.v1.serializers_v2 import ApplicationBriefSerializer
        app = ApplicationFactory(name='RNA Labeling', slug='rna-labeling', summary='Test summary')
        data = ApplicationBriefSerializer(app).data
        assert set(data.keys()) == {'id', 'name', 'slug', 'summary'}
        assert data['name'] == 'RNA Labeling'
        assert data['summary'] == 'Test summary'

    def test_t3_02_uses_summary_not_description(self):
        """T3-02: Uses summary field, not description."""
        from apps.commerce.api.v1.serializers_v2 import ApplicationBriefSerializer
        app = ApplicationFactory(summary='Test summary')
        data = ApplicationBriefSerializer(app).data
        assert 'summary' in data
        assert 'description' not in data


@pytest.mark.django_db
class TestMethodBriefSerializer:
    """T3-03."""

    def test_t3_03_fields(self):
        """T3-03: MethodBriefSerializer fields are id, name, slug, purpose."""
        from apps.commerce.api.v1.serializers_v2 import MethodBriefSerializer
        method = MethodFactory(name='CuAAC', slug='cuaac', purpose='Click chemistry')
        data = MethodBriefSerializer(method).data
        assert set(data.keys()) == {'id', 'name', 'slug', 'purpose'}
        assert data['purpose'] == 'Click chemistry'


@pytest.mark.django_db
class TestProtocolBriefSerializer:
    """T3-04 ~ T3-07."""

    def test_t3_04_fields(self):
        """T3-04: ProtocolBriefSerializer fields."""
        from apps.commerce.api.v1.serializers_v2 import ProtocolBriefSerializer
        protocol = ProtocolFactory(name='Click Protocol', slug='click-protocol', objective='Label RNA')
        data = ProtocolBriefSerializer(protocol).data
        assert 'id' in data
        assert 'name' in data
        assert 'slug' in data
        assert 'objective' in data
        assert 'estimated_time_minutes' in data

    def test_t3_05_estimated_time_with_steps(self):
        """T3-05: estimated_time_minutes computed from ProtocolStep."""
        from apps.commerce.api.v1.serializers_v2 import ProtocolBriefSerializer
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, duration_seconds=60)
        ProtocolStepFactory(protocol=protocol, duration_seconds=60)
        data = ProtocolBriefSerializer(protocol).data
        assert data['estimated_time_minutes'] == 2

    def test_t3_06_estimated_time_no_steps(self):
        """T3-06: estimated_time_minutes is 0 when no steps."""
        from apps.commerce.api.v1.serializers_v2 import ProtocolBriefSerializer
        protocol = ProtocolFactory()
        data = ProtocolBriefSerializer(protocol).data
        assert data['estimated_time_minutes'] == 0

    def test_t3_07_estimated_time_null_duration(self):
        """T3-07: estimated_time_minutes handles null duration_seconds."""
        from apps.commerce.api.v1.serializers_v2 import ProtocolBriefSerializer
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, duration_seconds=None)
        data = ProtocolBriefSerializer(protocol).data
        assert data['estimated_time_minutes'] == 0


@pytest.mark.django_db
class TestProductBriefSerializer:
    """T3-08."""

    def test_t3_08_fields(self):
        """T3-08: ProductBriefSerializer fields."""
        from apps.commerce.api.v1.serializers_v2 import ProductBriefSerializer
        product = ProductFactory(name='Test Product', catalog_no='SC8047', cas='12345-67-8')
        data = ProductBriefSerializer(product).data
        assert set(data.keys()) == {'id', 'name', 'slug', 'catalog_no', 'cas'}
        assert data['catalog_no'] == 'SC8047'


@pytest.mark.django_db
class TestReferenceBriefSerializer:
    """T3-09."""

    def test_t3_09_fields(self):
        """T3-09: ReferenceBriefSerializer fields."""
        from apps.commerce.api.v1.serializers_v2 import ReferenceBriefSerializer
        ref = ReferenceFactory(title='Test Paper', journal='Nature', year=2024, doi='10.1234/test')
        data = ReferenceBriefSerializer(ref).data
        assert set(data.keys()) == {'id', 'title', 'journal', 'year', 'doi'}
        assert data['title'] == 'Test Paper'


@pytest.mark.django_db
class TestRelatedProductSerializer:
    """T3-10."""

    def test_t3_10_fields(self):
        """T3-10: RelatedProductSerializer fields."""
        from apps.commerce.api.v1.serializers_v2 import RelatedProductSerializer
        data = RelatedProductSerializer({
            'id': 1, 'name': 'Test', 'catalog_no': 'SC8047',
            'cas': '12345-67-8', 'match_reason': 'Same Application'
        }).data
        assert set(data.keys()) == {'id', 'name', 'catalog_no', 'cas', 'match_reason'}
        assert data['match_reason'] == 'Same Application'


@pytest.mark.django_db
class TestFAQSerializer:
    """T3-11."""

    def test_t3_11_fields(self):
        """T3-11: FAQSerializer fields."""
        from apps.commerce.api.v1.serializers_v2 import FAQSerializer
        data = FAQSerializer({'question': 'What is X?', 'answer': 'Y'}).data
        assert set(data.keys()) == {'question', 'answer'}
        assert data['question'] == 'What is X?'


@pytest.mark.django_db
class TestProductFullSerializer:
    """T3-12 ~ T3-16."""

    def test_t3_12_has_all_product_fields(self):
        """T3-12: ProductFullSerializer has all product fields."""
        from apps.commerce.api.v1.serializers_v2 import ProductFullSerializer
        product = ProductFactory(
            catalog_no='SC8047', formula='C10H14N5O12P3',
            molecular_weight=587.21, concentration='100 mM'
        )
        data = ProductFullSerializer(product).data
        assert data['catalog_no'] == 'SC8047'
        assert data['formula'] == 'C10H14N5O12P3'
        assert data['molecular_weight'] == 587.21
        assert data['concentration'] == '100 mM'

    def test_t3_13_has_product_class_name(self):
        """T3-13: ProductFullSerializer has product_class_name."""
        from apps.commerce.api.v1.serializers_v2 import ProductFullSerializer
        from apps.commerce.tests.factories import ProductClassFactory
        pc = ProductClassFactory(name='Modified Nucleotides')
        product = ProductFactory(product_class=pc)
        data = ProductFullSerializer(product).data
        assert data['product_class_name'] == 'Modified Nucleotides'

    def test_t3_14_has_product_class_path(self):
        """T3-14: ProductFullSerializer has product_class_path."""
        from apps.commerce.api.v1.serializers_v2 import ProductFullSerializer
        from apps.commerce.tests.factories import ProductClassFactory
        parent = ProductClassFactory(name='Nucleotides', slug='nucleotides')
        child = ProductClassFactory(name='Modified', slug='modified', parent=parent)
        product = ProductFactory(product_class=child)
        data = ProductFullSerializer(product).data
        assert data['product_class_path'] == ['Nucleotides', 'Modified']

    def test_t3_15_includes_nested_skus(self):
        """T3-15: ProductFullSerializer includes nested skus."""
        from apps.commerce.api.v1.serializers_v2 import ProductFullSerializer
        product = ProductFactory()
        SKUFactory(product=product, sku_code='SKU-001')
        SKUFactory(product=product, sku_code='SKU-002')
        data = ProductFullSerializer(product).data
        assert len(data['skus']) == 2

    def test_t3_16_includes_nested_documents(self):
        """T3-16: ProductFullSerializer includes nested documents."""
        from apps.commerce.api.v1.serializers_v2 import ProductFullSerializer
        from apps.commerce.tests.factories import ProductDocumentFactory
        product = ProductFactory()
        ProductDocumentFactory(product=product)
        data = ProductFullSerializer(product).data
        assert len(data['documents']) == 1
