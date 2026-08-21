# Step 4 v0.5：二轮补词典 + 主方法排序改"首个操作词出现位置优先"（消词典序 bias）
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

# ---------- 二轮补词典 v0.5 ----------
PATCH2 = {
    "M03": ["gel imaging", "gel documentation", "dna separation"],
    "M07": ["serotonin", "hormone quantification", "abscisic acid"],
    "M10": ["amplicon sequencing"],
    "M22": ["eclip", "enhanced crosslinking"],
    "M24": ["cell culture maintenance", "hek293", "passaging", "subculture", "cell passaging"],
    "M26": ["cardiomyocyte isolation"],
    "M29": ["effector function", "cytokine production", "t cell activation"],
    "M34": ["geomx", "dsp", "spatial proteomics", "spatial protein"],
    "M42": ["atpase", "phosphatase", "enzyme kinetics"],
    "M46": ["salmonella", "food sample"],
    "M47": ["salmonella", "antimicrobial"],
    "M51": ["pole test"],
    "NEW-PlantBiochemAssay": ["cellulose", "hemicellulose", "plant hormone"],
    "NEW-ViralMolDetection": ["virus typing", "viral subtyping", "virus subtyping"],
    "SUP-BIOINFO": ["phylogenetic", "population genetics", "phylogenomics"],
}
APPEND_METHODS = [
    {"id": "NEW-GibsonAssembly", "name": "Gibson/Golden Gate DNA Assembly", "app": "A5", "type": "technique",
     "patterns": ["gibson assembly", "gibson", "dna assembly", "golden gate", "seamless cloning"]},
    {"id": "NEW-SmallMoleculeSynthesis", "name": "Small Molecule Synthesis", "app": "A12b", "type": "technique",
     "patterns": ["small molecule synthesis", "preparative-scale synthesis", "organic synthesis", "chemical synthesis"]},
]
for m in LEX:
    m["patterns"] += PATCH2.get(m["id"], [])
LEX.extend(APPEND_METHODS)
# v0.4.1 继承的收紧/过冲修正
for m in LEX:
    if m["id"] == "M16":
        m["patterns"] = [p for p in m["patterns"] if p not in ("race", "in vitro transcription")]
    if m["id"] == "M10":
        m["patterns"] = [p for p in m["patterns"] if p != "sequencing"]
    if m["id"] == "M32":
        m["patterns"] = [p for p in m["patterns"] if p != "imaging"]
    if m["id"] == "M24":
        m["patterns"] = [p for p in m["patterns"] if p not in ("primary culture", "cell culture")]

OP = ["extraction", "isolation", "purification", "assay", "staining", "culture", "synthesis",
      "imaging", "sequencing", "amplification", "transformation", "transduction", "transfection",
      "digestion", "lysis", "labeling", "detection", "measurement", "quantification", "screening",
      "crosslinking", "cryopreservation", "differentiation", "expression", "recording", "assessment",
      "analysis", "preparation", "ligation", "hybridization", "blotting", "cloning", "mutagenesis",
      "editing", "annotation", "modeling", "docking", "collection", "sampling", "sectioning",
      "embedding", "electroporation", "chromatography", "assembly"]
for m in LEX:
    m["op_patterns"] = [p for p in m["patterns"] if any(o in p for o in OP)]

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
    "NEW-GibsonAssembly": ["gibson assembly", "golden gate"], "NEW-SmallMoleculeSynthesis": ["preparative-scale synthesis", "small molecule synthesis"],
    "SUP-BIOINFO": ["bioinformatics", "structure prediction", "alphafold", "pipeline"], "INV-REVIEW": ["systematic review", "meta-analysis", "clinical trial"],
}

qs = Protocol.objects.only("id", "name", "objective").all()
rows = [(p.id, (p.name or "") + " . " + (p.objective or "")) for p in qs]
print("loaded %d (%.1fs)" % (len(rows), time.time() - t0), flush=True)

def first_pos(text, patterns):
    ps = [text.find(p) for p in patterns]
    ps = [x for x in ps if x != -1]
    return min(ps) if ps else None

signals = {}
for pid, text in rows:
    t = text.lower()
    hit_pos = {}
    for m in LEX:
        pos = first_pos(t, m["patterns"])
        if pos is not None:
            hit_pos[m["id"]] = pos
    op_pos = {}
    for m in LEX:
        pos = first_pos(t, m["op_patterns"])
        if pos is not None:
            op_pos[m["id"]] = pos
    strong_pos = {}
    for mid, spats in STRONG.items():
        pos = first_pos(t, spats)
        if pos is not None:
            strong_pos[mid] = pos
    if "INV-REVIEW" in strong_pos:
        primary = "INV-REVIEW"
    elif op_pos:
        primary = min(op_pos, key=op_pos.get)
    elif strong_pos:
        primary = min(strong_pos, key=strong_pos.get)
    elif hit_pos:
        primary = min(hit_pos, key=hit_pos.get)
    else:
        primary = None
    signals[pid] = {"methods": sorted(hit_pos.keys()), "op": sorted(op_pos.keys()),
                    "strong": sorted(strong_pos.keys()), "primary": primary}
json.dump(signals, open(os.path.join(OUT, "step4_signals_v05.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("signals v0.5 done (%.1fs)" % (time.time() - t0), flush=True)

VALID_EX = {"SUP-BIOINFO", "INV-REVIEW"}
prim_count = Counter(v["primary"] for v in signals.values())
n_total = len(signals)
n_no = sum(1 for v in signals.values() if not v["primary"])
n_rev = prim_count.get("INV-REVIEW", 0)
n_sup = prim_count.get("SUP-BIOINFO", 0)
n_eligible = n_total - n_rev
n_covered = sum(1 for v in signals.values() if v["primary"] and v["primary"] not in VALID_EX)
ec = n_covered / n_eligible * 100 if n_eligible else 0
n_multi = 0; n_any = 0
for v in signals.values():
    ops = [x for x in v["op"] if x not in VALID_EX]
    if ops:
        n_any += 1
        if len(ops) >= 2:
            n_multi += 1
mmr = n_multi / n_any * 100 if n_any else 0
print("==")
print("total:", n_total, "no_signal:", n_no, "review:", n_rev, "sup:", n_sup)
print("eligible:", n_eligible, "covered:", n_covered, "EC_v05: %.2f%%" % ec)
print("MultiMethod(op): %.2f%% (%d/%d)" % (mmr, n_multi, n_any))
print("top primaries:", prim_count.most_common(14))

lines = ["# Step 4 v0.5 报告：二轮补词典 + 位置优先主方法排序", "",
         f"- 协议总数：{n_total}；无信号：{n_no}；综述：{n_rev}；生信：{n_sup}",
         "",
         "| 指标 | v0.4.1 | **v0.5** |",
         "|---|---|---|",
         f"| EC（信号口径） | 69.98% | **{ec:.2f}%**（{n_covered}/{n_eligible}） |",
         f"| MultiMethod Rate | 22.49% | **{mmr:.2f}%**（op 口径） |",
         f"| 无信号 | 3372 (24.0%) | **{n_no} ({n_no/n_total*100:.1f}%)** |",
         "",
         "## 主方法分布（top 14）", "", "| Method | 数 | Method | 数 |", "|---|---|---|---|"]
top = prim_count.most_common(28)
half = (len(top) + 1) // 2
for i in range(half):
    l = top[i]; r = top[i + half] if i + half < len(top) else None
    lines.append("| %s | %d | %s | %s |" % (l[0], l[1], r[0] if r else "", r[1] if r else ""))
open(os.path.join(OUT, "step4_v05_report.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_v05_report.md")
