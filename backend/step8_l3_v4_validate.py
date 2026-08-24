# Step 8 L3 v4（代理第四轮）独立验收：v3↔v4 diff + 去向分布 + M13 误杀核查 + 分层抽检
import os, json, csv, random
from collections import Counter

V3 = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v3.csv"
V4 = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v4.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))
VALID = {e["id_code"] for e in entities} | {"INV-REVIEW", "SUP-BIOINFO"}

def load(p):
    rows = {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["protocol_id"]] = r
    return rows

r3, r4 = load(V3), load(V4)
print("v3 行:", len(r3), "| v4 行:", len(r4), "| 交集:", len(set(r3) & set(r4)))

# 非法 ID（v4）
illegal = [(pid, r4[pid]["corrected_method"]) for pid in r4 if (r4[pid]["corrected_method"] or "").strip() and r4[pid]["corrected_method"].strip() not in VALID]
print("v4 非法 ID:", len(illegal))

# 越界检测：非四类行是否被改
FOUR = ("M13", "M51", "SUP-BIOINFO", "INV-REVIEW")
changed = [(pid, r3[pid]["corrected_method"], r4[pid]["corrected_method"])
           for pid in r4 if (r3[pid]["corrected_method"] or "").strip() != (r4[pid]["corrected_method"] or "").strip()]
print("v3→v4 变更总条数:", len(changed))
out_of_scope = [(p, a, b) for p, a, b in changed if (a or "").strip() not in FOUR]
print("越界变更（非四类源被改）:", len(out_of_scope))
for p, a, b in out_of_scope[:10]:
    print("   ", p, repr(a), "->", repr(b))

# 四类去向分布
print("\n=== 四类去向分布 ===")
for src in FOUR:
    mov = [(p, b) for p, a, b in changed if (a or "").strip() == src]
    dst = Counter(b.strip() or "(留空)" for _, b in mov)
    print("%s %d 条 → top10: %s" % (src, len(mov), dst.most_common(10)))

# M13 误杀核查：v3 M13 中 objective 含病毒测序关键词的，v4 去哪了
print("\n=== M13 误杀核查（原 M13 中含 virus/sequencing 词的）===")
vir_kw = ["virus", "viral", "sars-cov-2", "covid", "dengue", "zika", "ebola", "influenza", "genome sequencing", "wgs", "amplicon", "consensus"]
suspect = []
for p, a, b in changed:
    if (a or "").strip() == "M13":
        t = ((r4[p]["objective"] or "") + " " + (r4[p]["protocol_name"] or "")).lower()
        if any(k in t for k in vir_kw):
            suspect.append((p, b.strip() or "(留空)", (r4[p]["protocol_name"] or "")[:50]))
print("原 M13 中含病毒/测序词条数:", len(suspect))
for p, b, n in suspect[:15]:
    print("  [%s] %s -> %s" % (p, n, b))

# 模板句 + 前缀
BLACK = ["当前文本不足以在 73 个合法 Method 中可靠确定唯一主方法",
         "文本只说明", "协议确有显微/成像操作", "文本描述的是计算流程",
         "文本明确涉及测序文库", "文本确认存在细胞培养", "文本核心是动物体内"]
hit = sum(1 for pid in r4 if any(b in (r4[pid].get("note") or "") for b in BLACK))
print("\n禁用模板句命中:", hit)
pref = Counter((r4[pid].get("note") or "").strip()[:40] for pid in r4)
print("最大前缀重复: %d (%.2f%%)" % (max(pref.values()), max(pref.values()) / len(r4) * 100))

# 分层抽检：M13移出 15 + M51保留 10 + SUP保留 10 + INV保留 10 = 45
random.seed(20260824)
m13_out = [(p, r4[p]) for p, a, b in changed if (a or "").strip() == "M13"]
m51_keep = [(p, r4[p]) for p in r4 if (r4[p]["corrected_method"] or "").strip() == "M51"]
sup_keep = [(p, r4[p]) for p in r4 if (r4[p]["corrected_method"] or "").strip() == "SUP-BIOINFO"]
inv_keep = [(p, r4[p]) for p in r4 if (r4[p]["corrected_method"] or "").strip() == "INV-REVIEW"]
random.shuffle(m13_out); random.shuffle(m51_keep); random.shuffle(sup_keep); random.shuffle(inv_keep)
sample = m13_out[:15] + m51_keep[:10] + sup_keep[:10] + inv_keep[:10]
lines = ["# Step 8 L3 v4 独立验收抽样（M13移出 15 + M51 10 + SUP 10 + INV 10 = 45）", "",
         "| # | 类型 | protocol_id | v4判定 | conf | name | objective（前 100 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, (pid, r) in enumerate(sample, 1):
    cm = r["corrected_method"].strip() or "(留空)"
    if cm == "M51": k = "m51"
    elif cm == "SUP-BIOINFO": k = "sup"
    elif cm == "INV-REVIEW": k = "inv"
    else: k = "m13_out"
    lines.append(f"| {i} | {k} | {pid} | {cm} | {r.get('confidence','')} | {(r.get('protocol_name') or '')[:32].replace('|','/')} | {(r.get('objective') or '')[:100].replace(chr(10),' ').replace('|','/')} |")
open(os.path.join(OUT, "step8_l3_v4_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step8_l3_v4_sample.md, n=", len(sample))

stat = {
    "v3": len(r3), "v4": len(r4), "illegal": len(illegal), "changed": len(changed),
    "out_of_scope": len(out_of_scope), "m13_suspect": len(suspect),
    "blacklist_hit": hit, "max_prefix": max(pref.values()),
}
json.dump(stat, open(os.path.join(OUT, "step8_l3_v4_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved step8_l3_v4_stats.json")
