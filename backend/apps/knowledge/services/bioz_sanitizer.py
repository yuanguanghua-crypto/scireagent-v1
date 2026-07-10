"""Bioz 引用上下文厂商无关化净化器。

Bioz 返回的 long/medium/short 引用上下文里渗透了厂商名（Jena Biosciences）和
SKU 变体（NU-1138 / nu-1138l / NU-1138s 等），原样挂到我们产品页既有别家名字
尴尬又有法律风险。本净化器删厂商名 + 删 SKU 变体 + 删 Bioz 标签 + 修剪标点，
输出厂商无关的"实验证据句"。

不动化学物质名（5-Methyl-CTP / Pseudo-UTP 等）——那是科学内容。

详见 docs/FIVE_DATASOURCES.md §5.3、Phase B 计划 §2。
"""
import re

# 厂商名变体（大小写不敏感匹配）。当前只 jena，多厂商时扩展。
_VENDOR_VARIANTS = {
    "Jena Bioscience": [
        r"Jena\s+Biosciences?",
    ],
}

# Bioz 内部标签（含 PrePrint 前缀、化学物质高亮、厂商高亮等）
_BIOZ_TAGS = [
    (r"<b>\s*PrePrint\s*:\s*</b>", ""),       # <b>PrePrint:</b>
    (r"</?[a-zA-Z][a-zA-Z0-9]*\s*/?>", ""),   # <c> </c> <t> </t> <cdd> </cdd> 等任意标签
]

# 残留标点修剪
_PUNCT_PATTERNS = [
    (r"\(\s*\)", ""),          # 空括号 ()
    (r"\[\s*\]", ""),          # 空方括号 []
    (r"\(\s*,\s*\)", ""),      # (, ) 残留
    (r"\s+,", ","),            # 逗号前空格 → 逗号（删厂商括号后残留）
    (r"\s{2,}", " "),          # 多空格
    (r"\s*\.\s*\.\s*", ". "),  # 双点 .. → 单点
    (r"\s*,\s*,\s*", ", "),    # 双逗号
    (r"^\s*[,.;:]\s*", ""),    # 首标点
    (r"\s*,\s*$", ""),         # 尾逗号
    (r"\s+$", ""),             # 尾空格
    (r"^\s+", ""),             # 首空格
]


def _build_sku_patterns(catalog_no: str, catalog_group: list) -> list[str]:
    """构造需删除的 SKU 变体正则列表。

    从 catalog_no + catalog_group 取全部变体，转义后大小写不敏感匹配。
    """
    variants = set()
    if catalog_no:
        variants.add(catalog_no)
    for v in (catalog_group or []):
        if v:
            variants.add(v)
    patterns = []
    for v in variants:
        v = str(v).strip()
        if not v:
            continue
        patterns.append(re.escape(v))
    return patterns


def sanitize_citation(text: str, catalog_no: str, vendor: str = "Jena Bioscience",
                      catalog_group: list | None = None) -> str:
    """净化单条引用上下文 → 厂商无关的实验证据句。

    Args:
        text: Bioz 的 long/medium/short 原文
        catalog_no: SKU（如 NU-1138）
        vendor: 供应商名
        catalog_group: SKU 变体列表（Bioz record 自带，更全）

    Returns:
        净化后字符串。原文只剩厂商名时返回空字符串。
    """
    if not text:
        return ""
    s = str(text)

    # 1. 删 Bioz 标签（先删标签，避免标签内容干扰后续匹配）
    for pat, repl in _BIOZ_TAGS:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)

    # 2. 删厂商名变体（大小写不敏感）
    vendor_patterns = _VENDOR_VARIANTS.get(vendor, [])
    for pat in vendor_patterns:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)

    # 3. 删 SKU 变体（大小写不敏感）。catalog_group 里的变体更全。
    for sku_pat in _build_sku_patterns(catalog_no, catalog_group or []):
        s = re.sub(sku_pat, "", s, flags=re.IGNORECASE)

    # 4. 修剪残留标点
    for pat, repl in _PUNCT_PATTERNS:
        s = re.sub(pat, repl, s)

    return s.strip()


def sanitize_record(record: dict, catalog_no: str, vendor: str = "Jena Bioscience") -> dict:
    """净化一条 Bioz record 的 long/medium/short 三级引用上下文。

    返回含 clean_long/clean_medium/clean_short 的新 dict（不含原始 long/medium/short
    和 catalog_group/catalog_number 等厂商字段）。
    """
    catalog_group = record.get("catalog_group", [])
    return {
        "article_title": record.get("article_title", ""),
        "authors": record.get("authors", []),
        "journal": record.get("journal", ""),
        "impact_factor": record.get("impact_factor") or 0.0,
        "pmid": record.get("pmid", ""),
        "pmcid": record.get("pmcid", ""),
        "doi": record.get("doi", ""),
        "pub_date": record.get("pub_date", ""),
        "techniques": record.get("techniques", []),
        "filter_data": record.get("filter_data") or [],
        "image_urls": record.get("image_urls", []) or [],
        "clean_long": sanitize_citation(record.get("long", ""), catalog_no, vendor, catalog_group),
        "clean_medium": sanitize_citation(record.get("medium", ""), catalog_no, vendor, catalog_group),
        "clean_short": sanitize_citation(record.get("short", ""), catalog_no, vendor, catalog_group),
    }
