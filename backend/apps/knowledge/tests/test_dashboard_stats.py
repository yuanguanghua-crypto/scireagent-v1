"""P1-4 健康看板：DashboardStatsView 治理指标。

覆盖 6 个新增治理字段：
verified_review / verified_active / verified_rejected（策展通道状态分布）、
canonical_methods（canonical Method 收敛）、
protocol_steps_coverage（已发布协议步骤覆盖率）、
hanging_protocols（已发布但无 MethodProtocol 关联的悬空协议）。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.tests.factories import (
    MethodFactory, ProtocolFactory, ProtocolStepFactory,
)
from apps.bridges.tests.factories import ProductMethodRelationFactory


class DashboardGovernanceStatsTest(TestCase):
    """GET /api/v1/admin/dashboard-stats/ 治理指标。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.staff)

    def _stats(self):
        resp = self.client.get('/api/v1/admin/dashboard-stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return resp.json()['data']

    def test_governance_fields_present_and_non_negative(self):
        data = self._stats()
        for key in ('verified_review', 'verified_active', 'verified_rejected',
                    'canonical_methods', 'protocol_steps_coverage', 'hanging_protocols'):
            self.assertIn(key, data)
            self.assertIsInstance(data[key], int)
            self.assertGreaterEqual(data[key], 0)

    def test_counts_reflect_seeded_governance_data(self):
        # canonical Method：application=None + status='active'
        MethodFactory(application=None, status='active')
        # verified 审核草稿：工厂默认 verified_applicability + review
        ProductMethodRelationFactory()
        # 已发布协议 + 步骤（有步骤、无 MethodProtocol 关联
        # → 既计入步骤覆盖率也计入悬空协议）
        proto = ProtocolFactory(status='published')
        ProtocolStepFactory(protocol=proto)

        data = self._stats()
        self.assertEqual(data['canonical_methods'], 1)
        self.assertEqual(data['verified_review'], 1)
        self.assertEqual(data['protocol_steps_coverage'], 100)
        self.assertEqual(data['hanging_protocols'], 1)
