"""Phase 2 质量闸门（T2.1）：二维结果模型（MUST-4）。

依据 product_association_infra_plan_v0.2.md §6 / §7 MUST-4 + 任务 T2.1。

run_quality_gate(product, edges) 返回二维结果：
    (execution_result, scientific_quality)
  - execution_result ∈ {SUCCESS, FAILED}
      * 本函数仅判定科学质量、不触 DB；正常路径恒返回 SUCCESS。
      * FAILED 由 process_product 在捕获系统级异常（DB/code error）后统一映射，
        不在本函数内产生（保持本函数纯函数、可单测）。
  - scientific_quality ∈ {ACCEPTABLE, REVIEW}
      * ACCEPTABLE = 存在可靠派生边，可进入 production 展示
      * REVIEW     = 科学证据不足（宁 miss 不错配）：无可靠边 / 仅低置信边 / 冲突，
                     不自动裁决、待研究员人工收口；产品仍保持 ACTIVE（Q2）

核心原则（方案 §3.3）：derived=0 是科学证据不足的正常结果，不是 pipeline failure。
故"空边"走 SUCCESS + REVIEW，绝不 FAILED。

冲突检测：Phase 2 暂未接入具体冲突探测器（化学一致性 conflict 属 AUTO MATCH 域，
与本 derived 管线解耦）。保留 detect_conflicts() 扩展钩子，硬约束为"无可靠信号即返回
无冲突"，避免把正确匹配误杀为 REVIEW（宁 miss 不错配）。
"""
from apps.bridges.services.derived_builder import PRIO

EXEC_SUCCESS = 'SUCCESS'
EXEC_FAILED = 'FAILED'
QUALITY_ACCEPTABLE = 'ACCEPTABLE'
QUALITY_REVIEW = 'REVIEW'


def detect_conflicts(product, edges):
    """冲突探测器（Phase 2 扩展钩子）。

    返回冲突信号列表。当前无可靠冲突信号源，返回空（不误判）。
    后续若接入（同一 Method 经互斥 ReagentClass 派生、化学一致性四象限冲突等），
    须以"任何不确定性一律降级 REVIEW"为唯一硬约束，不得自动裁决。
    """
    return []


def _all_low_confidence(edges):
    """所有派生边仅为 conditional（最低置信 assignment_type）→ 证据不足 / 残缺。

    edges 元素：(product_id, method_id, source_rc_id, prio_int)
    prio: primary=0 < secondary=1 < conditional=2
    """
    if not edges:
        return False
    return all(prio >= PRIO['conditional'] for _, _, _, prio in edges)


def run_quality_gate(product, edges):
    """判定二维结果（纯函数，不触 DB）。

    :param product: Product 实例（当前供冲突探测器扩展使用，本阶段未消费其字段）
    :param edges: rebuild_derived_for_product 返回的派生边列表
                  [(product_id, method_id, source_rc_id, prio_int), ...]
    :returns: (execution_result, scientific_quality)
    """
    # ① 宁 miss：无可靠派生边 → 科学证据不足（正常分支），非 pipeline failure
    if not edges:
        return EXEC_SUCCESS, QUALITY_REVIEW

    # ② 残缺 / 证据不足：全部边仅 conditional（最低置信）→ REVIEW
    if _all_low_confidence(edges):
        return EXEC_SUCCESS, QUALITY_REVIEW

    # ③ 冲突：当前无可靠信号源，探测器返回空 → 不降级（不误判）
    if detect_conflicts(product, edges):
        return EXEC_SUCCESS, QUALITY_REVIEW

    # ④ 其余：存在可靠派生边 → ACCEPTABLE
    return EXEC_SUCCESS, QUALITY_ACCEPTABLE
