"""
Management command: import_knowledge_graph
Imports knowledge_graph_v3_fixed.json into the database.

Strategy:
- Product: UPDATE existing (match by catalog_no), only fill empty fields
- ResearchGoal/Application/Method/Protocol: CREATE or UPDATE
- ProtocolStep: CREATE from Protocol.steps array
- SKU: CREATE (generate sku_code)
- Bridge tables: CREATE (ProductMethod, MethodProtocol)

Usage:
    python manage.py import_knowledge_graph path/to/knowledge_graph_v3_fixed.json
    python manage.py import_knowledge_graph path/to/file.json --dry-run
"""

import json
import re
import sys
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, ProtocolStep,
)
from apps.commerce.models import Product, SKU
from apps.bridges.models import ProductMethod, MethodProtocol


class Command(BaseCommand):
    help = 'Import knowledge graph JSON into database'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to the JSON file')
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    def handle(self, *args, **options):
        json_file = options['json_file']
        dry_run = options['dry_run']

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.stdout.write(f'Loading: {json_file}')
        self.stdout.write(f'Dry run: {dry_run}')
        self.stdout.write('')

        stats = {
            'goals_created': 0, 'goals_updated': 0,
            'apps_created': 0, 'apps_updated': 0,
            'methods_created': 0, 'methods_updated': 0,
            'protocols_created': 0, 'protocols_updated': 0,
            'steps_created': 0,
            'products_updated': 0,
            'skus_created': 0, 'skus_skipped': 0,
            'product_methods_created': 0,
            'method_protocols_created': 0,
        }

        # Build lookups
        goal_map = {}   # json_id -> DB instance
        app_map = {}
        method_map = {}
        protocol_map = {}
        product_map = {}  # catalog_no -> DB instance

        # ── Step 1: ResearchGoal ─────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('=== ResearchGoal ==='))
        for item in data['ResearchGoal']:
            priority = self._parse_priority(item.get('priority', 'medium'))
            obj, created = ResearchGoal.objects.update_or_create(
                slug=item['slug'],
                defaults={
                    'name': item['name'],
                    'summary': item.get('summary', ''),
                    'priority': priority,
                    'status': 'active',
                }
            )
            goal_map[item['id']] = obj
            if created:
                stats['goals_created'] += 1
                self.stdout.write(f'  + {obj.name}')
            else:
                stats['goals_updated'] += 1

        # ── Step 2: Application ──────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Application ==='))
        for item in data['Application']:
            # Find parent goal from goals list
            parent_goal = None
            for gid in item.get('goals', []):
                if gid in goal_map:
                    parent_goal = goal_map[gid]
                    break
            if not parent_goal:
                parent_goal = list(goal_map.values())[0]  # fallback

            obj, created = Application.objects.update_or_create(
                slug=item['slug'],
                defaults={
                    'name': item['name'],
                    'summary': item.get('overview', item.get('purpose', '')),
                    'research_goal': parent_goal,
                    'status': 'active',
                }
            )
            app_map[item['id']] = obj
            if created:
                stats['apps_created'] += 1
                self.stdout.write(f'  + {obj.name}')
            else:
                stats['apps_updated'] += 1

        # ── Step 3: Method ───────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Method ==='))
        for item in data['Method']:
            # Find parent app from applications list
            parent_app = None
            for aid in item.get('applications', []):
                if aid in app_map:
                    parent_app = app_map[aid]
                    break
            if not parent_app:
                parent_app = list(app_map.values())[0]  # fallback

            timeline = self._map_timeline(item.get('duration', ''))
            cost_band = self._map_cost(item.get('cost_estimate', ''))

            obj, created = Method.objects.update_or_create(
                slug=item['slug'],
                defaults={
                    'name': item['name'],
                    'summary': item.get('principle', ''),
                    'purpose': item.get('purpose', ''),
                    'advantages': '\n'.join(item.get('advantages', [])) if isinstance(item.get('advantages'), list) else item.get('advantages', ''),
                    'limitations': '\n'.join(item.get('limitations', [])) if isinstance(item.get('limitations'), list) else item.get('limitations', ''),
                    'cost_band': cost_band,
                    'timeline': timeline,
                    'application': parent_app,
                    'status': 'active',
                }
            )
            method_map[item['id']] = obj
            if created:
                stats['methods_created'] += 1
                self.stdout.write(f'  + {obj.name}')
            else:
                stats['methods_updated'] += 1

        # ── Step 4: Protocol + ProtocolStep ──────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Protocol ==='))
        for item in data['Protocol']:
            # Find parent method from methods list
            parent_method = None
            for mid in item.get('methods', []):
                if mid in method_map:
                    parent_method = method_map[mid]
                    break
            if not parent_method:
                parent_method = list(method_map.values())[0]  # fallback

            # Check unique_together: (method, slug, version)
            obj, created = Protocol.objects.update_or_create(
                method=parent_method,
                slug=item['slug'],
                version=item.get('version', '1.0'),
                defaults={
                    'name': item['name'],
                    'principle': item.get('principle', ''),
                    'materials': self._list_to_text(item.get('materials')),
                    'equipment': self._list_to_text(item.get('equipment')),
                    'troubleshooting': item.get('troubleshooting', ''),
                    'expected_results': item.get('expected_results', ''),
                    'status': 'published',
                }
            )
            protocol_map[item['id']] = obj

            if created:
                stats['protocols_created'] += 1
                self.stdout.write(f'  + {obj.name}')

                # Create ProtocolStep from steps array
                steps = item.get('steps', [])
                for idx, step_text in enumerate(steps, 1):
                    title, body = self._parse_step(step_text)
                    if not dry_run:
                        ProtocolStep.objects.create(
                            protocol=obj,
                            step_no=idx,
                            title=title[:255],
                            body=body,
                        )
                    stats['steps_created'] += 1
            else:
                stats['protocols_updated'] += 1

        # ── Step 5: Product update (only fill empty fields) ──
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Product (update only) ==='))
        for item in data['Product']:
            cn = item.get('catalog_no', '').strip()
            if not cn:
                continue

            try:
                product = Product.objects.get(catalog_no=cn)
            except Product.DoesNotExist:
                self.stdout.write(f'  ! Product {cn} not found in DB, skipping')
                continue

            product_map[cn] = product
            updated = False

            # Only fill empty fields
            overview = item.get('description', '').strip()
            if overview and not product.overview:
                product.overview = overview
                updated = True

            if updated and not dry_run:
                product.save()
                stats['products_updated'] += 1

        # ── Step 6: SKU ──────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== SKU ==='))
        for item in data['SKU']:
            pid = item.get('product_id', '')
            # Extract catalog_no from product_id: "product_sc8001" -> "SC8001"
            match = re.search(r'sc(\d+)', pid, re.IGNORECASE)
            if not match:
                stats['skus_skipped'] += 1
                continue

            catalog_no = f'SC{match.group(1)}'
            if catalog_no not in product_map:
                stats['skus_skipped'] += 1
                continue

            product = product_map[catalog_no]

            # Generate sku_code
            pack_size = item.get('pack_size', '').strip()
            sku_code = f'{catalog_no}-{pack_size}' if pack_size else f'{catalog_no}-DEFAULT'

            # Check if SKU already exists
            if SKU.objects.filter(sku_code=sku_code).exists():
                stats['skus_skipped'] += 1
                continue

            # Parse price
            price = self._parse_price(item.get('price', '0'))

            # Map stock_status
            stock_status = self._map_stock_status(item.get('stock_status', 'in_stock'))

            if not dry_run:
                SKU.objects.create(
                    product=product,
                    sku_code=sku_code,
                    pack_size=pack_size,
                    price=price,
                    currency=item.get('currency', 'USD'),
                    inventory_status=stock_status,
                    concentration=item.get('concentration', ''),
                    lead_time=item.get('lead_time', ''),
                    is_default=False,
                )
            stats['skus_created'] += 1

        # ── Step 7: Bridge tables ────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Bridge Tables ==='))

        # ProductMethod: infer from Product→Application→Method chain
        for product in product_map.values():
            # Find which applications this product links to (via category or description)
            for method_id, method_obj in method_map.items():
                # Check if product's category matches method's application
                if self._product_matches_method(product, method_obj):
                    obj, created = ProductMethod.objects.get_or_create(
                        product=product,
                        method=method_obj,
                        defaults={
                            'role': 'reagent',
                            'evidence_level': 'medium',
                        }
                    )
                    if created:
                        stats['product_methods_created'] += 1

        # MethodProtocol
        for method_id, method_obj in method_map.items():
            method_data = next((m for m in data['Method'] if m['id'] == method_id), None)
            if not method_data:
                continue
            for proto_id in method_data.get('protocols', []):
                if proto_id in protocol_map:
                    obj, created = MethodProtocol.objects.get_or_create(
                        method=method_obj,
                        protocol=protocol_map[proto_id],
                        defaults={'status': 'active'}
                    )
                    if created:
                        stats['method_protocols_created'] += 1

        # ── Summary ──────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Summary ==='))
        for key, val in stats.items():
            self.stdout.write(f'  {key}: {val}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes were saved.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport completed.'))

    # ── Helper methods ───────────────────────────────

    def _parse_priority(self, value):
        mapping = {'high': 10, 'medium': 5, 'low': 1}
        if isinstance(value, int):
            return value
        return mapping.get(str(value).lower(), 5)

    def _map_timeline(self, duration):
        if not duration:
            return ''
        d = duration.lower()
        if 'minute' in d or 'min' in d:
            return 'minutes'
        if 'hour' in d or 'hr' in d:
            return 'hours'
        if 'day' in d:
            return 'days'
        if 'week' in d:
            return 'weeks'
        return 'hours'  # default

    def _map_cost(self, estimate):
        if not estimate:
            return ''
        e = estimate.lower()
        if 'low' in e:
            return 'low'
        if 'medium' in e or 'moderate' in e:
            return 'medium'
        if 'high' in e:
            return 'high'
        return ''

    def _list_to_text(self, value):
        if isinstance(value, list):
            return '\n'.join(str(v) for v in value if v)
        return str(value) if value else ''

    def _parse_step(self, text):
        if not text:
            return 'Untitled', ''
        text = str(text).strip()
        # Try to extract title from bold markers or first line
        lines = text.split('\n')
        title = lines[0].strip().replace('**', '').replace('*', '')[:200]
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''
        if not body:
            body = title
            title = f'Step'
        return title, body

    def _parse_price(self, value):
        if not value:
            return Decimal('0.00')
        s = str(value).replace('$', '').replace(',', '').strip()
        try:
            return Decimal(s).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            return Decimal('0.00')

    def _map_stock_status(self, value):
        mapping = {
            'in_stock': 'in_stock',
            'in stock': 'in_stock',
            'available': 'in_stock',
            'limited': 'limited',
            'preorder': 'preorder',
            'pre-order': 'preorder',
            'out_of_stock': 'out_of_stock',
            'out of stock': 'out_of_stock',
        }
        return mapping.get(str(value).lower().strip(), 'in_stock')

    def _product_matches_method(self, product, method):
        """Check if product is related to method based on category/description."""
        method_name = method.name.lower()
        product_text = f'{product.name} {product.overview} {product.category_l1} {product.category_l2}'.lower()

        keywords = {
            '酶促标记': ['enzymatic', 'polymerase', 'labeling', 'labelling', 'incorporation'],
            '随机引物': ['random', 'priming', 'hexamer'],
            '末端标记': ['terminal', 'transferase', 'tailing'],
            't7转录': ['t7', 'transcription', 'in vitro', 'ivt'],
            '实时荧光定量pcr': ['qpcr', 'pcr', 'real-time', 'quantitative'],
            'sanger测序': ['sanger', 'sequencing', 'dideoxy'],
            'illumina测序': ['illumina', 'ngs', 'rna-seq', 'next generation'],
            'fish': ['fish', 'fluorescence in situ', 'chromosome'],
            '点击化学': ['click', 'cuac', 'spaac', 'azide', 'alkyne', 'propargyl', 'ethynyl'],
            '链霉亲和素': ['streptavidin', 'biotin', 'purification', 'pull-down'],
        }

        for cn_name, en_keywords in keywords.items():
            if cn_name in method_name:
                for kw in en_keywords:
                    if kw in product_text:
                        return True
        return False
