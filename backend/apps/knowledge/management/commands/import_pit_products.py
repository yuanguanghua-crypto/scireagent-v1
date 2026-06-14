"""
Import products from Product Intake Tool seed data.
Usage: python manage.py import_pit_products [--file path] [--clear]
"""
import json
import os
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.commerce.models import Product, SKU


class Command(BaseCommand):
    help = 'Import products from Product Intake Tool seed_products.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default=os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                '..', '..', '试剂网站的', '试剂信息同步上传工具', 'product-intake-tool', 'backend', 'seed_products.json'
            ),
            help='Path to seed_products.json',
        )
        parser.add_argument('--clear', action='store_true', help='Clear existing PIT data before import')

    def handle(self, *args, **options):
        file_path = options['file']
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            products_data = json.load(f)

        self.stdout.write(f'Loaded {len(products_data)} products from {file_path}')

        if options['clear']:
            count = Product.objects.filter(catalog_no__startswith='SC').delete()[0]
            self.stdout.write(self.style.WARNING(f'Deleted {count} existing PIT products'))

        created_products = 0
        created_skus = 0
        skipped = 0

        for pdata in products_data:
            catalog_no = pdata.get('catalog_no', '').strip()
            if not catalog_no:
                skipped += 1
                continue

            # Check if already exists
            if Product.objects.filter(catalog_no=catalog_no).exists():
                self.stdout.write(f'  Skip (exists): {catalog_no}')
                skipped += 1
                continue

            # Clean up fields (remove trailing ↵ and whitespace)
            def clean(val):
                if isinstance(val, str):
                    return val.replace('↵', '').strip()
                return val

            # Generate slug from catalog_no + product_name
            name = clean(pdata.get('product_name', ''))
            slug = slugify(f"{catalog_no}-{name}")[:250]
            # Ensure unique slug
            base_slug = slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"[:250]
                counter += 1

            # Parse category_l2 (merge L2 + L3)
            cat_l2 = clean(pdata.get('category_l2', ''))
            cat_l3 = clean(pdata.get('category_l3', ''))
            if cat_l2 and cat_l3:
                category_l2 = f"{cat_l2} | {cat_l3}"
            elif cat_l2:
                category_l2 = cat_l2
            elif cat_l3:
                category_l2 = cat_l3
            else:
                category_l2 = ''

            # Create product
            product = Product.objects.create(
                catalog_no=catalog_no,
                name=name,
                slug=slug,
                cas=clean(pdata.get('cas_number', '')),
                smiles=clean(pdata.get('smiles', '')),
                inchi=clean(pdata.get('inchi', '')),
                synonyms=pdata.get('synonyms', '').replace('↵', '').strip().split(',') if pdata.get('synonyms') else [],
                formula=clean(pdata.get('formula', '')),
                molecular_weight=pdata.get('molecular_weight'),
                purity=clean(pdata.get('purity', '')),
                concentration=clean(pdata.get('concentration', '')),
                storage=clean(pdata.get('storage', '')),
                shipping=clean(pdata.get('shipping_condition', '')),
                overview=clean(pdata.get('overview', '')),
                research_use_only=pdata.get('research_use_only', True),
                category_l1=clean(pdata.get('category_l1', '')),
                category_l2=category_l2,
                status='published',  # PIT data is already reviewed
            )
            created_products += 1

            # Create SKUs
            for sdata in pdata.get('skus', []):
                sku_code = clean(sdata.get('sku_code', ''))
                if not sku_code:
                    continue

                # Map stock_status
                stock_map = {
                    'IN_STOCK': 'in_stock',
                    'OUT_OF_STOCK': 'out_of_stock',
                    'PRE_ORDER': 'preorder',
                    'LIMITED': 'limited',
                }
                stock_raw = sdata.get('stock_status', 'IN_STOCK')
                stock_status = stock_map.get(stock_raw, 'in_stock')

                # Parse package_size to pack_size
                pack_size = clean(sdata.get('package_size', ''))

                SKU.objects.create(
                    product=product,
                    sku_code=sku_code,
                    pack_size=pack_size,
                    price=sdata.get('price_usd', 0) or 0,
                    currency='USD',
                    inventory_status=stock_status,
                    concentration=clean(sdata.get('concentration', '')),
                    lead_time=clean(sdata.get('lead_time', '')),
                    is_default=sdata.get('is_active', True),
                )
                created_skus += 1

            self.stdout.write(f'  ✓ {catalog_no} — {name} ({len(pdata.get("skus", []))} SKUs)')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created {created_products} products, {created_skus} SKUs, skipped {skipped}'
        ))
