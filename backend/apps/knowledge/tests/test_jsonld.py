from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient
from core.jsonld import (
    build_product_jsonld, build_method_jsonld, build_protocol_jsonld,
    build_reference_jsonld, _get_base_url, _build_product_properties
)
from apps.knowledge.tests.factories import (
    MethodFactory, ProtocolFactory, ProtocolStepFactory, ReferenceFactory
)
from apps.commerce.tests.factories import ProductFactory


class ProductJsonLdTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.factory = RequestFactory()

    def test_product_jsonld_structure(self):
        product = ProductFactory(name='Cy3-NHS', cas='12345-67-8')
        resp = self.client.get(f'/api/v1/products/{product.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@id', jsonld)
        self.assertIn('@type', jsonld)
        self.assertEqual(jsonld['name'], 'Cy3-NHS')

    def test_product_jsonld_type(self):
        product = ProductFactory()
        data = build_product_jsonld(product)
        self.assertIn('Product', data['@type'])
        self.assertIn('ChemicalSubstance', data['@type'])

    def test_product_jsonld_context(self):
        product = ProductFactory()
        data = build_product_jsonld(product)
        self.assertIn('https://schema.org', data['@context'])

    def test_product_jsonld_identifier_cas(self):
        product = ProductFactory(cas='12345-67-8', inchi='')
        data = build_product_jsonld(product)
        self.assertEqual(data['identifier'], '12345-67-8')

    def test_product_jsonld_identifier_inchi(self):
        product = ProductFactory(cas='', inchi='InChI=1S/test')
        data = build_product_jsonld(product)
        self.assertEqual(data['identifier'], 'InChI=1S/test')

    def test_product_jsonld_alternate_names(self):
        product = ProductFactory(synonyms=['Cy3', 'Cyanine3'])
        data = build_product_jsonld(product)
        self.assertEqual(data['alternateName'], ['Cy3', 'Cyanine3'])

    def test_product_jsonld_additional_properties(self):
        product = ProductFactory(cas='12345-67-8', smiles='CCO', purity='99%')
        data = build_product_jsonld(product)
        props = data['additionalProperty']
        prop_names = [p['name'] for p in props]
        self.assertIn('CAS', prop_names)
        self.assertIn('SMILES', prop_names)
        self.assertIn('Purity', prop_names)

    def test_product_jsonld_with_request(self):
        request = self.factory.get('/api/v1/products/1/json-ld/', SERVER_NAME='localhost', SERVER_PORT='8000')
        product = ProductFactory()
        data = build_product_jsonld(product, request)
        self.assertIn('localhost', data['@id'])


class MethodJsonLdTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_method_jsonld_structure(self):
        method = MethodFactory(name='Sanger Sequencing')
        resp = self.client.get(f'/api/v1/methods/{method.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@type', jsonld)
        self.assertIn('HowTo', jsonld['@type'])

    def test_method_jsonld_name(self):
        method = MethodFactory(name='Sanger Sequencing')
        data = build_method_jsonld(method)
        self.assertEqual(data['name'], 'Sanger Sequencing')

    def test_method_jsonld_type(self):
        method = MethodFactory()
        data = build_method_jsonld(method)
        self.assertIn('HowTo', data['@type'])
        self.assertIn('lab:Method', data['@type'])

    def test_method_jsonld_description_fallback(self):
        method = MethodFactory(summary='', purpose='DNA sequencing')
        data = build_method_jsonld(method)
        self.assertEqual(data['description'], 'DNA sequencing')

    def test_method_jsonld_description_summary(self):
        method = MethodFactory(summary='Sequencing method')
        data = build_method_jsonld(method)
        self.assertEqual(data['description'], 'Sequencing method')


class ProtocolJsonLdTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_protocol_jsonld_structure(self):
        protocol = ProtocolFactory(name='RNA Protocol')
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/json-ld/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertIn('@context', jsonld)
        self.assertIn('@type', jsonld)
        self.assertIn('step', jsonld)

    def test_protocol_jsonld_type(self):
        protocol = ProtocolFactory()
        data = build_protocol_jsonld(protocol)
        self.assertIn('HowTo', data['@type'])
        self.assertIn('CreativeWork', data['@type'])

    def test_protocol_jsonld_name_includes_version(self):
        protocol = ProtocolFactory(name='RNA Protocol', version='2.0')
        data = build_protocol_jsonld(protocol)
        self.assertIn('RNA Protocol', data['name'])
        self.assertIn('2.0', data['name'])

    def test_protocol_jsonld_with_steps(self):
        protocol = ProtocolFactory(name='RNA Protocol')
        ProtocolStepFactory(protocol=protocol, step_no=1, title='Step 1', body='Prepare')
        ProtocolStepFactory(protocol=protocol, step_no=2, title='Step 2', body='Execute')
        resp = self.client.get(f'/api/v1/protocols/{protocol.id}/json-ld/')
        data = resp.json()
        # EnvelopeRenderer wraps: {success: True, data: {<jsonld>}, meta: {}}
        jsonld = data.get('data', data)
        self.assertEqual(len(jsonld['step']), 2)
        self.assertEqual(jsonld['step'][0]['position'], 1)
        self.assertEqual(jsonld['step'][0]['name'], 'Step 1')
        self.assertEqual(jsonld['step'][1]['position'], 2)

    def test_protocol_jsonld_steps_type(self):
        protocol = ProtocolFactory()
        ProtocolStepFactory(protocol=protocol, step_no=1)
        data = build_protocol_jsonld(protocol, protocol.steps.all())
        for step in data['step']:
            self.assertEqual(step['@type'], 'HowToStep')

    def test_protocol_jsonld_empty_steps(self):
        protocol = ProtocolFactory()
        data = build_protocol_jsonld(protocol)
        self.assertEqual(data['step'], [])


class ReferenceJsonLdTest(TestCase):
    def test_reference_jsonld_type(self):
        ref = ReferenceFactory(title='Nature Paper', doi='10.1038/test')
        data = build_reference_jsonld(ref)
        self.assertEqual(data['@type'], 'ScholarlyArticle')

    def test_reference_jsonld_name(self):
        ref = ReferenceFactory(title='Nature Paper')
        data = build_reference_jsonld(ref)
        self.assertEqual(data['name'], 'Nature Paper')

    def test_reference_jsonld_identifier_doi(self):
        ref = ReferenceFactory(doi='10.1038/test', pmid='')
        data = build_reference_jsonld(ref)
        self.assertEqual(data['identifier'], '10.1038/test')

    def test_reference_jsonld_identifier_pmid(self):
        ref = ReferenceFactory(doi='', pmid='12345678')
        data = build_reference_jsonld(ref)
        self.assertEqual(data['identifier'], '12345678')

    def test_reference_jsonld_journal(self):
        ref = ReferenceFactory(journal='Nature')
        data = build_reference_jsonld(ref)
        self.assertIsNotNone(data['isPartOf'])
        self.assertEqual(data['isPartOf']['name'], 'Nature')

    def test_reference_jsonld_no_journal(self):
        ref = ReferenceFactory(journal='')
        data = build_reference_jsonld(ref)
        self.assertIsNone(data['isPartOf'])


class BaseUrlTest(TestCase):
    def test_get_base_url_with_request(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get('/test/', SERVER_NAME='localhost', SERVER_PORT='8000')
        url = _get_base_url(request)
        self.assertIn('localhost', url)

    def test_get_base_url_without_request(self):
        url = _get_base_url(None)
        self.assertEqual(url, 'https://scireagent.example.com')


class BuildProductPropertiesTest(TestCase):
    def test_build_properties_with_all_fields(self):
        product = ProductFactory(
            cas='12345-67-8', smiles='CCO', inchi='InChI=test', purity='99%'
        )
        props = _build_product_properties(product)
        names = [p['name'] for p in props]
        self.assertIn('CAS', names)
        self.assertIn('SMILES', names)
        self.assertIn('InChI', names)
        self.assertIn('Purity', names)

    def test_build_properties_with_shelf_life(self):
        from datetime import timedelta
        product = ProductFactory(shelf_life=timedelta(days=365))
        props = _build_product_properties(product)
        names = [p['name'] for p in props]
        self.assertIn('Shelf Life', names)

    def test_build_properties_empty_fields(self):
        product = ProductFactory(cas='', smiles='', inchi='', purity='')
        props = _build_product_properties(product)
        self.assertEqual(len(props), 0)

    def test_property_type(self):
        product = ProductFactory(cas='12345-67-8')
        props = _build_product_properties(product)
        cas_prop = next(p for p in props if p['name'] == 'CAS')
        self.assertEqual(cas_prop['@type'], 'PropertyValue')
        self.assertEqual(cas_prop['value'], '12345-67-8')
