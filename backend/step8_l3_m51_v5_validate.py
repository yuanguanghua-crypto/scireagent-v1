# Step 8 M51 微型第五轮验收：结构 + 保留/移出层 precision
import os, csv, json, random
from collections import Counter

M51 = r"C:\Users\yuankaifeng\Downloads\M51_rectified_v5.csv"
V4 = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v4.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
VALID = {e["id_code"] for e in entities} | {"INV-REVIEW", "SUP-BIOINFO"}

# v4 的 M51 97 条 protocol_id 集合
rows4 = []
with open(V4, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows4.append(r)
m51_ids_v4 = {r["protocol_id"] for r in rows4 if (r.get("corrected_method") or "").strip() == "M51"}
print("v4 M51 条数:", len(m51_ids_v4))

# 读 M51 修正文件
rows = []
with open(M51, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)
print("M51 修正文件行数:", len(rows), "| 列:", list(rows[0].keys()))

ids = {r["protocol_id"] for r in rows}
print("protocol_id 与 v4 M51 完全一致:", ids == m51_ids_v4)
print("v4 M51 中有但文件缺失:", len(m51_ids_v4 - ids), "| 文件有但 v4 没有:", len(ids - m51_ids_v4))

# 非法 ID
illegal = [(r["protocol_id"], r["corrected_method"]) for r in rows
           if (r.get("corrected_method") or "").strip() and r["corrected_method"].strip() not in VALID]
print("非法 ID:", len(illegal))
for p, c in illegal[:10]:
    print("   ", p, repr(c))

# 分布
dist = Counter((r.get("corrected_method") or "(留空)").strip() for r in rows)
print("分布:", dict(dist.most_common()))
keep_m51 = [r for r in rows if (r.get("corrected_method") or "").strip() == "M51"]
moved = [r for r in rows if (r.get("corrected_method") or "").strip() != "M51"]
print("保留 M51:", len(keep_m51), "| 移出:", len(moved))

# 点名案例
print("\n点名案例:")
for pid, expect in {"11646": "SUP-BIOINFO", "4429": "M26", "8776": "M32", "9925": "M26", "7727": "(留空)"}.items():
    for r in rows:
        if r["protocol_id"] == pid:
            got = r["corrected_method"].strip() or "(留空)"
            print("  %s: %s %s" % (pid, got, "OK" if got == expect else "MISMATCH 应 %s" % expect))
            break

# 抽样：保留 10 + 移出 10
random.seed(20260824)
random.shuffle(keep_m51); random.shuffle(moved)
sample = keep_m51[:10] + moved[:10]
lines = ["# M51 微型第五轮验收抽样（保留 10 + 移出 10 = 20）", "",
         "| # | 类型 | protocol_id | v5判定 | conf | name | objective（前 100 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, r in enumerate(sample, 1):
    cm = r["corrected_method"].strip() or "(留空)"
    k = "keep" if cm == "M51" else "moved"
    lines.append(f"| {i} | {k} | {r['protocol_id']} | {cm} | {r.get('confidence','')} | {(r.get('protocol_name') or '')[:32].replace('|','/')} | {(r.get('objective') or '')[:100].replace(chr(10),' ').replace('|','/')} |")
open(os.path.join(OUT, "step8_l3_m51_v5_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\nsaved step8_l3_m51_v5_sample.md, n=", len(sample))

stat = {"total": len(rows), "keep_m51": len(keep_m51), "moved": len(moved),
        "illegal": len(illegal), "dist": dict(dist)}
json.dump(stat, open(os.path.join(OUT, "step8_l3_m51_v5_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved step8_l3_m51_v5_stats.json")
