"""
TDD: Tests for Agent JSON Schema Validator.

This module validates Agent-output JSON (knowledge_graph_v3 format)
before it's imported into the database. Tests define the expected
validation rules and error reporting format.
"""
from django.test import TestCase

from core.json_validator import (
    validate_graph_json,
    ValidationReport,
    ValidationError,
    ValidationWarning,
)


class MetadataValidationTest(TestCase):
    """Metadata section must have required fields."""

    def test_metadata_required(self):
        """Metadata section is required."""
        report = validate_graph_json({})
        self.assertFalse(report.is_valid)
        self.assertIn('metadata', [e.field for e in report.errors])

    def test_metadata_missing_keys(self):
        """Metadata must have version and description."""
        data = {'metadata': {}}
        report = validate_graph_json(data)
        self.assertFalse(report.is_valid)

    def test_metadata_valid(self):
        """Valid metadata passes validation."""
        data = {
            'metadata': {'version': '3.0', 'description': 'Test data'},
            'ResearchGoal': [],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)


class EntityListValidationTest(TestCase):
    """Top-level entity lists must be present and have correct types."""

    def test_entity_lists_required(self):
        """All entity types must be present as keys."""
        data = {'metadata': {'version': '3.0', 'description': ''}}
        report = validate_graph_json(data)
        for entity in ['ResearchGoal', 'Application', 'Method',
                        'Protocol', 'Product', 'SKU']:
            self.assertIn(entity, [e.field for e in report.errors])

    def test_entity_lists_must_be_arrays(self):
        """Entity values must be arrays (lists)."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': 'not_a_list',
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        self.assertFalse(report.is_valid)

    def test_entity_lists_empty_is_valid(self):
        """Empty entity lists are valid (just import nothing)."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)


class ResearchGoalValidationTest(TestCase):
    """ResearchGoal entities must have correct structure."""

    def test_goal_requires_id(self):
        """Each ResearchGoal must have an 'id' field."""
        data = self._make_base_data()
        data['ResearchGoal'] = [{'name': 'Missing ID'}]
        report = validate_graph_json(data)
        self.assertFalse(report.is_valid)

    def test_goal_requires_name(self):
        """Each ResearchGoal must have a 'name' field."""
        data = self._make_base_data()
        data['ResearchGoal'] = [{'id': 'goal_001'}]
        report = validate_graph_json(data)
        self.assertFalse(report.is_valid)

    def test_goal_valid(self):
        """A valid ResearchGoal passes."""
        data = self._make_base_data()
        data['ResearchGoal'] = [{
            'id': 'goal_001',
            'name': 'RNA Labeling',
            'summary': 'Test summary',
        }]
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)

    def test_goal_optional_fields(self):
        """Summary and keywords are optional."""
        data = self._make_base_data()
        data['ResearchGoal'] = [{
            'id': 'goal_001',
            'name': 'DNA Labeling',
        }]
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)

    def _make_base_data(self):
        return {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }


class ApplicationValidationTest(TestCase):
    """Application entities must link to existing ResearchGoals."""

    def test_application_requires_goals_ref(self):
        """Application.goals referencing unknown IDs issues a warning (not error)."""
        data = self._make_base_data(['goal_001'])
        data['Application'] = [{
            'id': 'app_001',
            'name': 'FISH',
            'goals': ['goal_999'],  # does not exist
        }]
        report = validate_graph_json(data)
        # Cross-ref warnings don't invalidate — might be existing DB entities
        self.assertTrue(report.is_valid)
        self.assertGreater(len(report.warnings), 0)

    def test_application_valid_goal_ref(self):
        """Application.goals referencing existing goals passes."""
        data = self._make_base_data(['goal_001'])
        data['Application'] = [{
            'id': 'app_001',
            'name': 'FISH',
            'goals': ['goal_001'],
        }]
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)

    def _make_base_data(self, goal_ids=None):
        return {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [
                {'id': gid, 'name': f'Goal {gid}'} for gid in (goal_ids or [])
            ],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }


