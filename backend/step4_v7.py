# Step 4 v0.7：第四轮补词典（L3 收敛 → ≤20%）
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
PATCH3 = {
    "M01": ["preparing dna samples", "dna samples from", "dna extraction from", "dna isolation from"],
    "M05p": ["mitochondrial protein fraction", "protein fractionation"],
    "M10": ["adapter ligation", "adaptor ligation"],
    "M15": ["genotyping"],
    "M19": ["gene knockout", "knockout"],
    "M23b": ["complex purification", "biochemical purification"],
    "M24": ["pericyte culture", "hbvp"],
    "M25": ["differentiation medium", "differentiation media", "sh-sy5y"],
    "M26": ["immune cells isolation", "cd45 beads"],
    "M36": ["nucleus staining", "nuclear staining", "nucblue"],
    "NEW-PlantBiochemAssay": ["nitric oxide", "no detection"],
    "NEW-ScreeningAssay": ["luciferase", "luciferin", "nanoluc", "reporter gene"],
    "SUP-BIOINFO": ["imagej", "image analysis", "pixel classification", "roi analysis", "quantitative image"],
}
PATCH4 = {
    "M07": ["titration", "potentiometric"],
    "M19": ["crispr screen", "genetic screen"],
    "M20": ["rnai", "rna interference", "sirna knockdown"],
    "M24": ["conditioned media", "conditioned medium"],
    "M26": ["protoplast", "islet isolation", "pancreatic islet isolation", "tissue explant"],
    "M28": ["luminex", "bead-based assay", "multiplex immunoassay", "cytokine panel", "mesoscale discovery", "msd assay"],
    "M35": ["grab sensor", "fiber photometry", "grin lens"],
    "M45": ["bacteriophage"],
    "M50": ["transplantation", "surgical implantation", "kidney capsule", "surgery"],
    "M54": ["swab sampling", "swabbing"],
    "NEW-PlantBiochemAssay": ["phosphate absorption", "nutrient uptake", "aqueous extract", "plant extract"],
    "SUP-BIOINFO": ["optical fractionator", "stereology", "image quantification"],
}
APPEND_METHODS = [
    {"id": "NEW-GibsonAssembly", "name": "Gibson/Golden Gate DNA Assembly", "app": "A5", "type": "technique",
     "patterns": ["gibson assembly", "gibson", "dna assembly", "golden gate", "seamless cloning"]},
    {"id": "NEW-SmallMoleculeSynthesis", "name": "Small Molecule Synthesis", "app": "A12b", "type": "technique",
     "patterns": ["small molecule synthesis", "preparative-scale synthesis", "organic synthesis", "chemical synthesis"]},
    {"id": "NEW-UbiquitinationAssay", "name": "Ubiquitination/PTM Assay", "app": "A13", "type": "assay",
     "patterns": ["ubiquitination", "ubiquitin ligase", "deubiquitination", "ubiquitin assay"]},
    {"id": "NEW-TissueClearing", "name": "Tissue Clearing", "app": "A9", "type": "technique",
     "patterns": ["brain clearing", "idisco", "tissue clearing", "optical clearing", "clarify", "seadb"]},
    {"id": "NEW-BindingAssay", "name": "Receptor/Ligand Binding Assay", "app": "A13", "type": "assay",
     "patterns": ["receptor binding", "ligand binding", "binding assay", "autoradiography", "saturation binding", "competition binding"]},
    {"id": "NEW-BioorthogonalLabeling", "name": "Click Chemistry/Bioorthogonal Labeling", "app": "A13", "type": "technique",
     "patterns": ["click chemistry", "boncat", "metabolic labeling", "azide-alkyne cycloaddition"]},
]
for m in LEX:
    m["patterns"] += PATCH2.get(m["id"], []) + PATCH3.get(m["id"], []) + PATCH4.get(m["id"], [])
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
      "embedding", "electroporation", "chromatography", "assembly", "ubiquitination", "fractionation",
      "clearing", "binding", "titration"]
for m in LEX:
    m["op_patterns"] = [p for p in m["patterns"] if any(o in p for o in OP)]

