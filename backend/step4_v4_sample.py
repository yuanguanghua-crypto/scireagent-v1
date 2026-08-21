# v0.4.1 抽样 30 条（单信号 12 / 多op 10 / 无信号 8）判定 primary precision
import os, json, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
signals = json.load(open(os.path.join(OUT, "step4_signals_v05.json"), encoding="utf-8"))
random.seed(20260826)
VALID = {"SUP-BIOINFO", "INV-REVIEW"}

p_single = [pid for pid, v in signals.items()
            if v["primary"] and v["primary"] not in VALID
            and len([x for x in v["op"] if x not in VALID]) == 1]
p_multi = [pid for pid, v in signals.items()
           if len([x for x in v["op"] if x not in VALID]) >= 2]
p_nosig = [pid for pid, v in signals.items() if not v["primary"]]
random.shuffle(p_single); random.shuffle(p_multi); random.shuffle(p_nosig)
sample = p_single[:12] + p_multi[:10] + p_nosig[:8]
seen = set(); sample = [x for x in sample if not (x in seen or seen.add(x))]

objs = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=[int(x) for x in sample]).values_list("id", "name"))

lines = ["# v0.5 抽样 30 条（单信号 12 / 多op 10 / 无信号 8）——primary precision 判定", "",
         "| # | 类型 | 协议名 | primary | op 命中 | 全部信号 | objective（前 170 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, pid in enumerate(sample, 1):
    v = signals[pid]
    kind = "multi" if pid in p_multi else ("nosig" if pid in p_nosig else "single")
    op_s = "; ".join(v["op"]) if v["op"] else "-"
    sigs = "; ".join(v["methods"]) if v["methods"] else "-"
    obj = (objs.get(int(pid)) or "")[:170].replace("|", "/").replace("\n", " ")
    lines.append(f"| {i} | {kind} | {(names.get(int(pid)) or '?')[:42]} | {v['primary'] or '-'} | {op_s[:50]} | {sigs[:60]} | {obj} |")
open(os.path.join(OUT, "step4_v05_sample.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_v05_sample.md, n=", len(sample))
