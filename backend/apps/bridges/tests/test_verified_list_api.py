"""
C3 测试 — workspace verified 审核列表（GET /api/v1/verified/）。

验收：IsStaffUser 才可见；返回全状态 verified（REVIEW 草稿 + ACTIVE）；
含 method_name/product_name/catalog_no；支持 status/product_id 过滤。
公开端（匿名/普通用户）403。
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.bridges.models import ProductMethodRelation
from apps.bridges.tests.factories import ProductMethodRelationFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory

User = get_user_model()


class VerifiedListApiTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='curator1', password='x', is_staff=True)
        self.user = User.objects.create_user(
            username='user1', password='x', is_staff=False)
        self.product = ProductFactory(name='5-Iodo-dUTP', catalog_no='SC8023',
                                      status='active')
        self.method_review = MethodFactory(name='DNA Polymerase')
        self.method_active = MethodFactory(name='PCR')
        self.review = ProductMethodRelationFactory(
            product=self.product, method=self.method_review, status='review',
            evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '5237404'}],
            evidence_strength='medium', curator='system:miner',
            evidence_note='origin:ai_extracted|miner_v0.1|PubMed\nrelevance:pass')
        self.active = ProductMethodRelationFactory(
            product=self.product, method=self.method_active,
            status='active', evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '999'}],
            evidence_strength='high', curator='staff1')
        self.base = '/api/v1/verified'

    # ── 权限 ──
    def test_anonymous_gets_403(self):
        self.client.force_authenticate(None)
        resp = self.client.get(self.base + '/')
        self.assertIn(resp.status_code, (401, 403))  # 未认证 → 401，已认证非 staff → 403

    def test_normal_user_gets_403(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(self.base + '/')
        self.assertEqual(resp.status_code, 403)

    def test_staff_sees_all_statuses(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get(self.base + '/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()['data']
        statuses = {r['status'] for r in rows}
        self.assertIn('review', statuses)
        self.assertIn('active', statuses)

    # ── 字段 ──
    def test_rows_include_product_and_method_info(self):
        self.client.force_authenticate(self.staff)
        rows = self.client.get(self.base + '/').json()['data']
        row = next(r for r in rows if r['id'] == self.review.id)
        self.assertEqual(row['method_name'], self.method_review.name)
        self.assertEqual(row['product_name'], self.product.name)
        self.assertEqual(row['product_catalog_no'], 'SC8023')
        self.assertEqual(row['curator'], 'system:miner')
        self.assertIn('created_at', row)

    # ── 过滤 ──
    def test_status_filter(self):
        self.client.force_authenticate(self.staff)
        rows = self.client.get(self.base + '/', {'status': 'review'}).json()['data']
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r['status'], 'review')

    def test_product_id_filter(self):
        self.client.force_authenticate(self.staff)
        other = ProductMethodRelationFactory(
            product=ProductFactory(name='Other', status='active'),
            method=MethodFactory(name='PCR'), status='review')
        rows = self.client.get(self.base + '/',
                               {'product_id': self.product.id}).json()['data']
        self.assertIn(self.review.id, {r['id'] for r in rows})
        self.assertNotIn(other.id, {r['id'] for r in rows})
