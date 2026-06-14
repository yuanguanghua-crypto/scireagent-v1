"""
TDD Tests for faq_service and product_relationship_service.
Phase 1, Week 3.
"""
import pytest
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory,
)
from apps.bridges.models import ProductMethod


@pytest.mark.django_db
class TestFAQService:
    """T3-31 ~ T3-37: FAQ generation service."""

    def test_t3_31_faq_with_applications(self):
        """T3-31: FAQ with applications returns 'What is X used for?'."""
        from apps.commerce.services.faq_service import generate_faq
        product = ProductFactory(name='2-azido-dATP')
        app = ApplicationFactory(name='RNA Labeling', status='active')
        method = MethodFactory(application=app, status='active')
        ProductMethod.objects.create(product=product, method=method)
        faq = generate_faq(product)
        questions = [q['question'] for q in faq]
        assert any('used for' in q for q in questions)

    def test_t3_32_faq_with_methods(self):
        """T3-32: FAQ with methods returns 'Which methods use X?'."""
        from apps.commerce.services.faq_service import generate_faq
        product = ProductFactory(name='Test Product')
        method = MethodFactory(name='CuAAC', status='active')
        ProductMethod.objects.create(product=product, method=method)
        faq = generate_faq(product)
        questions = [q['question'] for q in faq]
        assert any('methods' in q.lower() for q in questions)

    def test_t3_33_faq_with_storage(self):
        """T3-33: FAQ with storage returns 'How should X be stored?'."""
        from apps.commerce.services.faq_service import generate_faq
        product = ProductFactory(name='Test Product', storage='-20C')
        faq = generate_faq(product)
        questions = [q['question'] for q in faq]
        assert any('stored' in q.lower() for q in questions)

    def test_t3_34_faq_with_protocols(self):
        """T3-34: FAQ with protocols returns 'Which protocols use X?'."""
        from apps.commerce.services.faq_service import generate_faq
        from apps.bridges.models import MethodProtocol
        product = ProductFactory(name='Test Product')
        method = MethodFactory(status='active')
        protocol = ProtocolFactory(method=method, name='Click Protocol', status='published')
        ProductMethod.objects.create(product=product, method=method)
        MethodProtocol.objects.create(method=method, protocol=protocol)
        faq = generate_faq(product)
        questions = [q['question'] for q in faq]
        assert any('protocols' in q.lower() for q in questions)

    def test_t3_35_faq_with_all_data(self):
        """T3-35: FAQ with all data returns 4 items."""
        from apps.commerce.services.faq_service import generate_faq
        from apps.bridges.models import MethodProtocol
        product = ProductFactory(name='Test', storage='-20C')
        app = ApplicationFactory(name='RNA Labeling', status='active')
        method = MethodFactory(application=app, name='CuAAC', status='active')
        protocol = ProtocolFactory(method=method, name='Click Protocol', status='published')
        ProductMethod.objects.create(product=product, method=method)
        MethodProtocol.objects.create(method=method, protocol=protocol)
        faq = generate_faq(product)
        assert len(faq) == 4

    def test_t3_36_faq_with_no_data(self):
        """T3-36: FAQ with no data returns empty list."""
        from apps.commerce.services.faq_service import generate_faq
        product = ProductFactory(name='Test', storage='')
        faq = generate_faq(product)
        assert len(faq) == 0

    def test_t3_37_faq_with_only_storage(self):
        """T3-37: FAQ with only storage returns 1 item."""
        from apps.commerce.services.faq_service import generate_faq
        product = ProductFactory(name='Test', storage='-20C')
        faq = generate_faq(product)
        assert len(faq) == 1
        assert 'stored' in faq[0]['question'].lower()


@pytest.mark.django_db
class TestProductRelationshipService:
    """T3-38 ~ T3-44: Related products service."""

    def test_t3_38_same_application(self):
        """T3-38: Products in same application appear with high score."""
        from apps.commerce.services.product_relationship_service import get_related_products
        app = ApplicationFactory(name='RNA Labeling', status='active')
        method = MethodFactory(application=app, status='active')
        product = ProductFactory(status='active')
        related = ProductFactory(status='active', name='Related Product')
        ProductMethod.objects.create(product=product, method=method)
        ProductMethod.objects.create(product=related, method=method)
        result = get_related_products(product, limit=4)
        assert len(result) >= 1
        assert result[0]['match_reason'] == 'Same Application'

    def test_t3_39_same_method(self):
        """T3-39: Products in same method appear."""
        from apps.commerce.services.product_relationship_service import get_related_products
        method = MethodFactory(status='active')
        product = ProductFactory(status='active')
        related = ProductFactory(status='active')
        ProductMethod.objects.create(product=product, method=method)
        ProductMethod.objects.create(product=related, method=method)
        result = get_related_products(product, limit=4)
        assert len(result) >= 1

    def test_t3_40_same_category(self):
        """T3-40: Products in same category appear."""
        from apps.commerce.services.product_relationship_service import get_related_products
        from apps.commerce.tests.factories import ProductClassFactory
        pc = ProductClassFactory(name='Nucleotides')
        product = ProductFactory(status='active', product_class=pc)
        related = ProductFactory(status='active', product_class=pc)
        result = get_related_products(product, limit=4)
        assert len(result) >= 1
        assert result[0]['match_reason'] == 'Same Category'

    def test_t3_41_limit(self):
        """T3-41: Returns at most limit items."""
        from apps.commerce.services.product_relationship_service import get_related_products
        product = ProductFactory(status='active')
        for i in range(10):
            ProductFactory(status='active', product_class=product.product_class)
        result = get_related_products(product, limit=4)
        assert len(result) <= 4

    def test_t3_42_excludes_self(self):
        """T3-42: Product not in results."""
        from apps.commerce.services.product_relationship_service import get_related_products
        product = ProductFactory(status='active')
        result = get_related_products(product, limit=4)
        ids = [r['id'] for r in result]
        assert product.id not in ids

    def test_t3_43_empty_when_no_relations(self):
        """T3-43: Returns empty list when no relations."""
        from apps.commerce.services.product_relationship_service import get_related_products
        product = ProductFactory(status='active')
        result = get_related_products(product, limit=4)
        assert isinstance(result, list)

    def test_t3_44_has_match_reason(self):
        """T3-44: Each result has match_reason."""
        from apps.commerce.services.product_relationship_service import get_related_products
        from apps.commerce.tests.factories import ProductClassFactory
        pc = ProductClassFactory()
        product = ProductFactory(status='active', product_class=pc)
        ProductFactory(status='active', product_class=pc)
        result = get_related_products(product, limit=4)
        for r in result:
            assert 'match_reason' in r
