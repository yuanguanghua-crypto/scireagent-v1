"""批量 enrich 的 `found` 必须有实义（A-173，2026-11-27）。

## 改前
`/api/v1/products/enrich-from-pubchem/` 批量模式把 `found` 原样传出，而"多候选"
分支（`confidence='multiple'`）同样返回 `found=True` 却**不带 properties**
⇒ 响应成了 `{found: true, cid: null, formula: '', molecular_weight: 0}`。

QA 实测（Batch 15）：
    POST {product_ids:[5456], cas:'63-39-2'} → 200
    data.enriched = {found: true, cid: null, cas: '63-39-2',
                     smiles: '', formula: '', molecular_weight: 0, xlogp: null, tpsa: null}

调用方看到"找到了"却拿不到任何字段 —— 这是**假 found**，与 A-055/A-053 同一类病
（把"没有确定结果"渲染成"有结果"）。

## 本文件钉三条
① 多候选 ⇒ `found=false` + `status='multiple_candidates'` + `candidates_count`；
② 真取到属性 ⇒ `found=true` + `status='verified'` + cid 能从 properties 兜底带出；
③ 未找到 ⇒ `status='not_found'`。
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory

URL = '/api/v1/products/enrich-from-pubchem/'


class BatchEnrichFoundSemanticsTest(TestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.product = ProductFactory()

    def _post(self, mocked_return):
        with patch(
            'apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties',
            return_value=mocked_return,
        ):
            r = self.client.post(URL, {'product_ids': [self.product.id], 'cas': '63-39-2'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()['data'][0]['enriched']

    def test_multiple_candidates_is_not_found(self):
        e = self._post({
            'found': True, 'requires_review': True, 'confidence': 'multiple',
            'candidates': [{'cid': 1}, {'cid': 2}],
            'properties': {},
        })
        self.assertFalse(e['found'], '★ 多候选不能算"找到了"，否则字段全空却报 found=true')
        self.assertEqual(e['status'], 'multiple_candidates')
        self.assertEqual(e['candidates_count'], 2)
        self.assertTrue(e['raw_found'], '原始 found 仍如实保留，便于排障')
        self.assertTrue(e['requires_review'])

    def test_verified_result_is_found_and_carries_cid(self):
        e = self._post({
            'found': True, 'identity_verified': True,
            'properties': {
                'cid': 1175, 'canonical_smiles': 'C1=NC=NC2=C1N=CN2',
                'molecular_formula': 'C5H5N5', 'molecular_weight': 135.13,
            },
        })
        self.assertTrue(e['found'])
        self.assertEqual(e['status'], 'verified')
        self.assertEqual(e['cid'], 1175, 'cid 必须能从 properties 兜底带出（顶层常常没有）')
        self.assertEqual(e['formula'], 'C5H5N5')

    def test_not_found(self):
        e = self._post({'found': False, 'properties': {}, 'candidates': []})
        self.assertFalse(e['found'])
        self.assertEqual(e['status'], 'not_found')
        self.assertEqual(e['candidates_count'], 0)
