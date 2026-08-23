# Step 8 L3 v3（代理第三轮）独立验收：结构 + M13 使用核查 + 点名案例 + 质量抽检
import os, json, csv, random
from collections import Counter

SRC = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v3.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
VALID = {e["id_code"] for e in entities} | {"INV-REVIEW", "SUP-BIOINFO"}
name_of = {e["id_code"]: e["name"] for e in entities}

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)
print("记录数:", len(rows))

filled = [r for r in rows if (r.get("corrected_method") or "").strip()]
blank = [r for r in rows if not (r.get("corrected_method") or "").strip()]
print("填写: %d | 留空: %d" % (len(filled), len(blank)))

illegal = [(r["protocol_id"], r["corrected_method"]) for r in filled if r["corrected_method"].strip() not in VALID]
print("非法 ID:", len(illegal))
for pid, cm in illegal[:10]:
    print("   ", pid, "->", repr(cm))

cm_dist = Counter(r["corrected_method"].strip() for r in filled)
print("top15:", cm_dist.most_common(15))
print("INV:", cm_dist.get("INV-REVIEW", 0), "| SUP:", cm_dist.get("SUP-BIOINFO", 0))
print("M13 使用:", cm_dist.get("M13", 0))

# ---- M13 使用核查（Viral Genome Sequencing vs 酶活误用） ----
m13 = [r for r in filled if r["corrected_method"].strip() == "M13"]
print("=== M13 %d 条，抽 8 条核对 ===" % len(m13))
random.seed(20260824)
random.shuffle(m13)
for r in m13[:8]:
    print("  [%s] %s | %s" % (r["protocol_id"], (r["protocol_name"] or "")[:45], (r["objective"] or "")[:100].replace(chr(10), " ")))

# ---- 点名案例核对 ----
print("=== 点名案例核对 ===")
targets = {"2806": "M20", "871": "(留空)", "14179": "SUP-BIOINFO", "8023": "(留空)", "6008": "M49"}
for pid, expect in targets.items():
    for r in rows:
        if r["protocol_id"] == pid:
            got = r["corrected_method"].strip() or "(留空)"
            mark = "OK" if got == expect else "MISMATCH(应 %s)" % expect
            print("  %s: %s %s" % (pid, got, mark))
            break

# ---- 禁用模板句黑名单 ----
BLACK = [
    "当前文本不足以在 73 个合法 Method 中可靠确定唯一主方法",
    "文本只说明“assay/测定/检测”",
    "协议确有显微/成像操作，但没有证据证明属于 M32",
    "文本描述的是计算流程、软件/数据库、算法或模型分析本身",
    "文本明确涉及测序文库/扩增子或 Illumina 类流程",
    "文本确认存在细胞培养，但未提供足够对象信息",
    "文本核心是动物体内给药、注射、移植或手术操作",
]
hit = sum(1 for r in rows if any(b in (r.get("note") or "") for b in BLACK))
print("禁用模板句命中:", hit)

# ---- note 前缀重复 ----
pref = Counter((r.get("note") or "").strip()[:40] for r in rows)
max_pref = max(pref.values())
print("最大前缀重复: %d (%.2f%%)" % (max_pref, max_pref / len(rows) * 100))

# ---- 质量抽检：Method 20 + SUP 10 + INV 10 + 留空 10 = 50 ----
random.seed(20260824)
with_method = [r for r in filled if r["corrected_method"].strip() not in ("INV-REVIEW", "SUP-BIOINFO")]
sup = [r for r in filled if r["corrected_method"].strip() == "SUP-BIOINFO"]
inv = [r for r in filled if r["corrected_method"].strip() == "INV-REVIEW"]
random.shuffle(with_method); random.shuffle(sup); random.shuffle(inv); random.shuffle(blank)
sample = with_method[:20] + sup[:10] + inv[:10] + blank[:10]
lines = ["# Step 8 L3 v3 独立验收抽样（Method 20 + SUP 10 + INV 10 + 留空 10 = 50）", "",
         "| # | 类型 | protocol_id | corrected | conf | name | objective（前 100 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, r in enumerate(sample, 1):
    cm = r["corrected_method"].strip() or "(留空)"
    if cm == "SUP-BIOINFO":
        k = "sup"
    elif cm == "INV-REVIEW":
        k = "inv"
    elif cm == "(留空)":
        k = "blank"
    else:
        k = "method"
    lines.append(f"| {i} | {k} | {r['protocol_id']} | {cm} | {r.get('confidence','')} | {(r.get('protocol_name') or '')[:32].replace('|','/')} | {(r.get('objective') or '')[:100].replace(chr(10),' ').replace('|','/')} |")
open(os.path.join(OUT, "step8_l3_v3_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step8_l3_v3_sample.md, n=", len(sample))

stat = {
    "total": len(rows), "filled": len(filled), "blank": len(blank), "illegal": len(illegal),
    "cm_top": cm_dist.most_common(15), "inv": cm_dist.get("INV-REVIEW", 0), "sup": cm_dist.get("SUP-BIOINFO", 0),
    "m13_count": cm_dist.get("M13", 0), "blacklist_hit": hit, "max_prefix": max_pref,
}
json.dump(stat, open(os.path.join(OUT, "step8_l3_v3_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved step8_l3_v3_stats.json")
