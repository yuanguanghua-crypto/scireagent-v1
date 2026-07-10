"""Phase 1 测试：分类重构后端模型与枚举收敛。

验证：
- CategoryL1 枚举砍到 3 项
- 完整性校验改用 product_class_id
- csv_importer 写 product_class
- setup_categories 构建 v1 树并回填 product_class_id
"""
import csv
import io
import pytest
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product, ProductClass
from apps.commerce.models import Product as _Product


CategoryL1 = _Product.CategoryL1
from apps.commerce.tests.factories import ProductFactory, SKUFactory, ProductClassFactory
from core.csv_importer import import_products_csv


class TestCategoryL1EnumShrunk:
    """TC: CategoryL1 枚举只剩 3 个采纳的 jena L1"""

    def test_only_three_choices(self):
        expected = {
            'nucleotides_nucleosides',
            'click_chemistry',
            'molecular_biology',
        }
        assert set(CategoryL1.values) == expected

    def test_removed_enums_not_present(self):
        values = set(CategoryL1.values)
        assert 'antibodies_antigens' not in values
        assert 'custom_synthesis' not in values
        assert 'proteins' not in values
        assert 'probes_epigenetics' not in values


@pytest.mark.django_db
class TestProductCompleteness:
    """TC: 完整性校验依赖 product_class_id 而非 category_l1"""

    def test_complete_requires_product_class(self):
        from apps.commerce.api.v1.serializers import _is_product_complete
        # 无 product_class 的产品即使 category_l1 有值也不完整
        product = ProductFactory(
            name='P', catalog_no='SC-X-001', cas='1927-31-7', smiles='CCO',
            category_l1='nucleotides_nucleosides',
        )
        SKUFactory(product=product, is_default=True)
        assert _is_product_complete(product) is False

    def test_complete_with_product_class(self):
        from apps.commerce.api.v1.serializers import _is_product_complete
        pc = ProductClassFactory(name='Nucleotides & Nucleosides', slug='nucleotides_nucleosides')
        product = ProductFactory(
            name='P', catalog_no='SC-X-002', cas='1927-31-7', smiles='CCO',
            product_class=pc,
        )
        SKUFactory(product=product, is_default=True)
        assert _is_product_complete(product) is True

    def test_incomplete_items_mentions_product_class(self):
        from apps.commerce.api.v1.serializers import _incomplete_items
        product = ProductFactory(
            name='P', catalog_no='SC-X-003', cas='1927-31-7', smiles='CCO',
        )
        items = _incomplete_items(product)
        assert any('product_class' in i for i in items)


@pytest.mark.django_db
class TestCsvImporterSetsProductClass:
    """TC: csv_importer 按 category_l1 slug 查 ProductClass L1 并设 product_class"""

    def _make_csv(self, rows):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    def test_csv_import_resolves_l1_slug(self):
        ProductClassFactory(name='Nucleotides & Nucleosides', slug='nucleotides_nucleosides')
        csv_content = self._make_csv([
            {
                'name': 'Test Reagent', 'catalog_no': 'SC-CSV-001',
                'category_l1': 'nucleotides_nucleosides',
                'sku_code': 'SKU-1', 'pack_size': '10mg', 'price': '50', 'currency': 'USD',
            },
        ])
        report = import_products_csv(csv_content)
        assert report.success, report.errors
        product = Product.objects.get(catalog_no='SC-CSV-001')
        assert product.product_class_id is not None
        assert product.product_class.slug == 'nucleotides_nucleosides'

    def test_csv_import_unknown_slug_leaves_null(self):
        csv_content = self._make_csv([
            {
                'name': 'Test Reagent 2', 'catalog_no': 'SC-CSV-002',
                'category_l1': 'nonexistent_slug',
                'sku_code': 'SKU-2', 'pack_size': '10mg', 'price': '50', 'currency': 'USD',
            },
        ])
        report = import_products_csv(csv_content)
        assert report.success, report.errors
        product = Product.objects.get(catalog_no='SC-CSV-002')
        assert product.product_class_id is None


@pytest.mark.django_db
class TestSetupCategoriesV1Tree:
    """TC: setup_categories 构建 v1 权威树（3 L1 / 21 L2）并回填产品"""

    def test_builds_three_l1(self):
        call_command('setup_categories')
        l1_count = ProductClass.objects.filter(parent__isnull=True).count()
        # v1 树 3 个 L1，但可能残留被产品引用的旧 L1（本测试无产品引用旧 L1）
        slugs = set(ProductClass.objects.filter(parent__isnull=True).values_list('slug', flat=True))
        assert 'nucleotides_nucleosides' in slugs
        assert 'click_chemistry' in slugs
        assert 'molecular_biology' in slugs

    def test_nucleotides_has_nine_l2(self):
        call_command('setup_categories')
        nuc = ProductClass.objects.get(slug='nucleotides_nucleosides', parent__isnull=True)
        l2_count = ProductClass.objects.filter(parent=nuc).count()
        assert l2_count == 9

    def test_total_l2_is_twentyone(self):
        call_command('setup_categories')
        l1s = ProductClass.objects.filter(
            slug__in=['nucleotides_nucleosides', 'click_chemistry', 'molecular_biology'],
            parent__isnull=True,
        )
        total_l2 = ProductClass.objects.filter(parent__in=l1s).count()
        assert total_l2 == 21

    def test_backfills_product_class_from_category_l1(self):
        # 预置一个有 category_l1 但无 product_class 的产品
        product = ProductFactory(
            name='Backfill Me', catalog_no='SC-BF-001',
            category_l1='nucleotides_nucleosides', product_class=None,
        )
        call_command('setup_categories')
        product.refresh_from_db()
        assert product.product_class_id is not None
        assert product.product_class.slug == 'nucleotides_nucleosides'

    def test_backfills_l2_when_category_l2_matches(self):
        nuc = ProductClassFactory(name='Nucleotides & Nucleosides', slug='nucleotides_nucleosides')
        # 先建 L2（setup_categories 会 update_or_create）
        ProductClassFactory(name='Fluorescent Nucleotides', slug='nucleotides_nucleosides-fluorescent-nucleotides', parent=nuc)
        product = ProductFactory(
            name='Backfill L2', catalog_no='SC-BF-002',
            category_l1='nucleotides_nucleosides',
            category_l2='Fluorescent Nucleotides',
            product_class=None,
        )
        call_command('setup_categories')
        product.refresh_from_db()
        assert product.product_class.parent_id == nuc.id

    def test_prunes_orphan_non_v1_categories(self):
        # 预置一个 v1 之外的孤立 L1（无产品引用）
        ProductClassFactory(name='Old Proteins', slug='proteins', parent=None)
        call_command('setup_categories')
        assert not ProductClass.objects.filter(slug='proteins', parent__isnull=True).exists()

    def test_keeps_non_v1_category_with_product(self):
        # 预置一个 v1 之外但被产品引用的 L1
        old_pc = ProductClassFactory(name='Old Proteins', slug='proteins', parent=None)
        ProductFactory(name='Ref', catalog_no='SC-REF-001', product_class=old_pc, category_l1='')
        call_command('setup_categories')
        assert ProductClass.objects.filter(slug='proteins', parent__isnull=True).exists()
