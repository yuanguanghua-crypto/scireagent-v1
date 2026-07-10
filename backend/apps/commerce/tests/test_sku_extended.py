"""Phase 1 TDD: SKU extended field tests (TC-S-001 ~ TC-S-006)"""
from django.test import TestCase
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class SKUExtendedFieldTest(TestCase):
    def test_concentration_storage(self):
        """TC-S-001: SKU concentration stores value"""
        sku = SKUFactory(concentration='100 mM')
        self.assertEqual(sku.concentration, '100 mM')

    def test_lead_time_storage(self):
        """TC-S-002: SKU lead_time stores value"""
        sku = SKUFactory(lead_time='1-3 business days')
        self.assertEqual(sku.lead_time, '1-3 business days')

    def test_is_default_false_by_default(self):
        """TC-S-003: is_default defaults to False"""
        sku = SKUFactory()
        self.assertFalse(sku.is_default)

    def test_is_default_true(self):
        """TC-S-004: is_default can be set to True"""
        sku = SKUFactory(is_default=True)
        self.assertTrue(sku.is_default)

    def test_multiple_skus_one_default(self):
        """TC-S-005: Only one default SKU per Product"""
        product = ProductFactory()
        SKUFactory(product=product, is_default=True, sku_code='SKU-D')
        SKUFactory(product=product, is_default=False, sku_code='SKU-N')
        defaults = product.skus.filter(is_default=True).count()
        self.assertEqual(defaults, 1)

    def test_concentration_default_empty(self):
        """TC-S-006: concentration defaults to empty"""
        sku = SKUFactory()
        self.assertEqual(sku.concentration, '')
