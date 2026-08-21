# Step 4 全量试跑：14065 协议 → 方法信号（词典 v0.3 = v0.2 + strong 主方法权重）
import os, json, time
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")
from django.db.models import Count, Q

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
t0 = time.time()
LEX = json.load(open(os.path.join(OUT, "method_signal_lexicon_v02.json"), encoding="utf-8"))["methods"]

# v0.3 覆盖：strong 主方法词（强特异词优先定主方法）；M16 收紧（删裸 race）
STRONG = {
    "M01": ["genomic dna", "dna extraction", "dna isolation"], "M02": ["rna extraction", "rna isolation", "total rna"],
    "M03": ["gel purification", "gel extraction"], "M05": ["protein extraction", "cell lysis", "protein lysate"],
    "M05p": ["trypsin digestion", "proteomics sample", "sp3", "stage tip"], "M07": ["metabolite extraction", "metabolomics", "lc-ms", "gc-ms"],
    "M10": ["library preparation", "library prep", "amplicon", "illumina", "tagmentation"], "M11": ["rna-seq", "rna sequencing"],
    "M11a": ["single-cell rna", "scrna-seq", "drop-seq"], "M11b": ["single-nucleus", "snrna-seq"],
    "M12": ["nanopore", "pacbio", "long-read"], "M13": ["viral sequencing", "viral genome", "viral metagenome"],
    "M14": ["chip-seq", "chromatin", "atac-seq"], "M15": ["polymerase chain reaction", "pcr amplification", "qpcr"],
    "M16": ["reverse transcription", "cdna synthesis", "revertaid"], "M17": ["competent cells", "heat-shock", "electroporation", "transformation"],
    "M18": ["agrobacterium"], "M19": ["crispr", "cas9", "genome editing"], "M20": ["mutagenesis", "base editing"],
    "M21": ["lentivirus", "lentiviral", "retrovirus", "transduction"], "M22": ["crosslinking", "clip", "proximity"],
    "M23": ["recombinant protein expression", "protein expression", "overexpression"], "M23b": ["affinity purification", "chromatography", "his-tag", "protein purification"],
    "M24": ["ipsc", "hpsc", "pluripotent", "organoid"], "M25": ["neuronal differentiation", "cortical neuron"],
    "M26": ["pbmc", "ficoll", "cell isolation"], "M27": ["cryopreservation", "cryopreserve"],
    "M28": ["elisa", "immunosorbent assay"], "M29": ["flow cytometry", "facs", "immunophenotyping"],
    "M31": ["colony immunoblot"], "M32": ["fluorescence imaging", "confocal", "live-cell imaging"],
    "M33": ["electron microscopy", "clem", "cryo-em"], "M34": ["codex", "multiplexed imaging", "visium"],
    "M35": ["calcium imaging", "gcamp"], "M36": ["immunofluorescence"],
    "M37": ["immunohistochemistry", "ihc"], "M38": ["western blot", "western blotting", "immunoblotting"],
    "M39": ["immunoprecipitation", "pull-down"], "M40": ["peptide synthesis", "solid-phase peptide"],
    "M41": ["microsphere", "particle synthesis"], "M42": ["kinase", "phosphorylation"],
    "M43": ["autophagy", "mitophagy"], "M43b": ["lysosomal", "lysosome"],
    "M44": ["alpha-synuclein", "amyloid", "aggregation"], "M45": ["infection assay", "focus assay", "plaque", "moi"],
    "M46": ["bacterial culture", "microbial culture", "cyanobacteria"], "M47": ["biofilm", "cfu"],
    "M48": ["pathogen", "rhizoctonia"], "M49": ["drosophila", "c. elegans", "caenorhabditis", "zebrafish"],
    "M50": ["in vivo recording", "craniotomy"], "M51": ["behavioral", "open field", "conditioning"],
    "M52": ["pharmacokinetic"], "M53": ["electrophysiology", "patch clamp", "whole-cell recording"],
    "M54": ["edna", "metabarcoding", "environmental dna"],
    "NEW-SDS-PAGE": ["sds-page", "polyacrylamide"], "NEW-RNAISH": ["in situ hybridization", "rnascope", "rna fish"],
    "NEW-TissueEmbedding": ["embedding", "cryosectioning"], "NEW-ScreeningAssay": ["high-throughput screening", "384-well"],
    "NEW-CellViabilityAssay": ["viability", "prestoblue", "resazurin"], "NEW-MitoFunctionAssay": ["mitochondrial function", "oxygen consumption", "seahorse"],
    "NEW-PlantBiochemAssay": ["guard cell", "stomata", "vacuole"], "NEW-ViralMolDetection": ["sars-cov-2", "viral detection", "rt-lamp"],
    "NEW-3DCulture": ["3d culture", "spheroid", "matrigel"], "NEW-EVIsolation": ["exosome", "extracellular vesicle"],
    "SUP-BIOINFO": ["bioinformatics", "structure prediction", "alphafold", "pipeline"], "INV-REVIEW": ["systematic review", "meta-analysis", "clinical trial"],
}
# M16 收紧：移除裸 race（过宽）
for m in LEX:
    if m["id"] == "M16":
        m["patterns"] = [p for p in m["patterns"] if p not in ("race", "in vitro transcription")]
LEX_IDX = {m["id"]: m for m in LEX}

# 全量协议
qs = Protocol.objects.only("id", "name", "objective").all()
rows = []
for p in qs:
    rows.append((p.id, (p.name or "") + " . " + (p.objective or "")))
print("loaded %d protocols (%.1fs)" % (len(rows), time.time() - t0), flush=True)

