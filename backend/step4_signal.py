# Step 4 方法信号抽取 v0.1：词典匹配 + 小批量验证（10 随机 + 6 目标案例）
import os, json, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
LEX = json.load(open(os.path.join(OUT, "method_signal_lexicon_v02.json"), encoding="utf-8"))["methods"]

def match_methods(text):
    t = text.lower()
    hits = []
    for m in LEX:
        for p in m["patterns"]:
            if p in t:
                hits.append(m)
                break
    return hits

def fmt(pid, name, obj, hits):
    sig = "; ".join("%s(%s)" % (h["id"], h["name"]) for h in hits) if hits else "-无命中-"
    return "| %d | %s | %s | %s |" % (
        pid, (name or "?")[:46], (obj or "")[:150].replace("|", "/").replace("\n", " "), sig)

lines = ["# Step 4 方法信号抽取 v0.2 小批量验证（修正 esc/fish/purification/漏检）", "",
         "> 词典：`method_signal_lexicon_v02.json`（60 条目）。匹配：name+objective 小写子串，可多方法命中。",
         ""]

# ---- A) 目标案例（验证能否纠正 Step 3 已知错配）----
lines += ["## A. 已知案例验证（词典能否纠正错配）", "", "| id | 协议名 | objective | 命中 Method |", "|---|---|---|---|"]
targets = ["padlock probe", "DSP-crosslinking", "Skd3", "Carboxypeptidase", "PrestoBlue", "Influenza A Virus Infection"]
for kw in targets:
    qs = Protocol.objects.filter(objective__icontains=kw) | Protocol.objects.filter(name__icontains=kw)
    p = qs.first()
    if not p:
        lines.append("| - | (未找到) %s | | |" % kw)
        continue
    hits = match_methods((p.name or "") + " . " + (p.objective or ""))
    lines.append(fmt(p.id, p.name, p.objective, hits))

# ---- B) 随机 10 条 ----
random.seed(20260823)
total_ids = list(Protocol.objects.values_list("id", flat=True))
sample_ids = random.sample(total_ids, 10)
objs = dict(Protocol.objects.filter(id__in=sample_ids).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=sample_ids).values_list("id", "name"))
lines += ["", "## B. 随机 10 条", "", "| id | 协议名 | objective | 命中 Method |", "|---|---|---|---|"]
for pid in sample_ids:
    hits = match_methods((names.get(pid) or "") + " . " + (objs.get(pid) or ""))
    lines.append(fmt(pid, names.get(pid), objs.get(pid), hits))

open(os.path.join(OUT, "step4_signal_test_v02.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_signal_test_v02.md")
