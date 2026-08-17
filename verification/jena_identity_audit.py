"""jena 身份字段完整性审计（AI auto match 链 load-bearing 字段）。

聚焦 4 个真正被 auto match 消费、且威胁"精准度"的身份字段：
  catalog_no   —— matcher 精确匹配主键 + Bioz search_by_sku 查询词（最致命）
  cas_number   —— matcher 优先级1精确匹配 + Bioz check_equivalence
  product_name —— find_by_name 双向子串匹配（jena_index.py:184，无校验门）
  category_path—— map_category_l1 → 平台分类

设计原则（用户）：
  1) 先确认 auto match 实际用 jena 哪些字段 → 已在代码审计中确认（见报告）。
  2) 先确保这些被使用字段的真实准确 → 本脚本即审计其准确性。
  3) 再验使用链路（matcher 逻辑）是否正确 → 后续步骤，不在本脚本范围。
  4) 重跑爬虫时如何校验 → 见脚本末尾 VALIDATION_GATE_SPEC（即 ingestion 闸门）。

分类：
  BLOCK = 字段值确属污染/畸形，必须隔离（不进 certified 索引）
  WARN  = 软风险（格式可疑/未映射/超长），待人工复核，不强行阻断

全程只读，不修改 jsonl。
"""
import json
import os
import re
import csv
import sys
from collections import Counter, defaultdict

# P0-3：允许环境变量 JENA_AUDIT_JSONL 覆盖，指向与校验/生产一致的权威副本
JSONL = os.environ.get(
    "JENA_AUDIT_JSONL",
    "C:/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/backend/data/jena/jena_products_v2.jsonl",
)
OUT_CSV = "C:/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/verification/jena_identity_audit.csv"
OUT_REPORT = "C:/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/verification/jena_identity_audit.md"

# 导航/面包屑泄漏标记（出现在身份字段里即视为污染）
# 注意：Jena 用 ' | ' 作合法层级分隔符，NOT 污染；仅 ' > ' 箭头才是面包屑
NAV_MARKERS = [
    "accessories", " > ", "home", "login", "cart", "search",
    "about us", "contact us", "breadcrumb", "add to cart", "your cart",
]
# catalog_no 干净形态：2+ 大写字母 + 可选 '-' + 数字；可选短后缀须以 '-' 引导
# （粘连描述词如 PR-969Proprotein 缺 '-' 引导 → 不匹配 → 判为污染）
CAT_RE = re.compile(r"^[A-Z]{2,}-?\d+(?:-[A-Z0-9]{2,6})?$")
# cas 标准形态（允许末尾括号注释）
CAS_RE = re.compile(r"^(\d{2,7})-(\d{2})-(\d)(?:\s*\(.*\))?$")


def cas_mod10_ok(cas: str) -> bool:
    """CAS 校验位 mod-10 算法。digits 不含校验位，从右起权重 1,2,3..."""
    digits = re.sub(r"\D", "", cas)
    if len(digits) < 3:
        return False
    body, check = digits[:-1], int(digits[-1])
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += (i + 1) * int(ch)
    return (total % 10) == check


def split_cas(raw: str):
    """CAS 字段可能含多个（逗号分隔）或括号注释，拆成候选列表。"""
    raw = raw.strip()
    # 去掉括号注释：保留括号前的主号；多号按逗号拆
    parts = re.split(r",", raw)
    out = []
    for p in parts:
        p = p.strip()
        m = re.match(r"^(\d{2,7}-\d{2}-\d)", p)
        if m:
            out.append(m.group(1))
        elif re.match(r"^\d{2,7}-\d{2}-\d", p):
            out.append(p)
    return out


def has_nav_leak(s: str) -> bool:
    low = s.lower()
    return any(m in low for m in NAV_MARKERS)


def audit_catalog_no(rec, issues):
    """catalog_no 裁判（P1-1 重构）。

    真实 jena 产品 URL 是描述性 slug（不含 catalog），故**不以 URL 是否含 catalog 作裁判**
    （旧逻辑对 100% 真实产品都打 WARN not_in_source_url，且 BLOCK 分支对真实数据成死代码）。
    裁判改为只看值的形态（过 CATALOG_RE 即合法家族 base / 变体字母形态）：
      - 空 / 含空格 → BLOCK
      - 过 CATALOG_RE（NU-851 / NU-851-680 / SP-25L 等）→ 合法；仅超长 WARN
      - 不过 CATALOG_RE：自身含干净前缀（粘连垃圾如 PR-969Proprotein）→ BLOCK glued
      - 否则 → BLOCK malformed
    """
    cat = (rec.get("jena_catalog_no") or "").strip()
    if not cat:
        issues.append(("catalog_no", "BLOCK", "empty", repr(cat)))
        return
    if " " in cat:
        issues.append(("catalog_no", "BLOCK", "contains_space", repr(cat)))
    if CAT_RE.match(cat):
        if len(cat) > 30:
            issues.append(("catalog_no", "WARN", "too_long", repr(cat)))
        return  # 形态干净 = 合法家族 base / 变体
    # 形态不干净
    prefix = CAT_RE.search(cat)
    if prefix:
        issues.append(("catalog_no", "BLOCK", "glued_or_spurious", repr(cat)))
    else:
        issues.append(("catalog_no", "BLOCK", "malformed", repr(cat)))
    if len(cat) > 30:
        issues.append(("catalog_no", "WARN", "too_long", repr(cat)))


