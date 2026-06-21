"""Word 解析 API 和服务层测试。

TDD: 先写测试，再实现功能。
"""
import os
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from rest_framework import status
from rest_framework.test import APIClient

from apps.commerce.services.word_parser import (
    WordParserService, FileUnreadableError, FileTooLargeError,
)
from apps.accounts.tests.factories import UserFactory

# ── Test Word content ────────────────────────────────────────

def _build_minimal_docx_bytes(text_lines):
    """用 python-docx 构造一个最小 .docx 用于测试。"""
    from docx import Document as DocxDocument
    doc = DocxDocument()
    for line in text_lines:
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


WORD_MINIMAL = _build_minimal_docx_bytes([
    '5-Propargylamino-CTP',
    'This is a chemically modified cytidine triphosphate.',
    'Synonyms: 5-Propargylamino-cytidine-5\'-triphosphate',
    'CAS Number: 150718-26-6',
    'Catalog Number: SC8001',
    'Formula: C12H19N4O14P3 (free acid)',
    'Molecular Weight: 536.01 g/mol (free acid)',
    'Purity: ≥ 95% (HPLC)',
    'Concentration: 100 mM',
    'Storage: stored at -20°C',
    'Shipping Condition: Shipped with Blue Ice',
    'Size: 10ul (100 mM)/ 50ul (100 mM)/ 100ul (100 mM)',
    'Price: $79/$349/$649',
])

WORD_NO_CAS = _build_minimal_docx_bytes([
    'Biotin-11-UTP',
    'Biotin-11-UTP is a Biotin-labeled uridine triphosphate.',
    'Synonyms: Biotin-11-uridine-5\'-triphosphate.',
    'Catalog Number: SC8014',
    'Formula: C28H45N6O18P3S (free acid)',
    'Molecular Weight: 878.7 g/mol (free acid)',
    'Purity: ≥ 95% (HPLC)',
    'Concentration: 10 mM',
    'Storage: stored at -20°C',
    'Shipping Condition: Shipped with Blue Ice',
    'Size: 10ul (10 mM)/50ul (10 mM)',
    'Price: $79/$269',
])

WORD_SINGLE_SKU = _build_minimal_docx_bytes([
    'Single-SKU Product',
    'Synonyms: test-synonym.',
    'Catalog Number: SC9999',
    'Formula: C10H20N5O10P3 (free acid)',
    'Concentration: 1 mM',
    'Storage: stored at -20°C',
    'Shipping Condition: Ambient',
    'Size: 50ul (1 mM)',
    'Price: $199',
])

WORD_EMPTY_DESCRIPTION = _build_minimal_docx_bytes([
    'No-Description Product',
    'Catalog Number: SC9998',
    'Synonyms: brief-synonym.',
    'Formula: C5H10O5',
    'Concentration: 100 mM',
    'Storage: stored at -20°C',
    'Shipping Condition: Shipped with Blue Ice',
    'Size: 10ul (100 mM)',
    'Price: $89',
])

WORD_ZERO_FIELDS = _build_minimal_docx_bytes([])

# ── Unit Tests ────────────────────────────────────────────────

