"""产品随增关联基础设施 — 关联管线服务（Phase 1 骨架）。

设计依据：方案 v0.2（Hardening Patch）§6 / MUST-1~7 / MUST-15。

职责：
- `process_product(product_id)` 是关联管线的唯一入口，由
  `CommerceService.activate_product()` 在 DRAFT→ACTIVE 转换时调用
  （真实触发点：commerce/api/v1/serializers.py:314-379 update() 的
  is_becoming_active 分支）。不使用 post_save 信号。
- 单产品 rebuild 在 transaction.atomic() + select_for_update() 内串行化
  （MUST-2，廉价一致性保险，非分布式锁）。
- 审计走标准 logging 结构化日志（logger=association_pipeline），不复用
  StatusLog（其 order 外键必填，复用需迁移越 scope）（MUST-5 修正）。
- DRAFT/DEPRECATED/ARCHIVED 不产生 production derived（核心原则 1 / A1）。

Phase 1 已落地入口 + DRAFT 护栏 + row lock；Phase 2 已接入 quality gate（T2.1，
二维结果）与结构化审计（T2.2，标准 logging）。classify / recompute ProductProtocol
在后续 Phase 逐步接入（recompute 当前仍由独立 auto_links 命令离线运行）。
"""
import logging
import time

from django.db import transaction

from apps.commerce.models import Product
from apps.bridges.models import ProductMethodRelation
from apps.bridges.services.derived_builder import rebuild_derived_for_product
from apps.bridges.services.quality_gate import run_quality_gate
from apps.bridges.services.pipeline_log import log_pipeline
from apps.bridges.services.rule_registry import RULE_VERSION

logger = logging.getLogger("association_pipeline")

# 管线版本（与 rule_registry.version 区分；此处为管线编排版本）
PIPELINE_VERSION = "0.1.0"


class AssociationService:
    """关联管线服务。所有方法为类方法/静态方法，便于 process_products 批量编排。"""

    @staticmethod
    def process_product(product_id, *, pipeline_version: str = PIPELINE_VERSION) -> dict:
        """对单个产品执行关联管线。

        返回结构化结果字典（execution_result / scientific_quality / edge 计数），
        供调用方与日志消费。Phase 2 已接入质量闸门（T2.1）与结构化审计（T2.2）。

        invariant（A1）：非 ACTIVE 状态产品不产生 production derived，
        直接 early-return（execution_result=SKIPPED）。

        二维结果模型（MUST-4 / GPT Q2）：
          - execution_result: SUCCESS（管线跑通，含"科学证据不足"正常分支）
                              / FAILED（系统级异常，内层 atomic 已回滚 derived 变更）
          - scientific_quality: ACCEPTABLE（有可靠派生边）
                              / REVIEW（宁 miss：derived=0 或仅低置信边或冲突）
          derived=0 是科学证据不足的正常结果，非 pipeline failure。

        MUST-3 双语义回滚：系统错误 → 内层 transaction.atomic 自动回滚 derived 变更
        （product 由 serializer 已在事务外置为 ACTIVE，保持 ACTIVE，符合 Q2：管线故障
        可恢复）。科学不足 → SUCCESS + REVIEW，product 仍 ACTIVE。
        """
        started = time.perf_counter()
        # Phase 2：actor 透传待 Phase 3 接线（serializer 当前仅传 product_id，未传 user）
        actor = 'system'
        with transaction.atomic():
            # MUST-2：单产品行级串行化，消除同产品并发 rebuild 竞争
            product = Product.objects.select_for_update().get(pk=product_id)

            if product.status != Product.Status.ACTIVE:
                # 核心原则 1 + A1：DRAFT/DEPRECATED/ARCHIVED 不触发生产关联
                duration_ms = int((time.perf_counter() - started) * 1000)
                log_pipeline(
                    product_id=product_id,
                    pipeline_version=pipeline_version,
                    execution_result='SKIPPED',
                    scientific_quality=None,
                    created_edges=0,
                    deleted_edges=0,
                    duration_ms=duration_ms,
                    actor=actor,
                )
                return {
                    "execution_result": "SKIPPED",
                    "scientific_quality": None,
                    "derived_created": 0,
                    "derived_deleted": 0,
                    "verified_touched": 0,
                }

            # ② rebuild_derived_for_product → PMR(derived)（含 MUST-15 四道 AND）
            #    仅重建 derived_relevance，绝不碰 verified_applicability（A6 护栏）。
            before = ProductMethodRelation.objects.filter(
                product_id=product_id, relation_type='derived_relevance'
            ).count()
            try:
                expected = rebuild_derived_for_product(product_id)
                # ④ quality gate：二维结果（纯函数，不触 DB）
                execution_result, scientific_quality = run_quality_gate(product, expected)
            except Exception as exc:
                # MUST-3：系统级异常 → FAILED；内层 atomic 已回滚 derived 变更
                duration_ms = int((time.perf_counter() - started) * 1000)
                log_pipeline(
                    product_id=product_id,
                    pipeline_version=pipeline_version,
                    execution_result='FAILED',
                    scientific_quality=None,
                    created_edges=0,
                    deleted_edges=0,
                    duration_ms=duration_ms,
                    actor=actor,
                    error=str(exc),
                )
                return {
                    "execution_result": "FAILED",
                    "scientific_quality": None,
                    "derived_created": 0,
                    "derived_deleted": 0,
                    "verified_touched": 0,
                }

            after = len(expected)
            duration_ms = int((time.perf_counter() - started) * 1000)
            log_pipeline(
                product_id=product_id,
                pipeline_version=pipeline_version,
                execution_result=execution_result,
                scientific_quality=scientific_quality,
                created_edges=after,
                deleted_edges=before,
                duration_ms=duration_ms,
                actor=actor,
            )
            return {
                "execution_result": execution_result,
                "scientific_quality": scientific_quality,
                "derived_created": after,
                "derived_deleted": before,
                "verified_touched": 0,
            }
