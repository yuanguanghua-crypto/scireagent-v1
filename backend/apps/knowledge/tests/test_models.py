import pytest
from django.test import TestCase
from django.db import IntegrityError, connection
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, ProtocolStep, Reference, Compatibility
)
from apps.knowledge.tests.factories import (
    ResearchGoalFactory, ApplicationFactory, MethodFactory,
    ProtocolFactory, ProtocolStepFactory, ReferenceFactory, CompatibilityFactory
)


class ResearchGoalModelTest(TestCase):
    def test_create(self):
        goal = ResearchGoalFactory(name='Label RNA', summary='RNA labeling workflows')
        self.assertEqual(goal.name, 'Label RNA')
        self.assertEqual(goal.summary, 'RNA labeling workflows')
        self.assertEqual(goal.status, 'draft')

    def test_slug_unique(self):
        ResearchGoalFactory(slug='test-goal')
        with self.assertRaises(IntegrityError):
            ResearchGoalFactory(slug='test-goal')

    def test_str(self):
        goal = ResearchGoalFactory(name='My Goal')
        self.assertEqual(str(goal), 'My Goal')

    def test_ordering(self):
        g1 = ResearchGoalFactory(priority=2)
        g2 = ResearchGoalFactory(priority=1)
        goals = list(ResearchGoal.objects.all())
        self.assertEqual(goals[0].id, g2.id)

    def test_status_choices(self):
        goal = ResearchGoalFactory(status='active')
        self.assertEqual(goal.status, 'active')

    def test_status_default_draft(self):
        goal = ResearchGoalFactory()
        self.assertEqual(goal.status, 'draft')

    def test_status_choices_values(self):
        choices = dict(ResearchGoal.Status.choices)
        self.assertIn('draft', choices)
        self.assertIn('active', choices)
        self.assertIn('deprecated', choices)
        self.assertIn('archived', choices)

    def test_max_length_name(self):
        goal = ResearchGoalFactory(name='A' * 255)
        self.assertEqual(len(goal.name), 255)

    def test_summary_blank_default(self):
        goal = ResearchGoalFactory(summary='')
        self.assertEqual(goal.summary, '')

    def test_priority_max_value_validator(self):
        goal = ResearchGoalFactory(priority=9999)
        self.assertEqual(goal.priority, 9999)

    def test_timestamped_fields(self):
        goal = ResearchGoalFactory()
        self.assertIsNotNone(goal.created_at)
        self.assertIsNotNone(goal.updated_at)

    def test_table_name(self):
        self.assertEqual(ResearchGoal._meta.db_table, 'research_goal')


class ApplicationModelTest(TestCase):
    def test_create(self):
        app = ApplicationFactory(name='RNA Labeling')
        self.assertEqual(app.name, 'RNA Labeling')
        self.assertIsNotNone(app.research_goal)

    def test_belongs_to_research_goal(self):
        goal = ResearchGoalFactory()
        app = ApplicationFactory(research_goal=goal)
        self.assertEqual(app.research_goal_id, goal.id)

    def test_slug_unique(self):
        ApplicationFactory(slug='rna-labeling')
        with self.assertRaises(IntegrityError):
            ApplicationFactory(slug='rna-labeling')

    def test_str(self):
        app = ApplicationFactory(name='RNA Labeling')
        self.assertEqual(str(app), 'RNA Labeling')

    def test_ordering(self):
        a1 = ApplicationFactory(sort_order=2)
        a2 = ApplicationFactory(sort_order=1)
        apps = list(Application.objects.all())
        self.assertEqual(apps[0].id, a2.id)

    def test_status_default(self):
        app = ApplicationFactory()
        self.assertEqual(app.status, 'draft')

    def test_related_name_on_research_goal(self):
        goal = ResearchGoalFactory()
        ApplicationFactory(research_goal=goal)
        ApplicationFactory(research_goal=goal)
        self.assertEqual(goal.applications.count(), 2)

    def test_cascade_delete(self):
        goal = ResearchGoalFactory()
        app = ApplicationFactory(research_goal=goal)
        goal_id = app.id
        goal.delete()
        self.assertFalse(Application.objects.filter(id=goal_id).exists())

    def test_table_name(self):
        self.assertEqual(Application._meta.db_table, 'application')


