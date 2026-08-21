# Step 8 L2 人工回填验收：结构/合法性统计 + 抽样复核清单
import os, json, csv, random
from collections import Counter

SRC = r"C:\Users\yuankaifeng\Downloads\L2_curation_workfile_corrected.csv"
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
n_filled = len(filled)
print("填写 corrected_method: %d (%.1f%%)" % (n_filled, n_filled / len(rows) * 100))

conf = Counter((r.get("confidence") or "").strip().lower() for r in filled)
print("confidence 分布:", dict(conf))

illegal = []
for r in filled:
    cm = r["corrected_method"].strip()
    if cm not in VALID:
        illegal.append((r["protocol_id"], cm))
print("非法 id_code 数:", len(illegal))
for pid, cm in illegal[:20]:
    print("   ", pid, "->", repr(cm))

changed = [r for r in filled if (r["corrected_method"].strip() or "") != (r.get("current_primary") or "").strip()]
print("变更（corrected != current）: %d (%.1f%%)" % (len(changed), len(changed) / max(n_filled, 1) * 100))
same = [r for r in filled if (r["corrected_method"].strip() or "") == (r.get("current_primary") or "").strip()]
print("保持不变: %d" % len(same))

corr_dist = Counter(r["corrected_method"].strip() for r in filled)
print("修正后主方法分布 top12:", corr_dist.most_common(12))

# 抽样复核清单：变更 30 + 未变 10 + low 5
random.seed(20260902)
random.shuffle(changed); random.shuffle(same)
low = [r for r in filled if (r.get("confidence") or "").strip().lower() == "low"]
random.shuffle(low)
sample = changed[:30] + same[:10] + low[:5]
lines = ["# Step 8 L2 回填抽样复核清单（变更 30 + 未变 10 + low 5 = 45）", "",
         "| # | 类型 | protocol_id | current | corrected | conf | objective（前 140 字符） |",
         "|---|---|---|---|---|---|---|"]
kinds = {}
for r in sample:
    kinds[id(r)] = "low" if (r.get("confidence") or "").strip().lower() == "low" else ("same" if (r["corrected_method"].strip() or "") == (r.get("current_primary") or "").strip() else "changed")
for i, r in enumerate(sample, 1):
    k = kinds[id(r)]
    lines.append(f"| {i} | {k} | {r['protocol_id']} | {r.get('current_primary','')} | {r['corrected_method'].strip()} | {r.get('confidence','')} | {(r.get('objective') or '')[:140].replace(chr(10),' ').replace('|','/')} |")
open(os.path.join(OUT, "step8_review_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step8_review_sample.md, n=", len(sample))

# 统计落盘
stat = {
    "total": len(rows), "filled": n_filled, "fill_rate": round(n_filled / len(rows) * 100, 1),
    "confidence": dict(conf), "illegal": len(illegal),
    "changed": len(changed), "changed_pct": round(len(changed) / max(n_filled, 1) * 100, 1),
    "corrected_top": corr_dist.most_common(15),
}
json.dump(stat, open(os.path.join(OUT, "step8_validation_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved step8_validation_stats.json")
