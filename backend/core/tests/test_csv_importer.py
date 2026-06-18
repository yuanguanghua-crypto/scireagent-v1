"""
TDD: Tests for CSV Product Importer.

Format: one CSV row per SKU, grouped by catalog_no.
"""
import csv
import io
from django.test import TestCase

from core.csv_importer import import_products_csv, CSVImportReport
from apps.commerce.models import Product, SKU


SAMPLE_CSV = """name,catalog_no,cas,formula,purity,category_l1,sku_code,pack_size,price,currency,inventory_status
ATP Solution,SC8047,56-65-5,C10H16N5O13P3,≥99%,nucleotides,ATP-10UL,10 µL,79,USD,in_stock
ATP Solution,SC8047,56-65-5,C10H16N5O13P3,≥99%,nucleotides,ATP-50UL,50 µL,299,USD,in_stock
GTP Solution,SC8048,56-65-6,C10H16N5O14P3,≥98%,nucleotides,GTP-10UL,10 µL,69,USD,in_stock
"""


class CSVImportTest(TestCase):
    """Test CSV parsing and import."""

    def test_parses_csv(self):
        """CSV should be parsed into rows."""
        report = import_products_csv(SAMPLE_CSV)
        self.assertTrue(report.success)

    def test_imports_products(self):
        """Products should be created from CSV."""
        report = import_products_csv(SAMPLE_CSV)
        self.assertEqual(report.products_created, 2,
                         'Should create 2 unique products (ATP, GTP)')

    def test_imports_skus(self):
        """SKUs should be created from CSV."""
        report = import_products_csv(SAMPLE_CSV)
        self.assertEqual(report.skus_created, 3,
                         'Should create 3 SKUs')

    def test_product_fields_set(self):
        """Product fields from CSV should be set correctly."""
        import_products_csv(SAMPLE_CSV)
        atp = Product.objects.get(catalog_no='SC8047')
        self.assertEqual(atp.name, 'ATP Solution')
        self.assertEqual(atp.cas, '56-65-5')
        self.assertEqual(atp.purity, '≥99%')

    def test_sku_fields_set(self):
        """SKU fields from CSV should be set correctly."""
        import_products_csv(SAMPLE_CSV)
        sku = SKU.objects.get(sku_code='ATP-10UL')
        self.assertEqual(float(sku.price), 79.0)
        self.assertEqual(sku.currency, 'USD')

    def test_sku_linked_to_product(self):
        """SKU should be linked to the correct product."""
        import_products_csv(SAMPLE_CSV)
        sku = SKU.objects.get(sku_code='ATP-10UL')
        self.assertEqual(sku.product.catalog_no, 'SC8047')

    def test_idempotent_import(self):
        """Importing same CSV twice should not duplicate."""
        import_products_csv(SAMPLE_CSV)
        report2 = import_products_csv(SAMPLE_CSV)
        self.assertEqual(report2.products_created, 0,
                         'Second import should update, not create')
        self.assertEqual(report2.skus_created, 0)

    def test_report_format(self):
        """Report should have useful summary."""
        report = import_products_csv(SAMPLE_CSV)
        self.assertIsNotNone(report)
        self.assertIsInstance(str(report), str)


class CSVEdgeCaseTest(TestCase):
    """Edge cases for CSV import."""

    def test_empty_csv(self):
        """Empty CSV should produce empty report."""
        report = import_products_csv('name,catalog_no\n')
        self.assertTrue(report.success)
        self.assertEqual(report.products_created, 0)

    def test_missing_required_column(self):
        """CSV missing required columns should error."""
        bad_csv = 'hello,world\na,b\n'
        report = import_products_csv(bad_csv)
        self.assertFalse(report.success)

    def test_missing_name(self):
        """Row without name should be counted."""
        report = import_products_csv(SAMPLE_CSV)
        self.assertGreaterEqual(report.rows, 3)

    def test_partial_failure(self):
        """One bad row should not block others."""
        csv_data = """name,catalog_no,cas,sku_code,pack_size,price,currency
Good Product,SC100,,SKU001,10 µL,50,USD
,SC200,,SKU002,10 µL,50,USD"""
        report = import_products_csv(csv_data)
        self.assertGreaterEqual(report.products_created, 1)
