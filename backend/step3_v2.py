# Step 3 v2：子簇重聚类后协议级归属 + 名义 EC 重算 + 二次抽样
import sys, os, json
sys.path.insert(0, r"D:\emb3_venv\Lib\site-packages")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import numpy as np
from sklearn.cluster import KMeans
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
NPZ = os.path.join(OUT, "protocol_embeds.npz")
assign = json.load(open(os.path.join(OUT, "step3_cluster_assign.json"), encoding="utf-8"))
cmap = json.load(open(os.path.join(OUT, "step3_cluster_map.json"), encoding="utf-8"))["clusters"]

TARGET = {"C22": 3, "C60": 3, "C42": 2, "C35": 3, "C74": 2, "C29": 3}

# 子簇 -> (method, application, status, method_type, note)  专家判定（来自 step3_subcluster.md）
SUB_METHOD = {
    "C22-0": ("M38", "A11", "valid", "technique", "Western blot → M38"),
    "C22-1": ("NEW-SDS-PAGE", "A11", "valid", "technique", "SDS-PAGE/凝胶电泳；草案外新增候选"),
    "C22-2": ("M39", "A11", "valid", "technique", "IP/亲和分离/蛋白互作 → M39 Immunoprecipitation"),
    "C60-0": ("M05", "A2", "valid", "technique", "蛋白提取+胰酶消化 → M05 Protein Lysis & Solubilization"),
    "C60-1": ("M05'", "A2", "valid", "sample_prep", "组织/LCM 蛋白组学样本制备 → M05' Proteomics Sample Prep"),
    "C60-2": (None, None, "supporting", None, "蛋白组数据分析(ProteoCombiner/Alpaca) → supporting 域，不计覆盖"),
    "C42-0": ("M23b", "A6b", "valid", "technique", "细菌重组蛋白表达+纯化流程 → 主归 M23b(含表达段 multi-method)"),
    "C42-1": ("M23b", "A6b", "valid", "technique", "GST 标签/AAV 纯化 → M23b Protein Purification"),
    "C35-0": ("M14", "A3", "valid", "technique", "ATAC-seq/染色质可及性 → M14 Chromatin Profiling(扩展)"),
    "C35-1": ("NEW-ScreeningAssay", "A13", "valid", "assay", "混合检测/筛选(FISH probe/384-well marker screening)；弱语义，新增候选(weak)"),
    "C35-2": ("M11b", "A3", "valid", "technique", "单核 RNA-seq 文库(sNucDrop/SHARE-seq) → M11b"),
    "C74-0": ("M37", "A10", "valid", "technique", "胰岛免疫组化/胰岛素检测 → M37 Immunohistochemistry(含 ELISA 段)"),
    "C74-1": ("NEW-TissueEmbedding", "A10", "valid", "sample_prep", "胰岛包埋/组织学样本制备；草案外新增候选"),
    "C29-0": ("NEW-RNAISH", "A9", "valid", "technique", "RNAscope/RNA 原位杂交 → NEW-RNA ISH(草案外新增候选；修正 Step3 抽样错配)"),
    "C29-1": ("M16", "A4", "valid", "technique", "RNA 提取+RT+qPCR → M16 Reverse Transcription & cDNA Synthesis"),
    "C29-2": ("M16", "A4", "valid", "technique", "cDNA 合成(RT/RACE/3'-DGE) → M16"),
}

npz = np.load(NPZ, allow_pickle=False)
ids = npz["ids"].tolist()
X = npz["X"].astype(np.float32)
id2idx = {pid: j for j, pid in enumerate(ids)}

# 子簇分配落盘
sub_assign = {}
for cl, k in TARGET.items():
    cids = assign[cl]
    idx = [id2idx[pid] for pid in cids]
    sub = KMeans(n_clusters=k, random_state=42, n_init=4).fit_predict(X[idx])
    for s in range(k):
        sub_ids = [cids[j] for j in np.where(sub == s)[0]]
        sub_assign["%s-%d" % (cl, s)] = sub_ids
with open(os.path.join(OUT, "step3_subcluster_assign.json"), "w", encoding="utf-8") as f:
    json.dump(sub_assign, f, ensure_ascii=False)

# 协议级 v2 归属
proto_status = {}   # pid -> status
proto_method = {}   # pid -> method
for cl, meta in cmap.items():
    if cl in TARGET:
        continue
    for pid in assign[cl]:
        proto_status[pid] = meta["status"]
        proto_method[pid] = meta.get("method")