class WordParserServiceTest(TestCase):
    """Word 解析 service 单元测试"""

    def setUp(self):
        self.service = WordParserService()

    def _make_uploaded_file(self, content, name='test.docx'):
        return SimpleUploadedFile(name, content,
                                  content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    def test_parse_valid_docx_extracts_all_fields(self):
        """上传标准 Word → 提取所有字段"""
        file = self._make_uploaded_file(WORD_MINIMAL)
        result = self.service.parse(file)

        self.assertGreater(result['fields_found'], 8)
        self.assertEqual(result['product_name'], '5-Propargylamino-CTP')
        self.assertEqual(result['cas'], '150718-26-6')
        self.assertEqual(result['catalog_number'], 'SC8001')
        self.assertEqual(result['formula'], 'C12H19N4O14P3 (free acid)')
        self.assertEqual(result['molecular_weight'], '536.01 g/mol (free acid)')
        self.assertEqual(result['purity'], '≥ 95% (HPLC)')
        self.assertEqual(result['concentration'], '100 mM')
        self.assertEqual(result['storage'], 'stored at -20°C')
        self.assertEqual(result['shipping'], 'Shipped with Blue Ice')
        self.assertIn('chemically modified', result.get('description', ''))

    def test_parse_docx_without_cas(self):
        """CAS 缺失的文档 → CAS 为 None，其他字段正常"""
        file = self._make_uploaded_file(WORD_NO_CAS)
        result = self.service.parse(file)

        self.assertNotIn('cas', result)
        self.assertEqual(result['product_name'], 'Biotin-11-UTP')
        self.assertEqual(result['catalog_number'], 'SC8014')
        self.assertEqual(result['purity'], '≥ 95% (HPLC)')
        self.assertEqual(result['concentration'], '10 mM')

    def test_parse_docx_skus_size_price_pairing(self):
        """Size 和 Price 按 / 分割后按位置正确配对"""
        file = self._make_uploaded_file(WORD_MINIMAL)
        result = self.service.parse(file)

        skus = result['skus']
        self.assertEqual(len(skus), 3)
        self.assertEqual(skus[0], {'pack_size': '10ul (100 mM)', 'price': '79'})
        self.assertEqual(skus[1], {'pack_size': '50ul (100 mM)', 'price': '349'})
        self.assertEqual(skus[2], {'pack_size': '100ul (100 mM)', 'price': '649'})

    def test_parse_docx_single_sku(self):
        """单 SKU 产品"""
        file = self._make_uploaded_file(WORD_SINGLE_SKU)
        result = self.service.parse(file)

        skus = result['skus']
        self.assertEqual(len(skus), 1)
        self.assertEqual(skus[0], {'pack_size': '50ul (1 mM)', 'price': '199'})

    def test_parse_docx_empty_description(self):
        """无描述段的文档 — description 为空或不存在"""
        file = self._make_uploaded_file(WORD_EMPTY_DESCRIPTION)
        result = self.service.parse(file)

        self.assertEqual(result['product_name'], 'No-Description Product')
        # No description paragraphs
        self.assertNotIn('description', result)

    def test_parse_docx_invalid_extension_raises(self):
        """非 .docx 文件 → ValidationError"""
        from django.core.exceptions import ValidationError
        file = self._make_uploaded_file(WORD_MINIMAL, name='test.pdf')

        with self.assertRaises(ValidationError):
            self.service.parse(file)

    def test_parse_zero_fields_returns_fields_found_zero(self):
        """空文档 → fields_found=0，skus=[]"""
        file = self._make_uploaded_file(WORD_ZERO_FIELDS)
        result = self.service.parse(file)

        self.assertEqual(result['fields_found'], 0)
        self.assertEqual(result['skus'], [])


# ── API Tests ────────────────────────────────────────────────

class WordParseAPITest(TestCase):
    """Word 解析 API 端点测试"""

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/products/parse-word/'

    def test_parse_word_requires_auth(self):
        """匿名用户 → 401 或 403"""
        file = SimpleUploadedFile('test.docx', WORD_MINIMAL,
                                  content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        resp = self.client.post(self.url, {'file': file})
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_parse_word_requires_staff(self):
        """非 staff 用户 → 403"""
        user = UserFactory(is_staff=False)
        self.client.force_authenticate(user=user)
        file = SimpleUploadedFile('test.docx', WORD_MINIMAL,
                                  content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        resp = self.client.post(self.url, {'file': file})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_parse_word_staff_success(self):
        """Staff 用户正常解析"""
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)
        file = SimpleUploadedFile('test.docx', WORD_MINIMAL,
                                  content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        resp = self.client.post(self.url, {'file': file})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('fields_found', data['data'])
        self.assertEqual(data['data']['product_name'], '5-Propargylamino-CTP')

    def test_parse_word_no_file_returns_400(self):
        """未上传文件 → 400"""
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parse_word_invalid_format_returns_400(self):
        """非 .docx 文件 → 400"""
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)
        file = SimpleUploadedFile('test.pdf', b'not a docx',
                                  content_type='application/pdf')
        resp = self.client.post(self.url, {'file': file})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.json()
        error_code = data.get('meta', {}).get('error', {}).get('code', '')
        self.assertIn('UNSUPPORTED_FORMAT', error_code)

    def test_parse_word_zero_fields_returns_200(self):
        """0 字段提取 → 200 + fields_found=0"""
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)
        file = SimpleUploadedFile('test.docx', WORD_ZERO_FIELDS,
                                  content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        resp = self.client.post(self.url, {'file': file})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data['data']['fields_found'], 0)
        self.assertEqual(data['data']['skus'], [])