def audit_cas(rec, issues):
    raw = (rec.get("cas_number") or "").strip()
    if not raw:
        return  # 86% 为空属正常，不记
    cands = split_cas(raw)
    if not cands:
        issues.append(("cas_number", "BLOCK", "format_unparseable", repr(raw)))
        return
    for c in cands:
        if not CAS_RE.match(c):
            issues.append(("cas_number", "WARN", "format_nonstandard", repr(c)))
        elif not cas_mod10_ok(c):
            issues.append(("cas_number", "BLOCK", "mod10_checkdigit_fail", repr(c)))


def audit_product_name(rec, issues):
    name = (rec.get("product_name") or "").strip()
    if not name:
        issues.append(("product_name", "BLOCK", "empty", repr(name)))
        return
    if has_nav_leak(name):
        issues.append(("product_name", "BLOCK", "nav_leak", repr(name)))
    if " > " in name:
        issues.append(("product_name", "BLOCK", "breadcrumb_leak", repr(name)))
    if re.search(r"[.!?]", name) and len(name) > 60:
        issues.append(("product_name", "WARN", "looks_like_prose", repr(name)))
    if len(name) > 120:
        issues.append(("product_name", "WARN", "too_long", repr(name)))


# 复刻 map_category_l1 的映射（仅采纳的 3 个 L1）
CATEGORY_L1_MAP = [
    ("nucleotides", "nucleotides_nucleosides"),
    ("click chemistry", "click_chemistry"),
    ("molecular biology", "molecular_biology"),
]


def map_category_l1(category_path):
    if not category_path:
        return ""
    segments = [s.strip().lower() for s in str(category_path).split("|")]
    for keyword, l1 in CATEGORY_L1_MAP:
        for seg in segments:
            if keyword in seg:
                return l1
    return ""


def audit_category_path(rec, issues):
    cp = (rec.get("category_path") or "").strip()
    if not cp:
        issues.append(("category_path", "WARN", "empty", repr(cp)))
        return
    if has_nav_leak(cp):
        issues.append(("category_path", "BLOCK", "nav_leak", repr(cp)))
    if not map_category_l1(cp):
        issues.append(("category_path", "WARN", "unmapped_to_l1", repr(cp[:60])))


