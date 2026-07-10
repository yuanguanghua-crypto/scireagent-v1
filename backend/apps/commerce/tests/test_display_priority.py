"""
TDD Tests for display_priority field on Product model.
Phase 1, Week 1.
"""
import pytest
from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory


@pytest.mark.django_db
class TestProductDisplayPriority:
    """T1-01 ~ T1-04: Product display_priority field."""

    def test_t1_01_default_value(self):
        """T1-01: Product has display_priority with default 0."""
        product = ProductFactory()
        assert product.display_priority == 0

    def test_t1_02_can_set_value(self):
        """T1-03: Product can set display_priority."""
        product = ProductFactory(display_priority=100)
        product.refresh_from_db()
        assert product.display_priority == 100

    def test_t1_03_filter_gt_zero(self):
        """T1-04: Filter products by display_priority > 0."""
        ProductFactory(display_priority=10)
        ProductFactory(display_priority=0)
        ProductFactory(display_priority=50)
        result = Product.objects.filter(display_priority__gt=0)
        assert result.count() == 2

    def test_t1_04_order_by_priority(self):
        """Products with higher priority come first."""
        p1 = ProductFactory(display_priority=10)
        p2 = ProductFactory(display_priority=100)
        p3 = ProductFactory(display_priority=50)
        result = list(Product.objects.filter(display_priority__gt=0).order_by('-display_priority'))
        assert result[0].id == p2.id
        assert result[1].id == p3.id
        assert result[2].id == p1.id
