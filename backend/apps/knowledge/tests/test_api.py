from django.test import TestCase
from rest_framework.test import APIClient
from apps.knowledge.tests.factories import (
    ResearchGoalFactory, ApplicationFactory, MethodFactory,
    ProtocolFactory, ProtocolStepFactory, ReferenceFactory, CompatibilityFactory
)
from apps.bridges.tests.factories import ProductMethodFactory, MethodProtocolFactory


class ResearchGoalAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_empty(self):
        resp = self.client.get('/api/v1/research-goals/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data'], [])

    def test_list_with_data(self):
        ResearchGoalFactory.create_batch(3)
        resp = self.client.get('/api/v1/research-goals/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 3)

    def test_list_envelope_format(self):
        ResearchGoalFactory()
        resp = self.client.get('/api/v1/research-goals/')
        data = resp.json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_detail(self):
        goal = ResearchGoalFactory(name='Test Goal')
        resp = self.client.get(f'/api/v1/research-goals/{goal.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data']['name'], 'Test Goal')

    def test_detail_fields(self):
        goal = ResearchGoalFactory()
        resp = self.client.get(f'/api/v1/research-goals/{goal.id}/')
        data = resp.json()['data']
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('summary', data)
        self.assertIn('priority', data)
        self.assertIn('status', data)
        self.assertIn('created_at', data)

    def test_create(self):
        resp = self.client.post('/api/v1/research-goals/', {
            'name': 'New Goal', 'slug': 'new-goal', 'summary': 'Test'
        }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_detail_not_found(self):
        resp = self.client.get('/api/v1/research-goals/99999/')
        self.assertEqual(resp.status_code, 404)


class ApplicationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        ApplicationFactory.create_batch(2)
        resp = self.client.get('/api/v1/applications/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        ApplicationFactory()
        resp = self.client.get('/api/v1/applications/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('slug', data)
        self.assertIn('research_goal_id', data)

    def test_detail_includes_methods(self):
        app = ApplicationFactory()
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('methods', resp.json()['data'])

    def test_detail_includes_protocols(self):
        app = ApplicationFactory()
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        self.assertIn('protocols', resp.json()['data'])

    def test_detail_includes_products(self):
        app = ApplicationFactory()
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        self.assertIn('products', resp.json()['data'])

    def test_detail_methods_populated(self):
        app = ApplicationFactory()
        method = MethodFactory(application=app)
        resp = self.client.get(f'/api/v1/applications/{app.id}/')
        data = resp.json()['data']
        method_ids = [m['id'] for m in data['methods']]
        self.assertIn(method.id, method_ids)

    def test_filter_by_research_goal_id(self):
        goal = ResearchGoalFactory()
        ApplicationFactory(research_goal=goal)
        ApplicationFactory()  # different goal
        resp = self.client.get(f'/api/v1/applications/?research_goal_id={goal.id}')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_status(self):
        ApplicationFactory(status='active')
        ApplicationFactory(status='draft')
        resp = self.client.get('/api/v1/applications/?status=active')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search(self):
        ApplicationFactory(name='RNA Labeling')
        ApplicationFactory(name='DNA Sequencing')
        resp = self.client.get('/api/v1/applications/?search=RNA')
        self.assertEqual(len(resp.json()['data']), 1)


class MethodAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        MethodFactory.create_batch(2)
        resp = self.client.get('/api/v1/methods/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        MethodFactory()
        resp = self.client.get('/api/v1/methods/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('application_id', data)

    def test_detail_includes_protocols(self):
        method = MethodFactory()
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        self.assertIn('protocols', resp.json()['data'])

    def test_detail_includes_products(self):
        method = MethodFactory()
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        self.assertIn('products', resp.json()['data'])

    def test_detail_protocols_populated(self):
        method = MethodFactory()
        protocol = ProtocolFactory(method=method)
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        data = resp.json()['data']
        protocol_ids = [p['id'] for p in data['protocols']]
        self.assertIn(protocol.id, protocol_ids)

    def test_detail_products_populated(self):
        method = MethodFactory()
        pm = ProductMethodFactory(method=method)
        resp = self.client.get(f'/api/v1/methods/{method.id}/')
        data = resp.json()['data']
        product_ids = [p['id'] for p in data['products']]
        self.assertIn(pm.product_id, product_ids)

    def test_filter_by_application_id(self):
        app = ApplicationFactory()
        MethodFactory(application=app)
        MethodFactory()  # different app
        resp = self.client.get(f'/api/v1/methods/?application_id={app.id}')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_status(self):
        MethodFactory(status='active')
        MethodFactory(status='draft')
        resp = self.client.get('/api/v1/methods/?status=active')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search(self):
        MethodFactory(name='Sanger Sequencing')
        MethodFactory(name='PCR')
        resp = self.client.get('/api/v1/methods/?search=Sanger')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_json_ld_endpoint(self):
        method = MethodFactory(name='Sanger Sequencing')
        resp = self.client.get(f'/api/v1/methods/{method.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@type', jsonld)


class ProtocolAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        ProtocolFactory.create_batch(2)
        resp = self.client.get('/api/v1/protocols/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        ProtocolFactory()
        resp = self.client.get('/api/v1/protocols/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('version', data)
        self.assertIn('method_id', data)

    def test_detail_includes_steps(self):
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, step_no=1)
        ProtocolStepFactory(protocol=protocol, step_no=2)
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        data = resp.json()['data']
        self.assertEqual(len(data['steps']), 2)
        self.assertEqual(data['steps'][0]['step_no'], 1)

    def test_detail_step_fields(self):
        protocol = ProtocolFactory()
        step = ProtocolStepFactory(protocol=protocol, step_no=1, title='Prepare')
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        step_data = resp.json()['data']['steps'][0]
        self.assertIn('id', step_data)
        self.assertIn('step_no', step_data)
        self.assertIn('title', step_data)
        self.assertIn('body', step_data)

    def test_detail_includes_references(self):
        protocol = ProtocolFactory()
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        self.assertIn('references', resp.json()['data'])

    def test_detail_includes_products(self):
        protocol = ProtocolFactory()
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/')
        self.assertIn('products', resp.json()['data'])

    def test_filter_by_method_id(self):
        method = MethodFactory()
        ProtocolFactory(method=method)
        ProtocolFactory()  # different method
        resp = self.client.get(f'/api/v1/protocols/?method_id={method.id}')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_status(self):
        ProtocolFactory(status='published')
        ProtocolFactory(status='draft')
        resp = self.client.get('/api/v1/protocols/?status=published')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search(self):
        ProtocolFactory(name='RNA Labeling Protocol')
        ProtocolFactory(name='DNA Extraction')
        resp = self.client.get('/api/v1/protocols/?search=RNA')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_json_ld_endpoint(self):
        protocol = ProtocolFactory(name='RNA Protocol')
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@type', jsonld)
        self.assertIn('step', jsonld)


class ReferenceAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        ReferenceFactory.create_batch(2)
        resp = self.client.get('/api/v1/references/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        ReferenceFactory()
        resp = self.client.get('/api/v1/references/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('title', data)
        self.assertIn('authors', data)
        self.assertIn('doi', data)
        self.assertIn('pmid', data)

    def test_detail(self):
        ref = ReferenceFactory(title='Nature 2024', doi='10.1038/test')
        resp = self.client.get(f'/api/v1/references/{ref.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['title'], 'Nature 2024')
        self.assertEqual(data['doi'], '10.1038/test')

    def test_search_by_title(self):
        ReferenceFactory(title='Nature Paper')
        ReferenceFactory(title='Science Paper')
        resp = self.client.get('/api/v1/references/?search=Nature')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_by_doi(self):
        ReferenceFactory(doi='10.1038/unique')
        ReferenceFactory(doi='10.1126/other')
        resp = self.client.get('/api/v1/references/?search=10.1038')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_source_type(self):
        ReferenceFactory(source_type='journal')
        ReferenceFactory(source_type='book')
        resp = self.client.get('/api/v1/references/?source_type=journal')
        self.assertEqual(len(resp.json()['data']), 1)


class CompatibilityAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list(self):
        CompatibilityFactory.create_batch(2)
        resp = self.client.get('/api/v1/compatibility/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 2)

    def test_list_fields(self):
        CompatibilityFactory()
        resp = self.client.get('/api/v1/compatibility/')
        data = resp.json()['data'][0]
        self.assertIn('id', data)
        self.assertIn('code', data)
        self.assertIn('scope', data)
        self.assertIn('rule_type', data)
        self.assertIn('severity', data)

    def test_detail(self):
        comp = CompatibilityFactory(code='COMP-001', rule_type='compatible')
        resp = self.client.get(f'/api/v1/compatibility/{comp.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['code'], 'COMP-001')

    def test_filter_by_scope(self):
        CompatibilityFactory(scope='product-product')
        CompatibilityFactory(scope='product-method')
        resp = self.client.get('/api/v1/compatibility/?scope=product-product')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_rule_type(self):
        CompatibilityFactory(rule_type='compatible')
        CompatibilityFactory(rule_type='incompatible')
        resp = self.client.get('/api/v1/compatibility/?rule_type=compatible')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_filter_by_severity(self):
        CompatibilityFactory(severity='info')
        CompatibilityFactory(severity='blocking')
        resp = self.client.get('/api/v1/compatibility/?severity=blocking')
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_by_code(self):
        CompatibilityFactory(code='COMP-Alpha')
        CompatibilityFactory(code='COMP-Beta')
        resp = self.client.get('/api/v1/compatibility/?search=Alpha')
        self.assertEqual(len(resp.json()['data']), 1)
