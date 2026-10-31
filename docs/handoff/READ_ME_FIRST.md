# READ ME FIRST

## What you are doing

Below you will receive batches of records. Each record links one laboratory **protocol**
to one canonical **method** (a technique category). For each record, decide whether that
link is correct — that is, whether the protocol genuinely uses that method.

You are judging **one record at a time**, independently. There is no answer key and no
prior labelling to match. Use your own domain knowledge and the method definitions in the
appendix at the bottom of this file.

---

## What you receive

1. **This file** — the task, the label definitions, the output format, and the definitions
   of all 83 methods.
2. **One batch file** (`part_XX.jsonl`) — a few hundred records, one JSON object per line.

Each record looks like this:

```json
{"task":"A","bridge_id":123,"method_id":47917,"criteria_key":"Sanger Sequencing",
 "protocol_id":456,"protocol_name":"...","protocol_objective":"...",
 "link_source":"manual_curated","link_status":"active"}
```

Notes:

- `protocol_name` and `protocol_objective` describe the protocol. `protocol_objective` may
  be empty; when it is, judge from the title alone and lower your confidence accordingly.
- **The record does not carry the method's name or definition.** Look those up by
  `method_id` in the appendix at the bottom of this file.
- `criteria_key`, `link_source` and `link_status` are metadata about how the link was
  originally produced. They are **not** evidence about whether it is correct — ignore them
  for judging.
- If a `method_id` is missing from the appendix, report it. Do not guess.

---

## Three labels

Pick exactly one per record:

| Label | Meaning |
|---|---|
| `on_topic` | The protocol's **core technique is** this method. |
| `tangential` | The method genuinely appears in the protocol, but only as a secondary or incidental step — not what the protocol is fundamentally about. |
| `wrong` | The protocol does not meaningfully involve this method. |

There is no preference ordering among these labels and no expectation about how often
each should appear. Call it as you see it.

---

## Output format

One JSON object per line, in the **same order as the input**. If the batch has 500 records,
output exactly 500 lines.

Required fields:

| Field | Type | Notes |
|---|---|---|
| `task` | string | always `"A"` |
| `method_id` | integer | copy from the input record |
| `protocol_id` | integer | copy from the input record |
| `verdict` | string | `on_topic` / `tangential` / `wrong` |
| `confidence` | string | `high` / `medium` / `low` |
| `reason` | string | <= 25 words, in English, stating why you chose this label |

Example of a single line:

```json
{"task":"A","method_id":47917,"protocol_id":456,"verdict":"wrong","confidence":"high","reason":"Protocol describes bacterial plate streaking; no sequencing performed."}
```

Rules for the output:

- **No** commentary, preamble, summary, or markdown fences. JSON lines only.
- Do not merge, split, deduplicate, or reorder records.
- If output is truncated, you will be asked to continue from where you stopped.
- `reason` should say what the protocol actually does and why that does or does not match
  the method — not restate the method's definition.

---

## Appendix — definitions of all 83 methods

Look up by `method_id`. The italic note marks methods that are typically supporting steps
inside other workflows rather than standalone techniques; that note is descriptive context
only and carries no judging instruction.

- `47888` — **Flow Cytometry**
  Flow cytometry measures optical and fluorescence properties of individual cells or particles in a fluid stream, enabling enumeration and phenotyping of heterogeneous populations. Researchers use it to quantify surface or intracellular markers, assess uptake and internalization, and track reporter expression across samples.
- `47889` — **PCR**
  PCR amplifies specific DNA sequences through repeated cycles of denaturation, primer annealing, and extension by a thermostable polymerase. Researchers use it to detect or quantify targets, prepare DNA for cloning or sequencing, and genotype samples from diverse sources.
- `47890` — **Immunofluorescence Staining**
  Immunofluorescence staining uses fluorophore-conjugated antibodies to label specific proteins in fixed or live cells and tissues, which are then imaged by fluorescence microscopy. Researchers choose it to determine protein localization, distribution, and abundance, or to visualize clustering, puncta, and internalization in situ.
