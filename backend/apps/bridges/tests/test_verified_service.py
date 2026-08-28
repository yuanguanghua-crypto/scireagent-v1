"""
VerifiedService 单元测试（Phase 3 verified 通道，T3.1）。

覆盖：
- 创建 REVIEW 草稿（verified，source_reagent_class=None）
- 部分草稿逐步补全（REVIEW 草稿允许 evidence 不全，用户决策）
- PATCH 补全 evidence（不改状态）
- approve 要求 ACTIVE verified 的 evidence 三件套非空，否则 ValidationError
- approve 置 ACTIVE(verified) + source_reagent_class=None + 记录 curator
- reject 置 REJECTED

依赖 apps.bridges.services.verified_service.VerifiedService（T3.1 实现前本文件 RED）。
"""
import pytest
from django.core.exceptions import ValidationError

from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory
from apps.bridges.models import ProductMethodRelation
from apps.bridges.services.verified_service import VerifiedService

pytestmark = pytest.mark.django_db


def _product():
    return ProductFactory(status='active')


def _method():
    return MethodFactory()


# ── 创建 REVIEW 草稿 ──
def test_create_verified_draft_is_review_verified():
    p = _product()
    m = _method()
    pmr = VerifiedService.create_verified_draft(
        product_id=p.id, method_id=m.id,
        evidence_type='pubmed',
        evidence_reference=[{'type': 'PMID', 'value': '123'}],
        evidence_strength='high', evidence_note='note', curator='u1',
    )
    assert pmr.relation_type == 'verified_applicability'
    assert pmr.status == 'review'
    assert pmr.source_reagent_class is None
    assert pmr.evidence_type == 'pubmed'


# ── 部分草稿逐步补全（用户决策：REVIEW 草稿可不全）──
def test_create_verified_draft_partial_evidence_allowed():
    p = _product()
    m = _method()
    pmr = VerifiedService.create_verified_draft(
        product_id=p.id, method_id=m.id,
        evidence_type='pubmed', evidence_reference=None,
        evidence_strength='', evidence_note='', curator='u1',
    )
    assert pmr.status == 'review'
    assert pmr.evidence_reference is None
    assert pmr.evidence_strength == ''


# ── PATCH 补全 evidence（不改状态）──
def test_patch_verified_completes_evidence_keeps_review():
    p = _product()
    m = _method()
    pmr = VerifiedService.create_verified_draft(
        product_id=p.id, method_id=m.id,
        evidence_type='pubmed', evidence_reference=None,
        evidence_strength='', evidence_note='', curator='u1',
    )
    VerifiedService.patch_verified(
        pmr.id,
        evidence_reference=[{'type': 'PMID', 'value': '999'}],
        evidence_strength='medium',
    )
    pmr.refresh_from_db()
    assert pmr.evidence_reference == [{'type': 'PMID', 'value': '999'}]
    assert pmr.evidence_strength == 'medium'
    assert pmr.status == 'review'


# ── approve 要求 ACTIVE verified 的 evidence 三件套非空 ──
def test_approve_verified_requires_full_evidence():
    p = _product()
    m = _method()
    pmr = VerifiedService.create_verified_draft(
        product_id=p.id, method_id=m.id,
        evidence_type='pubmed', evidence_reference=None,
        evidence_strength='', evidence_note='', curator='u1',
    )
    with pytest.raises(ValidationError):
        VerifiedService.approve_verified(pmr.id, curator='staff1')


def test_approve_verified_sets_active_null_source_rc_records_curator():
    p = _product()
    m = _method()
    pmr = VerifiedService.create_verified_draft(
        product_id=p.id, method_id=m.id,
        evidence_type='pubmed',
        evidence_reference=[{'type': 'PMID', 'value': '123'}],
        evidence_strength='high', evidence_note='', curator='u1',
    )
    VerifiedService.approve_verified(pmr.id, curator='staff1')
    pmr.refresh_from_db()
    assert pmr.status == 'active'
    assert pmr.source_reagent_class is None
    assert pmr.curator == 'staff1'


# ── reject 置 REJECTED ──
def test_reject_verified_sets_rejected():
    p = _product()
    m = _method()
    pmr = VerifiedService.create_verified_draft(
        product_id=p.id, method_id=m.id,
        evidence_type='pubmed',
        evidence_reference=[{'type': 'PMID', 'value': '123'}],
        evidence_strength='high', evidence_note='', curator='u1',
    )
    VerifiedService.reject_verified(pmr.id, curator='staff1', note='not relevant')
    pmr.refresh_from_db()
    assert pmr.status == 'rejected'
