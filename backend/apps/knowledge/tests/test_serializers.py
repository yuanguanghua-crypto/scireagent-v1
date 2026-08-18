from django.test import TestCase
from apps.knowledge.api.v1.serializers import (
    ResearchGoalListSerializer, ResearchGoalDetailSerializer, ApplicationListSerializer, ApplicationDetailSerializer,
    MethodListSerializer, MethodDetailSerializer, ProtocolListSerializer, ProtocolDetailSerializer,
    ReferenceSerializer, CompatibilitySerializer, ProtocolStepSerializer
)
from apps.knowledge.tests.factories import (
    ResearchGoalFactory, ApplicationFactory, MethodFactory,
    ProtocolFactory, ProtocolStepFactory, ReferenceFactory, CompatibilityFactory
)
from apps.bridges.tests.factories import ProductMethodFactory, MethodProtocolFactory
from apps.bridges.models import MethodProtocol
import factory
from apps.knowledge.models import FacetValue, ProtocolFacet


class FacetValueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FacetValue
    facet_type = 'method'
    kind = ''
    value = factory.Sequence(lambda n: f'Facet {n}')


class ProtocolFacetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProtocolFacet
    protocol = factory.SubFactory(ProtocolFactory)
    facet = factory.SubFactory(FacetValueFactory)
    source = 'cluster_main'


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
        self.assertIn('application_count', data)
        self.assertIn('created_at', data)

    def test_application_count_real(self):
        # #495-D：application_count 是真实关联 Application 计数，非死字段。
        goal = ResearchGoalFactory()
        ApplicationFactory.create_batch(3, research_goal=goal)
        serializer = ResearchGoalListSerializer(goal)
        self.assertEqual(serializer.data['application_count'], 3)

    def test_data_values(self):
        goal = ResearchGoalFactory(name='RNA Labeling')
        serializer = ResearchGoalListSerializer(goal)
        self.assertEqual(serializer.data['name'], 'RNA Labeling')


class ResearchGoalDetailSerializerTest(TestCase):
    """#495 轻量版：ResearchGoal 详情序列化器须暴露策展协议集（读=对象，写=ID列表）。"""

    def test_read_includes_protocol_objects(self):
        goal = ResearchGoalFactory()
        p1 = ProtocolFactory()
        p2 = ProtocolFactory()
        goal.protocols.add(p1, p2)
        data = ResearchGoalDetailSerializer(goal).data
        self.assertIn('protocols', data)
        ids = {p['id'] for p in data['protocols']}
        self.assertEqual(ids, {p1.id, p2.id})
        entry = data['protocols'][0]
        self.assertIn('id', entry)
        self.assertIn('name', entry)
        self.assertIn('slug', entry)

    def test_read_empty_protocols(self):
        goal = ResearchGoalFactory()
        data = ResearchGoalDetailSerializer(goal).data
        self.assertEqual(data['protocols'], [])

    def test_partial_update_sets_protocols(self):
        goal = ResearchGoalFactory()
        p1 = ProtocolFactory()
        serializer = ResearchGoalDetailSerializer(
            instance=goal, data={'protocols': [p1.id]}, partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.assertEqual(list(goal.protocols.values_list('id', flat=True)), [p1.id])

    def test_partial_update_clears_protocols(self):
        goal = ResearchGoalFactory()
        p1 = ProtocolFactory()
        goal.protocols.add(p1)
        serializer = ResearchGoalDetailSerializer(
            instance=goal, data={'protocols': []}, partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.assertEqual(list(goal.protocols.values_list('id', flat=True)), [])


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
        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=method, protocol=protocol)
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
        method = MethodFactory()
        protocol = ProtocolFactory()
        MethodProtocol.objects.create(method=method, protocol=protocol)
        pm = ProductMethodFactory(method=method)
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


class ProtocolDetailSerializerFacetTest(TestCase):
    """route B 加法（范围 A）：ProtocolDetailSerializer 必须暴露按 facet_type 分组的 facets。"""

    def _link(self, protocol, facet_type, value, kind=''):
        fv = FacetValueFactory(facet_type=facet_type, kind=kind, value=value)
        ProtocolFacetFactory(protocol=protocol, facet=fv)
        return fv

    def test_facets_grouped_by_type(self):
        protocol = ProtocolFactory()
        self._link(protocol, 'application', 'Sequencing & Library Prep')
        self._link(protocol, 'method', 'Bioinformatics & Data Analysis')
        self._link(protocol, 'biological_context', 'Homo sapiens', kind='species')
        self._link(protocol, 'biological_context', 'HEK293', kind='cell')
        self._link(protocol, 'study_type', 'Review')
        facets = ProtocolDetailSerializer(protocol).data['facets']
        self.assertIn('application', facets)
        self.assertEqual(facets['application'][0]['value'], 'Sequencing & Library Prep')
        self.assertEqual(facets['method'][0]['value'], 'Bioinformatics & Data Analysis')
        self.assertEqual(len(facets['biological_context']), 2)
        self.assertEqual(facets['study_type'][0]['value'], 'Review')

    def test_facet_entry_shape_no_source(self):
        protocol = ProtocolFactory()
        fv = self._link(protocol, 'application', 'Genomics & DNA')
        entry = ProtocolDetailSerializer(protocol).data['facets']['application'][0]
        self.assertEqual(entry['id'], fv.id)
        self.assertEqual(entry['facet_type'], 'application')
        self.assertEqual(entry['kind'], '')
        self.assertEqual(entry['value'], 'Genomics & DNA')
        # 用户决策：不暴露来源标记
        self.assertNotIn('source', entry)

    def test_biological_context_kind_preserved(self):
        protocol = ProtocolFactory()
        self._link(protocol, 'biological_context', 'Mus musculus', kind='species')
        self._link(protocol, 'biological_context', 'Cancer', kind='disease')
        facets = ProtocolDetailSerializer(protocol).data['facets']
        self.assertEqual({e['kind'] for e in facets['biological_context']}, {'species', 'disease'})

    def test_empty_facets_is_empty_dict(self):
        protocol = ProtocolFactory()
        self.assertEqual(ProtocolDetailSerializer(protocol).data['facets'], {})
