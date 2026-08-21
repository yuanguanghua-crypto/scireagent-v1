# 子簇重聚类：对 6 个高频混簇按方法粒度细分（零写库）
import sys, os, json, time
sys.path.insert(0, r"D:\emb3_venv\Lib\site-packages")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
NPZ = os.path.join(OUT, "protocol_embeds.npz")
assign = json.load(open(os.path.join(OUT, "step3_cluster_assign.json"), encoding="utf-8"))

TARGET = {"C22": 3, "C60": 3, "C42": 2, "C35": 3, "C74": 2, "C29": 3}  # 簇 -> 子簇数 k
t0 = time.time()

npz = np.load(NPZ, allow_pickle=False)
ids = npz["ids"].tolist()
X = npz["X"].astype(np.float32)
id2idx = {pid: j for j, pid in enumerate(ids)}

# 协议文本（TF-IDF 关键词用）
all_ids = [pid for cl in assign.values() for pid in cl]
name_map = dict(Protocol.objects.filter(id__in=all_ids).values_list("id", "name"))
obj_map = dict(Protocol.objects.filter(id__in=all_ids).values_list("id", "objective"))

lines = ["# 子簇重聚类摘要（方法粒度细分，零写库）", "",
         "| 原簇 | 子簇 | 规模 | 代表协议 | top 关键词 | 前 5 协议名 |",
         "|---|---|---|---|---|---|"]

for cl, k in TARGET.items():
    cids = assign[cl]
    idx = [id2idx[pid] for pid in cids]
    Xs = X[idx]
    km = KMeans(n_clusters=k, random_state=42, n_init=4)
    sub = km.fit_predict(Xs)
    for s in range(k):
        sub_idx = np.where(sub == s)[0]
        sub_pids = [cids[j] for j in sub_idx]
        # medoid: 距子簇中心最近
        center = km.cluster_centers_[s]
        dists = np.linalg.norm(Xs[sub_idx] - center, axis=1)
        med = sub_pids[int(np.argmin(dists))]
        # TF-IDF 关键词（子簇内 top 6，对照全量）
        texts = ["%s . %s" % ((name_map.get(p) or ""), (obj_map.get(p) or ""))[:600] for p in sub_pids]
        try:
            vec = TfidfVectorizer(stop_words="english", max_features=8000)
            tf = vec.fit_transform(texts)
            sums = np.asarray(tf.sum(axis=0)).ravel()
            order = np.argsort(sums)[::-1][:8]
            words = [vec.get_feature_names_out()[j] for j in order]
            # 过滤过泛词
            stop = {"protocol", "protocols", "use", "used", "using", "method", "methods",
                    "cell", "cells", "dna", "rna", "protein", "proteins", "sample", "samples",
                    "buffer", "solution", "described", "following", "step", "steps", "procedure",
                    "based", "well", "one", "two", "new", "simple", "efficient", "analysis",
                    "assay", "assays", "gene", "genes", "test", "tests", "study", "studies",
                    "mix", "mixture", "add", "incubate", "prepared", "prepare", "preparation"}
            words = [w for w in words if w not in stop][:6]
        except Exception as e:
            words = ["tfidf-err:%s" % e]
        names5 = " / ".join((name_map.get(p) or "?")[:45] for p in sub_pids[:5])
        lines.append("| %s | %s-%d | %d | %s | %s | %s |" % (
            cl, cl, s, len(sub_pids), (name_map.get(med) or "?")[:60], ", ".join(words), names5))

md = "\n".join(lines)
open(os.path.join(OUT, "step3_subcluster.md"), "w", encoding="utf-8").write(md)
print("saved step3_subcluster.md (%.1fs)" % (time.time() - t0))
print("DONE")