- `47891` — **Live-cell Fluorescence Imaging**
  Live-cell fluorescence imaging detects fluorescently tagged or stained molecules in intact cells over time. Researchers use it to follow localization, clustering, internalization, and reporter activity in living samples, preserving spatial and temporal context that fixed-cell methods cannot capture.
- `47892` — **Bacterial/Microbial Culture**
  Bacterial and microbial culture propagates microorganisms in controlled media to obtain viable cells, isolates, or stocks. Researchers use it when they need to expand cultures for downstream assays, maintain strains, or prepare inocula for experimental work.
- `47893` — **Cell Viability Assay**
  Cell viability assays quantify the proportion of live cells in a population after experimental treatment. Researchers use them to assess cytotoxicity, compare drug or compound effects, and monitor cell health over time across many cell types and formats.
- `47894` — **Genomic DNA Extraction**
  Genomic DNA extraction isolates DNA from a range of sample types, including plant nuclei, plasmid DNA on filter paper, and microbial or viral communities. Researchers choose it when they need DNA suitable for downstream applications such as sequencing, PCR, or methylome analysis.
- `47895` — **Real-Time Quantitative PCR (qPCR)**
  Real-time quantitative PCR amplifies a specific DNA target while measuring fluorescence each cycle, allowing quantification of starting template amounts. Researchers use it to measure gene expression, detect or quantify pathogens and specific sequences, and assess DNA modification status.
- `47896` — **Behavioral Assessment**
  Behavioral assessment measures observable actions, performance, or physiological outputs to infer function in living subjects. Researchers use it when the question concerns behavior, cognition, or integrated physiological responses rather than isolated molecular events. Protocols span invertebrate and rodent tasks, exercise testing, and clinical functional measures.
- `47897` — **Illumina Sequencing**
  Illumina sequencing is a short-read, sequencing-by-synthesis method that generates nucleotide reads from DNA or RNA-derived libraries. Researchers choose it for applications requiring high-throughput read output, including transcriptome profiling, small RNA and non-polyadenylated RNA analysis, methylation studies, amplicon sequencing, and microbiome taxonomy. Library preparation and read configuration are adapted to each application.
- `47898` — **3D Cell Culture**
  3D cell culture maintains cells in three-dimensional arrangements that better approximate tissue architecture, cell-cell contacts, and spatial gradients than planar culture. Researchers use it to study morphology, migration, aggregation, colony formation, and differentiation in contexts where spatial organization influences the observed phenotype.
- `47899` — **Immunohistochemistry**
  Immunohistochemistry detects specific proteins in tissue sections using antibody-based staining, preserving spatial context within the tissue architecture. Researchers choose it to localize or assess target expression in situ, including on biopsy and archived specimens.
- `47900` — **CRISPR-Cas9 Genome Editing**
  CRISPR-Cas9 introduces targeted double-strand breaks at genomic loci defined by a guide RNA, enabling knockouts, knock-ins, and other edits through cellular repair. Researchers choose it when they need site-specific modification of a gene in cells or organisms.
- `47901` — **ELISA**
  ELISA detects and quantifies specific proteins, antibodies, or small molecules in liquid samples using antibody-based binding and an enzymatic signal readout. Researchers choose it for sensitive, plate-based measurement of analytes across serum, culture, and environmental matrices.
- `47902` — **RNA Isolation**
  RNA isolation recovers total or fractionated RNA from cells, tissues, or body fluids for downstream analysis such as sequencing, RT-PCR, or small RNA detection. Researchers choose it when they need intact RNA suitable for transcriptome profiling, non-polyadenylated RNA enrichment, or microRNA characterization across diverse sample types.
- `47903` — **Protein Purification**
  Protein purification isolates a specific protein or protein complex from a biological source by separating it from other cellular components. Researchers choose it when downstream experiments require enriched, functionally active protein, such as structural analysis, activity assays, cross-linking, or proteomic profiling.