for sub, (m, app, st, mt, note) in SUB_METHOD.items():
    for pid in sub_assign[sub]:
        proto_status[pid] = st
        proto_method[pid] = m

# 名义 EC_v2
from collections import Counter
sc = Counter(proto_status.values())
n_total = len(proto_status)
n_valid = sc.get("valid", 0)
n_boundary = sc.get("boundary", 0)
n_supporting = sc.get("supporting", 0)
n_invalid = sc.get("invalid", 0)
n_eligible = n_total - n_invalid
n_covered = n_valid + n_boundary
print("v2 status:", dict(sc))
print("eligible:", n_eligible, "EC_v2:", round(n_covered / n_eligible * 100, 2), "%")

lines = ["# Step 3 v2：子簇重聚类后 EC 重算（名义）", "",
         f"- 总协议：{n_total}",
         f"- valid：{n_valid} / boundary：{n_boundary} / supporting：{n_supporting} / invalid：{n_invalid}",
         "",
         "| 指标 | 值 |",
         "|---|---|",
         f"| eligible（排除 invalid {n_invalid}） | {n_eligible} |",
         f"| **EC_v2 名义**（valid+boundary {n_covered}/{n_eligible}） | **{n_covered/n_eligible*100:.2f}%** |",
         f"| 与 v1 名义对比 | 99.16% → {n_covered/n_eligible*100:.2f}%（invalid 从 475 降至 {n_invalid}，因 C35 修正为方法簇） |",
         "",
         "> ⚠️ 名义仍待二次抽样校验收敛。关键：C22/C60/C42/C35/C74/C29 拆分后子簇内是否纯净。",
         ""]
open(os.path.join(OUT, "step3_ec_v2.md"), "w", encoding="utf-8").write("\n".join(lines))

# 二次抽样：子簇层 1-2 条 + 其他随机 10 条
import random
random.seed(20260822)
picked = []
subs_sorted = sorted(sub_assign.keys())
for sub in subs_sorted:
    picked.append((random.choice(sub_assign[sub]), sub, "subcluster"))
# 其他簇（非 TARGET）随机抽 8 条
other_pids = [pid for cl in assign for pid in assign[cl] if cl not in TARGET]
random.shuffle(other_pids)
picked_ids = {p[0] for p in picked}
for pid in other_pids:
    if len([p for p in picked if p[2] == "other"]) >= 8:
        break
    if pid in picked_ids:
        continue
    picked.append((pid, "?", "other"))
    picked_ids.add(pid)

objs = dict(Protocol.objects.filter(id__in=picked_ids).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=picked_ids).values_list("id", "name"))

lines = ["# Step 3 v2 二次抽样清单（子簇纯度校验 + 其他随机）", "",
         "| # | 来源 | 簇/子簇 | Method | status | 协议名 | objective（前 200 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, (pid, sub, kind) in enumerate(picked, 1):
    if sub != "?":
        m, app, st, mt, note = SUB_METHOD[sub]
    else:
        # 找所在簇
        cl = next((c for c, cids in assign.items() if pid in cids), "?")
        meta = cmap.get(cl, {})
        m, st = meta.get("method", "-"), meta.get("status", "?")
    obj = (objs.get(pid) or "")[:200].replace("|", "/").replace("\n", " ")
    lines.append(f"| {i} | {kind} | {sub} | {m} | {st} | {(names.get(pid) or '?')[:48]} | {obj} |")
open(os.path.join(OUT, "step3_sample_v2.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step3_ec_v2.md + step3_sample_v2.md, sample:", len(picked))

# v2 映射 JSON（80 簇展开子簇）
mapv2 = {"note": "v2：6 混簇按方法粒度拆分（C22/C60/C42/C35/C74/C29）", "clusters": {}}
for cl, meta in cmap.items():
    mapv2["clusters"][cl] = meta
for sub, (m, app, st, mt, note) in SUB_METHOD.items():
    mapv2["clusters"][sub] = {"application": app, "method": m, "method_type": mt, "status": st, "note": note, "parent": sub.split("-")[0]}
with open(os.path.join(OUT, "step3_cluster_map_v2.json"), "w", encoding="utf-8") as f:
    json.dump(mapv2, f, ensure_ascii=False, indent=1)
print("saved step3_cluster_map_v2.json")
