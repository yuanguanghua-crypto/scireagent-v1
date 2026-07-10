"""
TDD: Tests for Agent JSON Import Orchestrator.

Tests the full import pipeline: parse → validate → import in order.
"""
from django.test import TestCase

from core.json_validator import validate_graph_json
from core.json_importer import import_graph_json


SAMPLE_VALID_JSON = {
    'metadata': {'version': '3.0', 'description': 'Test import'},
    'ResearchGoal': [
        {'id': 'goal_001', 'name': 'RNA Labeling',
         'summary': 'Test summary', 'priority': 'high'},
    ],
    'Application': [
        {'id': 'app_001', 'name': 'FISH',
         'goals': ['goal_001']},
    ],
    'Method': [
        {'id': 'method_001', 'name': 'Nick Translation',
         'application': 'app_001',
         'purpose': 'Test method'},
    ],
    'Protocol': [
        {'id': 'protocol_001', 'name': 'FISH Protocol',
         'method': 'method_001',
         'objective': 'Test protocol'},
    ],
    'Product': [
        {'id': 'product_001', 'name': 'Biotin-dUTP',
         'catalog_no': 'SC8001', 'cas_no': '56-65-5',
         'formula': 'C10H16N5O13P3',
         'applications': ['app_001'],
         'protocols': ['protocol_001'],
         'skus': ['sku_001']},
    ],
    'SKU': [
        {'id': 'sku_001', 'product_id': 'product_001',
         'pack_size': '10 uL', 'price': '$79',
         'currency': 'USD', 'stock_status': 'in_stock'},
    ],
}


class ImportReportTest(TestCase):
    """ImportReport should provide useful feedback."""

    def test_report_has_success_count(self):
        """Report should count successfully imported entities."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertGreaterEqual(report.imported['ResearchGoal'], 1)

    def test_report_has_failure_count(self):
        """Report should count failures."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertIn('total_errors', report.summary)


class ImportOrderTest(TestCase):
    """Entities must be imported in dependency order."""

    def test_research_goal_imported_first(self):
        """ResearchGoal should be importable."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertEqual(report.imported['ResearchGoal'], 1)

    def test_application_imported(self):
        """Application links to ResearchGoal."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertEqual(report.imported['Application'], 1)

    def test_method_imported(self):
        """Method links to Application."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertEqual(report.imported['Method'], 1)

    def test_protocol_imported(self):
        """Protocol links to Method."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertEqual(report.imported['Protocol'], 1)

    def test_product_imported(self):
        """Product imported."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertEqual(report.imported['Product'], 1)

    def test_sku_imported(self):
        """SKU imported and linked to Product."""
        report = import_graph_json(SAMPLE_VALID_JSON)
        self.assertEqual(report.imported['SKU'], 1)

    def test_idempotent_import(self):
        """Importing the same data twice should not duplicate."""
        report1 = import_graph_json(SAMPLE_VALID_JSON)
        report2 = import_graph_json(SAMPLE_VALID_JSON)
        self.assertEqual(report2.imported['ResearchGoal'], 0,
                         'Second import should have 0 new goals (already exist)')


class InvalidDataTest(TestCase):
    """Import with invalid data should report errors gracefully."""

    def test_invalid_json_not_crash(self):
        """Invalid JSON should produce an error report, not crash."""
        report = import_graph_json({'invalid': True})
        self.assertFalse(report.success)
        self.assertGreater(len(report.errors), 0)

    def test_missing_required_field(self):
        """Entity missing required field should error and continue."""
        data = {
            'metadata': {'version': '3.0', 'description': ''},
            'ResearchGoal': [{'id': 'goal_001'}],  # missing 'name'
            'Application': [],
            'Method': [],
            'Protocol': [],
            'Product': [],
            'SKU': [],
        }
        report = import_graph_json(data)
        self.assertFalse(report.success)