def main():
    recs = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    total = len(recs)

    # 重复 catalog_no（主键唯一性）
    cat_counter = Counter((r.get("jena_catalog_no") or "").strip().upper() for r in recs)
    dup_cats = {c: n for c, n in cat_counter.items() if n > 1 and c}

    rows = []          # csv: catalog_no, field, severity, issue, value
    issue_counts = defaultdict(int)        # (field, severity, issue)
    block_recs = set()
    warn_recs = set()
    field_block = Counter()  # 每个字段有多少记录至少一次 BLOCK
    field_warn = Counter()

    for r in recs:
        cat = r.get("jena_catalog_no") or "?"
        issues = []
        audit_catalog_no(r, issues)
        audit_cas(r, issues)
        audit_product_name(r, issues)
        audit_category_path(r, issues)
        for field, sev, issue, val in issues:
            rows.append((cat, field, sev, issue, val))
            issue_counts[(field, sev, issue)] += 1
            if sev == "BLOCK":
                block_recs.add(cat)
                field_block[field] += 1
            else:
                warn_recs.add(cat)
                field_warn[field] += 1

    # 写出 CSV
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["catalog_no", "field", "severity", "issue", "value"])
        for row in rows:
            w.writerow(row)

    # 报告
    lines = []
    lines.append("# jena 身份字段完整性审计（auto match load-bearing 字段）\n")
    lines.append(f"- 数据源：`backend/data/jena/jena_products_v2.jsonl`（{total} 条）")
    lines.append(f"- 审计字段：catalog_no / cas_number / product_name / category_path")
    lines.append(f"- 分类：BLOCK=污染须隔离；WARN=软风险待复核\n")
    lines.append(f"## 汇总\n")
    lines.append(f"- **四身份字段全干净（无 BLOCK）的记录数：{total - len(block_recs)}（占 {(total - len(block_recs))*100//total}%）← 可信任基线**")
    lines.append(f"- 至少 1 个 BLOCK（污染须隔离）的记录数：**{len(block_recs)}**（占 {len(block_recs)*100//total}%）")
    lines.append(f"- 仅 WARN（软风险待复核、不阻断）的记录数：**{len(warn_recs - block_recs)}**（占 {len(warn_recs - block_recs)*100//total}%）")
    lines.append(f"- 主键 catalog_no 重复：{'无' if not dup_cats else str(len(dup_cats))+' 个重复值'}\n")

    lines.append("## 各字段 BLOCK / WARN 记录数\n")
    lines.append("| 字段 | BLOCK 记录数 | WARN 记录数 |")
    lines.append("|---|---|---|")
    for fld in ["catalog_no", "cas_number", "product_name", "category_path"]:
        lines.append(f"| {fld} | {field_block[fld]} | {field_warn[fld]} |")
    lines.append("")

    lines.append("## 问题细分（按 field × severity × issue）\n")
    lines.append("| 字段 | 严重度 | 问题 | 条数 |")
    lines.append("|---|---|---|---|")
    for (fld, sev, issue), n in sorted(issue_counts.items(), key=lambda x: (-x[1])):
        lines.append(f"| {fld} | {sev} | {issue} | {n} |")
    lines.append("")

    if dup_cats:
        lines.append("## catalog_no 重复值（主键冲突）\n")
        for c, n in list(dup_cats.items())[:30]:
            lines.append(f"- {c}: {n} 次")
        lines.append("")

    # 抽样坏记录
    lines.append("## 典型 BLOCK 样本（前 25 条）\n")
    shown = 0
    sample = defaultdict(list)
    for cat, field, sev, issue, val in rows:
        if sev == "BLOCK" and len(sample[cat]) < 3 and shown < 25:
            sample[cat].append(f"  - {field}.{issue} = {val}")
            shown += 1
    for cat, items in sample.items():
        lines.append(f"**{cat}**")
        lines.extend(items)
    lines.append("")

    # 校验闸门规范（重跑爬虫 ingestion 用）
    lines.append("## 重跑爬虫 / 清洗时的 ingestion 校验闸门规范（VALIDATION_GATE_SPEC）\n")
    lines.append("目标：最终形成的 jena 数据，凡被 auto match 消费的身份字段必须过闸，否则隔离（不进 certified 索引）。\n")
    lines.append("| 字段 | 校验规则 | 失败处置 | 阶段 |")
    lines.append("|---|---|---|---|")
    lines.append(r"| catalog_no | **终极裁判=出现在自身价格表/变体列表（span.catalogno 或 table cell，即爬虫 extract_family_catalog 候选源）则合法**（含 SP-25L / NU-851-680 类变体字母）；不在候选源 → BLOCK→隔离（真实 jena 产品 URL 是描述性 slug、不含 catalog，slug 不可作裁判）；格式须过 `^[A-Z]{2,}-?\d+(?:-[A-Z0-9]{2,6})?$`；无空格；长度≤30 | 见左 | 摄入即查 |")
    lines.append("| cas_number | 非空时过 `^\\d{2,7}-\\d{2}-\\d$` + mod-10 校验位 | 格式 WARN/校验位 BLOCK→隔离 | 摄入即查 |")
    lines.append("| product_name | 非空；无 ` > ` 面包屑箭头；无导航泄漏(accessories/home/login 等)；非散文(无句末标点或过长) | 面包屑/泄漏 BLOCK；散文 WARN | 摄入即查 |")
    lines.append("| category_path | 非空；无导航泄漏（`|` 是 Jena 合法层级分隔符，不判污染）；能 map_category_l1 到已知 L1（否则分类留空不硬填） | 泄漏 BLOCK；未映射 WARN | 摄入即查 |")
    lines.append("| 一致性(软) | catalog_no 必须出现在自身价格表/变体列表（爬虫抽取源）；真实 jena URL 不含 catalog，故 slug 不作裁判；抽取失败即 BLOCK（非 WARN，避免全文误隔离） | BLOCK→隔离 | 摄入即查 |")
    lines.append("| 主键唯一 | catalog_no 全库唯一 | 重复 BLOCK→隔离 | 摄入即查 |")
    lines.append("")
    lines.append("应用方式：scraper_v3.py 第 853-868 行提取后、写入 JSONL 前，插入本闸门；不过闸记录写入 `jena_quarantine.jsonl` 并打 `quality_flag`，不进入 `jena_products_v2.jsonl`（certified）。后端 `jena_index.build()` 仅读 certified 文件。")

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 控制台
    print(f"TOTAL={total}")
    print(f"BLOCK records={len(block_recs)} ({len(block_recs)*100//total}%)")
    print(f"WARN records={len(warn_recs)} ({len(warn_recs)*100//total}%)")
    print(f"dup catalog_no={len(dup_cats)}")
    print("issue breakdown:")
    for (fld, sev, issue), n in sorted(issue_counts.items(), key=lambda x: (-x[1])):
        print(f"  {fld:14} {sev:5} {issue:28} {n}")
    print(f"\nCSV -> {OUT_CSV}")
    print(f"REPORT -> {OUT_REPORT}")


if __name__ == "__main__":
    main()