- `47904` — **Amplicon/Illumina Library Prep**
  Amplicon/Illumina library prep converts PCR amplicons into indexed libraries for short-read sequencing on Illumina platforms. Researchers choose it when targeted loci, marker genes, or barcoded constructs must be sequenced across many samples in parallel.
- `47905` — **Western Blot**
  Western blot separates proteins by gel electrophoresis, transfers them to a membrane, and detects specific proteins with antibodies. Researchers use it to assess protein presence, size, and relative abundance in complex samples.
- `47906` — **Immunoprecipitation**
  Immunoprecipitation uses an antibody immobilized on a solid support to capture a specific antigen from a complex mixture, allowing its separation from other components. Researchers choose it to enrich a target protein or complex for downstream analysis, or to assess interactions and modifications in native samples.
- `47907` — **SDS-PAGE**
  SDS-PAGE separates proteins by molecular mass under denaturing conditions, using an anionic detergent to unfold polypeptides and impart a uniform charge-to-mass ratio. Researchers use it to assess purity, monitor fractionation, verify protein preparation, and resolve samples before immunoblotting or mass spectrometry.
- `47908` — **Metabolite Extraction (LC-MS)**
  Metabolite extraction prepares biological samples for LC-MS analysis by isolating small-molecule metabolites from cells or tissues. Researchers choose it when profiling metabolite composition, quantifying specific compounds, or comparing metabolic states across samples.
- `47909` — **Calcium/Functional Imaging**
  Calcium/functional imaging uses fluorescent or luminescent indicators to monitor intracellular ion dynamics and related functional readouts in living cells and tissues. Researchers choose it to follow signaling events, vesicle turnover, or reporter activity over time in situ.
- `47910` — **Immune/Stromal Cell Isolation & Culture**
  Covers isolation and culture of immune and stromal cells from blood, tissue, or culture, including depletion and activation steps. Researchers use it when a defined cell population is needed for downstream assays such as sequencing, reporter assays, or functional testing.
- `47911` — **Electrophysiological Recording**
  Electrophysiological recording measures electrical activity from excitable tissues such as nerves, muscle, and heart using electrodes placed in vitro, in vivo, or on the body surface. Researchers choose it to capture real-time physiological signals, including single-unit activity, nerve compound potentials, and electrocardiograms.
- `47912` — **In-vivo Recording & Surgery**
  In-vivo recording and surgery covers procedures for instrumenting live animals to acquire physiological or neural signals, including electrode implantation, cannulation, and telemetry. Researchers choose it when measurements must be made in the intact, functioning organism rather than in vitro.
- `47913` — **Recombinant Protein Expression**
  Recombinant protein expression uses host cells or cell-free systems to produce a target protein from a cloned gene. Researchers choose it when they need preparative amounts of a protein for purification, biochemical assays, or structural work.
- `47914` — **RNA-seq Library Prep**
  RNA-seq library prep converts RNA into sequenceable cDNA libraries for transcriptome profiling. Variants accommodate polyadenylated or non-polyadenylated inputs, bulk tissues, single cells, small RNAs, and long reads, so researchers select a protocol matched to their sample type and question.
- `47915` — **Single-cell RNA-seq**
  Single-cell RNA-seq profiles transcriptomes of individual cells, resolving cell types, states, and heterogeneity within a sample. Researchers choose it when bulk measurements would obscure cell-to-cell variation, such as mapping tissue composition or identifying rare populations.
- `47916` — **Bacterial Transformation**
  Bacterial transformation introduces exogenous DNA into competent bacterial cells, typically via heat shock or electroporation, followed by selection on antibiotic-containing media. Researchers use it to propagate plasmids, build libraries, and move constructs between hosts.
- `47917` — **Sanger Sequencing** *(often a supporting step rather than a standalone technique)*
  Sanger sequencing determines the nucleotide sequence of DNA fragments by chain-termination synthesis with dideoxynucleotides and capillary or gel electrophoretic separation of the products. It is chosen for targeted, low-throughput readouts such as verifying constructs, confirming PCR products, and genotyping specific loci.
