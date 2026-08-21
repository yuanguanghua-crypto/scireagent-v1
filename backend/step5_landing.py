# Step 5 C 分层落地：L1/L2 候选表生成 + 分布统计 + 抽样预览（零写库）
import os, json, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")
from collections import Counter

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
layers = json.load(open(os.path.join(OUT, "step4_layers_v07.json"), encoding="utf-8"))
signals = json.load(open(os.path.join(OUT, "step4_signals_v07.json"), encoding="utf-8"))
LEX = json.load(open(os.path.join(OUT, "method_signal_lexicon_v02.json"), encoding="utf-8"))["methods"]

# Method id -> application（词典源）
app_of = {}
for m in LEX:
    app_of[m["id"]] = m.get("app")
for extra in [("NEW-GibsonAssembly", "A5"), ("NEW-SmallMoleculeSynthesis", "A12b"),
              ("NEW-UbiquitinationAssay", "A13"), ("NEW-TissueClearing", "A9"),
              ("NEW-BindingAssay", "A13"), ("NEW-BioorthogonalLabeling", "A13")]:
    app_of[extra[0]] = extra[1]

VALID_EX = {"SUP-BIOINFO", "INV-REVIEW"}
cands = {}
for pid, layer in layers.items():
    if layer not in ("L1_HIGH", "L2_MID"):
        continue
    v = signals[str(pid)]
    methods = [m for m in v["methods"] if m not in VALID_EX]
    cands[str(pid)] = {
        "primary": v["primary"],
        "app": app_of.get(v["primary"]),
        "methods": methods,
        "layer": layer,
        "n_methods": len(methods),
    }
json.dump(cands, open(os.path.join(OUT, "step5_landing_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)

# 统计
n = len(cands)
l1 = sum(1 for c in cands.values() if c["layer"] == "L1_HIGH")
l2 = n - l1
prim_dist = Counter(c["primary"] for c in cands.values())
app_dist = Counter(c["app"] for c in cands.values() if c["app"])
multi = sum(1 for c in cands.values() if c["n_methods"] >= 2)
print("候选协议总数:", n, "L1:", l1, "L2:", l2, "多方法:", multi)
print("top primary:", prim_dist.most_common(12))
print("app 分布:", app_dist.most_common(14))

lines = ["# Step 5 C 分层落地：候选表统计", "",
         f"- 候选协议总数：**{n}**（L1 高置信 {l1} + L2 中置信 {l2}）；多方法协议：{multi}",
         "",
         "## 主方法分布（top 12）", "",
         "| Method | 候选数 | | Method | 候选数 |",
         "|---|---|---|---|---|"]
top = prim_dist.most_common(24)
half = (len(top) + 1) // 2
for i in range(half):
    l = top[i]; r = top[i + half] if i + half < len(top) else None
    lines.append("| %s | %d | | %s | %s |" % (l[0], l[1], r[0] if r else "", r[1] if r else ""))
lines += ["", "## Application 分布（top 14）", "", "| Application | 候选数 | | Application | 候选数 |", "|---|---|---|---|---|"]
topa = app_dist.most_common(28)
half = (len(topa) + 1) // 2
for i in range(half):
    l = topa[i]; r = topa[i + half] if i + half < len(topa) else None
    lines.append("| %s | %d | | %s | %s |" % (l[0], l[1], r[0] if r else "", r[1] if r else ""))
open(os.path.join(OUT, "step5_landing_stats.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step5_landing_candidates.json + step5_landing_stats.md")

# 抽样预览 15 条（L1 10 + L2 5）
random.seed(20260830)
p1 = [pid for pid, c in cands.items() if c["layer"] == "L1_HIGH"]
p2 = [pid for pid, c in cands.items() if c["layer"] == "L2_MID"]
random.shuffle(p1); random.shuffle(p2)
sample = p1[:10] + p2[:5]
objs = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "name"))
lines = ["# Step 5 候选表抽样预览（L1 10 + L2 5）", "",
         "| # | 层 | 协议名 | primary | 全部方法 | objective（前 140 字符） |",
         "|---|---|---|---|---|---|"]
for i, pid in enumerate(sample, 1):
    c = cands[pid]
    sigs = "; ".join(c["methods"]) if c["methods"] else "-"
    lines.append(f"| {i} | {c['layer'][:7]} | {(names.get(int(pid)) or '?')[:42]} | {c['primary']} | {sigs[:55]} | {(objs.get(int(pid)) or '')[:140].replace('|','/').replace(chr(10),' ')} |")
open(os.path.join(OUT, "step5_landing_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step5_landing_sample.md")
