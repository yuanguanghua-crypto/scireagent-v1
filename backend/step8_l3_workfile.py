# 生成 L3 人工收口工作文件（CSV）+ 补充专名速查表（md）
# L3 = 无信号（3,072）+ SUP-BIOINFO primary（663），共 3,735 条
# 与 L2 不同：L3 大多无自动标注，人工需从 objective 文本识别主方法
import os, json, csv
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
layers = json.load(open(os.path.join(OUT, "step4_layers_v08.json"), encoding="utf-8"))
signals = json.load(open(os.path.join(OUT, "step4_signals_v08.json"), encoding="utf-8"))
entities = json.load(open(os.path.join(OUT, "step6_method_entities.json"), encoding="utf-8"))

name_of = {e["id_code"]: e["name"] for e in entities}

l3_ids = [int(pid) for pid, l in layers.items() if l == "L3_OPEN"]
l3_ids.sort()
print("L3 条数:", len(l3_ids))

objs = dict(Protocol.objects.filter(id__in=l3_ids).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=l3_ids).values_list("id", "name"))

# ---- CSV 工作文件 ----
csv_path = os.path.join(OUT, "L3_curation_workfile.csv")
n_no = n_sup = 0
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["protocol_id", "protocol_name", "objective", "current_primary",
                "current_method_name", "corrected_method", "confidence", "note"])
    for pid in l3_ids:
        v = signals.get(str(pid), {})
        cur = v.get("primary") or ""
        obj = objs.get(pid, "") or ""
        if cur == "SUP-BIOINFO":
            cur_name = "Bioinformatics (Supporting)"
            n_sup += 1
        else:
            cur_name = ""
            n_no += 1
        note = "(objective 为空，仅凭 name 判定)" if not obj.strip() else ""
        w.writerow([pid, names.get(pid, ""), obj, cur or "",
                    cur_name, "", "", note])
print("saved L3_curation_workfile.csv（无信号 %d / SUP %d）" % (n_no, n_sup))

# ---- 补充专名速查表（L3 探针暴露的高价值专名，提示人工勿留空） ----
terms = [
    ("protoplast", "原生质体制备/转化", "NEW-PlantCellWork / M21"),
    ("islet isolation", "胰岛分离", "NEW-TissueIsolation（候选）"),
    ("tissue clearing / iDISCO", "组织透明化", "NEW-TissueClearing"),
    ("luminex", "多重免疫检测", "M28 Immunoassay"),
    ("titration", "电位/酸碱滴定", "M13 Analytical Chemistry"),
    ("transplantation", "组织/细胞移植", "M50 In-vivo Models"),
    ("conditioned medium", "条件培养基", "M24 Cell Culture"),
    ("receptor binding", "受体结合实验", "NEW-BindingAssay"),
    ("GRAB sensor", "GRAB 成像探针", "M32 Imaging"),
    ("click chemistry", "点击化学标记", "NEW-BioorthogonalLabeling"),
    ("electroporation", "电穿孔转染", "M21 Transfection"),
    ("organoid", "类器官培养", "M24 Cell Culture"),
    ("xenograft", "异种移植瘤", "M50 In-vivo Models"),
    ("microdialysis", "微透析", "M49 Perfusion"),
    ("patch clamp", "膜片钳", "M53 Electrophysiology"),
    ("GST pull-down", "蛋白互作", "M39 Immunoprecipitation"),
    ("yeast two-hybrid", "酵母双杂交", "NEW-ProteinInteraction"),
    ("BIAcore / SPR", "表面等离子共振", "NEW-BindingAssay"),
    ("chromatin immunoprecipitation", "染色质免疫沉淀", "M14 Epigenetics"),
    ("single-molecule FRET", "单分子 FRET", "NEW-SingleMolecule"),
    ("enzyme-linked lectin", "凝集素 ELISA", "M28 Immunoassay"),
    ("phage display", "噬菌体展示", "M45 Phage Display"),
    ("CRISPR screen", "CRISPR 筛选", "M19 Genome Editing"),
    ("RNA interference / siRNA", "RNAi 敲低", "NEW-RNAi"),
    ("mass photometry", "质光法", "M13 Analytical Chemistry"),
    ("seahorse", "线粒体压力测试", "NEW-MetabolicAssay"),
    ("zygotic injection", "受精卵注射", "NEW-EmbryoInjection"),
    ("caudal fin regeneration", "尾鳍再生", "M50 In-vivo Models"),
    ("behavioral test / open field", "行为学测试", "M51 Behavioral"),
    ("C. elegans lifespan", "线虫寿命实验", "M50 In-vivo Models"),
]
lines = ["# L3 补充专名速查表（词典未覆盖，人工判定时请勿留空）", "",
         "> L3 探针（20 条）实测：无信号层 70% 是真实方法协议，只是词典缺这些技术专名。",
         "> 命中下表专名时，按右侧建议方法判定；不确定时参考 73 Method 名单全文。", "",
         "| 专名/关键词 | 实验含义 | 建议 Method |",
         "|---|---|---|"]
for t, c, m in terms:
    lines.append(f"| {t} | {c} | {m} |")
md = "\n".join(lines)
open(os.path.join(OUT, "L3_curation_terms.md"), "w", encoding="utf-8").write(md)
print("saved L3_curation_terms.md（%d 个专名）" % len(terms))