- `47918` — **Long-read Sequencing**
  Long-read sequencing generates continuous nucleotide reads from single DNA or RNA molecules, resolving repeats, structural variants, and full-length transcripts that short reads fragment. Researchers choose it for de novo assembly, isoform characterization, haplotype phasing, and genome or amplicon analysis where read length or continuity matters.
- `47919` — **Pluripotent Stem Cell Culture**
  Pluripotent stem cell culture maintains undifferentiated embryonic and induced pluripotent stem cells under defined conditions, supporting self-renewal and subsequent differentiation. Researchers use it to expand lines for gene editing, differentiation, and reprogramming studies.
- `47920` — **Pathogen Infection Assay**
  A Pathogen Infection Assay introduces a defined pathogen to a host, tissue, or substrate under controlled conditions and measures the resulting infection, colonization, or killing. Researchers use it to compare virulence, test antimicrobial or immune treatments, or quantify pathogen burden across experimental groups.
- `47921` — **High-throughput Screening Assay**
  A high-throughput screening assay measures a defined phenotype across many samples or variants in parallel, typically in multiwell plates with automated liquid handling and plate readers or imaging. Researchers choose it when comparing large libraries, compound sets, or mutant panels requires consistent, miniaturized measurement rather than one-off assays.
- `47922` — **Single-nucleus RNA-seq**
  Single-nucleus RNA-seq profiles gene expression from individual nuclei, enabling transcriptomic analysis of tissues that are difficult to dissociate into intact cells, including frozen or archived material. Researchers choose it when whole-cell dissociation is impractical or when nuclear transcripts are the desired readout.
- `47923` — **Reverse Transcription & cDNA Synthesis**
  Reverse transcription converts RNA templates into complementary DNA using a reverse transcriptase, primed by oligo-dT, random primers, or gene-specific primers. Researchers choose it when RNA must be stabilized as cDNA for downstream amplification, library construction, or transcript quantification.
- `47924` — **Viral Vector Transduction**
  Viral vector transduction introduces genetic material into target cells using viral particles, enabling stable or transient expression of shRNAs, cDNAs, reporters, or CRISPR components. Researchers choose it when they need efficient delivery across hard-to-transfect cells or sustained expression for perturbation and lineage-tracing studies.
- `47925` — **Lipid Extraction**
  Lipid extraction separates lipids from aqueous and non-lipid components of a sample using organic solvents, yielding a lipid fraction suitable for downstream quantification or analysis. Researchers choose it when preparing cells, tissues, or other matrices for measurement of total lipids or specific lipid classes.
- `47926` — **Tissue Embedding**
  Tissue embedding infiltrates and surrounds specimens with a supporting medium so they can be sectioned or imaged while preserving structure. Researchers choose it when samples need mechanical support for microtomy, cryosectioning, or resin-based fluorescence and electron microscopy workflows.
- `47927` — **Protein Lysis & Solubilization**
  Protein lysis and solubilization disrupts cells and extracts proteins into solution for downstream analysis. Researchers choose it when preparing lysates for assays, fractionation, or proteomic workflows, with buffer composition adjusted to preserve the target protein's activity or interactions.
- `47928` — **Plant Biochemical Assay**
  Plant biochemical assays measure chemical constituents, enzyme activities, or staining reactions in plant tissues to assess physiological state, stress responses, or developmental processes. Researchers choose these assays when a specific biochemical or histochemical readout is needed to complement phenotypic or genetic observations.
- `47929` — **Model-organism Husbandry**
  Covers the routine care and propagation of model organisms, including feeding, watering, housing, acclimation, breeding, and synchronized culture. Researchers use it to establish and maintain healthy, reproducible stocks before experimental manipulation.
- `47930` — **Proteomics Sample Prep**
  Proteomics sample prep covers the steps that turn cells, tissues, or purified complexes into peptides suitable for mass spectrometry, including lysis, protein extraction, reduction and alkylation, digestion, and optional labelling or fractionation. Researchers choose it when they need to identify or quantify proteins from a defined sample, from single complexes to whole proteomes.
