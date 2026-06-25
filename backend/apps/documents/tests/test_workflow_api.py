"""
documents 应用测试 — COA/SDS workflow + API 端点
"""
import datetime
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

User = get_user_model()

from apps.documents.models import Batch, Coa, SdsRevision, PubChemCache
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.documents.services.coa_generator import generate_coa_pdf
from apps.documents.services.sds_generator import generate_sds_pdf
from apps.documents.services.workflow import create_coa, approve_coa, generate_sds, approve_sds


class COAWorkflowTest(TestCase):
    """COA 工作流: create → QC update → approve + PDF"""

    def setUp(self):
        self.product = ProductFactory(
            catalog_no='SC8001', name='Test Nucleotide',
            cas='123-45-6', formula='C10H12N5O8P3',
            molecular_weight='522.13', storage='-20°C',
            purity='≥ 95% (HPLC)',
        )
        self.sku = SKUFactory(product=self.product, sku_code='SC8001-SKU1')

    def test_create_coa_workflow(self):
        """create_coa 创建 Batch + Coa draft"""
        coa = create_coa(
            sku_id=self.sku.id,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
            retest_at=datetime.date(2027, 1, 15),
        )
        self.assertIsNotNone(coa)
        self.assertEqual(coa.status, Coa.Status.DRAFT)
        self.assertEqual(coa.product_name, 'Test Nucleotide')
        self.assertEqual(coa.catalog_number, 'SC8001')
        self.assertEqual(coa.cas_number, '123-45-6')
        self.assertEqual(coa.molecular_formula, 'C10H12N5O8P3')
        self.assertIn('COA-SC8001-', coa.doc_id)
        self.assertIsNotNone(coa.batch)

    def test_generate_coa_pdf(self):
        """COA PDF 生成成功"""
        coa = create_coa(
            sku_id=self.sku.id,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
        )
        pdf_path = generate_coa_pdf(coa)
        self.assertTrue(pdf_path.startswith('documents/coa/'))
        self.assertTrue(pdf_path.endswith('.pdf'))

    def test_approve_coa_workflow(self):
        """approve_coa: 状态变更 + PDF 生成"""
        coa = create_coa(
            sku_id=self.sku.id,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
        )
        approved = approve_coa(
            coa.id,
            qc_analyst='Dr. Wang',
            qa_approval='Dr. Li',
        )
        self.assertEqual(approved.status, Coa.Status.APPROVED)
        self.assertEqual(approved.qc_analyst, 'Dr. Wang')
        self.assertEqual(approved.qa_approval, 'Dr. Li')
        self.assertIsNotNone(approved.approved_at)
        self.assertTrue(approved.pdf_path.startswith('documents/coa/'))


class SDSWorkflowTest(TestCase):
    """SDS 工作流: generate from PubChem → approve + PDF"""

    def setUp(self):
        self.product = ProductFactory(
            catalog_no='SC8001', name='Test Nucleotide',
            cas='64-17-5',  # ethanol — PubChem 必有
        )

    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_generate_sds_workflow(self, mock_fetch):
        """generate_sds 创建 SdsRevision"""
        mock_fetch.return_value = {
            'cid': 702,
            'signal_word': 'Warning',
            'pictograms': ['GHS02'],
            'hazard_codes': ['H225'],
            'precaution_codes': ['P210'],
            'section_data': {
                'section_1': {'product_name': 'ethanol'},
                'section_9': {'appearance': 'Clear liquid'},
            },
        }
        sds = generate_sds(product_id=self.product.id)
        self.assertIsNotNone(sds)
        self.assertEqual(sds.revision_no, 1)
        self.assertEqual(sds.signal_word, 'Warning')
        self.assertEqual(sds.get_pictograms(), ['GHS02'])

    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_generate_sds_creates_incremental_revision(self, mock_fetch):
        """多次 generate 递增 revision_no"""
        mock_fetch.return_value = {
            'cid': 702, 'signal_word': 'Warning',
            'pictograms': [], 'hazard_codes': [], 'precaution_codes': [],
            'section_data': {},
        }
        sds1 = generate_sds(product_id=self.product.id)
        sds2 = generate_sds(product_id=self.product.id)
        self.assertEqual(sds1.revision_no, 1)
        self.assertEqual(sds2.revision_no, 2)

    def test_generate_sds_no_cas_raises(self):
        """没有 CAS 号的产品抛出 ValueError"""
        product = ProductFactory(cas='', catalog_no='SC9999')
        with self.assertRaises(ValueError):
            generate_sds(product_id=product.id)

    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_generate_sds_pdf(self, mock_fetch):
        """SDS PDF 生成成功"""
        mock_fetch.return_value = {
            'cid': 702, 'signal_word': 'Warning',
            'pictograms': ['GHS02'], 'hazard_codes': ['H225'],
            'precaution_codes': ['P210'],
            'section_data': {
                'section_1': {'product_name': 'ethanol',
                              'recommended_use': 'Lab reagent',
                              'restrictions': 'R&D only',
                              'supplier': {'company': 'SciReagent'}},
                'section_2': {'signal_word': 'Warning', 'pictograms': ['GHS02'],
                              'hazard_codes': ['H225'], 'precaution_codes': ['P210'],
                              'other_hazards': ''},
                'section_3': {'composition': [{'name': 'ethanol', 'concentration': '100%',
                                               'classification': 'Flam. Liq. 2'}],
                              'note': ''},
                'section_4': {}, 'section_5': {}, 'section_6': {}, 'section_7': {},
                'section_8': {}, 'section_9': {'appearance': 'Clear liquid'},
                'section_10': {}, 'section_11': {}, 'section_12': {},
                'section_13': {}, 'section_14': {}, 'section_15': {},
                'section_16': {'prepared_by': 'SciReagent', 'references': []},
            },
        }
        sds = generate_sds(product_id=self.product.id)
        pdf_path = generate_sds_pdf(sds)
        self.assertTrue(pdf_path.startswith('documents/sds/'))
        self.assertTrue(pdf_path.endswith('.pdf'))

    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_approve_sds_sets_current(self, mock_fetch):
        """approve_sds 设置 Product.current_sds"""
        mock_fetch.return_value = {
            'cid': 702, 'signal_word': 'Warning',
            'pictograms': [], 'hazard_codes': [], 'precaution_codes': [],
            'section_data': {},
        }
        sds = generate_sds(product_id=self.product.id)
        approved = approve_sds(sds.id)
        self.assertIsNotNone(approved.pdf_path)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_sds_id, approved.id)


