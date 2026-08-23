# Step 8 L3 v2（代理整改后）独立验收：结构 + 留空构成 + 抽样
import os, json, csv, random, re
from collections import Counter

SRC = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_r2_L3_v2.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
VALID = {e["id_code"] for e in entities} | {"INV-REVIEW", "SUP-BIOINFO"}

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
print("top12:", cm_dist.most_common(12))
print("INV:", cm_dist.get("INV-REVIEW", 0), "| SUP:", cm_dist.get("SUP-BIOINFO", 0), "| M32:", cm_dist.get("M32", 0))

conf = Counter((r.get("confidence") or "").strip().lower() for r in filled)
print("confidence:", dict(conf))

# note 去重（留空层的 note 也算）
notes = Counter((r.get("note") or "").strip() for r in rows)
dup_note = sum(n for k, n in notes.items() if n > 1 and k)
dup_rows = sum(n for k, n in notes.items() if n > 1 and k)
print("note 去重: 重复文本数 %d, 重复行数 %d (%.2f%%)" % (dup_note, dup_rows, dup_rows / len(rows) * 100))

# ---- 留空 3,000 条构成预扫描（关键词分类） ----
GAP_KW = ["mass spectr", "ms/ms", "lc-ms", "gc-ms", "afm", "atomic force", "electron microsc", "em ", "tem ", "sem ", "crystalli", "northern", "southern blot", "restriction digest", "liposome", "reporter assay", "luciferase", "x-ray", "nmr", "dsc", "itc", "surface plasmon", "spr ", "flow cytometr", "facs", "chromatograph", "hplc", "gel filtration", "size exclusion", "circular dichroism", "microarray", "elispot", "scratch", "wound healing", "transwell", "migration", "invasion", "colony", "cfu", "plaque", "titer", "viral load", "qrt-pcr", "qpcr", "real-time pcr"]
MISSED_KW = ["gel purif", "agarose", "gel extraction", "immunohistochem", "ihc", "immunofluorescen", "if staining", "elisa", "western blot", "sds-page", "immunoblot", "co-ip", "pull-down", "chipseq", "chip-seq", "crispr", "genome edit", "transfection", "electroporation", "culture", "differentiation", "stem cell", "flow", "facs", "rt-pcr", "reverse transcription", "cdna", "library", "sequencing", "illumina", "nanopore", "rna-seq", "in situ hybridization", "fish ", "frozen section", "paraffin", "embedding", "h&e", "hematoxylin", "eosin", "ki-67", "tunel", "brdu", "cck-8", "mtt", "mts", "viability", "apoptosis", "annexin", "cell cycle", "propidium"]

def classify_blank(r):
    obj = ((r.get("objective") or "") + " " + (r.get("protocol_name") or "")).lower()
    if any(k in obj for k in GAP_KW):
        return "gap_kw（roster 可能缺：质谱/EM/结晶/blot 变体等）"
    if any(k in obj for k in MISSED_KW):
        return "missed_kw（roster 已有方法但漏判？）"
    return "other"

bc = Counter(classify_blank(r) for r in blank)
print("留空构成（关键词预扫描）:", dict(bc))

# ---- 分层抽样：留空 15（含 gap/missed/other 各 5）+ 有 Method 12 + INV 3 + SUP 5 = 35 ----
random.seed(20260824)
with_method = [r for r in filled if r["corrected_method"].strip() not in ("INV-REVIEW", "SUP-BIOINFO")]
inv = [r for r in filled if r["corrected_method"].strip() == "INV-REVIEW"]
sup = [r for r in filled if r["corrected_method"].strip() == "SUP-BIOINFO"]
b_gap = [r for r in blank if classify_blank(r).startswith("gap")]
b_missed = [r for r in blank if classify_blank(r).startswith("missed")]
b_other = [r for r in blank if classify_blank(r).startswith("other")]
random.shuffle(with_method); random.shuffle(inv); random.shuffle(sup)
random.shuffle(b_gap); random.shuffle(b_missed); random.shuffle(b_other)
sample = with_method[:12] + b_gap[:5] + b_missed[:5] + b_other[:5] + inv[:3] + sup[:5]
lines = ["# Step 8 L3 v2 独立验收抽样（Method 12 + 留空gap 5 + 留空missed 5 + 留空other 5 + INV 3 + SUP 5 = 35）", "",
         "| # | 类型 | protocol_id | corrected | conf | name | objective（前 110 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, r in enumerate(sample, 1):
    cm = r["corrected_method"].strip() or "(留空)"
    if cm in ("INV-REVIEW", "SUP-BIOINFO"):
        k = cm.lower().replace("review", "inv")
    elif cm == "(留空)":
        k = "blank_" + classify_blank(r).split("（")[0]
    else:
        k = "method"
    lines.append(f"| {i} | {k} | {r['protocol_id']} | {cm} | {r.get('confidence','')} | {(r.get('protocol_name') or '')[:35].replace('|','/')} | {(r.get('objective') or '')[:110].replace(chr(10),' ').replace('|','/')} |")
open(os.path.join(OUT, "step8_l3_v2_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step8_l3_v2_sample.md, n=", len(sample))

stat = {
    "total": len(rows), "filled": len(filled), "blank": len(blank), "illegal": len(illegal),
    "cm_top": cm_dist.most_common(12), "inv": cm_dist.get("INV-REVIEW", 0), "sup": cm_dist.get("SUP-BIOINFO", 0),
    "confidence": dict(conf), "note_dup_rows": dup_rows, "note_dup_pct": round(dup_rows / len(rows) * 100, 2),
    "blank_cat": dict(bc),
}
json.dump(stat, open(os.path.join(OUT, "step8_l3_v2_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved step8_l3_v2_stats.json")
