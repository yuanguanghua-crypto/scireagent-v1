"""
B2 测试 — COA approve→PUBLISHED 状态机边界补强。

现有覆盖（test_workflow_api.py）：create→QC→approve 主路径 + API 发布。
本文件补齐状态机边界（GREEN-first 回归护栏）：
  1. 重复 approve 幂等（状态保持 PUBLISHED，无异常）
  2. 越权 approve（非 staff → 403；staff → 200）
  3. withdraw→reapprove 完整环（DRAFT → PUBLISHED → DRAFT → PUBLISHED）
  4. approve 记录 qc_analyst / qa_approval / approved_at
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.documents.models import Coa
from apps.documents.services.workflow import approve_coa, create_coa, withdraw_coa

User = get_user_model()


def _make_coa():
    product = ProductFactory(catalog_no='SC9999', name='Boundary Test',
                             cas='111-22-3')
    sku = SKUFactory(product=product, sku_code='SC9999-SKU1')
    return create_coa(
        sku_id=sku.id,
        lot_number='SC9999-L2026001',
        produced_at=datetime.date(2026, 1, 15),
        retest_at=datetime.date(2027, 1, 15),
    )


class CoaStateMachineBoundaryTests(TestCase):

    def test_duplicate_approve_is_idempotent_keeps_published(self):
        coa = _make_coa()
        first = approve_coa(coa.id, qc_analyst='a1', qa_approval='qa1')
        self.assertEqual(first.status, Coa.Status.PUBLISHED)
        # 重复 approve：不抛异常、状态保持 PUBLISHED
        again = approve_coa(coa.id, qc_analyst='a2', qa_approval='qa2')
        self.assertEqual(again.status, Coa.Status.PUBLISHED)

    def test_withdraw_then_reapprove_full_cycle(self):
        coa = _make_coa()
        approve_coa(coa.id)
        coa.refresh_from_db()
        self.assertEqual(coa.status, Coa.Status.PUBLISHED)
        withdraw_coa(coa.id)
        coa.refresh_from_db()
        self.assertEqual(coa.status, Coa.Status.DRAFT)
        approve_coa(coa.id)
        coa.refresh_from_db()
        self.assertEqual(coa.status, Coa.Status.PUBLISHED)

    def test_approve_records_analyst_fields(self):
        coa = _make_coa()
        approve_coa(coa.id, qc_analyst='qc-wang', qa_approval='qa-li')
        coa.refresh_from_db()
        self.assertEqual(coa.qc_analyst, 'qc-wang')
        self.assertEqual(coa.qa_approval, 'qa-li')
        self.assertIsNotNone(coa.approved_at)


class CoaApprovePermissionTests(APITestCase):

    def setUp(self):
        self.coa = _make_coa()
        self.staff = User.objects.create_user(
            username='coa_staff', password='x', is_staff=True)

    def test_approve_api_rejects_anonymous(self):
        resp = self.client.post(f'/api/v1/coas/{self.coa.id}/approve/')
        self.assertIn(resp.status_code, (401, 403))

    def test_approve_api_rejects_normal_user(self):
        user = User.objects.create_user(username='coa_user', password='x')
        self.client.force_authenticate(user)
        resp = self.client.post(f'/api/v1/coas/{self.coa.id}/approve/')
        self.assertEqual(resp.status_code, 403)

    def test_approve_api_allows_staff(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(f'/api/v1/coas/{self.coa.id}/approve/', {
            'qc_analyst': 'qc', 'qa_approval': 'qa',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.coa.refresh_from_db()
        self.assertEqual(self.coa.status, Coa.Status.PUBLISHED)
