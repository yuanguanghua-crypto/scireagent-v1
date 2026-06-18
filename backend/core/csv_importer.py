"""
CSV Product Importer.

Format: one CSV row per SKU, grouped by catalog_no.
Required columns: name, catalog_no
Optional columns: cas, formula, purity, concentration, category_l1, status,
                    sku_code, pack_size, price, currency, inventory_status
"""

import csv
import io
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from apps.commerce.models import Product, SKU

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ['name', 'catalog_no']
COLUMN_ALIASES = {
    'cas_no': 'cas',
    'cat_no': 'catalog_no',
    'catalog': 'catalog_no',
    'catalogue': 'catalog_no',
    'product_name': 'name',
}


@dataclass
class CSVImportReport:
    """Result of CSV import, structured for UI display."""
    success: bool = True
    products_created: int = 0
    products_updated: int = 0
    skus_created: int = 0
    skus_updated: int = 0
    errors: list[str] = field(default_factory=list)
    rows: int = 0

    def __str__(self) -> str:
        status = 'SUCCESS' if self.success else 'COMPLETED WITH ERRORS'
        return (
            f'[{status}] '
            f'Products: {self.products_created} created, {self.products_updated} updated, '
            f'SKUs: {self.skus_created} created, {self.skus_updated} updated, '
            f'Errors: {len(self.errors)}'
        )


def import_products_csv(csv_content: str) -> CSVImportReport:
    """
    Import products from CSV content string.

    Groups rows by catalog_no to create one Product with multiple SKUs.
    Skips rows with missing required fields and reports errors.
    """
    report = CSVImportReport()
    reader = csv.DictReader(io.StringIO(csv_content))

    # Normalize column names
    fieldnames = [_normalize_col(name) for name in (reader.fieldnames or [])]
    if not _validate_columns(fieldnames, report):
        return report

    # Group rows by catalog_no
    product_rows: dict[str, list[dict]] = {}
    for row in reader:
        normalized = {_normalize_col(k): v for k, v in row.items()}
        catalog_no = normalized.get('catalog_no', '').strip()
        if not catalog_no:
            report.errors.append(f'Row {reader.line_num}: missing catalog_no, skipped')
            report.success = False
            continue
        if catalog_no not in product_rows:
            product_rows[catalog_no] = []
        product_rows[catalog_no].append(normalized)
        report.rows += 1

    # Import each product
    for catalog_no, rows in product_rows.items():
        try:
            _import_product(catalog_no, rows, report)
        except Exception as e:
            report.errors.append(f'Product {catalog_no}: import failed - {e}')
            report.success = False

    return report


def _normalize_col(name: str) -> str:
    """Normalize column name: lowercase, strip, apply aliases."""
    cleaned = name.strip().lower().replace(' ', '_')
    return COLUMN_ALIASES.get(cleaned, cleaned)


def _validate_columns(fieldnames: list[str], report: CSVImportReport) -> bool:
    """Check that all required columns are present."""
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        report.errors.append(f'Missing required columns: {", ".join(missing)}')
        report.success = False
        return False
    return True


@transaction.atomic
def _import_product(catalog_no: str, rows: list[dict], report: CSVImportReport) -> None:
    """Create or update a Product and its SKUs from grouped rows."""
    first_row = rows[0]
    name = first_row.get('name', '').strip()
    if not name:
        report.errors.append(f'Product {catalog_no}: missing name')
        report.success = False
        return

    # Generate slug from name
    slug = name.lower().replace(' ', '-').replace('/', '-')[:200]

    # Create or update product
    product, was_created = Product.objects.update_or_create(
        catalog_no=catalog_no,
        defaults={
            'slug': slug,
            'name': name,
            'cas': first_row.get('cas', ''),
            'formula': first_row.get('formula', ''),
            'purity': first_row.get('purity', ''),
            'concentration': first_row.get('concentration', ''),
            'category_l1': first_row.get('category_l1', ''),
            'smiles': first_row.get('smiles', ''),
            'overview': first_row.get('overview', ''),
            'status': first_row.get('status', 'active'),
        },
    )

    if was_created:
        report.products_created += 1
    else:
        report.products_updated += 1

    # Create or update SKUs
    for row in rows:
        sku_code = row.get('sku_code', '').strip()
        if not sku_code:
            continue

        pack_size = row.get('pack_size', '')
        price_str = row.get('price', '0')
        currency = row.get('currency', 'USD')

        try:
            price = Decimal(str(price_str).replace('$', '').replace(',', ''))
        except (ValueError, TypeError):
            price = Decimal('0')

        sku, sku_created = SKU.objects.update_or_create(
            sku_code=sku_code,
            defaults={
                'product': product,
                'pack_size': pack_size,
                'price': price,
                'currency': currency,
                'inventory_status': row.get('inventory_status', 'in_stock'),
            },
        )

        if sku_created:
            report.skus_created += 1
        else:
            report.skus_updated += 1
