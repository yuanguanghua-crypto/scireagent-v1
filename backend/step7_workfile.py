# 生成 L2 人工收口工作文件（CSV）+ Method 名单附录（md）
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

# Method id -> name（entities）
name_of = {e["id_code"]: e["name"] for e in entities}
type_of = {e["id_code"]: e["method_type"] for e in entities}
app_of = {e["id_code"]: e["app_code"] for e in entities}

l2_ids = [int(pid) for pid, l in layers.items() if l == "L2_MID"]
print("L2 条数:", len(l2_ids))

objs = dict(Protocol.objects.filter(id__in=l2_ids).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=l2_ids).values_list("id", "name"))

# ---- CSV 工作文件 ----
csv_path = os.path.join(OUT, "L2_curation_workfile.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["protocol_id", "protocol_name", "objective", "current_primary",
                "current_method_name", "corrected_method", "confidence", "note"])
    for pid in l2_ids:
        v = signals[str(pid)]
        cur = v["primary"] or ""
        w.writerow([pid, names.get(pid, ""), objs.get(pid, ""), cur,
                    name_of.get(cur, ""), "", "", ""])
print("saved L2_curation_workfile.csv")

# ---- Method 名单附录 md ----
lines = ["# L2 人工收口：Method 候选名单（73 个，判定目标集）", "",
         "| id_code | 英文规范名 | 类型 | 所属 Application | 定义 |",
         "|---|---|---|---|---|"]
for e in entities:
    lines.append(f"| {e['id_code']} | {e['name']} | {e['method_type']} | {e['app_code']} | {e['definition']} |")
md = "\n".join(lines)
open(os.path.join(OUT, "L2_method_roster_appendix.md"), "w", encoding="utf-8").write(md)
print("saved L2_method_roster_appendix.md（%d 个 Method）" % len(entities))