class MethodModelTest(TestCase):
    def test_create(self):
        method = MethodFactory(name='Sanger Sequencing')
        self.assertEqual(method.name, 'Sanger Sequencing')

    def test_belongs_to_application(self):
        app = ApplicationFactory()
        method = MethodFactory(application=app)
        self.assertEqual(method.application_id, app.id)

    def test_slug_unique(self):
        MethodFactory(slug='sanger')
        with self.assertRaises(IntegrityError):
            MethodFactory(slug='sanger')

    def test_slug_index_exists(self):
        indexes = Method._meta.indexes
        slug_indexes = [i for i in indexes if 'slug' in str(i.fields)]
        self.assertTrue(len(slug_indexes) > 0)

    def test_slug_index_name(self):
        indexes = Method._meta.indexes
        slug_indexes = [i for i in indexes if i.name == 'method_slug_idx']
        self.assertEqual(len(slug_indexes), 1)

    def test_str(self):
        method = MethodFactory(name='Sanger Sequencing')
        self.assertEqual(str(method), 'Sanger Sequencing')

    def test_related_name_on_application(self):
        app = ApplicationFactory()
        MethodFactory(application=app)
        MethodFactory(application=app)
        self.assertEqual(app.methods.count(), 2)

    def test_optional_fields_default_blank(self):
        method = MethodFactory()
        self.assertEqual(method.purpose, '')
        self.assertEqual(method.advantages, '')
        self.assertEqual(method.limitations, '')
        self.assertEqual(method.cost_band, '')
        self.assertEqual(method.timeline, '')

    def test_table_name(self):
        self.assertEqual(Method._meta.db_table, 'method')


class ProtocolModelTest(TestCase):
    def test_create(self):
        protocol = ProtocolFactory(name='Standard Protocol', version='1.0')
        self.assertEqual(protocol.name, 'Standard Protocol')
        self.assertEqual(protocol.version, '1.0')

    def test_unique_together_method_slug_version(self):
        method = MethodFactory()
        ProtocolFactory(method=method, slug='test-proto', version='1.0')
        with self.assertRaises(IntegrityError):
            ProtocolFactory(method=method, slug='test-proto', version='1.0')

    def test_same_slug_different_version_allowed(self):
        method = MethodFactory()
        p1 = ProtocolFactory(method=method, slug='test-proto', version='1.0')
        p2 = ProtocolFactory(method=method, slug='test-proto', version='2.0')
        self.assertNotEqual(p1.id, p2.id)

    def test_status_default(self):
        protocol = ProtocolFactory()
        self.assertEqual(protocol.status, 'draft')

    def test_published_at_nullable(self):
        protocol = ProtocolFactory()
        self.assertIsNone(protocol.published_at)

    def test_superseded_at_nullable(self):
        protocol = ProtocolFactory()
        self.assertIsNone(protocol.superseded_at)

    def test_str(self):
        protocol = ProtocolFactory(name='RNA Protocol', version='2.0')
        result = str(protocol)
        self.assertIn('RNA Protocol', result)
        self.assertIn('2.0', result)

    def test_publication_status_choices(self):
        choices = dict(Protocol.PublicationStatus.choices)
        self.assertIn('draft', choices)
        self.assertIn('published', choices)
        self.assertIn('superseded', choices)
        self.assertIn('archived', choices)

    def test_slug_index_exists(self):
        indexes = Protocol._meta.indexes
        slug_indexes = [i for i in indexes if i.name == 'protocol_slug_idx']
        self.assertEqual(len(slug_indexes), 1)

    def test_ordering(self):
        method = MethodFactory()
        p2 = ProtocolFactory(method=method, version='2.0')
        p1 = ProtocolFactory(method=method, version='1.0')
        protocols = list(Protocol.objects.all())
        # ordering is ['method', '-version']
        self.assertEqual(protocols[0].version, '2.0')

    def test_related_name_on_method(self):
        method = MethodFactory()
        ProtocolFactory(method=method)
        ProtocolFactory(method=method)
        self.assertEqual(method.protocols.count(), 2)

    def test_table_name(self):
        self.assertEqual(Protocol._meta.db_table, 'protocol')


class ProtocolStepModelTest(TestCase):
    def test_create(self):
        step = ProtocolStepFactory(step_no=1, title='Prepare RNA')
        self.assertEqual(step.step_no, 1)
        self.assertEqual(step.title, 'Prepare RNA')

    def test_unique_together_protocol_step_no(self):
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, step_no=1)
        with self.assertRaises(IntegrityError):
            ProtocolStepFactory(protocol=protocol, step_no=1)

    def test_ordering(self):
        protocol = ProtocolFactory()
        s2 = ProtocolStepFactory(protocol=protocol, step_no=2)
        s1 = ProtocolStepFactory(protocol=protocol, step_no=1)
        steps = list(protocol.steps.all())
        self.assertEqual(steps[0].step_no, 1)
        self.assertEqual(steps[1].step_no, 2)

    def test_str(self):
        step = ProtocolStepFactory(step_no=3, title='Add Buffer')
        result = str(step)
        self.assertIn('3', result)
        self.assertIn('Add Buffer', result)

    def test_related_name_on_protocol(self):
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, step_no=1)
        ProtocolStepFactory(protocol=protocol, step_no=2)
        self.assertEqual(protocol.steps.count(), 2)

    def test_duration_seconds_nullable(self):
        step = ProtocolStepFactory(duration_seconds=None)
        self.assertIsNone(step.duration_seconds)

    def test_duration_seconds_set(self):
        step = ProtocolStepFactory(duration_seconds=300)
        self.assertEqual(step.duration_seconds, 300)

    def test_protocol_step_index_exists(self):
        indexes = ProtocolStep._meta.indexes
        step_indexes = [i for i in indexes if i.name == 'protocol_step_idx']
        self.assertEqual(len(step_indexes), 1)

    def test_table_name(self):
        self.assertEqual(ProtocolStep._meta.db_table, 'protocol_step')


