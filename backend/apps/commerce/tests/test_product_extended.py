"""Phase 1 TDD: Product extended field tests (TC-P-001 ~ TC-P-012)"""
from django.test import TestCase
from django.db import IntegrityError
from apps.commerce.tests.factories import ProductFactory


class ProductExtendedFieldTest(TestCase):
    def test_catalog_no_nullable(self):
        """TC-P-001: catalog_no can be null"""
        product = ProductFactory(catalog_no=None)
        self.assertIsNone(product.catalog_no)

    def test_catalog_no_unique(self):
        """TC-P-002: catalog_no must be unique when set"""
        ProductFactory(catalog_no='SC8111')
        with self.assertRaises(IntegrityError):
            ProductFactory(catalog_no='SC8111')

    def test_formula_storage(self):
        """TC-P-003: formula stores molecular formula"""
        product = ProductFactory(formula='C11H12N2O5')
        self.assertEqual(product.formula, 'C11H12N2O5')

    def test_molecular_weight_float(self):
        """TC-P-004: molecular_weight stores float"""
        product = ProductFactory(molecular_weight=283.24)
        self.assertAlmostEqual(product.molecular_weight, 283.24)

    def test_molecular_weight_nullable(self):
        """TC-P-004b: molecular_weight can be null"""
        product = ProductFactory(molecular_weight=None)
        self.assertIsNone(product.molecular_weight)

    def test_concentration_storage(self):
        """TC-P-005: concentration stores concentration value"""
        product = ProductFactory(concentration='100 mM')
        self.assertEqual(product.concentration, '100 mM')

    def test_overview_long_text(self):
        """TC-P-006: overview can store 5000 characters"""
        long_text = 'A' * 5000
        product = ProductFactory(overview=long_text)
        self.assertEqual(len(product.overview), 5000)

    def test_structure_svg_storage(self):
        """TC-P-007: structure_svg stores SVG XML"""
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        product = ProductFactory(structure_svg=svg)
        self.assertIn('<svg', product.structure_svg)

    def test_seo_title_default_empty(self):
        """TC-P-008: seo_title defaults to empty"""
        product = ProductFactory()
        self.assertEqual(product.seo_title, '')

    def test_seo_description_default_empty(self):
        """TC-P-009: seo_description defaults to empty"""
        product = ProductFactory()
        self.assertEqual(product.seo_description, '')

    def test_category_l1_storage(self):
        """TC-P-010: category_l1 stores primary category"""
        product = ProductFactory(category_l1='nucleotides_nucleosides')
        self.assertEqual(product.category_l1, 'nucleotides_nucleosides')

    def test_category_l2_with_l3_concat(self):
        """TC-P-011: category_l2 can store L2|L3 concatenated value"""
        product = ProductFactory(category_l2='click_chemistry | 5-Formyl')
        self.assertEqual(product.category_l2, 'click_chemistry | 5-Formyl')
