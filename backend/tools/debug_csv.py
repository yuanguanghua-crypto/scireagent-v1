"""Debug CSV importer — run via pytest, not standalone."""
import sys
sys.path.insert(0, '.')
from core.csv_importer import import_products_csv

SAMPLE = """name,catalog_no,cas,formula,purity,category_l1,sku_code,pack_size,price,currency,inventory_status
ATP Solution,SC8047,56-65-5,C10H16N5O13P3,≥99%,nucleotides,ATP-10UL,10 µL,79,USD,in_stock
ATP Solution,SC8047,56-65-5,C10H16N5O13P3,≥99%,nucleotides,ATP-50UL,50 µL,299,USD,in_stock
GTP Solution,SC8048,56-65-6,C10H16N5O14P3,≥98%,nucleotides,GTP-10UL,10 µL,69,USD,in_stock
"""

report = import_products_csv(SAMPLE)
print(f'Success: {report.success}')
print(f'Products: {report.products_created} created, {report.products_updated} updated')
print(f'SKUs: {report.skus_created} created, {report.skus_updated} updated')
print(f'Errors: {report.errors}')
print(f'Rows: {report.rows}')
