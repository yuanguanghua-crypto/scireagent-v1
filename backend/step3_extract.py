# Step 3 提取：重算 14065 协议→80 簇分配（确定性，与探针一致），落盘全量分配 + 80 簇摘要
import sys, os, json, time
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
J = os.path.join(OUT, "probe_completeness.json")
t0 = time.time()

d = json.load(open(J, encoding="utf-8"))
meta_clusters = {int(c["cluster"]): c for c in d["clusters"]}
assert set(meta_clusters.keys()) == set(range(80)), "json clusters 不覆盖 0-79"

npz = np.load(NPZ, allow_pickle=False)
ids = npz["ids"].tolist()
X = npz["X"].astype(np.float32)
print("embeds:", X.shape, "ids:", len(ids), "(%.1fs)" % (time.time() - t0), flush=True)

km = KMeans(n_clusters=80, random_state=42, n_init=4)
labels = km.fit_predict(X)
print("kmeans done (%.1fs)" % (time.time() - t0), flush=True)

# 验证与探针 size 一致
from collections import Counter
cnt = Counter(labels)
mismatch = [(i, cnt.get(i), int(meta_clusters[i]["size"]))
            for i in range(80)
            if cnt.get(i) != int(meta_clusters[i]["size"])]
print("size mismatch:", mismatch if mismatch else "NONE (与探针分配一致)")

# 协议 id→name
name_map = dict(Protocol.objects.filter(id__in=ids).values_list("id", "name"))

# 落盘：cluster -> ids
assign = {}
for i in range(80):
    cids = [ids[j] for j in np.where(labels == i)[0]]
    assign["C%d" % i] = cids
with open(os.path.join(OUT, "step3_cluster_assign.json"), "w", encoding="utf-8") as f:
    json.dump(assign, f, ensure_ascii=False)
print("saved step3_cluster_assign.json (%.1fs)" % (time.time() - t0), flush=True)

# 80 簇摘要表（md）
lines = ["# Step 3 全量 80 簇摘要（自下而上，14065 协议→80 簇）", "",
         "| 簇 | 规模 | 代表协议 | TF-IDF 关键词 | 前 3 协议名 |", "|---|---|---|---|---|"]
for i in range(80):
    c = meta_clusters.get(i)
    if c is None:
        continue
    cids = assign["C%d" % i]
    names = [name_map.get(pid, "?")[:60] for pid in cids[:3]]
    kw = " / ".join([str(k) for k in (c.get("keywords") or [])[:5]])
    lines.append("| C%d | %d | %s | %s | %s |" % (
        i, int(c["size"]), (c.get("exemplar_name") or "")[:70], kw,
        "<br>".join(names)))
md = "\n".join(lines)
with open(os.path.join(OUT, "step3_all_clusters.md"), "w", encoding="utf-8") as f:
    f.write(md)
print("saved step3_all_clusters.md (%.1fs)" % (time.time() - t0), flush=True)
print("DONE")
