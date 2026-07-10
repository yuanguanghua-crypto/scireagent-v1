"""
Agent JSON Knowledge Graph Importer

Imports validated Agent JSON into the database in dependency order:
ResearchGoal → Application → Method → Protocol → Product → SKU

Each step maps string IDs to database objects and handles create/update.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from core.json_validator import validate_graph_json

from apps.knowledge.models import ResearchGoal, Application, Method, Protocol
from apps.commerce.models import Product, SKU

logger = logging.getLogger(__name__)


# ── Report ────────────────────────────────────────────────────────────────────

@dataclass
class ImportReport:
    """Result of an import operation, structured for UI display."""
    success: bool = False
    imported: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [f'Success: {self.success}']
        if self.imported:
            created = ', '.join(f'{k}={v}' for k, v in self.imported.items() if v)
            lines.append(f'Created: {created}')
        if self.updated:
            updated = ', '.join(f'{k}={v}' for k, v in self.updated.items() if v)
            lines.append(f'Updated: {updated}')
        if self.errors:
            lines.append(f'Errors ({len(self.errors)}):')
            for err in self.errors[:5]:
                lines.append(f'  ✗ {err}')
        return '\n'.join(lines)


# ── Import order (dependency-aware) ───────────────────────────────────────────

IMPORT_ORDER = [
    'ResearchGoal',   # no FK dependencies
    'Application',    # FK → ResearchGoal
    'Method',         # FK → Application
    'Protocol',       # FK → Method
    'Product',        # no FK to knowledge (bridge tables handled separately)
    'SKU',            # FK → Product
]

# ── ID mapping ────────────────────────────────────────────────────────────────

# Stores mapping from JSON string IDs to database primary keys
_id_map: dict[str, dict[str, int]] = {
    'ResearchGoal': {},
    'Application': {},
    'Method': {},
    'Protocol': {},
    'Product': {},
    'SKU': {},
}


# ── Importers ─────────────────────────────────────────────────────────────────

def _import_goals(entities: list[dict]) -> tuple[int, int]:
    """Import ResearchGoal entities. Returns (created, updated)."""
    created = updated = 0
    for entity in entities:
        obj, was_created = ResearchGoal.objects.update_or_create(
            slug=entity.get('slug') or _slugify(entity['name']),
            defaults={
                'name': entity['name'],
                'summary': entity.get('summary', ''),
                'status': 'active',
            },
        )
        _id_map['ResearchGoal'][entity['id']] = obj.id
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def _import_applications(entities: list[dict]) -> tuple[int, int]:
    """Import Application entities, linking to ResearchGoal."""
    created = updated = 0
    for entity in entities:
        goal_id = _resolve_goal(entity.get('goals', []))
        obj, was_created = Application.objects.update_or_create(
            slug=entity.get('slug') or _slugify(entity['name']),
            defaults={
                'name': entity['name'],
                'summary': entity.get('overview') or entity.get('purpose', ''),
                'research_goal_id': goal_id,
                'status': 'active',
            },
        )
        _id_map['Application'][entity['id']] = obj.id
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def _import_methods(entities: list[dict]) -> tuple[int, int]:
    """Import Method entities, linking to Application."""
    created = updated = 0
    for entity in entities:
        app_id = entity.get('application')
        mapped_app_id = _id_map['Application'].get(app_id) if app_id else None
        if not mapped_app_id:
            logger.warning('Method %s: no valid application reference, skipping', entity['id'])
            continue
        defaults = {
            'name': entity['name'],
            'purpose': entity.get('purpose', ''),
            'advantages': '\n'.join(entity.get('advantages', [])) if isinstance(entity.get('advantages'), list) else entity.get('advantages', ''),
            'limitations': '\n'.join(entity.get('limitations', [])) if isinstance(entity.get('limitations'), list) else entity.get('limitations', ''),
            'application_id': mapped_app_id,
            'status': 'active',
        }
        obj, was_created = Method.objects.update_or_create(
            slug=entity.get('slug') or _slugify(entity['name']),
            defaults=defaults,
        )
        _id_map['Method'][entity['id']] = obj.id
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def _import_protocols(entities: list[dict]) -> tuple[int, int]:
    """Import Protocol entities, linking to Method."""
    created = updated = 0
    for entity in entities:
        method_id = entity.get('method')
        mapped_method_id = _id_map['Method'].get(method_id) if method_id else None
        if not mapped_method_id:
            logger.warning('Protocol %s: no valid method reference, skipping', entity['id'])
            continue
        defaults = {
            'name': entity['name'],
            'objective': entity.get('objective', ''),
            'principle': entity.get('principle', ''),
            'method_id': mapped_method_id,
            'status': 'published',
        }
        obj, was_created = Protocol.objects.update_or_create(
            slug=entity.get('slug') or _slugify(entity['name']),
            defaults=defaults,
        )
        _id_map['Protocol'][entity['id']] = obj.id
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def _import_products(entities: list[dict]) -> tuple[int, int]:
    """Import Product entities."""
    created = updated = 0
    for entity in entities:
        defaults = {
            'name': entity['name'],
            'catalog_no': entity.get('catalog_no', ''),
            'cas': entity.get('cas_no', ''),
            'formula': entity.get('formula', ''),
            'purity': entity.get('purity', ''),
            'concentration': entity.get('concentration', ''),
            'storage': entity.get('storage', ''),
            'overview': entity.get('description', ''),
            'status': 'active',
        }
        obj, was_created = Product.objects.update_or_create(
            catalog_no=entity.get('catalog_no', ''),
            defaults=defaults,
        )
        _id_map['Product'][entity['id']] = obj.id
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def _import_skus(entities: list[dict]) -> tuple[int, int]:
    """Import SKU entities, linking to Product."""
    created = updated = 0
    for entity in entities:
        product_id = entity.get('product_id')
        mapped_product_id = _id_map['Product'].get(product_id) if product_id else None
        if not mapped_product_id:
            logger.warning('SKU %s references unknown product %s', entity['id'], product_id)
            continue
        defaults = {
            'pack_size': entity.get('pack_size', ''),
            'price': _parse_price(entity.get('price', '0')),
            'currency': entity.get('currency', 'USD'),
            'inventory_status': entity.get('stock_status', 'in_stock'),
            'product_id': mapped_product_id,
        }
        obj, was_created = SKU.objects.update_or_create(
            sku_code=entity['id'],
            defaults=defaults,
        )
        _id_map['SKU'][entity['id']] = obj.id
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


# ── Main importer ─────────────────────────────────────────────────────────────

IMPORTERS = {
    'ResearchGoal': _import_goals,
    'Application': _import_applications,
    'Method': _import_methods,
    'Protocol': _import_protocols,
    'Product': _import_products,
    'SKU': _import_skus,
}


def import_graph_json(data: dict) -> ImportReport:
    """
    Import a knowledge graph JSON into the database.

    Validates first, then imports entities in dependency order.
    Returns an ImportReport with counts of created/updated entities
    and any errors encountered.
    """
    report = ImportReport()
    report.imported = {k: 0 for k in IMPORT_ORDER}
    report.updated = {k: 0 for k in IMPORT_ORDER}

    # Step 1: Validate
    validation = validate_graph_json(data)
    if not validation.is_valid:
        report.errors.extend(
            f'{e.field}: {e.message}' for e in validation.errors
        )
        report.success = False
        report.summary = {'total_errors': len(report.errors)}
        return report

    # Step 2: Clear ID map
    for key in _id_map:
        _id_map[key].clear()

    # Step 3: Import in dependency order
    for entity_type in IMPORT_ORDER:
        entities = data.get(entity_type, [])
        if not entities:
            continue

        importer = IMPORTERS.get(entity_type)
        if not importer:
            report.errors.append(f'No importer for {entity_type}')
            continue

        try:
            created, updated = importer(entities)
            report.imported[entity_type] = created
            report.updated[entity_type] = updated
        except Exception as e:
            report.errors.append(f'{entity_type} import failed: {e}')

    # Step 4: Finalize report
    total_errors = len(report.errors)
    report.success = total_errors == 0
    report.summary = {
        'total_created': sum(report.imported.values()),
        'total_updated': sum(report.updated.values()),
        'total_errors': total_errors,
        'id_map_size': sum(len(v) for v in _id_map.values()),
    }

    return report


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Simple slug from name."""
    return name.lower().replace(' ', '-').replace('/', '-')[:200]


def _resolve_goal(goal_ids: list) -> int | None:
    """Resolve the first valid ResearchGoal ID from a list."""
    for gid in goal_ids:
        mapped = _id_map['ResearchGoal'].get(gid)
        if mapped:
            return mapped
    return None


def _parse_price(price_str: str) -> float:
    """Parse price string like '$79' or '79.00' to float."""
    if not price_str:
        return 0.0
    cleaned = price_str.replace('$', '').replace(',', '').strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0
