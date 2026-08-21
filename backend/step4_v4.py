# Step 4 v0.4：操作词加权主方法排序 + 补词典 + strong 口径 MultiMethod（混合方案第 1 段）
import os, json, time
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")
from collections import Counter

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
t0 = time.time()
LEX = json.load(open(os.path.join(OUT, "method_signal_lexicon_v02.json"), encoding="utf-8"))["methods"]

# ---------- 词典补丁 v0.4 ----------
PATCH = {
    "M01": ["bead cleanup", "dna clean-up", "clean up", "ampure"],
    "M24": ["primary culture", "cell culture"],
    "M25": ["neuron culture", "primary neuron culture", "neuronal culture"],
    "M26": ["transwell", "co-culture", "coculture", "supernatant transfer", "bystander killing"],
    "M42": ["dehydrogenase", "spectrophotometric assay", "enzyme activity", "enzyme assay"],
    "M46": ["exopolysaccharide", "polysaccharide production", "fungal culture", "mushroom culture"],
    "SUP-BIOINFO": ["conda", "installation instructions", "phylogenetic analysis", "genome assembly", "variant calling"],
}
for m in LEX:
    m["patterns"] += PATCH.get(m["id"], [])
# M16 收紧（v0.3 继承）
for m in LEX:
    if m["id"] == "M16":
        m["patterns"] = [p for p in m["patterns"] if p not in ("race", "in vitro transcription")]
# v0.4.1 过冲修正：删泛词（裸 sequencing/imaging/cell culture 致主方法过冲）
for m in LEX:
    if m["id"] == "M10":
        m["patterns"] = [p for p in m["patterns"] if p != "sequencing"]
    if m["id"] == "M32":
        m["patterns"] = [p for p in m["patterns"] if p != "imaging"]
    if m["id"] == "M13":
        m["patterns"] += ["population-based sequencing", "viral deep sequencing"]
    if m["id"] == "M24":
        m["patterns"] = [p for p in m["patterns"] if p not in ("primary culture", "cell culture")]

# ---------- 操作词表（主方法判定核心） ----------
OP = ["extraction", "isolation", "purification", "assay", "staining", "culture", "synthesis",
      "imaging", "sequencing", "amplification", "transformation", "transduction", "transfection",
      "digestion", "lysis", "labeling", "detection", "measurement", "quantification", "screening",
      "crosslinking", "cryopreservation", "differentiation", "expression", "recording", "assessment",
      "analysis", "preparation", "ligation", "hybridization", "blotting", "cloning", "mutagenesis",
      "editing", "annotation", "modeling", "docking", "collection", "sampling", "sectioning",
      "embedding", "electroporation", "chromatography"]

# 预计算每 method 的"操作 pattern"（pattern 含 OP 词）
for m in LEX:
    m["op_patterns"] = [p for p in m["patterns"] if any(o in p for o in OP)]

STRONG = json.load(open(os.path.join(OUT, "method_signal_lexicon_v02.json"), encoding="utf-8"))["methods"]
# STRONG 复用 step4_full 的字典（内嵌）
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
LEX_IDX = {m["id"]: m for m in LEX}

qs = Protocol.objects.only("id", "name", "objective").all()
rows = [(p.id, (p.name or "") + " . " + (p.objective or "")) for p in qs]
print("loaded %d (%.1fs)" % (len(rows), time.time() - t0), flush=True)

signals = {}
for pid, text in rows:
    t = text.lower()
    hit = []; op_hit = []; strong_hit = []
    for m in LEX:
        matched = any(p in t for p in m["patterns"])
        if not matched:
            continue
        hit.append(m["id"])
        if any(p in t for p in m["op_patterns"]):
            op_hit.append(m["id"])
    for mid, spats in STRONG.items():
        if any(p in t for p in spats):
            strong_hit.append(mid)
    # primary：综述 > 操作命中(strong 优先) > strong > 普通
    if "INV-REVIEW" in strong_hit:
        primary = "INV-REVIEW"
    else:
        op_strong = [x for x in op_hit if x in strong_hit]
        if op_strong:
            primary = op_strong[0]
        elif op_hit:
            primary = op_hit[0]
        elif strong_hit:
            primary = strong_hit[0]
        elif hit:
            primary = hit[0]
        else:
            primary = None
    signals[pid] = {"methods": hit, "op": op_hit, "strong": strong_hit, "primary": primary}
json.dump(signals, open(os.path.join(OUT, "step4_signals_v04.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("signals v0.4 done (%.1fs)" % (time.time() - t0), flush=True)

VALID_EX = {"SUP-BIOINFO", "INV-REVIEW"}
prim_count = Counter(v["primary"] for v in signals.values())
n_total = len(signals)
n_no = sum(1 for v in signals.values() if not v["primary"])
n_rev = prim_count.get("INV-REVIEW", 0)
n_sup = prim_count.get("SUP-BIOINFO", 0)
n_eligible = n_total - n_rev
n_covered = sum(1 for v in signals.values() if v["primary"] and v["primary"] not in VALID_EX)
ec = n_covered / n_eligible * 100 if n_eligible else 0
# 真实 MultiMethod：≥2 个 op 命中（非 SUP/INV）
n_multi = 0; n_any = 0
for v in signals.values():
    ops = [x for x in v["op"] if x not in VALID_EX]
    if ops:
        n_any += 1
        if len(ops) >= 2:
            n_multi += 1
mmr = n_multi / n_any * 100 if n_any else 0
# 未决：无信号 + 多 op 冲突
n_multi_op = sum(1 for v in signals.values() if len([x for x in v["op"] if x not in VALID_EX]) >= 2)
print("==")
print("total:", n_total, "no_signal:", n_no, "review:", n_rev, "sup:", n_sup)
print("eligible:", n_eligible, "covered:", n_covered, "EC_v04: %.2f%%" % ec)
print("MultiMethod(op口径): %.2f%% (%d/%d); 多op协议数: %d" % (mmr, n_multi, n_any, n_multi_op))
print("top primaries:", prim_count.most_common(14))

lines = ["# Step 4 v0.4.1 报告：操作词加权主方法 + 补词典 + strong 口径 MultiMethod（修正过冲）", "",
         f"- 协议总数：{n_total}；无信号：{n_no}；综述：{n_rev}；生信：{n_sup}",
         "",
         "| 指标 | v0.3 | v0.4 | **v0.4.1** |",
         "|---|---|---|---|",
         f"| EC（信号口径） | 72.88% | 73.31% | **{ec:.2f}%**（{n_covered}/{n_eligible}） |",
         f"| MultiMethod Rate | 54.15% | 29.28% | **{mmr:.2f}%**（op 口径 {n_multi}/{n_any}） |",
         f"| 无信号 | 3238 (23%) | 3058 | **{n_no} ({n_no/n_total*100:.1f}%)** |",
         "",
         "## 主方法分布（top 14）", "",
         "| Method | 数 | Method | 数 |",
         "|---|---|---|---|"]
top = prim_count.most_common(28)
half = (len(top) + 1) // 2
for i in range(half):
    l = top[i]; r = top[i + half] if i + half < len(top) else None
    lines.append("| %s | %d | %s | %s |" % (l[0], l[1], r[0] if r else "", r[1] if r else ""))
open(os.path.join(OUT, "step4_v041_report.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_v041_report.md")
