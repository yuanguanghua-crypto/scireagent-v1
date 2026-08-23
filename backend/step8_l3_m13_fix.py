# Step 8 L3 M13 修正表：539 条分类（关键词粗分 → 每类正确处置）
import os, json, csv, random
from collections import Counter

SRC = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v3.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)

m13 = [r for r in rows if (r.get("corrected_method") or "").strip() == "M13"]
print("M13 条数:", len(m13))

# 关键词分类（按优先级）
def classify(r):
    t = ((r.get("objective") or "") + " " + (r.get("protocol_name") or "")).lower()
    if any(k in t for k in ["viral genome", "virus genome", "viral sequencing", "virus sequencing", "sars-cov-2", "covid", "consensus genome", "whole-genome sequencing of virus", "viral metagenom", "hiv-1 genome", "influenza virus", "dengue", "zika", "ebola", "coronavirus genome", "viral rna sequencing", "amplicon-based sequencing", "tiled amplicon", "viral outbreak"]):
        return "A_病毒测序（保留 M13）"
    if any(k in t for k in ["enzyme", "kinase", "transferase", "hydrolase", "oxidase", "reductase", "catalase", "atpase", "protease activit", "activity assay", "enzymatic activ", "enzyme activ", "dehydrogenase", "phosphatase", "lysase", "synthase activ", "zymogram"]):
        return "B_酶活测定（→NEW-EnzymeAssay 提名）"
    if any(k in t for k in ["plant", "chloroplast", "photosynth", "root", "leaf", "arabidopsis", "crop", "seedling", "rice", "maize", "wheat", "soybean", "mesophyll", "stomata", "xylem", "phloem", "pollination", "pollen", "seed"]):
        return "C_植物生化（→NEW-PlantBiochemAssay 或留空）"
    if any(k in t for k in ["lipid", "fatty acid", "phospholipid", "cholesterol", "squalene", "triglyceride", "triacylglycerol", "sterol", "phosphoinositide", "pi4p", "sphingolipid", "ceramide", "nile red", "bodipy", "membrane lipid", "wax ester"]):
        return "D_脂质定量（→留空提名 NEW-LipidAssay 或生化）"
    if any(k in t for k in ["invadopodia", "migration", "proliferation", "invasion assay", "wound healing", "transwell", "chemotaxis", "motility", "swimming", "swarming", "twitching"]):
        return "E_细胞/微生物运动功能（→M32/M46/M24 或留空）"
    if any(k in t for k in ["dissection", "anatomy", "nerve", "brain", "tissue harvest", "organ harvest", "perfusion", "surgery", "implant", "injection", "cannula"]):
        return "F_解剖/体内操作（→M50/M49）"
    if any(k in t for k in ["quantif", "measurement", "determination", "detection", "assay", "spectrophotometr", "colorimetr", "fluorometr", "hplc", "gc-ms", "lc-ms", "titration", "nano", "nanoparticle", "microparticle", "synthesis", "preparation", "isolation", "purification", "extraction"]):
        return "G_生化定量/制备/提取（→留空或按具体重映射）"
    return "H_其他（逐条人工）"

c = Counter(classify(r) for r in m13)
print("分类分布:")
for k, v in c.most_common():
    print("  %s: %d" % (k, v))

# 每类落盘：id/name/objective + 处置
lines = ["# Step 8 L3 M13 修正表（539 条分类，每类给正确处置）", "",
         "| 分类 | 数量 | 处置 |",
         "|---|---|---|"]
for k, v in c.most_common():
    lines.append("| %s | %d | 见下表 |" % (k, v))
lines.append("")
for k, v in c.most_common():
    lines.append("## %s（%d 条）" % (k, v))
    lines.append("")
    lines.append("| protocol_id | name | 处置建议 |")
    lines.append("|---|---|---|")
    for r in [x for x in m13 if classify(x) == k]:
        lines.append("| %s | %s | — |" % (r["protocol_id"], (r["protocol_name"] or "")[:50].replace("|", "/")))
    lines.append("")
open(os.path.join(OUT, "step8_l3_m13_fixlist.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step8_l3_m13_fixlist.md")

# 每类抽样 4 条供人工复核分类质量
random.seed(20260824)
print("\n=== 每类抽样 4 条复核 ===")
for k in c:
    pool = [x for x in m13 if classify(x) == k]
    random.shuffle(pool)
    print("-- %s --" % k)
    for r in pool[:4]:
        print("  [%s] %s" % (r["protocol_id"], (r["protocol_name"] or "")[:45]))
        print("     ", (r["objective"] or "")[:100].replace(chr(10), " "))
