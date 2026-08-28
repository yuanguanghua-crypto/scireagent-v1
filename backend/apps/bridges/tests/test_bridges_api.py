"""
bridges API 单元测试（Phase 3 verified 通道 + 双 edge，T3.2）。

覆盖六端点 + 权限：
- GET  products/{id}/methods  → 双 edge 分离（related_methods / verified_methods）
- GET  methods/{id}/products  → 反向
- POST verified               → 登录用户可建 REVIEW 草稿
- PATCH verified/{id}          → 登录用户可补 evidence
- POST verified/{id}/approve   → 仅 IsStaffUser
- POST verified/{id}/reject    → 仅 IsStaffUser

bridges API 挂载于 api/v1/（同 commerce），端点直接位于 api/v1/ 下。
T3.2 实现前本文件 RED（视图/路由/序列化器不存在）。
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory
from apps.bridges.models import ProductMethodRelation
from apps.bridges.tests.factories import ProductMethodRelationFactory

User = get_user_model()


class BridgesApiTestCase(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff1', password='x', is_staff=True, is_superuser=False,
        )
        self.user = User.objects.create_user(
            username='user1', password='x', is_staff=False,
        )
        self.product = ProductFactory(status='active')
        self.method = MethodFactory()
        # bridges API 挂载于 api/v1/（同 commerce），端点直接位于 api/v1/ 下
        self.base = '/api/v1'

    # ── 双 edge 读取 ──
    def test_get_product_methods_dual_edge(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get(f'{self.base}/products/{self.product.id}/methods/')
        assert resp.status_code == 200
        data = resp.json()['data']
        assert 'related_methods' in data
        assert 'verified_methods' in data

    def test_get_method_products_reverse(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get(f'{self.base}/methods/{self.method.id}/products/')
        assert resp.status_code == 200
        data = resp.json()['data']
        assert 'products' in data

    # ── 创建 verified 草稿：权限 ──
    def test_create_verified_requires_auth(self):
        self.client.force_authenticate(None)
        resp = self.client.post(f'{self.base}/verified/', {
            'product_id': self.product.id, 'method_id': self.method.id,
            'evidence_type': 'pubmed',
            'evidence_reference': [{'type': 'PMID', 'value': '1'}],
            'evidence_strength': 'high',
        }, format='json')
        assert resp.status_code in (401, 403)

    def test_create_verified_as_authenticated_user(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(f'{self.base}/verified/', {
            'product_id': self.product.id, 'method_id': self.method.id,
            'evidence_type': 'pubmed',
            'evidence_reference': [{'type': 'PMID', 'value': '1'}],
            'evidence_strength': 'high',
        }, format='json')
        assert resp.status_code == 201
        assert ProductMethodRelation.objects.filter(
            product=self.product, method=self.method,
            relation_type='verified_applicability', status='review',
        ).exists()

    # ── PATCH 补 evidence：登录用户可 ──
    def test_patch_verified_as_authenticated_user(self):
        pmr = ProductMethodRelationFactory(
            product=self.product, method=self.method,
            evidence_type='pubmed', evidence_reference=None,
            evidence_strength='', evidence_note='',
        )
        self.client.force_authenticate(self.user)
        resp = self.client.patch(f'{self.base}/verified/{pmr.id}/', {
            'evidence_reference': [{'type': 'PMID', 'value': '2'}],
            'evidence_strength': 'medium',
        }, format='json')
        assert resp.status_code == 200
        pmr.refresh_from_db()
        assert pmr.evidence_reference == [{'type': 'PMID', 'value': '2'}]

    # ── approve：仅 IsStaffUser ──
    def test_approve_verified_requires_staff(self):
        pmr = ProductMethodRelationFactory(
            product=self.product, method=self.method,
            evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '1'}],
            evidence_strength='high',
        )
        self.client.force_authenticate(self.user)
        resp = self.client.post(f'{self.base}/verified/{pmr.id}/approve/', {}, format='json')
        assert resp.status_code == 403

    def test_approve_verified_as_staff(self):
        pmr = ProductMethodRelationFactory(
            product=self.product, method=self.method,
            evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '1'}],
            evidence_strength='high',
        )
        self.client.force_authenticate(self.staff)
        resp = self.client.post(f'{self.base}/verified/{pmr.id}/approve/', {}, format='json')
        assert resp.status_code == 200
        pmr.refresh_from_db()
        assert pmr.status == 'active'
        assert pmr.curator == 'staff1'

    # ── reject：仅 IsStaffUser ──
    def test_reject_verified_requires_staff(self):
        pmr = ProductMethodRelationFactory(
            product=self.product, method=self.method,
            evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '1'}],
            evidence_strength='high',
        )
        self.client.force_authenticate(self.user)
        resp = self.client.post(f'{self.base}/verified/{pmr.id}/reject/', {}, format='json')
        assert resp.status_code == 403

    def test_reject_verified_as_staff(self):
        pmr = ProductMethodRelationFactory(
            product=self.product, method=self.method,
            evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '1'}],
            evidence_strength='high',
        )
        self.client.force_authenticate(self.staff)
        resp = self.client.post(f'{self.base}/verified/{pmr.id}/reject/', {}, format='json')
        assert resp.status_code == 200
        pmr.refresh_from_db()
        assert pmr.status == 'rejected'