class COAApiTest(TestCase):
    """COA API 端点测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_coa', password='testpass', email='admin@coa.test',
            is_staff=True,
        )
        self.product = ProductFactory(
            catalog_no='SC8001', name='Test Product',
            cas='123-45-6', formula='C10H12N5O8P3',
            molecular_weight='522.13', storage='-20°C',
        )
        self.sku = SKUFactory(product=self.product, sku_code='SC8001-SKU1')

    def test_create_coa_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/coas/create-coa/', {
            'sku_id': self.sku.id,
            'lot_number': 'SC8001-L2026001',
            'produced_at': '2026-01-15',
        })
        self.assertEqual(response.status_code, 201)

    def test_create_coa_missing_sku(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/coas/create-coa/', {
            'sku_id': 9999,
            'lot_number': 'FAKE-LOT',
            'produced_at': '2026-01-15',
        })
        self.assertEqual(response.status_code, 400)

    def test_list_coas(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/coas/')
        self.assertEqual(response.status_code, 200)
        # EnvelopeRenderer wraps response; data may be list or paginated dict
        data = response.json()['data']
        self.assertIsInstance(data, (list, dict))

    def test_coa_download_without_pdf(self):
        self.client.force_authenticate(user=self.admin)
        coa = create_coa(
            sku_id=self.sku.id,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
        )
        response = self.client.get(f'/api/v1/coas/{coa.id}/download/')
        self.assertEqual(response.status_code, 404)

    def test_coa_approve_and_download(self):
        self.client.force_authenticate(user=self.admin)
        coa = create_coa(
            sku_id=self.sku.id,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
        )
        resp = self.client.post(f'/api/v1/coas/{coa.id}/approve/', {
            'qc_analyst': 'Dr. Wang',
            'qa_approval': 'Dr. Li',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        resp2 = self.client.get(f'/api/v1/coas/{coa.id}/download/')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2['Content-Type'], 'application/pdf')

    def test_update_qc_results(self):
        self.client.force_authenticate(user=self.admin)
        coa = create_coa(
            sku_id=self.sku.id,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
        )
        resp = self.client.put(f'/api/v1/coas/{coa.id}/qc-results/', {
            'appearance_result': 'White powder',
            'purity_result': '99.5%',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['appearance_result'], 'White powder')


class SdsApiTest(TestCase):
    """SDS API 端点测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_sds', password='testpass', email='admin@sds.test',
            is_staff=True,
        )
        self.product = ProductFactory(
            catalog_no='SC8001', name='Test Product',
            cas='64-17-5',
        )

    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_generate_sds_endpoint(self, mock_fetch):
        mock_fetch.return_value = {
            'cid': 702, 'signal_word': 'Warning',
            'pictograms': [], 'hazard_codes': [], 'precaution_codes': [],
            'section_data': {},
        }
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/sds-revisions/generate/', {
            'product_id': self.product.id,
        }, format='json')
        self.assertEqual(response.status_code, 201)

    def test_generate_sds_no_cas(self):
        product = ProductFactory(cas='', catalog_no='SC9999')
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/v1/sds-revisions/generate/', {
            'product_id': product.id,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_list_sds_revisions(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/sds-revisions/')
        self.assertEqual(response.status_code, 200)

    def test_filter_sds_by_product(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/sds-revisions/?product_id={self.product.id}')
        self.assertEqual(response.status_code, 200)