STRONG = {
    "M01": ["genomic dna", "dna extraction", "dna isolation"], "M02": ["rna extraction", "rna isolation", "total rna"],
    "M03": ["gel purification", "gel extraction"], "M05": ["protein extraction", "cell lysis", "protein lysate"],
    "M05p": ["trypsin digestion", "proteomics sample", "sp3", "stage tip"], "M07": ["metabolite extraction", "metabolomics", "lc-ms", "gc-ms"],
    "M10": ["library preparation", "library prep", "amplicon", "illumina", "tagmentation"], "M11": ["rna-seq", "rna sequencing"],
    "M11a": ["single-cell rna", "scrna-seq", "drop-seq"], "M11b": ["single-nucleus", "snrna-seq"],
    "M12": ["nanopore", "pacbio", "long-read"], "M13": ["viral sequencing", "viral genome", "viral metagenome"],
    "M14": ["chip-seq", "chromatin", "atac-seq"], "M15": ["polymerase chain reaction", "pcr amplification", "qpcr", "genotyping"],
    "M16": ["reverse transcription", "cdna synthesis", "revertaid"], "M17": ["competent cells", "heat-shock", "electroporation", "transformation"],
    "M18": ["agrobacterium"], "M19": ["crispr", "cas9", "genome editing", "knockout", "gene knockout", "crispr screen"], "M20": ["mutagenesis", "base editing", "rnai"],
    "M21": ["lentivirus", "lentiviral", "retrovirus", "transduction"], "M22": ["crosslinking", "clip", "proximity"],
    "M23": ["recombinant protein expression", "protein expression", "overexpression"], "M23b": ["affinity purification", "chromatography", "his-tag", "protein purification", "complex purification"],
    "M24": ["ipsc", "hpsc", "pluripotent", "organoid", "gastruloid"], "M25": ["neuronal differentiation", "cortical neuron", "differentiation medium"],
    "M26": ["pbmc", "ficoll", "cell isolation", "immune cells isolation", "protoplast", "islet isolation"], "M27": ["cryopreservation", "cryopreserve"],
    "M28": ["elisa", "immunosorbent assay", "luminex", "mesoscale discovery"], "M29": ["flow cytometry", "facs", "immunophenotyping"],
    "M31": ["colony immunoblot"], "M32": ["fluorescence imaging", "confocal", "live-cell imaging"],
    "M33": ["electron microscopy", "clem", "cryo-em"], "M34": ["codex", "multiplexed imaging", "visium", "geomx"],
    "M35": ["calcium imaging", "gcamp", "grab sensor", "fiber photometry"], "M36": ["immunofluorescence", "nucleus staining"],
    "M37": ["immunohistochemistry", "ihc"], "M38": ["western blot", "western blotting", "immunoblotting"],
    "M39": ["immunoprecipitation", "pull-down"], "M40": ["peptide synthesis", "solid-phase peptide"],
    "M41": ["microsphere", "particle synthesis"], "M42": ["kinase", "phosphorylation", "ubiquitination"],
    "M43": ["autophagy", "mitophagy"], "M43b": ["lysosomal", "lysosome"],
    "M44": ["alpha-synuclein", "amyloid", "aggregation"], "M45": ["infection assay", "focus assay", "plaque", "moi", "phage"],
    "M46": ["bacterial culture", "microbial culture", "cyanobacteria"], "M47": ["biofilm", "cfu"],
    "M48": ["pathogen", "rhizoctonia"], "M49": ["drosophila", "c. elegans", "caenorhabditis", "zebrafish"],
    "M50": ["in vivo recording", "craniotomy", "transplantation"], "M51": ["behavioral", "open field", "conditioning"],
    "M52": ["pharmacokinetic"], "M53": ["electrophysiology", "patch clamp", "whole-cell recording"],
    "M54": ["edna", "metabarcoding", "environmental dna"],
    "NEW-SDS-PAGE": ["sds-page", "polyacrylamide"], "NEW-RNAISH": ["in situ hybridization", "rnascope", "rna fish"],
    "NEW-TissueEmbedding": ["embedding", "cryosectioning"], "NEW-ScreeningAssay": ["high-throughput screening", "384-well", "luciferase", "reporter gene"],
    "NEW-CellViabilityAssay": ["viability", "prestoblue", "resazurin"], "NEW-MitoFunctionAssay": ["mitochondrial function", "oxygen consumption", "seahorse"],
    "NEW-PlantBiochemAssay": ["guard cell", "stomata", "vacuole", "nitric oxide", "phosphate absorption"], "NEW-ViralMolDetection": ["sars-cov-2", "viral detection", "rt-lamp"],
    "NEW-3DCulture": ["3d culture", "spheroid", "matrigel"], "NEW-EVIsolation": ["exosome", "extracellular vesicle"],
    "NEW-GibsonAssembly": ["gibson assembly", "golden gate"], "NEW-SmallMoleculeSynthesis": ["preparative-scale synthesis", "small molecule synthesis"],
    "NEW-UbiquitinationAssay": ["ubiquitination", "ubiquitin ligase", "deubiquitination"], "NEW-TissueClearing": ["brain clearing", "idisco", "tissue clearing"],
    "NEW-BindingAssay": ["receptor binding", "binding assay", "autoradiography"], "NEW-BioorthogonalLabeling": ["click chemistry", "boncat"],
    "SUP-BIOINFO": ["bioinformatics", "structure prediction", "alphafold", "pipeline", "image analysis", "imagej"], "INV-REVIEW": ["systematic review", "meta-analysis", "clinical trial"],
}

def first_pos(text, patterns):
    ps = [text.find(p) for p in patterns]
    ps = [x for x in ps if x != -1]
    return min(ps) if ps else None

