from django.test import TestCase
from apps.knowledge.api.v1.serializers import (
    ResearchGoalListSerializer, ApplicationListSerializer, ApplicationDetailSerializer,
    MethodListSerializer, MethodDetailSerializer, ProtocolListSerializer, ProtocolDetailSerializer,
    ReferenceSerializer, CompatibilitySerializer, ProtocolStepSerializer
)
from apps.knowledge.tests.factories import (
    ResearchGoalFactory, ApplicationFactory, MethodFactory,
    ProtocolFactory, ProtocolStepFactory, ReferenceFactory, CompatibilityFactory
)
from apps.bridges.tests.factories import ProductMethodFactory, MethodProtocolFactory


class ResearchGoalListSerializerTest(TestCase):
    def test_fields(self):
        goal = ResearchGoalFactory(name='Test Goal', priority=5)
        serializer = ResearchGoalListSerializer(goal)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('summary', data)
        self.assertIn('priority', data)
        self.assertIn('status', data)
        self.assertIn('created_at', data)

    def test_data_values(self):
        goal = ResearchGoalFactory(name='RNA Labeling')
        serializer = ResearchGoalListSerializer(goal)
        self.assertEqual(serializer.data['name'], 'RNA Labeling')


class ApplicationListSerializerTest(TestCase):
    def test_fields(self):
        app = ApplicationFactory()
        serializer = ApplicationListSerializer(app)
        data = serializer.data
        self.assertIn('research_goal_id', data)
        self.assertEqual(data['research_goal_id'], app.research_goal_id)


class ApplicationDetailSerializerTest(TestCase):
    def test_method_ids_field(self):
        app = ApplicationFactory()
        method = MethodFactory(application=app)
        serializer = ApplicationDetailSerializer(app)
        method_ids = [m['id'] for m in serializer.data['methods']]
        self.assertIn(method.id, method_ids)

    def test_protocol_ids_field(self):
        app = ApplicationFactory()
        method = MethodFactory(application=app)
        mp = MethodProtocolFactory(method=method)
        serializer = ApplicationDetailSerializer(app)
        protocol_ids = [p['id'] for p in serializer.data['protocols']]
        self.assertIn(mp.protocol_id, protocol_ids)

    def test_product_ids_field(self):
        app = ApplicationFactory()
        method = MethodFactory(application=app)
        pm = ProductMethodFactory(method=method)
        serializer = ApplicationDetailSerializer(app)
        product_ids = [p['id'] for p in serializer.data['products']]
        self.assertIn(pm.product_id, product_ids)

    def test_empty_method_ids(self):
        app = ApplicationFactory()
        serializer = ApplicationDetailSerializer(app)
        self.assertEqual(serializer.data['methods'], [])

    def test_empty_protocol_ids(self):
        app = ApplicationFactory()
        serializer = ApplicationDetailSerializer(app)
        self.assertEqual(serializer.data['protocols'], [])

    def test_empty_product_ids(self):
        app = ApplicationFactory()
        serializer = ApplicationDetailSerializer(app)
        self.assertEqual(serializer.data['products'], [])


class MethodDetailSerializerTest(TestCase):
    def test_protocol_ids_field(self):
        method = MethodFactory()
        protocol = ProtocolFactory(method=method)
        serializer = MethodDetailSerializer(method)
        protocol_ids = [p['id'] for p in serializer.data['protocols']]
        self.assertIn(protocol.id, protocol_ids)

    def test_product_ids_field(self):
        method = MethodFactory()
        pm = ProductMethodFactory(method=method)
        serializer = MethodDetailSerializer(method)
        product_ids = [p['id'] for p in serializer.data['products']]
        self.assertIn(pm.product_id, product_ids)

    def test_empty_ids(self):
        method = MethodFactory()
        serializer = MethodDetailSerializer(method)
        self.assertEqual(serializer.data['protocols'], [])
        self.assertEqual(serializer.data['products'], [])


class ProtocolStepSerializerTest(TestCase):
    def test_fields(self):
        step = ProtocolStepFactory(step_no=1, title='Prepare', body='Body text')
        serializer = ProtocolStepSerializer(step)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('step_no', data)
        self.assertIn('title', data)
        self.assertIn('body', data)
        self.assertIn('duration_seconds', data)
        self.assertIn('warnings', data)
        self.assertIn('required_materials', data)


class ProtocolDetailSerializerTest(TestCase):
    def test_steps_field(self):
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, step_no=1)
        ProtocolStepFactory(protocol=protocol, step_no=2)
        serializer = ProtocolDetailSerializer(protocol)
        self.assertEqual(len(serializer.data['steps']), 2)

    def test_reference_ids_empty(self):
        protocol = ProtocolFactory()
        serializer = ProtocolDetailSerializer(protocol)
        self.assertEqual(serializer.data['references'], [])

    def test_product_ids_field(self):
        protocol = ProtocolFactory()
        pm = ProductMethodFactory(method=protocol.method)
        serializer = ProtocolDetailSerializer(protocol)
        product_ids = [p['id'] for p in serializer.data['products']]
        self.assertIn(pm.product_id, product_ids)

    def test_reference_ids_from_doi(self):
        from apps.knowledge.models import Reference
        ref = Reference.objects.create(
            title='Test', doi='10.1038/test123', source_type='journal'
        )
        protocol = ProtocolFactory(references='doi: 10.1038/test123')
        serializer = ProtocolDetailSerializer(protocol)
        ref_ids = [r['id'] for r in serializer.data['references']]
        self.assertIn(ref.id, ref_ids)

    def test_reference_ids_from_pmid(self):
        from apps.knowledge.models import Reference
        ref = Reference.objects.create(
            title='Test', pmid='12345678', source_type='journal'
        )
        protocol = ProtocolFactory(references='PMID: 12345678')
        serializer = ProtocolDetailSerializer(protocol)
        ref_ids = [r['id'] for r in serializer.data['references']]
        self.assertIn(ref.id, ref_ids)


class ReferenceSerializerTest(TestCase):
    def test_fields(self):
        ref = ReferenceFactory(title='Test Paper', doi='10.1038/test', pmid='12345678')
        serializer = ReferenceSerializer(ref)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('title', data)
        self.assertIn('authors', data)
        self.assertIn('journal', data)
        self.assertIn('year', data)
        self.assertIn('doi', data)
        self.assertIn('pmid', data)
        self.assertIn('url', data)
        self.assertIn('source_type', data)


class CompatibilitySerializerTest(TestCase):
    def test_fields(self):
        comp = CompatibilityFactory(code='COMP-001', scope='product-product', rule_type='compatible')
        serializer = CompatibilitySerializer(comp)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('code', data)
        self.assertIn('scope', data)
        self.assertIn('rule_type', data)
        self.assertIn('severity', data)
        self.assertIn('expression_json', data)
        self.assertIn('summary', data)
        self.assertIn('status', data)
