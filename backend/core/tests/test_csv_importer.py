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


class CSVImportArchivedNumberTest(TestCase):
    """旁路修复（B′ 口径）：CSV 重导命中**回收站**里的货号，必须「跳过并上报」，
    绝不能静默 `update_or_create` 复活/覆盖旧行。

    语义依据：货号是产品的永久身份，归档（archived=True）不释放编号。
    批量导入不能整体失败 → 语义取「跳过 + 计入报告 + success=False（让操作者必须看到）」。
    """

    def _archive(self, catalog_no, name):
        p = Product.objects.create(
            catalog_no=catalog_no, slug=f'{catalog_no.lower()}-old', name=name, status='active')
        p.archived = True
        p.save()
        return p

    def test_reimport_archived_catalog_no_is_skipped_not_overwritten(self):
        p = self._archive('SC8047', 'Old ATP')
        report = import_products_csv(SAMPLE_CSV)

        # ① 旧行原封不动（不复活、不覆盖）
        p.refresh_from_db()
        self.assertTrue(p.archived, '归档行不得被导入静默复活')
        self.assertEqual(p.name, 'Old ATP', '归档行数据不得被静默覆盖')

        # ② 跳过被完整上报
        self.assertEqual(report.products_skipped_archived, 1)
        self.assertFalse(report.success)
        joined = ' '.join(report.errors)
        self.assertIn('SC8047', joined)
        self.assertIn('回收站', joined)
        self.assertIn('restore', joined)

        # ③ 跳过是"整条跳过"——该产品的 SKU 不得被半途建出来
        self.assertFalse(SKU.objects.filter(sku_code='ATP-10UL').exists())

        # ④ 同一批里的其它货号不受牵连
        self.assertTrue(Product.objects.filter(catalog_no='SC8048', archived=False).exists())

    def test_normal_reimport_still_updates(self):
        """命中在售行仍走「重导即刷新」——不放宽口径，也不过度封锁。"""
        import_products_csv(SAMPLE_CSV)
        report2 = import_products_csv(SAMPLE_CSV)
        self.assertEqual(report2.products_skipped_archived, 0)
        self.assertTrue(report2.success)
        self.assertEqual(report2.products_updated, 2)
