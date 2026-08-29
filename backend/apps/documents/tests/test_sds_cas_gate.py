"""
B1 测试 — SDS CAS 合规软闸门（TECH-P0-3，上线合规闸门）。

设计（2026-08-29 实测依据 + 铁律 5）：
- active 产品仅 62/105 有 CAS（41% 无 CAS）→ 硬阻断会让近半产品 SDS 永远无法发布，
  不可行；且架构铁律 5「研究员是最终权威，发布检查=告知非硬阻断」。
- 因此 B1 = 软闸门：approve_sds 不阻断发布，但返回 compliance 警告
  （无 CAS → compliant=False, reason='no_cas'），API 响应携带供前端展示。
"""
from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.commerce.tests.factories import ProductFactory
from apps.documents.models import SdsRevision
from apps.documents.services.workflow import approve_sds

User = get_user_model()


def _make_sds(product, confidence=SdsRevision.DataConfidence.VERY_LOW):
    return SdsRevision.objects.create(
        product=product,
        revision_no=1,
        revised_at=date(2026, 8, 29),
        signal_word='Warning',
        data_confidence=confidence,
        data_source_detail='test',
    )


class SdsCasGateServiceTests(APITestCase):

    def test_approve_sds_without_cas_returns_non_compliant(self):
        product = ProductFactory(status='active', cas='')
        sds = _make_sds(product)
        _, compliance = approve_sds(sds.id)
        self.assertFalse(compliance['compliant'])
        self.assertEqual(compliance['reason'], 'no_cas')

    def test_approve_sds_with_cas_returns_compliant(self):
        product = ProductFactory(status='active', cas='73449-06-6')
        sds = _make_sds(product)
        _, compliance = approve_sds(sds.id)
        self.assertTrue(compliance['compliant'])

    def test_soft_gate_still_publishes_casless_sds(self):
        """软闸门：无 CAS 不阻断发布（铁律 5：告知非硬阻断）。"""
        product = ProductFactory(status='active', cas='')
        sds = _make_sds(product)
        sds, compliance = approve_sds(sds.id)
        product.refresh_from_db()
        self.assertEqual(product.current_sds_id, sds.id)
        self.assertFalse(compliance['compliant'])


class SdsCasGateApiTests(APITestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            username='qa_staff', password='x', is_staff=True,
        )
        self.client.force_authenticate(self.staff)

    def test_approve_api_returns_compliance_warning_for_casless(self):
        product = ProductFactory(status='active', cas='')
        sds = _make_sds(product)
        resp = self.client.post(f'/api/v1/sds-revisions/{sds.id}/approve/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        compliance = data.get('compliance')
        self.assertIsNotNone(compliance)
        self.assertFalse(compliance['compliant'])
        self.assertEqual(compliance['reason'], 'no_cas')

    def test_approve_api_compliant_when_cas_present(self):
        product = ProductFactory(status='active', cas='73449-06-6')
        sds = _make_sds(product)
        resp = self.client.post(f'/api/v1/sds-revisions/{sds.id}/approve/')
        self.assertEqual(resp.status_code, 200)
        compliance = resp.json()['data']['compliance']
        self.assertTrue(compliance['compliant'])
