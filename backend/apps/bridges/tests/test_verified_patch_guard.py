"""F1 回归 — PATCH /api/v1/verified/<pk>/ 越权写 + 无状态门。

修复前缺陷（已核实）：
- `VerifiedPatchView` 只有 `IsAuthenticated` ⇒ 任意注册用户可改**任意 id** 的
  verified 证据，而 `ProductMethodRelation.id` 可从公开匿名端点
  `GET /api/v1/products/<pk>/methods/` 枚举出来。
- `VerifiedService.patch_verified()` 只按 `pk + relation_type` 取对象，
  既不校验 status 也不校验调用者；且它不改 `curator` ⇒ 篡改记在原审核人名下，
  审计链被伪造。

本文件钉住修复后的四条契约：
1. 非 staff 登录用户 PATCH → 403（修复前 200）
2. staff PATCH 一个 status=ACTIVE 的 verified → 400 + code=invalid_status，
   且对象 evidence_note 未被改动（从 DB 重取断言）
3. staff PATCH 一个 status=REVIEW 的 → 200，字段确实更新
4. 未登录 → 401/403
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.bridges.models import ProductMethodRelation
from apps.bridges.tests.factories import ProductMethodRelationFactory

User = get_user_model()


class VerifiedPatchGuardTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='curator1', password='x', is_staff=True)
        self.user = User.objects.create_user(
            username='user1', password='x', is_staff=False)

        self.review = ProductMethodRelationFactory(
            status='review', evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '5237404'}],
            evidence_strength='medium', curator='system:miner',
            evidence_note='origin:ai_extracted',
        )
        self.active = ProductMethodRelationFactory(
            status='active', evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '999'}],
            evidence_strength='high', curator='staff1',
            evidence_note='audited|keep-me',
        )

    def _url(self, pmr):
        return f'/api/v1/verified/{pmr.id}/'

    # ── 1. 非 staff 登录用户不得改 ──
    def test_normal_user_patch_forbidden(self):
        self.client.force_authenticate(self.user)
        resp = self.client.patch(
            self._url(self.review), {'evidence_note': 'hijacked'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content[:300])
        # 顺带钉住：越权写没有落地
        self.review.refresh_from_db()
        self.assertNotEqual(self.review.evidence_note, 'hijacked')

    # ── 2. staff 也不得改非 REVIEW（status 门）──
    def test_staff_patch_active_rejected_with_400_and_no_write(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.patch(
            self._url(self.active), {'evidence_note': 'tampered'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content[:300])
        body = resp.json()
        self.assertFalse(body['success'])
        self.assertEqual(body['meta']['error']['code'], 'invalid_status')
        # 关键：内容未被改动（从 DB 重取，不信内存对象）
        fresh = ProductMethodRelation.objects.get(pk=self.active.pk)
        self.assertEqual(fresh.evidence_note, 'audited|keep-me')

    # ── 3. staff 可改 REVIEW 草稿 ──
    def test_staff_patch_review_succeeds_and_updates(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.patch(
            self._url(self.review),
            {'evidence_note': 'filled by curator', 'evidence_strength': 'high'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertTrue(resp.json()['success'])
        fresh = ProductMethodRelation.objects.get(pk=self.review.pk)
        self.assertEqual(fresh.evidence_note, 'filled by curator')
        self.assertEqual(fresh.evidence_strength, 'high')
        self.assertEqual(fresh.status, 'review')  # PATCH 不改状态

    # ── 4. 匿名不得改 ──
    def test_anonymous_patch_denied(self):
        self.client.force_authenticate(None)
        resp = self.client.patch(
            self._url(self.review), {'evidence_note': 'anon'}, format='json')
        self.assertIn(resp.status_code, (401, 403), resp.content[:300])
        fresh = ProductMethodRelation.objects.get(pk=self.review.pk)
        self.assertNotEqual(fresh.evidence_note, 'anon')
