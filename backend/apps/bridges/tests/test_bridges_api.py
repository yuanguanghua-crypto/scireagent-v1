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

    # ── 双 edge 读取（Phase 4 决策：公开读 AllowAny；批次 C T0：仅 ACTIVE verified 公开）──
    def test_get_product_methods_dual_edge_anonymous(self):
        """匿名（公开产品页）可读双 edge；两列表互不混入 + method_name 直出。"""
        from apps.bridges.tests.factories import ProductMethodRelationFactory as PMRFactory
        ProductMethodRelationFactory(  # ACTIVE verified 边（公开可见）
            product=self.product, method=self.method,
            relation_type='verified_applicability', status='active',
            evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '123'}],
            evidence_strength='high',
        )
        self.client.force_authenticate(None)
        resp = self.client.get(f'{self.base}/products/{self.product.id}/methods/')
        assert resp.status_code == 200
        data = resp.json()['data']
        assert 'related_methods' in data
        assert 'verified_methods' in data
        # 两列表互不混入（T4.1 验收）
        for row in data['verified_methods']:
            assert row['relation_type'] == 'verified_applicability'
        assert data['verified_methods'][0]['method_name'] == self.method.name
        assert data['verified_methods'][0]['method_slug'] == self.method.slug

    def test_public_get_hides_review_draft(self):
        """T0 合规：REVIEW 草稿不得出现在公开响应（研究员未审完的草稿不外泄）。"""
        from apps.bridges.tests.factories import ProductMethodRelationFactory as PMRFactory
        ProductMethodRelationFactory(  # REVIEW 草稿（证据不全）
            product=self.product, method=self.method,
            relation_type='verified_applicability', status='review',
            evidence_type='', evidence_reference=None, evidence_strength='',
        )
        self.client.force_authenticate(None)
        resp = self.client.get(f'{self.base}/products/{self.product.id}/methods/')
        assert resp.status_code == 200
        assert resp.json()['data']['verified_methods'] == []

    def test_public_get_hides_rejected(self):
        """T0 合规：REJECTED 不公开。"""
        from apps.bridges.tests.factories import ProductMethodRelationFactory as PMRFactory
        ProductMethodRelationFactory(
            product=self.product, method=self.method,
            relation_type='verified_applicability', status='rejected',
            evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '1'}],
            evidence_strength='high',
        )
        self.client.force_authenticate(None)
        resp = self.client.get(f'{self.base}/products/{self.product.id}/methods/')
        assert resp.json()['data']['verified_methods'] == []

    def test_reverse_hides_review_draft(self):
        """T0 合规：反向端点同样只公开 ACTIVE verified。"""
        from apps.bridges.tests.factories import ProductMethodRelationFactory as PMRFactory
        ProductMethodRelationFactory(  # REVIEW 草稿
            product=self.product, method=self.method,
            relation_type='verified_applicability', status='review',
        )
        self.client.force_authenticate(None)
        resp = self.client.get(f'{self.base}/methods/{self.method.id}/products/')
        assert resp.status_code == 200
        for row in resp.json()['data']['products']:
            assert not (row['relation_type'] == 'verified_applicability'
                        and row['status'] != 'active')

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

    # ── approve 400：evidence 不全不得落半截 ACTIVE（PMR-01 硬约束）──
    def test_approve_verified_incomplete_evidence_returns_400(self):
        """ACTIVE verified 必须 evidence 三件套非空；缺 evidence_reference → 400 且不改状态。"""
        pmr = ProductMethodRelationFactory(
            product=self.product, method=self.method,
            evidence_type='pubmed',
            evidence_reference=None,  # 不完整
            evidence_strength='high',
        )
        self.client.force_authenticate(self.staff)
        resp = self.client.post(f'{self.base}/verified/{pmr.id}/approve/', {}, format='json')
        assert resp.status_code == 400
        assert resp.json()['meta']['error']['code'] == 'validation'
        pmr.refresh_from_db()
        assert pmr.status == 'review'  # 不落半截 ACTIVE

    # ── create 400：重复 product+method 唯一约束冲突 ──
    def test_create_verified_duplicate_returns_400(self):
        """同一 product+method 已存在 verified → 第二次创建 400（code=unique_conflict）。"""
        payload = {
            'product_id': self.product.id, 'method_id': self.method.id,
            'evidence_type': 'pubmed',
            'evidence_reference': [{'type': 'PMID', 'value': '1'}],
            'evidence_strength': 'high',
        }
        self.client.force_authenticate(self.user)
        r1 = self.client.post(f'{self.base}/verified/', payload, format='json')
        assert r1.status_code == 201
        # 第一条已落库（验证用，避免在 400 后的 broken transaction 内再查 DB）
        assert ProductMethodRelation.objects.filter(
            product=self.product, method=self.method,
            relation_type='verified_applicability',
        ).count() == 1
        r2 = self.client.post(f'{self.base}/verified/', payload, format='json')
        assert r2.status_code == 400
        assert r2.json()['meta']['error']['code'] == 'unique_conflict'
