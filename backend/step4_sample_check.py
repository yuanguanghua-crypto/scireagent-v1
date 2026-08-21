# Step 4 全量后：20 条分层抽样（信号/无信号/多信号）供人工校验
import os, json, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
signals = json.load(open(os.path.join(OUT, "step4_signals_full.json"), encoding="utf-8"))
random.seed(20260824)

VALID = {"SUP-BIOINFO", "INV-REVIEW"}
p_signal = [pid for pid, v in signals.items() if v["primary"] and v["primary"] not in VALID]
p_nosig = [pid for pid, v in signals.items() if not v["primary"]]
p_multi = [pid for pid, v in signals.items()
           if len([m for m in v["methods"] if m not in VALID]) >= 2]
random.shuffle(p_signal); random.shuffle(p_nosig); random.shuffle(p_multi)
sample = (p_signal[:12] + p_nosig[:4] + p_multi[:4])
# 去重保序
seen = set(); sample = [x for x in sample if not (x in seen or seen.add(x))]

objs = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "name"))

lines = ["# Step 4 信号质量抽样（20 条：12 有信号 / 4 无信号 / 4 多信号）", "",
         "| # | 类型 | 协议名 | primary | 全部信号 | objective（前 160 字符） |",
         "|---|---|---|---|---|---|"]
for i, pid in enumerate(sample, 1):
    v = signals[pid]
    kind = "multi" if pid in p_multi else ("nosig" if pid in p_nosig else "signal")
    sigs = "; ".join(v["methods"]) if v["methods"] else "-"
    obj = (objs.get(int(pid)) or "")[:160].replace("|", "/").replace("\n", " ")
    lines.append(f"| {i} | {kind} | {(names.get(int(pid)) or '?')[:44]} | {v['primary'] or '-'} | {sigs[:70]} | {obj} |")
open(os.path.join(OUT, "step4_sample_check.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_sample_check.md, n=", len(sample))
