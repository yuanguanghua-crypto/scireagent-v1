"""Bioz 文献落库服务 — 把 Bioz enrich 的 references 批量落库到 Reference + ProductReference。

去重策略（降级）：
1. DOI 命中 → 复用现有 Reference
2. PMID 命中 → 复用现有 Reference
3. title 精确命中 → 复用现有 Reference
4. 都没有 → 新建 Reference

关联去重：ProductReference 按 (product, reference, citation_role) 唯一约束（unique_together）。

单条失败不中断整体（收集 errors），整体在事务内执行。
"""
import logging
import re

from django.db import transaction

from apps.bridges.models import ProductReference
from apps.knowledge.models import Reference

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _extract_year(pub_date) -> int | None:
    """从 pub_date 提取 4 位年份。格式可能是 'YYYY-MM-DD' / 'YYYY' / '' / None。"""
    if not pub_date:
        return None
    m = _YEAR_RE.search(str(pub_date))
    if not m:
        return None
    y = int(m.group(0))
    # 合理性校验：1900–2099
    if 1900 <= y <= 2099:
        return y
    return None


def _find_existing(doi: str, pmid: str, title: str) -> Reference | None:
    """降级查重：DOI > PMID > title。返回已存在的 Reference 或 None。"""
    doi = (doi or "").strip()
    pmid = (pmid or "").strip()
    title = (title or "").strip()
    if doi:
        r = Reference.objects.filter(doi=doi).first()
        if r:
            return r
    if pmid:
        r = Reference.objects.filter(pmid=pmid).first()
        if r:
            return r
    if title:
        r = Reference.objects.filter(title__iexact=title).first()
        if r:
            return r
    return None


def _build_reference(ref: dict) -> Reference:
    """从 bioz reference dict 构建新 Reference 对象（未保存）。"""
    authors = ref.get("authors") or ""
    # bioz 有时返回 list → 拼成逗号字符串
    if isinstance(authors, list):
        authors = ", ".join(str(a) for a in authors if a)
    return Reference(
        title=(ref.get("article_title") or "").strip(),
        authors=authors.strip(),
        journal=(ref.get("journal") or "").strip(),
        year=_extract_year(ref.get("pub_date")),
        doi=(ref.get("doi") or "").strip() or None,
        pmid=(ref.get("pmid") or "").strip() or None,
        source_type=Reference.SourceType.JOURNAL,
    )


def adopt_bioz_references(product, refs: list, citation_role: str = "supporting") -> dict:
    """把 bioz references 落库到 Reference + ProductReference。

    Args:
        product: commerce.Product 实例
        refs: bioz reference dict 列表
        citation_role: ProductReference.citation_role，默认 supporting

    Returns:
        {
            adopted: int,         # 新建关联数
            skipped: int,         # 关联已存在跳过数
            created_refs: [int],  # 新建 Reference id
            linked_refs: [int],   # 关联的 Reference id（含复用）
            errors: [str],        # 单条失败原因
        }
    """
    adopted = 0
    skipped = 0
    created_refs = []
    linked_refs = []
    errors = []

    with transaction.atomic():
        for idx, ref in enumerate(refs or []):
            try:
                title = (ref.get("article_title") or "").strip()
                if not title:
                    errors.append(f"[{idx}] missing article_title, skipped")
                    continue

                doi = (ref.get("doi") or "").strip()
                pmid = (ref.get("pmid") or "").strip()

                # 1. 查重 → 复用 or 新建
                existing = _find_existing(doi, pmid, title)
                if existing:
                    ref_obj = existing
                else:
                    ref_obj = _build_reference(ref)
                    ref_obj.save()
                    created_refs.append(ref_obj.id)

                # 2. 关联去重：(product, reference, role)
                _, created = ProductReference.objects.get_or_create(
                    product=product,
                    reference=ref_obj,
                    citation_role=citation_role,
                )
                linked_refs.append(ref_obj.id)
                if created:
                    adopted += 1
                else:
                    skipped += 1

            except Exception as e:
                logger.warning(f"bioz adopt ref[{idx}] failed: {e}")
                errors.append(f"[{idx}] {e}")

    return {
        "adopted": adopted,
        "skipped": skipped,
        "created_refs": created_refs,
        "linked_refs": linked_refs,
        "errors": errors,
    }
