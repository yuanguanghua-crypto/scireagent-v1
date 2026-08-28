"""关联资格规则注册表（Python 配置 + 显式 version）。

设计依据：product_association_infra_plan_v0.2.md
  - MUST-15 Derived Scientific Eligibility Guard
  - 配置级 allow-list（非 Schema 扩张，符合 Ontology/Schema/Mapping 三冻结）

MAPPER_VERSION 教训：改规则须显式 bump version，否则改动无法被审计与回溯。

derived 生成须同时满足（四道 AND，见 derived_builder）：
  1. PRC.status      ∈ {auto_accepted, human_verified}
  2. RC.status       = approved
  3. MRC.status      = curated
  4. Method.slug     ∈ DERIVED_METHOD_ALLOWLIST   ← MUST-15 新增第 4 道
  5. Product.archived = False

verified_applicability 不受 MUST-15 限制（研究员显式确认即事实）。
"""

RULE_VERSION = '1.0'

# MUST-15 第 4 道 AND：仅经明确科学审查的 Method 允许进入 production derived pipeline。
# 初始 ALLOW_ALL_METHODS=True → 放行所有 Method（冻结现有 derived 行为，保回归闸门：
#   现状 dev 150 边 / prod 159 边逐条一致）。
# 后续收紧：研究员审查后，把可信 Method 的 slug 列入 ALLOWED_METHOD_SLUGS，
#   并置 ALLOW_ALL_METHODS=False，未列入的 Method 不再自动产生 derived（防低可信 seed 语义放大）。
ALLOW_ALL_METHODS = True
ALLOWED_METHOD_SLUGS: frozenset = frozenset([])

MUST15_VERSION = '1.0'


def method_allowed(slug: str) -> bool:
    """MUST-15 判定：该 Method 是否允许进入 derived pipeline。"""
    if ALLOW_ALL_METHODS:
        return True
    return slug in ALLOWED_METHOD_SLUGS
