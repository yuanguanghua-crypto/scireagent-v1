"""化学等同性校验（决定 Bioz 文献是否适用于平台产品）。

jena_matcher 是 name + synonyms 模糊匹配，"名字像"不等于"同一化学物质"。
只有 CAS 严格一致才算同物，Bioz 文献才完全适用；CAS 不一致或缺失的 name 模糊
命中，降级标记 needs_review，由研究员确认。

ChEMBL fallback 坑（pubchem_enhancer.py:454 把 SMILES 错塞进 cas_resolved）
由 cas_normalize 的形态校验兜住——非 CAS 形态直接当"无 CAS"处理。

详见 Phase B 计划 §3。
"""
from apps.commerce.services.cas_normalize import cas_normalize


def check_equivalence(platform_cas, jena_cas, match_key: str) -> dict:
    """判定平台产品与 jena 记录的化学等同性。

    Args:
        platform_cas: 平台产品的 CAS（Product.cas 或 enrich 输入 cas 或 chemical.cas_resolved）
        jena_cas: jena_matcher 返回的 cas_number
        match_key: jena_matcher 返回的 match_key（"cas"/"name"/"synonym:..."）

    Returns:
        {equivalence: str, needs_review: bool}
        equivalence ∈ {"exact", "name_match", "weak", "mismatch"}
    """
    p = cas_normalize(platform_cas)
    j = cas_normalize(jena_cas)

    # ① CAS 双方都有且等同 → exact
    if p and j:
        if p == j:
            return {"equivalence": "exact", "needs_review": False}
        # 双方都有 CAS 但不一致 → mismatch（罕见，jena CAS 查到但与平台不符）
        return {"equivalence": "mismatch", "needs_review": True}

    # ② 一方有 CAS 一方无：无法 CAS 证实，按 match_key 降级
    # ③ 双方都无 CAS：只能靠 name/synonym 模糊命中
    # 统一按 match_key 判定置信度
    if match_key == "cas":
        # match_key=cas 说明 jena 用 CAS 查到，但平台 CAS 缺失或 jena CAS 缺失
        # 实际是 name 兜底命中的特殊情况，降级为 name_match
        return {"equivalence": "name_match", "needs_review": True}
    if match_key and match_key.startswith("synonym:"):
        return {"equivalence": "name_match", "needs_review": True}
    if match_key == "name":
        return {"equivalence": "weak", "needs_review": True}

    # match_key 未知/空
    return {"equivalence": "weak", "needs_review": True}
