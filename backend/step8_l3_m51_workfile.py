# 生成 M51 微型第五轮工作文件（97 条，从 v4 提取）
import os, csv

V4 = r"C:\Users\yuankaifeng\Downloads\L3_curation_workfile_v4.csv"
OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"

rows = []
with open(V4, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)

m51 = [r for r in rows if (r.get("corrected_method") or "").strip() == "M51"]
print("v4 中 M51 条数:", len(m51))

# 非行为学词表（命中即移出提示）
NONBEH = ["culture", "expansion", "differentiat", "primary culture", "simulation",
          "coarse-grained", "molecular dynamics", "alignment", "hydrogel", "neurite",
          "pituitary", "gel", "sensor", "cell line", "organoid", "sphere",
          "transfection", "rna-seq", "sequencing", "bioinformatic", "software", "database"]

csv_path = os.path.join(OUT, "L3_curation_workfile_m51_v41.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["protocol_id", "protocol_name", "objective", "current_primary",
                "current_method_name", "hint", "corrected_method", "confidence", "note"])
    n_hint = 0
    for r in m51:
        t = ((r.get("objective") or "") + " " + (r.get("protocol_name") or "")).lower()
        hits = [k for k in NONBEH if k in t]
        hint = "疑似非行为学，命中: " + ", ".join(hits) if hits else "核对：是否动物/人体行为测试"
        if hits:
            n_hint += 1
        w.writerow([r["protocol_id"], r["protocol_name"], r["objective"], "M51",
                    "Behavioral Assessment", hint, "", "", ""])
print("saved L3_curation_workfile_m51_v41.csv（%d 条，其中 %d 条命中非行为学词表）" % (len(m51), n_hint))