- `47931` — **Cryopreservation**
  Cryopreservation preserves cells, organisms, and biological samples at low temperature for long-term storage. Researchers use it to maintain cell lines, archive strains, and prepare samples for downstream cryo-based analysis or shipment.
- `47932` — **Gel Purification of DNA**
  Gel purification separates DNA fragments by agarose gel electrophoresis and recovers a specific size band from the gel matrix. Researchers use it when a defined fragment must be isolated from mixed products, primers, or other bands, such as after restriction digestion, PCR, or library preparation.
- `47933` — **Viral Infection & Focus Assays**
  Viral infection and focus assays quantify infectious virus by inoculating susceptible cells and detecting infected foci, often with antibody or reporter-based readouts. Researchers use them to titrate viral stocks, assess neutralization, and measure replication-competent virus in samples.
- `47934` — **Environmental/eDNA Sampling**
  Environmental/eDNA sampling collects biological material from air, water, sediment, soil, or surfaces to detect organisms present in a habitat without direct capture. Researchers choose it for biodiversity inventories, pathogen or indicator monitoring, and detection of species that are difficult to observe directly.
- `47935` — **Receptor/Ligand Binding Assay**
  Receptor/ligand binding assays measure the interaction between a receptor and its ligand, typically to determine affinity, kinetics, or binding specificity. Researchers choose this approach when they need to quantify binding under defined conditions, including whole-cell or cell-free formats.
- `47936` — **Agrobacterium-mediated Plant Transformation**
  Agrobacterium-mediated transformation delivers DNA into plant cells via bacterial infection, enabling stable integration or transient expression. Researchers use it for generating transgenic lines, transient assays, virus-induced gene silencing, and studying gene function in diverse plant species.
- `47937` — **Viral Molecular Detection**
  Viral molecular detection covers the purification and concentration of virus particles from environmental, faecal, sediment, and clinical samples, followed by molecular assays to identify and characterise viral nucleic acid. Researchers choose it when they need to detect or type viruses directly rather than rely on culture or serology.
- `47938` — **Multiplexed Tissue Imaging**
  Multiplexed tissue imaging detects multiple markers within a single tissue section while preserving spatial context. Researchers choose it to map cell types, states, and tissue architecture across heterogeneous samples in one experiment.
- `47939` — **Targeted Mutagenesis (TAM)**
  Targeted mutagenesis introduces defined sequence changes at a chosen genomic locus, enabling construction of point mutants, deletions, and reporter or variant alleles in bacterial, mouse, and mammalian systems. Researchers choose it when a specific genetic alteration is needed to test gene function or model a variant.
- `47940` — **ChIP-seq/Chromatin Profiling**
  Chromatin profiling methods map protein-DNA interactions, nucleosome positions, and chromatin accessibility genome-wide. Researchers choose these approaches to locate transcription factor binding sites, define chromatin states, or resolve chromatin architecture in bulk or single cells.
- `47941` — **Neuronal Differentiation**
  Neuronal differentiation converts stem cells or somatic cells into neuron-like cells that express neuronal markers, extend processes, and form functional synapses. Researchers use it to obtain cultured neurons for morphological, electrophysiological, and imaging-based assays of synaptic, mitochondrial, and organelle function.
- `47942` — **FISH Technique**
  Fluorescence in situ hybridisation detects specific DNA or RNA sequences in fixed cells and tissue by hybridising labelled probes and visualising them by fluorescence microscopy. Researchers use it to localise sequences within intact cellular and tissue architecture, including whole-mount preparations and cultured cells.
- `47943` — **Enzymatic Labeling** *(often a supporting step rather than a standalone technique)*
  Enzymatic labeling uses an enzyme's catalytic activity to attach a detectable label or to convert a substrate into a measurable product. Researchers choose it when they need to visualize or quantify enzyme activity, label surface proteins, or measure metabolite concentrations in biological samples.
- `47944` — **Correlative Light-Electron Microscopy**
  Correlative light-electron microscopy pairs fluorescence imaging of labeled molecules with electron microscopy of the same specimen, allowing fluorescent signals to be mapped onto ultrastructural context. Researchers choose it when molecular identity must be assigned within detailed cellular architecture.
