# Step 4 分层量化：L1高置信/L2中置信/L3未决/L4排除 + 分层抽样（零写库）
import os, json, time, random
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.apps import apps
Protocol = apps.get_model("knowledge", "Protocol")
from collections import Counter

OUT = r"C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\_audit_tmp"
t0 = time.time()
LEX = json.load(open(os.path.join(OUT, "method_signal_lexicon_v02.json"), encoding="utf-8"))["methods"]
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
STRONG = json.load(open(os.path.join(OUT, "method_signal_lexicon_v02.json"), encoding="utf-8"))["methods"]
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

def first_pos(text, patterns):
    ps = [text.find(p) for p in patterns]
    ps = [x for x in ps if x != -1]
    return min(ps) if ps else None

qs = Protocol.objects.only("id", "name", "objective").all()
rows = [(p.id, (p.name or "") + " . " + (p.objective or "")) for p in qs]
print("loaded %d (%.1fs)" % (len(rows), time.time() - t0), flush=True)

layers = {}
for pid, text in rows:
    t = text.lower()
    L = len(t)
    hit_pos = {}; op_pos = {}; strong_pos = {}
    for m in LEX:
        p = first_pos(t, m["patterns"])
        if p is not None:
            hit_pos[m["id"]] = p
    for m in LEX:
        p = first_pos(t, m["op_patterns"])
        if p is not None:
            op_pos[m["id"]] = p
    for mid, spats in STRONG.items():
        p = first_pos(t, spats)
        if p is not None:
            strong_pos[mid] = p
    if "INV-REVIEW" in strong_pos:
        layer = "L4_EXCLUDE"; primary = "INV-REVIEW"
    elif not hit_pos:
        layer = "L3_OPEN"; primary = None
    elif op_pos:
        primary = min(op_pos, key=op_pos.get)
        op_list = [x for x in op_pos if x not in ("SUP-BIOINFO", "INV-REVIEW")]
        # L1：唯一 op、op==primary、strong 含 primary、op 位置在前 35%
        if (len(op_list) == 1 and op_list[0] == primary and primary in strong_pos
                and op_pos[primary] <= L * 0.35):
            layer = "L1_HIGH"
        elif primary in ("SUP-BIOINFO", "INV-REVIEW"):
            layer = "L3_OPEN"
        else:
            layer = "L2_MID"
    elif strong_pos:
        primary = min(strong_pos, key=strong_pos.get)
        if primary in ("SUP-BIOINFO", "INV-REVIEW"):
            layer = "L3_OPEN"
        else:
            layer = "L2_MID"
    else:
        primary = min(hit_pos, key=hit_pos.get)
        if primary in ("SUP-BIOINFO", "INV-REVIEW"):
            layer = "L3_OPEN"
        else:
            layer = "L2_MID"
    layers[pid] = layer

cnt = Counter(layers.values())
n_total = len(layers)
print("layers:", dict(cnt))
print("L1+L2 (候选可落地):", cnt.get("L1_HIGH", 0) + cnt.get("L2_MID", 0))
print("L3 (未决):", cnt.get("L3_OPEN", 0), " L4 (排除):", cnt.get("L4_EXCLUDE", 0))
json.dump(layers, open(os.path.join(OUT, "step4_layers.json"), "w", encoding="utf-8"), ensure_ascii=False)

# 分层抽样
random.seed(20260827)
p1 = [pid for pid, l in layers.items() if l == "L1_HIGH"]
p2 = [pid for pid, l in layers.items() if l == "L2_MID"]
p3 = [pid for pid, l in layers.items() if l == "L3_OPEN"]
random.shuffle(p1); random.shuffle(p2); random.shuffle(p3)
sample = p1[:15] + p2[:10] + p3[:8]
objs = dict(Protocol.objects.filter(id__in=sample).values_list("id", "objective"))
names = dict(Protocol.objects.filter(id__in=sample).values_list("id", "name"))
signals = json.load(open(os.path.join(OUT, "step4_signals_v05.json"), encoding="utf-8"))

lines = ["# Step 4 分层量化抽样（L1 15 / L2 10 / L3 8）", "",
         "| # | 层 | 协议名 | primary | op | 全部信号 | objective（前 160 字符） |",
         "|---|---|---|---|---|---|---|"]
for i, pid in enumerate(sample, 1):
    v = signals[str(pid)]
    op_s = "; ".join(v["op"]) if v["op"] else "-"
    sigs = "; ".join(v["methods"]) if v["methods"] else "-"
    obj = (objs.get(pid) or "")[:160].replace("|", "/").replace("\n", " ")
    lines.append(f"| {i} | {layers[pid]} | {(names.get(pid) or '?')[:42]} | {v['primary'] or '-'} | {op_s[:45]} | {sigs[:55]} | {obj} |")
md = "\n".join(lines)
open(os.path.join(OUT, "step4_layers_sample.md"), "w", encoding="utf-8").write(md)
print("saved step4_layers.json + step4_layers_sample.md, n=", len(sample))