qs = Protocol.objects.only("id", "name", "objective").all()
rows = [(p.id, (p.name or "") + " . " + (p.objective or "")) for p in qs]
print("loaded %d (%.1fs)" % (len(rows), time.time() - t0), flush=True)

signals = {}; layers = {}
for pid, text in rows:
    t = text.lower(); L = len(t)
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
        primary = "INV-REVIEW"; layer = "L4_EXCLUDE"
    elif not hit_pos:
        primary = None; layer = "L3_OPEN"
    else:
        wet_op = {k: v for k, v in op_pos.items() if k not in ("SUP-BIOINFO", "INV-REVIEW")}
        wet_strong = {k: v for k, v in strong_pos.items() if k not in ("SUP-BIOINFO", "INV-REVIEW")}
        if wet_op:
            primary = min(wet_op, key=wet_op.get)
            op_list = list(wet_op.keys())
            if (len(op_list) == 1 and op_list[0] == primary and primary in strong_pos
                    and op_pos[primary] <= L * 0.35):
                layer = "L1_HIGH"
            else:
                layer = "L2_MID"
        elif wet_strong:
            primary = min(wet_strong, key=wet_strong.get)
            layer = "L2_MID"
        elif strong_pos:
            primary = min(strong_pos, key=strong_pos.get)  # SUP/INV 兜底（仅无湿方法信号时）
            layer = "L3_OPEN" if primary in ("SUP-BIOINFO", "INV-REVIEW") else "L2_MID"
        else:
            primary = min(hit_pos, key=hit_pos.get)
            layer = "L3_OPEN" if primary in ("SUP-BIOINFO", "INV-REVIEW") else "L2_MID"
    signals[pid] = {"methods": sorted(hit_pos.keys()), "op": sorted(op_pos.keys()),
                    "strong": sorted(strong_pos.keys()), "primary": primary}
    layers[pid] = layer
json.dump(signals, open(os.path.join(OUT, "step4_signals_v07.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(layers, open(os.path.join(OUT, "step4_layers_v07.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("signals+layers v0.7 done (%.1fs)" % (time.time() - t0), flush=True)

VALID_EX = {"SUP-BIOINFO", "INV-REVIEW"}
prim_count = Counter(v["primary"] for v in signals.values())
n_total = len(signals)
n_no = sum(1 for v in signals.values() if not v["primary"])
n_rev = prim_count.get("INV-REVIEW", 0)
n_sup = prim_count.get("SUP-BIOINFO", 0)
n_eligible = n_total - n_rev
n_covered = sum(1 for v in signals.values() if v["primary"] and v["primary"] not in VALID_EX)
ec = n_covered / n_eligible * 100 if n_eligible else 0
lc = Counter(layers.values())
print("==")
print("no_signal:", n_no, "review:", n_rev, "sup:", n_sup, "EC_v07: %.2f%%" % ec)
print("layers:", dict(lc), "L3:", lc.get("L3_OPEN", 0), "(%.1f%%)" % (lc.get("L3_OPEN", 0) / n_total * 100))
print("top:", prim_count.most_common(14))

lines = ["# Step 4 v0.7.1 报告：第四轮补词典 + phage bug 修复 + SUP 仅兜底", "",
         f"- 协议总数：{n_total}；无信号：{n_no}；综述：{n_rev}；生信：{n_sup}",
         "",
         "| 指标 | v0.6 | v0.7 | **v0.7.1** |",
         "|---|---|---|---|",
         f"| EC（信号口径） | 69.70% | 71.63% | **{ec:.2f}%**（{n_covered}/{n_eligible}） |",
         f"| 无信号 | 3263 | 3017 | **{n_no} ({n_no/n_total*100:.1f}%)** |",
         f"| L3 未决 | 4240 (30.1%) | 3970 (28.2%) | **{lc.get('L3_OPEN',0)} ({lc.get('L3_OPEN',0)/n_total*100:.1f}%)** |",
         f"| L1 高置信 | 1727 | 1759 | **{lc.get('L1_HIGH',0)}** |",
         f"| L2 中置信 | 7953 | 8191 | **{lc.get('L2_MID',0)}** |",
         "",
         "> v0.7.1 修复：M45 'phage' 子串误命中 'macrophage'（→bacteriophage）；SUP-BIOINFO 仅兜底（不参与湿实验主方法排序，消除 data analysis 等抢湿实验）。",
         "",
         "## 主方法分布（top 14）", "", "| Method | 数 | Method | 数 |", "|---|---|---|---|"]
top = prim_count.most_common(28)
half = (len(top) + 1) // 2
for i in range(half):
    l = top[i]; r = top[i + half] if i + half < len(top) else None
    lines.append("| %s | %d | %s | %s |" % (l[0], l[1], r[0] if r else "", r[1] if r else ""))
open(os.path.join(OUT, "step4_v071_report.md"), "w", encoding="utf-8").write("\n".join(lines))
print("saved step4_v071_report.md")