- `47945` — **RNA In Situ Hybridization**
  RNA in situ hybridization detects specific RNA transcripts within intact cells or tissue sections by hybridizing labelled probes to target sequences. Researchers use it to localize RNA spatially while preserving tissue morphology, including multiplexed detection of individual transcripts.
- `47946` — **Click Chemistry Labeling**
  Click chemistry labeling covalently attaches tags, fluorophores, or affinity handles to biomolecules through bioorthogonal reactions such as azide-alkyne cycloaddition. Researchers choose it when selective, mild conjugation is needed on proteins, nucleic acids, or labeled metabolites in complex samples.
- `47947` — **Microsphere/Particle Synthesis**
  Microsphere and particle synthesis produces dispersed colloidal or polymeric particles with controlled composition and size, using approaches such as reduction, emulsion, membrane emulsification, or nanoprecipitation. Researchers choose it to generate nanoparticles, nanogels, or droplets for drug delivery, imaging, catalysis, or in vitro reconstitution.
- `47948` — **In-vivo PK Sampling & Bioanalysis**
  In-vivo PK sampling and bioanalysis collects blood or plasma at defined times after dosing and quantifies drug concentrations to characterize absorption, distribution, and clearance. Researchers use it when they need time-resolved exposure data from living animals or human subjects.
- `47949` — **Tissue Clearing**
  Tissue clearing renders biological specimens optically transparent by removing or matching refractive index of lipids and other light-scattering components, enabling deep imaging of internal structures by light and fluorescence microscopy. Researchers choose it when intact three-dimensional architecture must be visualized without physical sectioning.
- `47950` — **Mitochondrial Function Assay**
  Mitochondrial function assays measure respiration, complex activity, morphology, mtDNA turnover, and flux in live or fixed samples. Researchers choose them to assess oxidative phosphorylation, mitochondrial quality control, and organelle dynamics across cell types and organisms.
- `47951` — **Kinase Activity Assay**
  A kinase activity assay measures the catalytic activity of a kinase by detecting phosphorylation of a substrate or a coupled readout of nucleotide consumption. Researchers use it to quantify kinase function, compare activity across samples or conditions, and support kinetic or inhibitor studies.
- `47952` — **Extracellular Vesicle Isolation**
  Extracellular vesicle isolation separates vesicles from biological fluids, conditioned media, or tissue preparations. Researchers choose it when downstream analysis requires vesicle-enriched fractions for characterization, staining, or protein study.
- `47953` — **Glycogen/Carbohydrate Assay**
  The glycogen/carbohydrate assay quantifies glycogen or total carbohydrate in biological samples, typically by colorimetric detection after extraction or hydrolysis. Researchers choose it when carbohydrate content must be measured alongside lipid, glucose, or metabolite assays in the same sample set.
- `47954` — **Gibson DNA Assembly**
  Gibson DNA Assembly joins DNA fragments with overlapping end sequences in a single isothermal reaction using an exonuclease, a polymerase, and a ligase. Researchers choose it to assemble multiple fragments or insert DNA into a vector without restriction digestion and ligation.
- `47955` — **Viral Genome Sequencing**
  Viral genome sequencing recovers and characterizes genetic material from viruses in cultured isolates, purified preparations, or metagenomic samples. Researchers use it to identify viruses, assemble genomes, and support phylogenetic or variant analysis. It suits studies requiring sequence-level resolution of viral populations.
- `47956` — **Protein Aggregation Assay**
  Protein aggregation assays detect and quantify aggregated or fibrillar protein species, often using fluorescence, imaging, or light scattering readouts. Researchers use them to follow aggregation kinetics, assess aggregate clearance, or characterise phase-separated and amyloid-like assemblies in vitro and in biological samples.
- `47957` — **RNA-Protein Crosslinking (CLIP)**
  RNA-protein crosslinking covalently links RNAs to interacting proteins in intact cells, typically with UV light, enabling purification and sequencing of bound RNA segments. Researchers use it to map protein-RNA binding sites and identify interaction partners in vivo.