class ReferenceModelTest(TestCase):
    def test_create(self):
        ref = ReferenceFactory(title='Nature Paper 2024')
        self.assertEqual(ref.title, 'Nature Paper 2024')

    def test_doi_unique(self):
        ReferenceFactory(doi='10.1038/unique-test-doi')
        with self.assertRaises(IntegrityError):
            ReferenceFactory(doi='10.1038/unique-test-doi')

    def test_pmid_unique(self):
        ReferenceFactory(pmid='99999999')
        with self.assertRaises(IntegrityError):
            ReferenceFactory(pmid='99999999')

    def test_doi_nullable(self):
        ref = ReferenceFactory(doi=None)
        self.assertIsNone(ref.doi)

    def test_pmid_nullable(self):
        ref = ReferenceFactory(pmid=None)
        self.assertIsNone(ref.pmid)

    def test_source_type_default(self):
        ref = ReferenceFactory()
        self.assertEqual(ref.source_type, 'journal')

    def test_source_type_choices(self):
        choices = dict(Reference.SourceType.choices)
        self.assertIn('journal', choices)
        self.assertIn('book', choices)
        self.assertIn('patent', choices)
        self.assertIn('thesis', choices)
        self.assertIn('web', choices)
        self.assertIn('other', choices)

    def test_str_truncates(self):
        ref = ReferenceFactory(title='A' * 200)
        self.assertLessEqual(len(str(ref)), 80)

    def test_ordering(self):
        r1 = ReferenceFactory(year=2020, title='B Paper')
        r2 = ReferenceFactory(year=2024, title='A Paper')
        refs = list(Reference.objects.all())
        # ordering is ['-year', 'title']
        self.assertEqual(refs[0].year, 2024)

    def test_year_nullable(self):
        ref = ReferenceFactory(year=None)
        self.assertIsNone(ref.year)

    def test_table_name(self):
        self.assertEqual(Reference._meta.db_table, 'reference')


class CompatibilityModelTest(TestCase):
    def test_create(self):
        comp = CompatibilityFactory(code='COMP-001')
        self.assertEqual(comp.code, 'COMP-001')

    def test_code_unique(self):
        CompatibilityFactory(code='COMP-001')
        with self.assertRaises(IntegrityError):
            CompatibilityFactory(code='COMP-001')

    def test_expression_json_default(self):
        comp = CompatibilityFactory()
        self.assertEqual(comp.expression_json, {})

    def test_scope_choices(self):
        choices = dict(Compatibility.Scope.choices)
        self.assertIn('product-product', choices)
        self.assertIn('product-method', choices)
        self.assertIn('product-protocol', choices)
        self.assertIn('product-instrument', choices)

    def test_rule_type_choices(self):
        choices = dict(Compatibility.RuleType.choices)
        self.assertIn('compatible', choices)
        self.assertIn('incompatible', choices)
        self.assertIn('conditional', choices)
        self.assertIn('warning', choices)

    def test_severity_choices(self):
        choices = dict(Compatibility.Severity.choices)
        self.assertIn('info', choices)
        self.assertIn('warning', choices)
        self.assertIn('blocking', choices)
        self.assertIn('critical', choices)

    def test_severity_default(self):
        comp = CompatibilityFactory()
        self.assertEqual(comp.severity, 'info')

    def test_str(self):
        comp = CompatibilityFactory(code='COMP-001', rule_type='compatible')
        result = str(comp)
        self.assertIn('COMP-001', result)
        self.assertIn('compatible', result)

    def test_ordering(self):
        c2 = CompatibilityFactory(code='B-COMP')
        c1 = CompatibilityFactory(code='A-COMP')
        comps = list(Compatibility.objects.all())
        self.assertEqual(comps[0].code, 'A-COMP')

    def test_status_default(self):
        comp = CompatibilityFactory()
        self.assertEqual(comp.status, 'draft')

    def test_table_name(self):
        self.assertEqual(Compatibility._meta.db_table, 'compatibility')
