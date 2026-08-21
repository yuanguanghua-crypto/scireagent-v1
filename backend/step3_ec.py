# Step 3 EC：名义统计 + 分层抽样清单（供专家逐条语义校验）
import os, json, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
assign = json.load(open(os.path.join(OUT, "step3_cluster_assign.json"), encoding="utf-8"))
cmap = json.load(open(os.path.join(OUT, "step3_cluster_map.json"), encoding="utf-8"))["clusters"]

# 簇规模
sizes = {k: len(v) for k, v in assign.items()}

# ---------- 1) 名义统计 ----------
stat = {}
for cl, meta in cmap.items():
    st = meta["status"]
    stat.setdefault(st, 0)
    stat[st] += sizes[cl]
total = sum(assign.values(), [])
n_total = len(total)
n_valid = stat.get("valid", 0)
n_boundary = stat.get("boundary", 0)
n_supporting = stat.get("supporting", 0)
n_invalid = stat.get("invalid", 0)
n_eligible = n_total - n_invalid  # eligible: 排除综述/模板等无方法语义
n_covered = n_valid + n_boundary  # 计入 boundary，不含 supporting

lines = ["# Step 3 Entity Completeness 名义统计（未抽样校验）", "",
         f"- 总协议数：{n_total}",
         f"- valid 簇：{stat.get('valid',0)} / boundary：{stat.get('boundary',0)} / supporting：{stat.get('supporting',0)} / invalid：{stat.get('invalid',0)}",
         "",
         f"| 指标 | 公式 | 值 |",
         f"|---|---|---|",
         f"| L1 Corpus Coverage | 14065/14065 | 100% |",
         f"| eligible（可做 Method 映射） | 总 - invalid(综述/模板 {n_invalid}) | {n_eligible} |",
         f"| EC 名义（含 boundary，不含 supporting） | {n_covered}/{n_eligible} | {n_covered/n_eligible*100:.2f}% |",
         f"| EC 名义（排除 boundary） | {n_valid}/{n_eligible} | {n_valid/n_eligible*100:.2f}% |",
         f"| MultiMethod Rate（单簇硬分配） | 0/{n_covered} | 0%（须抽样文本信号验证 M:N） |",
         "",
         "> ⚠️ 名义 EC≈99% 是聚类自洽的假象：分子分母来自同一 KMeans 分配。真实 Valid Method Coverage 必须靠分层抽样逐条文本校验。",
         ""]
md = "\n".join(lines)
open(os.path.join(OUT, "step3_ec_nominal.md"), "w", encoding="utf-8").write(md)
print("nominal stats:", stat, "eligible:", n_eligible, "EC:", round(n_covered/n_eligible*100, 2), "%")

# ---------- 2) 分层抽样 ----------
random.seed(20260821)
STRATA = [
    ("large>250",   ["C15", "C37", "C40", "C61", "C47"], 3),
    ("medium100-250", ["C13", "C67", "C78", "C22", "C33", "C42", "C60", "C23", "C31"], 4),
    ("small<100",   ["C73", "C65", "C74", "C63", "C14", "C45", "C51", "C77", "C79"], 3),
    ("cross_app",   ["C29", "C43", "C38", "C76", "C54", "C48"], 3),
    ("boundary",    ["C75", "C8"], 2),
    ("invalid",     ["C47", "C35"], 2),
    ("split",       ["C60", "C22", "C42"], 2),
    ("new_candidate", ["C34", "C72", "C49", "C77", "C79"], 3),
]
picked = []   # (cluster, pid)
picked_clusters = set()
for layer, cl_list, n in STRATA:
    got = 0
    for cl in cl_list:
        if got >= n:
            break
        if cl in picked_clusters:
            continue
        pid = random.choice(assign[cl])
        picked.append((layer, cl, pid))
        picked_clusters.add(cl)
        got += 1
# 全局随机兜底 10 条
all_ids = [pid for cl in assign.values() for pid in cl]
picked_ids = {p[2] for p in picked}
random.shuffle(all_ids)
extra = 0
for pid in all_ids:
    if extra >= 10:
        break
    if pid in picked_ids:
        continue
    picked.append(("random_global", "?", pid))
    picked_ids.add(pid)
    extra += 1

# 查协议文本
pid_map = {p[2]: p for p in picked}
objs = dict(Protocol.objects.filter(id__in=list(picked_ids)).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=list(picked_ids)).values_list("id", "name"))

lines = ["# Step 3 分层抽样清单（待专家逐条语义校验）", "",
         "| # | 层 | 簇 | Method | status | 协议名 | objective（前 260 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, (layer, cl, pid) in enumerate(picked, 1):
    meta = cmap.get(cl, {})
    method = (meta.get("method") or "-") if cl != "?" else "-"
    status = (meta.get("status") or "?") if cl != "?" else "?"
    obj = (objs.get(pid) or "")[:260].replace("|", "/").replace("\n", " ")
    name = (names.get(pid) or "?")[:50]
    lines.append(f"| {i} | {layer} | {cl} | {method} | {status} | {name} | {obj} |")
md = "\n".join(lines)
open(os.path.join(OUT, "step3_sample.md"), "w", encoding="utf-8").write(md)
print("sample size:", len(picked), "-> saved step3_sample.md")