- `47958` — **Biofilm Assay**
  A biofilm assay quantifies microbial biofilm formation, typically by growing cells in wells or on surfaces, staining attached biomass, and measuring retained signal. Researchers use it to assess how treatments, surfaces, or growth conditions affect biofilm development and to compare biofilm phenotypes among strains.
- `47959` — **Streptavidin Purification**
  Streptavidin purification isolates streptavidin or biotinylated molecules through the high-affinity streptavidin–biotin interaction. Researchers use it to capture biotin-tagged proteins, nucleic acids, or complexes for downstream assays and enrichment.
- `47960` — **Mitochondrial Isolation**
  Mitochondrial isolation separates mitochondria from other cellular components using differential centrifugation and density-gradient steps. Researchers choose it when they need an enriched mitochondrial fraction for proteomics, enzyme activity assays, protein solubility studies, or structural analysis.
- `47961` — **Small Molecule Synthesis**
  Small molecule synthesis covers the preparation of defined organic and organometallic compounds through controlled chemical reactions, including derivatization reagents, fluorinated compounds, polymers, and functional probes. Researchers choose it when a specific molecular structure must be built or modified for downstream applications such as labeling, materials assembly, or biological treatment.
- `47962` — **eDNA/Metabarcoding Sampling**
  Environmental DNA and metabarcoding sampling collects genetic material from water, soil, or other environmental matrices, typically through filtration or direct preservation, followed by nucleic acid extraction and amplification of marker genes. Researchers choose it to survey organisms or microbial communities without direct capture, including rare or difficult-to-observe taxa.
- `47963` — **T7 Transcription**
  T7 transcription uses bacteriophage T7 RNA polymerase to synthesize RNA from a DNA template carrying a T7 promoter. Researchers use it to produce RNA for probes, guide RNAs, mRNA constructs, and polymerase activity assays.
- `47964` — **End Labeling** *(often a supporting step rather than a standalone technique)*
  End labeling adds a detectable or reactive moiety to the terminus of a nucleic acid molecule, using enzymatic or chemical means. Researchers use it to prepare probes, quantify specific lesions, map RNA or DNA termini, and render fragment ends suitable for downstream ligation or detection.
- `47965` — **Peptide Synthesis**
  Peptide synthesis builds peptides from amino acid building blocks, either in solution or on a solid support. Researchers use it to obtain defined peptides for assays, binding studies, and immunization when a specific sequence is needed.
- `47966` — **Autophagy Flux Assay**
  Autophagy flux assays measure the progression of autophagic cargo through the pathway, typically by combining reporters or substrates with lysosomal inhibition to distinguish delivery from degradation. Researchers choose them to assess whether a perturbation alters autophagic activity rather than simply autophagosome numbers.
- `47967` — **Lysosomal Activity Assay**
  The Lysosomal Activity Assay measures lysosomal function using readouts such as DQ-BSA fluorescence, LAMP1-positive puncta quantification, or substrate cleavage. Researchers choose it to assess lysosomal degradation capacity and endolysosomal integrity in cells or purified fractions.
- `47968` — **Ubiquitination Assay**
  Ubiquitination assays detect and characterize covalent attachment of ubiquitin to substrate proteins, using purified components or cell lysates. Researchers use them to test E3 ligase activity, substrate specificity, and chain formation, or to enrich ubiquitinated proteins for downstream analysis.
- `47969` — **Click Chemistry**
  Click chemistry is a set of modular, high-yield reactions used to covalently join two molecular partners under mild, bio-orthogonal conditions. Researchers choose it when they need selective labeling, conjugation, or ligation of biomolecules without interfering with native cellular chemistry.
- `47970` — **Random Primer Method** *(often a supporting step rather than a standalone technique)*
  Random primers are short oligonucleotides of mixed sequence that anneal throughout a nucleic acid template, allowing DNA polymerase to initiate synthesis at many sites. This enables uniform labeling or amplification of DNA, including degraded or fragmented samples, and is used to generate probes or prepare libraries for sequencing.
