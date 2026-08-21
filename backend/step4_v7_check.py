# v0.7 新词质量抽查：v0.6 L3 → v0.7 有 primary 的协议抽 12 条判定
import os, json, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
layers6 = json.load(open(os.path.join(OUT, "step4_layers_v06.json"), encoding="utf-8"))
sig7 = json.load(open(os.path.join(OUT, "step4_signals_v07.json"), encoding="utf-8"))
random.seed(20260829)

# v0.6 L3 无信号 → v0.7 有 primary
moved = [pid for pid, l in layers6.items()
         if l == "L3_OPEN" and sig7[str(pid)]["primary"]]
random.shuffle(moved)
sample = moved[:12]
objs = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "name"))
lines = ["# v0.7 新词质量抽查（12 条：v0.6 无信号 → v0.7 命中）", "",
         "| # | 协议名 | primary | 全部信号 | objective（前 150 字符） |",
         "|---|---|---|---|---|"]
for i, pid in enumerate(sample, 1):
    v = sig7[str(pid)]
    sigs = "; ".join(v["methods"]) if v["methods"] else "-"
    lines.append(f"| {i} | {(names.get(int(pid)) or '?')[:44]} | {v['primary']} | {sigs[:60]} | {(objs.get(int(pid)) or '')[:150].replace('|','/').replace(chr(10),' ')} |")
open(os.path.join(OUT, "step4_v07_check.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_v07_check.md, n=", len(sample))
