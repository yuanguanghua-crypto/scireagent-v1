"""
TDD: Tests for Knowledge Chain Quick Creator.

Creates a complete chain: ResearchGoal → Application → Method → Protocol
in a single call.
"""
from django.test import TestCase

from core.chain_creator import create_knowledge_chain, ChainInput, ChainReport
from apps.knowledge.models import ResearchGoal, Application, Method, Protocol


class ChainCreateTest(TestCase):
    """Test creating a complete knowledge chain."""

    def test_creates_research_goal(self):
        """ResearchGoal should be created."""
        report = create_knowledge_chain(ChainInput(
            goal_name='RNA Labeling',
            goal_summary='Study RNA labeling techniques',
            app_name='Fluorescent Labeling',
            app_summary='Label RNA with fluorophores',
            method_name='Enzymatic Labeling',
            method_purpose='Incorporate labeled nucleotides',
            protocol_name='Standard Labeling Protocol',
            protocol_objective='Protocol for RNA labeling',
        ))
        self.assertEqual(report.created['ResearchGoal'], 1)
        self.assertTrue(ResearchGoal.objects.filter(name='RNA Labeling').exists())

    def test_creates_application(self):
        """Application should be created and linked to ResearchGoal."""
        report = create_knowledge_chain(ChainInput(
            goal_name='Goal', app_name='App',
            method_name='Method', protocol_name='Protocol',
        ))
        self.assertEqual(report.created['Application'], 1)
        app = Application.objects.get(name='App')
        self.assertEqual(app.research_goal.name, 'Goal')

    def test_creates_method(self):
        """Method should be created and linked to Application."""
        report = create_knowledge_chain(ChainInput(
            goal_name='Goal', app_name='App',
            method_name='Method', protocol_name='Protocol',
        ))
        self.assertEqual(report.created['Method'], 1)
        method = Method.objects.get(name='Method')
        self.assertEqual(method.application.name, 'App')

    def test_creates_protocol(self):
        """Protocol should be created and linked to Method."""
        report = create_knowledge_chain(ChainInput(
            goal_name='Goal', app_name='App',
            method_name='Method', protocol_name='Protocol',
        ))
        self.assertEqual(report.created['Protocol'], 1)
        protocol = Protocol.objects.get(name='Protocol')
        self.assertEqual(protocol.method.name, 'Method')

    def test_chain_integrity(self):
        """Full chain should be traversable."""
        report = create_knowledge_chain(ChainInput(
            goal_name='Cell Study',
            app_name='PCR',
            method_name='qPCR',
            protocol_name='SYBR Green Protocol',
        ))
        goal = ResearchGoal.objects.get(name='Cell Study')
        app = goal.applications.first()
        method = app.methods.first()
        protocol = method.protocols.first()
        self.assertEqual(protocol.name, 'SYBR Green Protocol')

    def test_report_counts(self):
        """Report should track created entities."""
        report = create_knowledge_chain(ChainInput(
            goal_name='Goal', app_name='App',
            method_name='Method', protocol_name='Protocol',
        ))
        self.assertEqual(sum(report.created.values()), 4)
        self.assertTrue(report.success)

    def test_idempotent(self):
        """Creating the same chain twice should not duplicate."""
        inp = ChainInput(
            goal_name='Goal', app_name='App',
            method_name='Method', protocol_name='Protocol',
        )
        create_knowledge_chain(inp)
        report = create_knowledge_chain(inp)
        self.assertEqual(sum(report.created.values()), 0,
                         'Second call should not create duplicates')

    def test_empty_input(self):
        """Missing required fields should produce error report."""
        report = create_knowledge_chain(ChainInput())
        self.assertFalse(report.success)
        self.assertGreater(len(report.errors), 0)

    def test_report_string(self):
        """Report should have readable string representation."""
        report = create_knowledge_chain(ChainInput(
            goal_name='Goal', app_name='App',
            method_name='Method', protocol_name='Protocol',
        ))
        self.assertIsInstance(str(report), str)
