"""Bioz 文献证据编排层（pipeline）。

编排 bioz_client（请求）→ bioz_equivalence（等同性）→ bioz_sanitizer（净化）→
按 IF 排序 → 组装 enrich 返回的 bioz section 草案。

出层的完整 bioz section 结构见本文件末 DISCLAIMER / assemble_bioz_section。

详见 Phase B 计划 §5。
"""
import logging

from apps.knowledge.services.bioz_client import BiozClient
from apps.knowledge.services.bioz_equivalence import check_equivalence
from apps.knowledge.services.bioz_sanitizer import sanitize_record

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "文献基于同化学实体匹配，非特定厂商产品引用。"
    "展示实验证据需研究员确认后纳入正式产品文档。"
)


def fetch_bioz_evidence(jena_result: dict, platform_cas: str = "",
                        vendor: str = "Jena Bioscience", max_results: int = 10) -> dict:
    """编排 Bioz 文献证据查询 → 返回 enrich 所需的 bioz section。

    Args:
        jena_result: jena_matcher.match_jena 的返回 dict
        platform_cas: 平台产品的 CAS
        vendor: 供应商名（Bioz widget 的 cx 参数）
        max_results: 返回文献数上限

    Returns:
        bioz section dict（见 assemble_bioz_section）。
        jena 未匹配 → {"queried": false, "reason": "no_jena_match"}。
        Bioz 查询失败 → {"queried": true, "error": str, "references": []}。
    """
    if not jena_result.get("matched"):
        return {"queried": False, "reason": "no_jena_match"}

    catalog_no = jena_result.get("catalog_no", "")
    jena_cas = jena_result.get("cas_number") or ""
    match_key = jena_result.get("match_key", "")

    if not catalog_no:
        return {"queried": False, "reason": "no_catalog_no"}

    # 化学等同性
    equiv = check_equivalence(platform_cas, jena_cas, match_key)

    # 查 Bioz
    try:
        client = BiozClient()
        raw_records = client.search_by_sku(catalog_no, vendor=vendor, max_results=max_results)
    except Exception as e:
        logger.warning(f"Bioz search failed for {catalog_no}: {e}")
        return {
            "queried": True,
            "vendor": vendor,
            "catalog_no": catalog_no,
            "equivalence": equiv.get("equivalence", "weak"),
            "needs_review": True,
            "disclaimer": DISCLAIMER,
            "error": str(e),
            "references": [],
        }

    # 净化 + 排序
    clean = [sanitize_record(r, catalog_no, vendor) for r in raw_records]
    clean.sort(key=lambda r: (
        float(r.get("impact_factor") or 0),
        r.get("pub_date", "9999-99-99"),
    ), reverse=True)
    # IF 按降序；上面 pub_date 也反向但需要前向——实际更稳的写法：
    # 用 IF 主序，同年份降序 pub_date。简化：python sort stable，分两趟
    clean.sort(key=lambda r: r.get("pub_date", "0000"), reverse=True)
    clean.sort(key=lambda r: float(r.get("impact_factor") or 0), reverse=True)

    return {
        "queried": True,
        "vendor": vendor,
        "catalog_no": catalog_no,
        "equivalence": equiv.get("equivalence", "weak"),
        "needs_review": equiv.get("needs_review", True),
        "disclaimer": DISCLAIMER,
        "total": len(clean),
        "references": clean,
    }
