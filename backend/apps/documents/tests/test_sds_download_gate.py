"""B10 — SDS 下载发布状态门控（COA B9 的 SDS 侧对称补齐）。

漏洞：`SdsRevisionViewSet.download`（views.py:212-225）修前**只判 pdf_path 空不空**，
无任何发布状态门控；而 `withdraw_sds`（workflow.py:325-336）**只清 Product.current_sds
指针、刻意保留 PDF** ⇒ 已撤回的 SDS PDF 仍可**匿名**下载（本 ViewSet 的
`IsAdminOrReadOnly` 放行匿名 GET），违反 `docs/COA_SDS_PRD.md:80`
「仅 status=PUBLISHED 允许下载」。

对齐目标：COA 侧同款门控（views.py:127-143，2026-09-22 修 B9）——
**对外（匿名/普通用户）一律 404；staff 仍可下载**（内部复核与审计留痕，
故不删 PDF、只加门控）。本文件锁死该口径。

⚠️ 本文件刻意只锁「门控行为」，不锁 migration 实现细节。
"""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.tests.factories import ProductFactory
from apps.documents.models import SdsRevision
from apps.documents.services.workflow import approve_sds, generate_sds, withdraw_sds

User = get_user_model()


PUBCHEM_HIT = {
    'cid': 702,
    'signal_word': 'Warning',
    'pictograms': ['GHS02'],
    'hazard_codes': ['H225'],
    'precaution_codes': ['P210'],
    'section_data': {},
}


def _make_approved_sds(catalog_no, cas='64-17-5'):
    """生成并审批一版 SDS ⇒ 有真实 PDF + current_sds 指向它（= 已发布）。"""
    product = ProductFactory(catalog_no=catalog_no, name='Gate Test', cas=cas)
    with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m:
        m.return_value = PUBCHEM_HIT
        sds = generate_sds(product_id=product.id)
    approve_sds(sds.id)
    sds.refresh_from_db()
    return product, sds


class SdsDownloadGateTests(TestCase):
    """★ 核心：匿名下载未发布（撤回/草稿）SDS 必须 404。"""

    def setUp(self):
        self.client = APIClient()

    # ── 漏洞本体：撤回后匿名仍可下载 ──────────────────
    def test_anon_download_withdrawn_sds_returns_404(self):
        """approve → withdraw 后，匿名 GET download 必须 404（修前返回 200 + PDF）。"""
        product, sds = _make_approved_sds('SC9101')
        self.assertTrue(sds.pdf_path)  # 前置：PDF 确实存在（否则测不到门控）

        withdraw_sds(sds.id)
        sds.refresh_from_db()
        # PDF 文件仍在磁盘上（withdraw 不删文件）—— 这正是漏洞成立的前提
        self.assertTrue(sds.pdf_path)

        resp = self.client.get(f'/api/v1/sds-revisions/{sds.id}/download/')
        self.assertEqual(resp.status_code, 404)

    def test_anon_download_draft_sds_returns_404(self):
        """未审批（草稿）SDS 无 PDF → 404（既有行为，防回归）。"""
        product = ProductFactory(catalog_no='SC9102', name='Draft Only', cas='64-17-5')
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m:
            m.return_value = PUBCHEM_HIT
            sds = generate_sds(product_id=product.id)
        self.assertEqual(sds.pdf_path, '')

        resp = self.client.get(f'/api/v1/sds-revisions/{sds.id}/download/')
        self.assertEqual(resp.status_code, 404)

    # ── 不能把门做死：已发布 SDS 匿名必须仍能下 ──────
    def test_anon_download_published_sds_returns_200(self):
        """已审批发布的 SDS 匿名可下载 200 + application/pdf（PRD P0-5 硬要求）。"""
        product, sds = _make_approved_sds('SC9103')
        resp = self.client.get(f'/api/v1/sds-revisions/{sds.id}/download/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    # ── staff 例外：内部审计仍可下载（与 COA 同口径）──
    def test_staff_can_download_withdrawn_sds(self):
        """撤回后 staff 仍可下载（内部复核/审计留痕），故 PDF 不删、只加门控。"""
        staff = User.objects.create_user(
            username='sds_gate_staff', password='x', is_staff=True)
        product, sds = _make_approved_sds('SC9104')
        withdraw_sds(sds.id)

        self.client.force_authenticate(staff)
        resp = self.client.get(f'/api/v1/sds-revisions/{sds.id}/download/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_normal_user_cannot_download_withdrawn_sds(self):
        """普通已认证用户（非 staff）同样应 404 —— 门控不是只挡匿名。"""
        user = User.objects.create_user(username='sds_gate_plain', password='x')
        product, sds = _make_approved_sds('SC9105')
        withdraw_sds(sds.id)

        self.client.force_authenticate(user)
        resp = self.client.get(f'/api/v1/sds-revisions/{sds.id}/download/')
        self.assertEqual(resp.status_code, 404)


class SdsStatusStateMachineTests(TestCase):
    """SDS 发布状态机：draft →(approve) published →(withdraw) draft。"""

    def setUp(self):
        self.product = ProductFactory(catalog_no='SC9201', name='StateMachine', cas='64-17-5')
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m:
            m.return_value = PUBCHEM_HIT
            self.sds = generate_sds(product_id=self.product.id)

    def test_new_revision_is_draft(self):
        self.assertEqual(self.sds.status, SdsRevision.Status.DRAFT)

    def test_approve_sets_published(self):
        approve_sds(self.sds.id)
        self.sds.refresh_from_db()
        self.assertEqual(self.sds.status, SdsRevision.Status.PUBLISHED)

    def test_withdraw_reverts_to_draft(self):
        approve_sds(self.sds.id)
        withdraw_sds(self.sds.id)
        self.sds.refresh_from_db()
        self.assertEqual(self.sds.status, SdsRevision.Status.DRAFT)

    def test_withdraw_keeps_pdf_and_reapprove_full_cycle(self):
        """withdraw→reapprove 完整环：PDF 保留、状态可回到 published。"""
        approve_sds(self.sds.id)
        withdraw_sds(self.sds.id)
        sds2, _compliance = approve_sds(self.sds.id)
        sds2.refresh_from_db()
        self.assertEqual(sds2.status, SdsRevision.Status.PUBLISHED)
        self.assertTrue(sds2.pdf_path)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_sds_id, self.sds.id)

    def test_withdraw_of_superseded_revision_does_not_touch_pointer(self):
        """撤回非当前版本（指针指向别版）⇒ 指针不动，但该版自身状态回 draft。"""
        approve_sds(self.sds.id)
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m:
            m.return_value = PUBCHEM_HIT
            newer = generate_sds(product_id=self.product.id)
        approve_sds(newer.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_sds_id, newer.id)

        withdraw_sds(self.sds.id)  # 撤回历史版本 v1
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_sds_id, newer.id)  # 指针未被误清
        self.sds.refresh_from_db()
        self.assertEqual(self.sds.status, SdsRevision.Status.DRAFT)