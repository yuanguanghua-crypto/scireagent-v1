"""verified（已验证适用）通道服务（Phase 3，T3.1）。

设计依据：方案 v0.2 §6/§7/§8 + 用户决策（部分草稿逐步补全）。

职责与铁律：
- verified 完全独立于 derived，**不受 MUST-15 Method allow-list 限制**（研究员显式确认即事实）。
- 本服务是 verified 通道唯一的 PMR 写入口；API 层只编排本服务，**不直接 ORM 改 PMR**。
- PMR-01（放宽后）：仅 status=ACTIVE 的 verified 强约束 source_reagent_class=NULL
  + evidence 三件套非空；REVIEW/REJECTED 草稿允许 evidence 不全。
- approve 写 source_reagent_class=NULL（PMR-01 硬约束）+ 记录 curator；
  evidence 不全时 approve 抛 ValidationError（不落半截 ACTIVE）。
"""
import logging

from django.core.exceptions import ValidationError

from apps.bridges.models import ProductMethodRelation

logger = logging.getLogger("association_pipeline")

# PATCH 哨兵：区分"未提供"与"显式置空"
_NOT_PROVIDED = object()


def _validate_full_evidence(evidence_type, evidence_reference, evidence_strength):
    """ACTIVE verified 必须有完整 evidence 三件套（非空）。"""
    if not evidence_type or not str(evidence_type).strip():
        raise ValidationError("ACTIVE verified 必须提供 evidence_type")
    # [] 视为缺失（结构由 evidence_reference 字段 validator 把关，此处只判"有内容"）
    if not evidence_reference:
        raise ValidationError("ACTIVE verified 必须提供 evidence_reference")
    if not evidence_strength or not str(evidence_strength).strip():
        raise ValidationError("ACTIVE verified 必须提供 evidence_strength")


class VerifiedService:
    """verified 通道服务（全部为静态方法，便于 API 编排与批量）。"""

    @staticmethod
    def create_verified_draft(*, product_id, method_id, evidence_type="",
                              evidence_reference=None, evidence_strength="",
                              evidence_note="", curator=""):
        """创建 verified REVIEW 草稿（允许 evidence 不全，用户决策：部分草稿逐步补全）。"""
        pmr = ProductMethodRelation.objects.create(
            product_id=product_id,
            method_id=method_id,
            relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY,
            source_reagent_class=None,  # PMR-01：verified 必须 NULL
            status=ProductMethodRelation.Status.REVIEW,
            evidence_type=evidence_type or "",
            evidence_reference=evidence_reference,
            evidence_strength=evidence_strength or "",
            evidence_note=evidence_note or "",
            curator=curator or "",
        )
        logger.info(
            "verified draft created pmr=%s product=%s method=%s curator=%s",
            pmr.id, product_id, method_id, curator,
        )
        return pmr

    @staticmethod
    def patch_verified(pmr_id, *, evidence_type=_NOT_PROVIDED,
                       evidence_reference=_NOT_PROVIDED,
                       evidence_strength=_NOT_PROVIDED,
                       evidence_note=_NOT_PROVIDED):
        """PATCH 补全 evidence（不改状态；REVIEW 草稿可部分更新）。
        仅更新调用方实际提供的字段（含显式置空）。
        """
        pmr = ProductMethodRelation.objects.get(
            pk=pmr_id,
            relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY,
        )
        changed = []
        if evidence_type is not _NOT_PROVIDED:
            pmr.evidence_type = evidence_type
            changed.append("evidence_type")
        if evidence_reference is not _NOT_PROVIDED:
            pmr.evidence_reference = evidence_reference
            changed.append("evidence_reference")
        if evidence_strength is not _NOT_PROVIDED:
            pmr.evidence_strength = evidence_strength
            changed.append("evidence_strength")
        if evidence_note is not _NOT_PROVIDED:
            pmr.evidence_note = evidence_note
            changed.append("evidence_note")
        if changed:
            pmr.save(update_fields=changed)
        return pmr

    @staticmethod
    def approve_verified(pmr_id, *, curator):
        """approve：置 ACTIVE(verified) + source_reagent_class=NULL + 记录 curator。
        evidence 不全 → ValidationError（不落半截 ACTIVE，PMR-01 不被破坏）。
        """
        pmr = ProductMethodRelation.objects.get(
            pk=pmr_id,
            relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY,
        )
        _validate_full_evidence(
            pmr.evidence_type, pmr.evidence_reference, pmr.evidence_strength,
        )
        pmr.status = ProductMethodRelation.Status.ACTIVE
        pmr.source_reagent_class = None  # 防御性：PMR-01 硬约束
        pmr.curator = curator or pmr.curator
        pmr.save(update_fields=["status", "source_reagent_class", "curator"])
        logger.info("verified approved pmr=%s curator=%s", pmr.id, curator)
        return pmr

    @staticmethod
    def reject_verified(pmr_id, *, curator="", note=""):
        """reject：置 REJECTED（草稿可不全；REJECTED 豁免 PMR-01 分支 2）。"""
        pmr = ProductMethodRelation.objects.get(
            pk=pmr_id,
            relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY,
        )
        pmr.status = ProductMethodRelation.Status.REJECTED
        if note:
            prefix = pmr.evidence_note and (pmr.evidence_note + "\n") or ""
            pmr.evidence_note = (prefix + "[reject] " + note).strip()
        if curator:
            pmr.curator = curator
        pmr.save(update_fields=["status", "evidence_note", "curator"])
        logger.info("verified rejected pmr=%s curator=%s", pmr.id, curator)
        return pmr
