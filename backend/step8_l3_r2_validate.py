# Step 8 L3 R2（第三方代理执行）验收：结构统计 + INV note 分类 + 分层抽样
import os, json, csv, random, re
from collections import Counter

SRC = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_r2_L3_completed_v1.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
VALID = {e["id_code"] for e in entities} | {"INV-REVIEW", "SUP-BIOINFO"}

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)
print("记录数:", len(rows))

filled = [r for r in rows if (r.get("corrected_method") or "").strip()]
print("填写率: %d (%.1f%%)" % (len(filled), len(filled)/len(rows)*100))

illegal = [(r["protocol_id"], r["corrected_method"]) for r in filled if r["corrected_method"].strip() not in VALID]
print("非法 ID:", len(illegal))
for pid, cm in illegal[:10]:
    print("   ", pid, "->", repr(cm))

cm_dist = Counter(r["corrected_method"].strip() for r in filled)
print("top15 分布:", cm_dist.most_common(15))
print("INV-REVIEW:", cm_dist.get("INV-REVIEW", 0), "| SUP-BIOINFO:", cm_dist.get("SUP-BIOINFO", 0))

conf = Counter((r.get("confidence") or "").strip().lower() for r in filled)
print("confidence:", dict(conf))

# ---- INV-REVIEW note 分类（排除 inv-review 自身子串干扰） ----
def _note(r):
    return (r.get("note") or "").strip().lower().replace("inv-review", " ").replace("inv_review", " ")

inv = [r for r in filled if r["corrected_method"].strip() == "INV-REVIEW"]
cat = Counter()
for r in inv:
    note = _note(r)
    if "综述" in note or "meta-anal" in note or "systematic" in note or "literature review" in note or "review of" in note:
        cat["真综述/临床/观察"] += 1
    elif "无足够文本证据" in note or "无合适" in note or "无合法" in note or "不能建立" in note or "待人工" in note or "候选" in note or "gap" in note or "nominate" in note or "暂列" in note:
        cat["无映射提名（真实方法但 roster 缺）"] += 1
    elif "objective 为空" in note:
        cat["objective 空"] += 1
    else:
        cat["其他"] += 1
print("INV note 分类:", dict(cat))

# note 样例
for r in inv[:5]:
    print("  INV note 样例:", (r.get("note") or "")[:90], "| name:", (r.get("protocol_name") or "")[:40])

# ---- 分层抽样 ----
random.seed(20260823)
with_method = [r for r in filled if r["corrected_method"].strip() not in ("INV-REVIEW", "SUP-BIOINFO")]
inv_true = [r for r in inv if cat.get("真综述/临床/观察") and True]  # 用同逻辑重判
sup = [r for r in filled if r["corrected_method"].strip() == "SUP-BIOINFO"]
# 分层：有 Method 15 + INV 无映射 8 + INV 综述 5 + SUP 5 = 33
def is_inv_true(r):
    note = _note(r)
    return any(k in note for k in ("综述", "meta-anal", "systematic", "literature review", "review of"))
inv_nomap = [r for r in inv if not is_inv_true(r)]
inv_true2 = [r for r in inv if is_inv_true(r)]
random.shuffle(with_method); random.shuffle(inv_nomap); random.shuffle(inv_true2); random.shuffle(sup)
sample = with_method[:15] + inv_nomap[:8] + inv_true2[:5] + sup[:5]
lines = ["# Step 8 L3 R2 执行验收抽样（Method 15 + INV无映射 8 + INV综述 5 + SUP 5 = 33）", "",
         "| # | 类型 | protocol_id | corrected | conf | name | objective（前 120 字符） |",
         "|---|---|---|---|---|---|---|"]
kinds = {}
for r in sample:
    cm = r["corrected_method"].strip()
    if cm not in ("INV-REVIEW", "SUP-BIOINFO"):
        k = "method"
    elif cm == "SUP-BIOINFO":
        k = "sup"
    else:
        k = "inv_true" if is_inv_true(r) else "inv_nomap"
    kinds[id(r)] = k
for i, r in enumerate(sample, 1):
    k = kinds[id(r)]
    lines.append(f"| {i} | {k} | {r['protocol_id']} | {r['corrected_method'].strip()} | {r.get('confidence','')} | {(r.get('protocol_name') or '')[:40].replace('|','/')} | {(r.get('objective') or '')[:120].replace(chr(10),' ').replace('|','/')} |")
open(os.path.join(OUT, "step8_l3_r2_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step8_l3_r2_sample.md, n=", len(sample))

stat = {
    "total": len(rows), "filled": len(filled), "illegal": len(illegal),
    "cm_top": cm_dist.most_common(15), "inv": cm_dist.get("INV-REVIEW", 0), "sup": cm_dist.get("SUP-BIOINFO", 0),
    "confidence": dict(conf), "inv_note_cat": dict(cat),
}
json.dump(stat, open(os.path.join(OUT, "step8_l3_r2_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved step8_l3_r2_stats.json")
