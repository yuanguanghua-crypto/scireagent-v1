# Step 8 L3 A+C 落地：A=候选草稿清单（非 M13）+ C=LLM 收口工作文件（M13+留空+SUP+INV）
import os, json, csv
from collections import Counter

SRC = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v3.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)
print("总记录:", len(rows))

def classify_m13(r):
    t = ((r.get("objective") or "") + " " + (r.get("protocol_name") or "")).lower()
    if any(k in t for k in ["viral genome", "virus genome", "viral sequencing", "virus sequencing", "sars-cov-2", "consensus genome", "viral metagenom", "hiv-1 genome", "influenza virus", "dengue", "zika", "ebola", "coronavirus genome", "viral rna sequencing", "amplicon-based sequencing", "tiled amplicon", "viral outbreak"]):
        return "病毒测序(保留M13候选)"
    if any(k in t for k in ["enzyme", "kinase", "transferase", "hydrolase", "oxidase", "reductase", "catalase", "atpase", "protease activit", "activity assay", "enzymatic activ", "enzyme activ", "dehydrogenase", "phosphatase", "zymogram"]):
        return "酶活测定(NEW-EnzymeAssay候选)"
    if any(k in t for k in ["plant", "chloroplast", "photosynth", "root", "leaf", "arabidopsis", "crop", "seedling", "rice", "maize", "wheat", "soybean", "mesophyll", "stomata", "pollen", "seed"]):
        return "植物生化(NEW-PlantBiochemAssay候选)"
    if any(k in t for k in ["lipid", "fatty acid", "phospholipid", "cholesterol", "squalene", "triglyceride", "triacylglycerol", "sterol", "phosphoinositide", "pi4p", "sphingolipid", "ceramide", "nile red", "bodipy", "membrane lipid"]):
        return "脂质定量(NEW-LipidAssay候选)"
    if any(k in t for k in ["dissection", "anatomy", "nerve", "tissue harvest", "organ harvest", "perfusion", "surgery", "implant", "injection", "cannula", "anesthesia"]):
        return "解剖/体内(M50/M49候选)"
    if any(k in t for k in ["invadopodia", "migration", "proliferation", "invasion assay", "wound healing", "transwell", "chemotaxis", "motility", "swimming", "swarming", "twitching"]):
        return "运动功能(M32/M46/M24候选)"
    if any(k in t for k in ["quantif", "measurement", "determination", "detection", "assay", "spectrophotometr", "colorimetr", "fluorometr", "hplc", "gc-ms", "lc-ms", "titration", "nano", "nanoparticle", "microparticle", "synthesis", "preparation", "isolation", "purification", "extraction"]):
        return "生化定量/制备/提取(逐条判断)"
    return "其他(逐条判断)"

method_non_m13 = [r for r in rows if (r.get("corrected_method") or "").strip() not in ("", "INV-REVIEW", "SUP-BIOINFO", "M13")]
m13 = [r for r in rows if (r.get("corrected_method") or "").strip() == "M13"]
blank = [r for r in rows if not (r.get("corrected_method") or "").strip()]
sup = [r for r in rows if (r.get("corrected_method") or "").strip() == "SUP-BIOINFO"]
inv = [r for r in rows if (r.get("corrected_method") or "").strip() == "INV-REVIEW"]
print("非M13 Method: %d | M13: %d | 留空: %d | SUP: %d | INV: %d" %
      (len(method_non_m13), len(m13), len(blank), len(sup), len(inv)))

# ---- A：候选草稿清单（非 M13 Method，建议 status=review） ----
csv_a = os.path.join(OUT, "L3_candidate_draft_v3A.csv")
with open(csv_a, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["protocol_id", "protocol_name", "objective", "corrected_method", "confidence", "note", "draft_status"])
    for r in method_non_m13:
        w.writerow([r["protocol_id"], r["protocol_name"], r["objective"],
                    r["corrected_method"].strip(), r["confidence"], r["note"], "review"])
print("saved L3_candidate_draft_v3A.csv (%d)" % len(method_non_m13))

# ---- C：LLM 收口工作文件（M13 + 留空 + SUP + INV，带提示） ----
csv_c = os.path.join(OUT, "L3_curation_workfile_llm_c1.csv")
with open(csv_c, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["protocol_id", "protocol_name", "objective", "current_primary",
                "current_method_name", "hint", "corrected_method", "confidence", "note"])
    n_m13 = n_blank = n_sup = n_inv = 0
    for r in m13:
        hint = "M13误配需重判 | " + classify_m13(r)
        w.writerow([r["protocol_id"], r["protocol_name"], r["objective"], "M13", "Viral Genome Sequencing", hint, "", "", ""])
        n_m13 += 1
    for r in blank:
        w.writerow([r["protocol_id"], r["protocol_name"], r["objective"], "", "", "留空需重判：可能可判", "", "", ""])
        n_blank += 1
    for r in sup:
        w.writerow([r["protocol_id"], r["protocol_name"], r["objective"], "SUP-BIOINFO", "Bioinformatics", "SUP需复核：仅纯计算/软件/数据才保留SUP", "", "", ""])
        n_sup += 1
    for r in inv:
        w.writerow([r["protocol_id"], r["protocol_name"], r["objective"], "INV-REVIEW", "Review", "INV需复核：仅真综述/临床才保留INV", "", "", ""])
        n_inv += 1
print("saved L3_curation_workfile_llm_c1.csv (M13 %d + 留空 %d + SUP %d + INV %d = %d)" %
      (n_m13, n_blank, n_sup, n_inv, n_m13 + n_blank + n_sup + n_inv))

# M13 分类分布（供 LLM 提示参考）
cc = Counter(classify_m13(r) for r in m13)
print("M13 分类提示分布:", dict(cc.most_common()))

stat = {"method_non_m13": len(method_non_m13), "m13": len(m13), "blank": len(blank),
        "sup": len(sup), "inv": len(inv), "m13_cat": dict(cc)}
json.dump(stat, open(os.path.join(OUT, "step8_l3_ac_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved step8_l3_ac_stats.json")