class ProductProtocolRefTest(TestCase):
    """Product must reference existing protocols."""

    def test_product_refers_to_existing_protocol(self):
        """Product.protocols referencing unknown IDs issues a warning."""
        data = self._make_base_data()
        data['Product'] = [{
            'id': 'product_001',
            'name': 'ATP',
            'protocols': ['protocol_999'],
        }]
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)
        self.assertGreater(len(report.warnings), 0)

    def test_product_valid_protocol_ref(self):
        """Product.protocols referencing existing protocols passes."""
        data = self._make_base_data()
        data['Protocol'] = [{'id': 'protocol_001', 'name': 'ATP Assay'}]
        data['Product'] = [{
            'id': 'product_001',
            'name': 'ATP',
            'protocols': ['protocol_001'],
        }]
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)

    def _make_base_data(self):
        return {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }


class SKUValidationTest(TestCase):
    """SKUs must reference existing products."""

    def test_sku_requires_product_id(self):
        """SKU referencing unknown product_id issues a warning."""
        data = self._make_base_data(['product_001'])
        data['SKU'] = [{
            'id': 'sku_001',
            'product_id': 'product_999',
        }]
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)
        self.assertGreater(len(report.warnings), 0)

    def test_sku_valid_product_ref(self):
        """SKU with existing product_id passes."""
        data = self._make_base_data(['product_001'])
        data['SKU'] = [{
            'id': 'sku_001',
            'product_id': 'product_001',
            'pack_size': '10 uL',
            'price': '$79',
            'currency': 'USD',
            'stock_status': 'in_stock',
        }]
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)

    def _make_base_data(self, product_ids=None):
        return {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [
                {'id': pid, 'name': f'Product {pid}'} for pid in (product_ids or [])
            ],
            'SKU': [],
        }


class IDUniquenessTest(TestCase):
    """IDs must be unique within and across entity types."""

    def test_duplicate_id_within_type(self):
        """Same ID appearing twice in the same type is an error."""
        data = self._make_base_data()
        data['ResearchGoal'] = [
            {'id': 'goal_001', 'name': 'First'},
            {'id': 'goal_001', 'name': 'Duplicate'},
        ]
        report = validate_graph_json(data)
        self.assertFalse(report.is_valid)

    def _make_base_data(self):
        return {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }


class ValidationReportFormatTest(TestCase):
    """ValidationReport must produce structured, usable output."""

    def test_report_has_summary(self):
        """Report should summarize total entities found."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [{'id': 'g1', 'name': 'G1'}],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        self.assertEqual(report.summary['ResearchGoal'], 1)
        self.assertEqual(report.summary['Application'], 0)

    def test_report_separates_errors_and_warnings(self):
        """Report should have separate error and warning lists."""
        report = ValidationReport()
        self.assertIsInstance(report.errors, list)
        self.assertIsInstance(report.warnings, list)
        self.assertIsInstance(report.is_valid, bool)

    def test_report_readable_messages(self):
        """Error messages should be human-readable."""
        data = {'metadata': {}}
        report = validate_graph_json(data)
        if report.errors:
            for err in report.errors:
                self.assertIsInstance(err.message, str)
                self.assertGreater(len(err.message), 0)

    def test_summary_str(self):
        """Report should have a readable string representation."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        summary_str = str(report)
        self.assertIn('valid', summary_str.lower())

    def test_warning_for_orphan_application(self):
        """Application with no goals is a warning, not an error."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [],
            'Application': [{'id': 'app_001', 'name': 'FISH', 'goals': []}],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        self.assertTrue(report.is_valid)
        self.assertGreater(len(report.warnings), 0)
        # Warning should reference this application
        warning_ids = [w.entity_id for w in report.warnings]
        self.assertIn('app_001', warning_ids)


class EdgeCaseTest(TestCase):
    """Robustness against malformed input."""

    def test_non_dict_object(self):
        """Should handle non-dict top-level gracefully."""
        report = validate_graph_json([])
        self.assertFalse(report.is_valid)

    def test_entity_not_a_list(self):
        """Entity that's a dict instead of list should error."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': {},
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        self.assertFalse(report.is_valid)

    def test_none_field_values(self):
        """None values in fields should not crash validator."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [{'id': None, 'name': 'Goal'}],
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = validate_graph_json(data)
        # Should handle gracefully, not crash
        self.assertIsNotNone(report)
