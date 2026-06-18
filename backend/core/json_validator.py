"""
Agent JSON Knowledge Graph Validator

Validates Agent-output JSON (knowledge_graph_v3 format) before import.
Checks structure, required fields, data types, and cross-reference integrity.

Usage:
    report = validate_graph_json(json_data)
    if report.is_valid:
        proceed_with_import()
    else:
        show_errors_to_user(report)
"""

from dataclasses import dataclass, field
from typing import Any


# ── Report Types ──────────────────────────────────────────────────────────────

@dataclass
class ValidationError:
    """A critical issue that prevents import."""
    field: str
    message: str
    entity_id: str = ''


@dataclass
class ValidationWarning:
    """A non-critical issue that should be reviewed."""
    field: str
    message: str
    entity_id: str = ''


@dataclass
class ValidationReport:
    """Complete validation result with structured output for UI display."""
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Valid = no errors (warnings are OK)."""
        return len(self.errors) == 0

    def __str__(self) -> str:
        status = 'VALID' if self.is_valid else 'INVALID'
        parts = [
            f'Validation: {status}',
            f'Errors: {len(self.errors)}, Warnings: {len(self.warnings)}',
        ]
        if self.summary:
            parts.append('Entities: ' + ', '.join(
                f'{k}={v}' for k, v in self.summary.items() if v > 0
            ))
        for err in self.errors[:5]:
            parts.append(f'  ✗ [{err.field}] {err.message}')
        for warn in self.warnings[:5]:
            parts.append(f'  ⚠ [{warn.field}] {warn.message}')
        return '\n'.join(parts)


# ── Entity Schemas ────────────────────────────────────────────────────────────

ENTITY_SCHEMAS = {
    'ResearchGoal': {
        'required_fields': ['id', 'name'],
        'optional_fields': ['slug', 'summary', 'keywords', 'priority', 'applications'],
    },
    'Application': {
        'required_fields': ['id', 'name'],
        'optional_fields': ['slug', 'overview', 'purpose', 'workflow',
                            'advantages', 'limitations', 'goals', 'methods',
                            'protocols'],
    },
    'Method': {
        'required_fields': ['id', 'name'],
        'optional_fields': ['slug', 'principle', 'purpose', 'advantages',
                            'limitations', 'duration', 'cost_estimate',
                            'applications', 'protocols'],
    },
    'Protocol': {
        'required_fields': ['id', 'name'],
        'optional_fields': ['slug', 'version', 'principle', 'materials',
                            'equipment', 'steps', 'troubleshooting',
                            'expected_results', 'source_url', 'source',
                            'matched_keywords', 'match_score',
                            'methods', 'products'],
    },
    'Product': {
        'required_fields': ['id', 'name'],
        'optional_fields': ['slug', 'catalog_no', 'cas_no', 'smiles',
                            'inchikey', 'formula', 'molecular_weight',
                            'purity', 'concentration', 'storage', 'shipping',
                            'description', 'product_type',
                            'protocols', 'applications', 'skus'],
    },
    'SKU': {
        'required_fields': ['id', 'product_id'],
        'optional_fields': ['pack_size', 'purity', 'concentration',
                            'currency', 'price', 'stock_status', 'lead_time'],
    },
}

REQUIRED_ENTITY_TYPES = list(ENTITY_SCHEMAS.keys())


# ── Reference keys to validate ────────────────────────────────────────────────

ENTITY_REFERENCES = {
    'ResearchGoal': {
        'applications': 'Application',
    },
    'Application': {
        'goals': 'ResearchGoal',
        'methods': 'Method',
        'protocols': 'Protocol',
    },
    'Method': {
        'applications': 'Application',
        'protocols': 'Protocol',
    },
    'Protocol': {
        'methods': 'Method',
        'products': 'Product',
    },
    'Product': {
        'protocols': 'Protocol',
        'applications': 'Application',
        'skus': 'SKU',
    },
    'SKU': {
        'product_id': 'Product',
    },
}


# ── Validator ─────────────────────────────────────────────────────────────────

def validate_graph_json(data: Any) -> ValidationReport:
    """
    Validate an Agent knowledge graph JSON structure.

    Returns a ValidationReport with errors, warnings, and entity summary.
    The report.is_valid flag indicates whether the data can be imported.
    """
    report = ValidationReport()

    # 1. Top-level must be a dict
    if not isinstance(data, dict):
        report.errors.append(ValidationError(
            field='root',
            message='Top-level structure must be a JSON object (dict).',
        ))
        return report

    # 2. Metadata
    _validate_metadata(report, data.get('metadata', {}))

    # 3. All entity types must be present
    entity_data = {}
    for entity_type in REQUIRED_ENTITY_TYPES:
        value = data.get(entity_type)
        if value is None:
            report.errors.append(ValidationError(
                field=entity_type,
                message=f'Missing required entity list: "{entity_type}".',
            ))
        elif not isinstance(value, list):
            report.errors.append(ValidationError(
                field=entity_type,
                message=f'"{entity_type}" must be an array (list), got {type(value).__name__}.',
            ))
        else:
            entity_data[entity_type] = value
            report.summary[entity_type] = len(value)

    # 4. Collect all entity IDs for cross-reference validation
    all_ids = {}  # {entity_type: {id: count}}
    for entity_type, entities in entity_data.items():
        type_ids = {}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            eid = entity.get('id')
            if eid:
                if eid in type_ids:
                    report.errors.append(ValidationError(
                        field=entity_type,
                        message=f'Duplicate ID "{eid}" in {entity_type}.',
                        entity_id=eid,
                    ))
                type_ids[eid] = type_ids.get(eid, 0) + 1
        all_ids[entity_type] = type_ids

    # 5. Validate each entity's fields and references
    for entity_type, entities in entity_data.items():
        schema = ENTITY_SCHEMAS[entity_type]
        refs = ENTITY_REFERENCES.get(entity_type, {})

        for entity in entities:
            if not isinstance(entity, dict):
                report.errors.append(ValidationError(
                    field=entity_type,
                    message=f'Entity is not a dict: {entity}',
                ))
                continue

            eid = entity.get('id', '?')

            # Check required fields
            for req_field in schema['required_fields']:
                if req_field not in entity or entity.get(req_field) is None:
                    report.errors.append(ValidationError(
                        field=entity_type,
                        message=f'Missing required field "{req_field}"',
                        entity_id=eid,
                    ))

            # Check cross-references
            for ref_field, target_type in refs.items():
                ref_value = entity.get(ref_field)
                if ref_value is None:
                    continue
                if isinstance(ref_value, list):
                    for ref_id in ref_value:
                        _check_ref(report, entity_type, eid, ref_field,
                                   ref_id, target_type, all_ids)
                elif isinstance(ref_value, str):
                    _check_ref(report, entity_type, eid, ref_field,
                               ref_value, target_type, all_ids)

    # 6. Warnings for entities with no connections
    _check_orphans(report, entity_data)

    return report


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_metadata(report: ValidationReport, metadata: Any) -> None:
    """Validate metadata section."""
    if not isinstance(metadata, dict):
        report.errors.append(ValidationError(
            field='metadata',
            message='Metadata must be a JSON object.',
        ))
        return
    if 'version' not in metadata:
        report.errors.append(ValidationError(
            field='metadata',
            message='Missing required field "version".',
        ))
    if 'description' not in metadata:
        report.errors.append(ValidationError(
            field='metadata',
            message='Missing required field "description".',
        ))


def _check_ref(report: ValidationReport, source_type: str, source_id: str,
               ref_field: str, ref_id: Any, target_type: str,
               all_ids: dict) -> None:
    """Check that a cross-reference ID exists in the target type."""
    if not isinstance(ref_id, str) or not ref_id:
        report.errors.append(ValidationError(
            field=source_type,
            message=f'Invalid reference in "{ref_field}": "{ref_id}".',
            entity_id=source_id,
        ))
        return

    target_ids = all_ids.get(target_type, {})
    if ref_id not in target_ids:
        # Reference to entity that doesn't exist in the same JSON
        # Could be a pre-existing DB entity — warn, not error
        report.warnings.append(ValidationWarning(
            field=source_type,
            message=f'Reference "{ref_id}" in "{ref_field}" not found '
                    f'in this JSON (may reference existing DB entity).',
            entity_id=source_id,
        ))


def _check_orphans(report: ValidationReport, entity_data: dict) -> None:
    """Warn about entities with no connections to other entities."""
    # Application without goals
    for app in entity_data.get('Application', []):
        if isinstance(app, dict):
            goals = app.get('goals', [])
            if not goals:
                report.warnings.append(ValidationWarning(
                    field='Application',
                    message='Application has no ResearchGoal connections.',
                    entity_id=app.get('id', '?'),
                ))

    # Product without SKUs
    for prod in entity_data.get('Product', []):
        if isinstance(prod, dict):
            skus = prod.get('skus', [])
            if not skus:
                report.warnings.append(ValidationWarning(
                    field='Product',
                    message='Product has no SKU entries.',
                    entity_id=prod.get('id', '?'),
                ))
