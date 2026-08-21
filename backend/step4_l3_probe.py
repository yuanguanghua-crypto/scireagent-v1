# L3 无信号层构成探针：抽 20 条分类（真漏检/边缘/观察生态）
import os, json, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
layers = json.load(open(os.path.join(OUT, "step4_layers_v06.json"), encoding="utf-8"))
signals = json.load(open(os.path.join(OUT, "step4_signals_v06.json"), encoding="utf-8"))
random.seed(20260828)

nosig_l3 = [pid for pid, l in layers.items() if l == "L3_OPEN" and not signals[pid]["primary"]]
random.shuffle(nosig_l3)
sample = nosig_l3[:20]
objs = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "name"))
lines = ["# L3 无信号构成探针（20 条）——判定：真方法漏检 / 边缘可接受 / 观察生态 / 其他", "",
         "| # | 协议名 | objective（前 150 字符） |", "|---|---|---|"]
for i, pid in enumerate(sample, 1):
    lines.append(f"| {i} | {(names.get(int(pid)) or '?')[:46]} | {(objs.get(int(pid)) or '')[:150].replace('|','/').replace(chr(10),' ')} |")
open(os.path.join(OUT, "step4_l3_probe.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_l3_probe.md, n=", len(sample))