signals = {}
for pid, text in rows:
    t = text.lower()
    hit = {}      # id -> 1
    strong_hit = {}  # id -> 1
    for m in LEX:
        for pat in m["patterns"]:
            if pat in t:
                hit[m["id"]] = 1
                break
    for mid, spats in STRONG.items():
        for pat in spats:
            if pat in t:
                strong_hit[mid] = 1
                break
    # 主方法：INV-REVIEW strong 优先(排除类) > 具体方法 strong(词典序) > 普通命中(词典序)
    if "INV-REVIEW" in strong_hit:
        primary = "INV-REVIEW"
    elif strong_hit:
        primary = next((mid for m in LEX if (mid := m["id"]) in strong_hit), None)
    elif hit:
        primary = next((m["id"] for m in LEX if m["id"] in hit), None)
    else:
        primary = None
    signals[pid] = {"methods": sorted(hit.keys(), key=lambda x: [i for i, m in enumerate(LEX) if m["id"] == x][0]),
                    "strong": sorted(strong_hit.keys()),
                    "primary": primary}
print("signals done (%.1fs)" % (time.time() - t0), flush=True)
json.dump(signals, open(os.path.join(OUT, "step4_signals_full.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---- 统计 ----
from collections import Counter
prim_count = Counter(v["primary"] for v in signals.values())
n_total = len(signals)
n_no_signal = sum(1 for v in signals.values() if not v["primary"])
n_review = prim_count.get("INV-REVIEW", 0)
n_sup = prim_count.get("SUP-BIOINFO", 0)
n_valid_primary = n_total - n_no_signal - n_review - n_sup
# eligible: 有文本且非综述（综述协议科学上不做方法映射）
n_eligible = n_total - n_review
# covered: 有 ≥1 有效方法信号(非 SUP/INV)
n_covered = sum(1 for v in signals.values() if v["primary"] not in (None, "SUP-BIOINFO", "INV-REVIEW"))
ec = n_covered / n_eligible * 100 if n_eligible else 0
# MultiMethod: ≥2 个非 SUP/INV 信号
n_multi = 0
n_any = 0
for v in signals.values():
    valid_methods = [m for m in v["methods"] if m not in ("SUP-BIOINFO", "INV-REVIEW")]
    if valid_methods:
        n_any += 1
        if len(valid_methods) >= 2:
            n_multi += 1
mmr = n_multi / n_any * 100 if n_any else 0

print("==")
print("total:", n_total, "no_signal:", n_no_signal, "review:", n_review, "sup:", n_sup)
print("eligible:", n_eligible, "covered:", n_covered, "EC_signal: %.2f%%" % ec)
print("MultiMethod Rate: %.2f%% (%d/%d)" % (mmr, n_multi, n_any))
print("top primaries:", prim_count.most_common(15))

# 与簇归属对比（v2 子簇展开）
assign = json.load(open(os.path.join(OUT, "step3_cluster_assign.json"), encoding="utf-8"))
mapv2 = json.load(open(os.path.join(OUT, "step3_cluster_map_v2.json"), encoding="utf-8"))["clusters"]
sub_assign = json.load(open(os.path.join(OUT, "step3_subcluster_assign.json"), encoding="utf-8"))
# 协议→簇 method
proto_clust_method = {}
for cl, cids in assign.items():
    m = mapv2.get(cl, {}).get("method")
    for pid in cids:
        proto_clust_method[pid] = m
for sub, cids in sub_assign.items():
    m = mapv2.get(sub, {}).get("method")
    for pid in cids:
        proto_clust_method[pid] = m
# 一致率（primary 与簇 method 相同；簇 method 可能为 None(支持/无效)）
same = 0; both_valid = 0; clust_none = 0; diff = 0
for pid, v in signals.items():
    if not v["primary"]:
        continue
    cm = proto_clust_method.get(pid)
    if cm is None:
        clust_none += 1
        continue
    if v["primary"] == cm:
        same += 1
    else:
        diff += 1
agree = same / (same + diff) * 100 if (same + diff) else 0
print("cluster-vs-signal: same=%d diff=%d (clust_none=%d) agree=%.1f%%" % (same, diff, clust_none, agree))

# 报告落盘
lines = ["# Step 4 全量试跑报告：方法信号口径 EC（词典 v0.3）", "",
         f"- 协议总数：{n_total}；无信号：{n_no_signal}；综述(INV-REVIEW)：{n_review}；生信(SUP-BIOINFO)：{n_sup}",
         "",
         "| 指标 | 值 |",
         "|---|---|",
         f"| eligible（排除综述 {n_review}） | {n_eligible} |",
         f"| **EC（信号口径）** = 有≥1 有效信号 {n_covered} / {n_eligible} | **{ec:.2f}%** |",
         f"| MultiMethod Rate = ≥2 信号 {n_multi} / 有信号 {n_any} | **{mmr:.2f}%** |",
         f"| 簇归属 vs 信号主方法一致率 | **{agree:.1f}%**（same {same} / diff {diff}，簇无 method {clust_none}） |",
         "",
         "## 主方法分布（top 15）", "",
         "| Method | 协议数 | | Method | 协议数 |",
         "|---|---|---|---|---|"]
top = prim_count.most_common(30)
half = (len(top) + 1) // 2
for i in range(half):
    l = top[i]; r = top[i + half] if i + half < len(top) else None
    if r:
        lines.append(f"| {l[0]} | {l[1]} | | {r[0]} | {r[1]} |")
    else:
        lines.append(f"| {l[0]} | {l[1]} | | | |")
open(os.path.join(OUT, "step4_full_report.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_full_report.md")
