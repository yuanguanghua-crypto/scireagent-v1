# READ ME FIRST — 每次对话都要先上传这个文件

你（模型）的任务：判断「某条实验协议是否真的属于某个技术方法」，以及评审方法说明文字的质量。

本次只做**一件事**：Task A —— 逐条判断协议与方法之间的关联是否成立。

---

## 一、你会收到什么

1. **本文件**（READ_ME_FIRST.md）—— 规则、判据、输出格式、方法定义
2. **一个数据文件**（part_XX.jsonl）—— 500 条待判记录，一行一条（JSONL 格式）

数据行长这样（单条）：

```json
{"task":"A","bridge_id":123,"method_id":47917,"criteria_key":"Sanger Sequencing",
 "protocol_id":456,"protocol_name":"...","protocol_objective":"...",
 "link_source":"manual_curated","link_status":"active"}
```

⚠️ **注意：数据行里没有方法名和方法定义**。你需要用 `method_id` 到本文件末尾
的「方法定义表」里查。

---

## 二、怎么查方法

数据行的 `method_id`（例如 `47917`）→ 到本文末尾「附录：83 个方法定义」里找
对应条目 → 拿到方法的 name 和 definition。

- 查不到某个 `method_id` → 说明数据有问题，**在报告里指出，不要猜**。
- 标记 `[common step]` 的方法只是背景信息，**不改变判定规则**。

---

## 三、判定规则（核心）

对每一条记录，输出三选一：

| 判定 | 含义 |
|---|---|
| `on_topic` | 这条协议的**核心技术就是**这个方法 |
| `tangential` | 这个方法确实出现了，但只是次要步骤 |
| `wrong` | 这条协议跟这个方法没关系，或命中了排除条款 |

### 判定流程（按顺序做）

1. 看数据行的 `criteria_key`
2. 若**不是** `general` → 到下方「四、判据表」找同名条目，按 essence → must → exclude 逐条比对
3. 若是 `general` → 只用「五、通用规则」+ 该方法的 definition
4. **判据优先于你的直觉**：命中任何 exclude 条目就判 `wrong`，
   除非该方法仍是这条协议的核心产出

### 五条通用规则

1. 核心产出原则：该方法必须是协议要交付的核心产出手段。若只是顺带一步，判 tangential；若撤掉它协议仍成立且结论不变，不算本方法。
2. 不做上游替代：协议主体是样本制备/提取，而本方法只是其后续分析，判 tangential 或 wrong。
3. 不做下游替代：协议主体是分析方法，而某制备技术只是准备步骤，该制备技术不因此获得本方法标签。
4. 方法同名不同物：优先按技术机制判定，不按字面词撞车（如 lymphocyte transformation ≠ bacterial transformation；SCFA extraction ≠ eDNA sampling）。
5. 标注档位：on_topic = 核心；tangential = 有该步骤但非核心；wrong = 完全不涉及。

### 三条硬要求（违反即视为格式错误）

1. **判据压过直觉**。不许因为"我觉得它基本相关"就推翻排除条款。
2. **必须引用依据**。`criteria_hit` 不能为空，要写 `exclude#2` / `must#1` /
   `universal#3` / `definition` 之一。
3. **`tangential` 不能当保险档**。它只用于"确实有这个方法的一步，但不是主体"。
   **拿不准就判 `wrong` 并把 `confidence` 设成 `low`**，不要用 tangential 和稀泥。
   （我们实测过：tangential 是分歧最大的一档，一个方法 144 条里有 47 条卡在这）

---

## 四、判据表（20 个高分歧方法，其余方法用通用规则）

### Sanger Sequencing
- **Essence**: 用双脱氧链终止法（Sanger/dideoxy）从模板直接读出碱基序列
- **IS this method only if**: 协议核心产出是 Sanger 测序读长或色谱图
- **Judge NOT this method when any applies**:
  - 仅为送 Sanger 测序做模板制备（PCR 扩增、质粒抽提、片段纯化、引物设计）
  - 用 Sanger 测序作为克隆/编辑/构建的下游验证手段，协议主体不是测序
  - 二代/三代测序（属 Illumina Sequencing / Long-read Sequencing）
  - 片段分析（如微卫星分型、SNaPshot）与 Sanger 机制不同者

### Lysosomal Activity Assay
- **Essence**: 测量溶酶体酶活性或溶酶体功能状态（如 acid phosphatase、cathepsin、LysoTracker 通量）
- **IS this method only if**: 测量对象是溶酶体本身的酶活或功能
- **Judge NOT this method when any applies**:
  - 自噬通量测定（autophagic flux）——属 Autophagy Flux Assay
  - 泛素-蛋白酶体系统降解测定
  - 仅为成像而使用溶酶体染料做定位/形态观察，无活性读数
  - 线粒体功能测定（属 Mitochondrial Function Assay）

### Enzymatic Labeling
- **Essence**: 用酶的催化活性把可检测标记共价接到目标分子上（如 TdT、kinase、transferase 标记）
- **IS this method only if**: 标记的引入依赖酶的催化反应
- **Judge NOT this method when any applies**:
  - 化学标记（NHS-ester、click chemistry、荧光染料直接偶联）
  - 仅用酶做切割/降解/合成，目的不是加标记
  - 免疫学检测（抗体-酶偶联显色，那是 ELISA/WB 的读出方式）
  - 代谢标记（如 EU/BrdU 掺入）若不是酶催化引入者

### SDS-PAGE
- **Essence**: 用 SDS 变性 + 聚丙烯酰胺凝胶电泳按分子量分离蛋白，并以染色/成像得到分离结果
- **IS this method only if**: 凝胶电泳分离本身是协议的核心步骤并产出具判定价值的结果
- **Judge NOT this method when any applies**:
  - 协议标题或目的明确是 Western blot / 免疫印迹 / 蛋白免疫检测 —— 判 tangential（跑胶是其一步，但协议主体是免疫检测）
  - 协议标题是凝胶配方、缓冲液配方、样品缓冲液制备 —— 判 wrong（无电泳分离过程）
  - 仅作为质谱/测序样品的脱盐或分级准备，无染色/成像结果判读
  - 琼脂糖凝胶电泳分离核酸（属 Gel Purification of DNA 等）
  - Native-PAGE/等电聚焦等非 SDS 变性体系（另有其方法）

### FISH Technique
- **Essence**: 用荧光标记的核酸探针与靶序列原位杂交，在细胞/组织原位显示特定序列位置
- **IS this method only if**: 核心是原位杂交 + 荧光探针检测
- **Judge NOT this method when any applies**:
  - 免疫荧光染色（抗体检测蛋白，属 Immunofluorescence Staining）
  - 原位 PCR/RT-PCR 若不以探针杂交为读出
  - Southern/Northern blot（膜上杂交，非原位）
  - 染色体涂染/核型分析若不以探针原位杂交为核心

### Mitochondrial Isolation
- **Essence**: 从细胞/组织中分离出富集的完整线粒体组分
- **IS this method only if**: 核心产出是纯化后的线粒体组分
- **Judge NOT this method when any applies**:
  - 线粒体功能/呼吸测定（属 Mitochondrial Function Assay）
  - 仅用商业试剂盒裂解后做下游检测，无分离纯化步骤
  - mtDNA 提取（属 DNA Extraction）
  - 线粒体形态成像而无分离

### Neuronal Differentiation
- **Essence**: 把干细胞/祖细胞定向诱导为神经元谱系并验证其神经元身份
- **IS this method only if**: 核心过程是从多能/祖细胞向神经元的分化诱导
- **Judge NOT this method when any applies**:
  - 仅培养原代神经元（取材自组织）——属 Immune/Stromal Cell Isolation 或神经元培养
  - 多能干细胞维持培养但未诱导分化（属 Pluripotent Stem Cell Culture）
  - 神经元功能记录/成像（属 Electrophysiological Recording / Calcium Imaging）
  - 神经干细胞增殖而不定向分化

### Agrobacterium-mediated Plant Transformation
- **Essence**: 用农杆菌侵染植物外植体把外源基因整合进植物基因组并再生/筛选转化体
- **IS this method only if**: 核心是农杆菌介导的植物遗传转化流程
- **Judge NOT this method when any applies**:
  - 仅制备农杆菌感受态或转化农杆菌（属 Bacterial Transformation）
  - 植物组织培养/再生而不涉及转化
  - 其他物种转化（如酵母、真菌、动物细胞）
  - 瞬时表达（agroinfiltration）若不涉及稳定整合——视是否为转化意图判定，倾向 tangential

### Lipid Extraction
- **Essence**: 用有机溶剂体系把脂质从样本中分离出来供下游分析
- **IS this method only if**: 核心产出是脂质组分（如 Folch/Bligh-Dyer/MTBE 法）
- **Judge NOT this method when any applies**:
  - 代谢物全谱提取（属 Metabolite Extraction (LC-MS)）
  - 仅脂质染色/成像（如 Oil Red O、BODIPY），无提取
  - 膜蛋白增溶/去垢剂处理（属 Protein Lysis & Solubilization）
  - 脂质体/脂质纳米颗粒制备

### Random Primer Method
- **Essence**: 用随机引物（random hexamer/octamer）起始延伸来标记或扩增未知序列
- **IS this method only if**: 核心依赖随机引物起始
- **Judge NOT this method when any applies**:
  - oligo-dT 或基因特异引物起始者（属 Reverse Transcription / PCR）
  - 随机引物只是 RT 流程中的可选组分，协议主体是 RT（判 tangential）
  - 随机突变/随机文库构建若不以此为核心

### Gel Purification of DNA
- **Essence**: 从凝胶中切出目标 DNA 条带并回收纯化
- **IS this method only if**: 核心是从凝胶回收 DNA 片段
- **Judge NOT this method when any applies**:
  - 仅跑胶观察/鉴定而不回收
  - 柱纯化/PCR cleanup 而无凝胶步骤
  - 蛋白从凝胶中回收（属 Proteomics Sample Prep）
  - RNA 从凝胶回收

### Environmental/eDNA Sampling
- **Essence**: 从环境基质（水/土/沉积物/空气/表面）采集并保存生物材料以检测其中的生物
- **IS this method only if**: 核心是环境基质的采样与保存（及 eDNA 富集）
- **Judge NOT this method when any applies**:
  - 从生物个体/组织取样（如根结线虫卵从根提取、粪便拭子、临床阴道拭子）——非环境基质
  - 对环境 DNA 的下游分析（扩增测序属 eDNA/Metabarcoding Sampling 的分析端，但采样协议本身归属需看主体）
  - 纯培养物的核酸提取

### Live-cell Fluorescence Imaging
- **Essence**: 在活的、未固定细胞上用荧光报告分子随时间成像
- **IS this method only if**: 样本是活细胞且成像过程未固定
- **Judge NOT this method when any applies**:
  - 固定细胞/组织的免疫荧光成像（属 Immunofluorescence Staining / Immunohistochemistry）
  - 活细胞成像但读出不是荧光（如明场、全息、相差）
  - 流式细胞术（属 Flow Cytometry）
  - 仅做图像处理分析而无活细胞采集

### Reverse Transcription & cDNA Synthesis
- **Essence**: 用逆转录酶把 RNA 转成 cDNA
- **IS this method only if**: 核心产出是 cDNA 或依赖 RT 的读出
- **Judge NOT this method when any applies**:
  - RNA 提取/纯化（属 RNA Isolation）
  - 不依赖 RT 的 RNA 检测（如直接 RNA 测序的某些建库、Northern blot）
  - RT 只是 RT-qPCR/RNA-seq 全流程中的一步且协议主体是整体流程（判 tangential）
  - RNA 结构解析（如 SHAPE）若 RT 仅作读出手段而非目标（判 tangential）

### Glycogen/Carbohydrate Assay
- **Essence**: 定量糖类（糖原、总糖、单糖）含量或相关酶活
- **IS this method only if**: 测量对象是糖/糖原的丰度或糖代谢酶活
- **Judge NOT this method when any applies**:
  - 脂质测定
  - 蛋白/核酸定量
  - 细胞活力测定（如 MTT 依赖代谢但目的是活力）
  - 糖基化修饰分析若不以糖含量为核心

### Protein Lysis & Solubilization
- **Essence**: 裂解细胞/组织并把蛋白溶解释放到可分析状态
- **IS this method only if**: 核心产出是可溶的蛋白裂解液
- **Judge NOT this method when any applies**:
  - 蛋白纯化（属 Protein Purification）
  - 免疫沉淀前的常规裂解若协议主体是 IP（判 tangential）
  - 膜蛋白增溶若为核心步骤则可算（需看主体）
  - 核酸提取的裂解步骤（那属对应核酸方法）

### Multiplexed Tissue Imaging
- **Essence**: 在同一组织切片上同时成像多个标志物（如 CODEX、CycIF、IMC、mIF）
- **IS this method only if**: 核心是多标志物同片成像并获得空间信息
- **Judge NOT this method when any applies**:
  - 单标志物免疫荧光/组化
  - 质谱成像（MALDI-MSI）若不以抗体/探针多重标记为核心
  - 空间转录组（如 Visium/Nova-ST）——测序读出，非成像
  - 仅做图像分析而不涉及多重染色

### Amplicon/Illumina Library Prep
- **Essence**: 把 PCR 扩增子转成带 index 的 Illumina 测序文库
- **IS this method only if**: 核心是从扩增子到可上机文库的构建
- **Judge NOT this method when any applies**:
  - 仅做 PCR 扩增（属 PCR）
  - 非扩增子来源的文库构建（如全基因组、RNA-seq 建库——属 RNA-seq Library Prep / 其他）
  - 仅做文库定量/质检
  - 空间转录组建库（有自己的方法）

### Pathogen Infection Assay
- **Essence**: 用病原体感染宿主并定量感染结果（滴度、病变、载量）
- **IS this method only if**: 核心是病原体对宿主的感染过程及感染读数
- **Judge NOT this method when any applies**:
  - 仅培养病原体而无感染宿主（属 Bacterial/Microbial Culture）
  - 病毒包装/制备（属 Viral Production）
  - 宿主对非病原刺激的响应（如 LPS 刺激若不视为感染模型，需看定义）
  - 植物病原接种若协议核心是病害表型评估，视是否以感染过程为主体

### Click Chemistry Labeling
- **Essence**: 用生物正交 click 反应（CuAAC/SPAAC 等）把标记共价接到目标分子
- **IS this method only if**: 核心依赖 click 反应完成标记/偶联
- **Judge NOT this method when any applies**:
  - NHS-ester/马来酰亚胺等非 click 化学偶联
  - 仅提及 click 可用的探针但协议未做 click 反应
  - 代谢掺入（如 EU 掺入）后续若不接 click 步骤
  - 酶法标记


---

## 五、输出格式

**一行一条 JSON**，字段如下（缺任何一个字段都会导致这条被退回）：

```json
{"task":"A","method_id":47917,"protocol_id":456,
 "verdict":"on_topic|tangential|wrong",
 "criteria_hit":["exclude#2"],
 "confidence":"high|medium|low",
 "reason":"不超过25个英文单词，必须和你引用的判据一致"}
```

要求：

- 严格保持输入顺序，**不许合并、去重、跳过任何一条**
- 输入多少条，就输出多少行
- 只输出 JSON，不要加解释文字、不要加代码块围栏

---

## 六、Task B（本次不做，后续另发）

如果你收到的数据行带 `"task":"B"`，那是另一件事（评审方法说明文字质量），
按当时给的说明做。本次只做 `"task":"A"`。

---

## 附录：83 个方法定义

按 `method_id` 查（升序）：

- `47888` **Flow Cytometry** — Flow cytometry measures optical and fluorescence properties of individual cells or particles in a fluid stream, enabling enumeration and phenotyping of heterogeneous populations. Researchers use it to quantify surface or intracellular markers, assess uptake and internalization, and track reporter expression across samples.
- `47889` **PCR** — PCR amplifies specific DNA sequences through repeated cycles of denaturation, primer annealing, and extension by a thermostable polymerase. Researchers use it to detect or quantify targets, prepare DNA for cloning or sequencing, and genotype samples from diverse sources.
- `47890` **Immunofluorescence Staining** — Immunofluorescence staining uses fluorophore-conjugated antibodies to label specific proteins in fixed or live cells and tissues, which are then imaged by fluorescence microscopy. Researchers choose it to determine protein localization, distribution, and abundance, or to visualize clustering, puncta, and internalization in situ.
- `47891` **Live-cell Fluorescence Imaging** — Live-cell fluorescence imaging detects fluorescently tagged or stained molecules in intact cells over time. Researchers use it to follow localization, clustering, internalization, and reporter activity in living samples, preserving spatial and temporal context that fixed-cell methods cannot capture.
- `47892` **Bacterial/Microbial Culture** — Bacterial and microbial culture propagates microorganisms in controlled media to obtain viable cells, isolates, or stocks. Researchers use it when they need to expand cultures for downstream assays, maintain strains, or prepare inocula for experimental work.
- `47893` **Cell Viability Assay** — Cell viability assays quantify the proportion of live cells in a population after experimental treatment. Researchers use them to assess cytotoxicity, compare drug or compound effects, and monitor cell health over time across many cell types and formats.
- `47894` **Genomic DNA Extraction** — Genomic DNA extraction isolates DNA from a range of sample types, including plant nuclei, plasmid DNA on filter paper, and microbial or viral communities. Researchers choose it when they need DNA suitable for downstream applications such as sequencing, PCR, or methylome analysis.
- `47895` **Real-Time Quantitative PCR (qPCR)** — Real-time quantitative PCR amplifies a specific DNA target while measuring fluorescence each cycle, allowing quantification of starting template amounts. Researchers use it to measure gene expression, detect or quantify pathogens and specific sequences, and assess DNA modification status.
- `47896` **Behavioral Assessment** — Behavioral assessment measures observable actions, performance, or physiological outputs to infer function in living subjects. Researchers use it when the question concerns behavior, cognition, or integrated physiological responses rather than isolated molecular events. Protocols span invertebrate and rodent tasks, exercise testing, and clinical functional measures.
- `47897` **Illumina Sequencing** — Illumina sequencing is a short-read, sequencing-by-synthesis method that generates nucleotide reads from DNA or RNA-derived libraries. Researchers choose it for applications requiring high-throughput read output, including transcriptome profiling, small RNA and non-polyadenylated RNA analysis, methylation studies, amplicon sequencing, and microbiome taxonomy. Library preparation and read configuration are adapted to each application.
- `47898` **3D Cell Culture** — 3D cell culture maintains cells in three-dimensional arrangements that better approximate tissue architecture, cell-cell contacts, and spatial gradients than planar culture. Researchers use it to study morphology, migration, aggregation, colony formation, and differentiation in contexts where spatial organization influences the observed phenotype.
- `47899` **Immunohistochemistry** — Immunohistochemistry detects specific proteins in tissue sections using antibody-based staining, preserving spatial context within the tissue architecture. Researchers choose it to localize or assess target expression in situ, including on biopsy and archived specimens.
- `47900` **CRISPR-Cas9 Genome Editing** — CRISPR-Cas9 introduces targeted double-strand breaks at genomic loci defined by a guide RNA, enabling knockouts, knock-ins, and other edits through cellular repair. Researchers choose it when they need site-specific modification of a gene in cells or organisms.
- `47901` **ELISA** — ELISA detects and quantifies specific proteins, antibodies, or small molecules in liquid samples using antibody-based binding and an enzymatic signal readout. Researchers choose it for sensitive, plate-based measurement of analytes across serum, culture, and environmental matrices.
- `47902` **RNA Isolation** — RNA isolation recovers total or fractionated RNA from cells, tissues, or body fluids for downstream analysis such as sequencing, RT-PCR, or small RNA detection. Researchers choose it when they need intact RNA suitable for transcriptome profiling, non-polyadenylated RNA enrichment, or microRNA characterization across diverse sample types.
- `47903` **Protein Purification** — Protein purification isolates a specific protein or protein complex from a biological source by separating it from other cellular components. Researchers choose it when downstream experiments require enriched, functionally active protein, such as structural analysis, activity assays, cross-linking, or proteomic profiling.
- `47904` **Amplicon/Illumina Library Prep** — Amplicon/Illumina library prep converts PCR amplicons into indexed libraries for short-read sequencing on Illumina platforms. Researchers choose it when targeted loci, marker genes, or barcoded constructs must be sequenced across many samples in parallel.
- `47905` **Western Blot** — Western blot separates proteins by gel electrophoresis, transfers them to a membrane, and detects specific proteins with antibodies. Researchers use it to assess protein presence, size, and relative abundance in complex samples.
- `47906` **Immunoprecipitation** — Immunoprecipitation uses an antibody immobilized on a solid support to capture a specific antigen from a complex mixture, allowing its separation from other components. Researchers choose it to enrich a target protein or complex for downstream analysis, or to assess interactions and modifications in native samples.
- `47907` **SDS-PAGE** — SDS-PAGE separates proteins by molecular mass under denaturing conditions, using an anionic detergent to unfold polypeptides and impart a uniform charge-to-mass ratio. Researchers use it to assess purity, monitor fractionation, verify protein preparation, and resolve samples before immunoblotting or mass spectrometry.
- `47908` **Metabolite Extraction (LC-MS)** — Metabolite extraction prepares biological samples for LC-MS analysis by isolating small-molecule metabolites from cells or tissues. Researchers choose it when profiling metabolite composition, quantifying specific compounds, or comparing metabolic states across samples.
- `47909` **Calcium/Functional Imaging** — Calcium/functional imaging uses fluorescent or luminescent indicators to monitor intracellular ion dynamics and related functional readouts in living cells and tissues. Researchers choose it to follow signaling events, vesicle turnover, or reporter activity over time in situ.
- `47910` **Immune/Stromal Cell Isolation & Culture** — Covers isolation and culture of immune and stromal cells from blood, tissue, or culture, including depletion and activation steps. Researchers use it when a defined cell population is needed for downstream assays such as sequencing, reporter assays, or functional testing.
- `47911` **Electrophysiological Recording** — Electrophysiological recording measures electrical activity from excitable tissues such as nerves, muscle, and heart using electrodes placed in vitro, in vivo, or on the body surface. Researchers choose it to capture real-time physiological signals, including single-unit activity, nerve compound potentials, and electrocardiograms.
- `47912` **In-vivo Recording & Surgery** — In-vivo recording and surgery covers procedures for instrumenting live animals to acquire physiological or neural signals, including electrode implantation, cannulation, and telemetry. Researchers choose it when measurements must be made in the intact, functioning organism rather than in vitro.
- `47913` **Recombinant Protein Expression** — Recombinant protein expression uses host cells or cell-free systems to produce a target protein from a cloned gene. Researchers choose it when they need preparative amounts of a protein for purification, biochemical assays, or structural work.
- `47914` **RNA-seq Library Prep** — RNA-seq library prep converts RNA into sequenceable cDNA libraries for transcriptome profiling. Variants accommodate polyadenylated or non-polyadenylated inputs, bulk tissues, single cells, small RNAs, and long reads, so researchers select a protocol matched to their sample type and question.
- `47915` **Single-cell RNA-seq** — Single-cell RNA-seq profiles transcriptomes of individual cells, resolving cell types, states, and heterogeneity within a sample. Researchers choose it when bulk measurements would obscure cell-to-cell variation, such as mapping tissue composition or identifying rare populations.
- `47916` **Bacterial Transformation** — Bacterial transformation introduces exogenous DNA into competent bacterial cells, typically via heat shock or electroporation, followed by selection on antibiotic-containing media. Researchers use it to propagate plasmids, build libraries, and move constructs between hosts.
- `47917` **Sanger Sequencing** [common step] — Sanger sequencing determines the nucleotide sequence of DNA fragments by chain-termination synthesis with dideoxynucleotides and capillary or gel electrophoretic separation of the products. It is chosen for targeted, low-throughput readouts such as verifying constructs, confirming PCR products, and genotyping specific loci.
- `47918` **Long-read Sequencing** — Long-read sequencing generates continuous nucleotide reads from single DNA or RNA molecules, resolving repeats, structural variants, and full-length transcripts that short reads fragment. Researchers choose it for de novo assembly, isoform characterization, haplotype phasing, and genome or amplicon analysis where read length or continuity matters.
- `47919` **Pluripotent Stem Cell Culture** — Pluripotent stem cell culture maintains undifferentiated embryonic and induced pluripotent stem cells under defined conditions, supporting self-renewal and subsequent differentiation. Researchers use it to expand lines for gene editing, differentiation, and reprogramming studies.
- `47920` **Pathogen Infection Assay** — A Pathogen Infection Assay introduces a defined pathogen to a host, tissue, or substrate under controlled conditions and measures the resulting infection, colonization, or killing. Researchers use it to compare virulence, test antimicrobial or immune treatments, or quantify pathogen burden across experimental groups.
- `47921` **High-throughput Screening Assay** — A high-throughput screening assay measures a defined phenotype across many samples or variants in parallel, typically in multiwell plates with automated liquid handling and plate readers or imaging. Researchers choose it when comparing large libraries, compound sets, or mutant panels requires consistent, miniaturized measurement rather than one-off assays.
- `47922` **Single-nucleus RNA-seq** — Single-nucleus RNA-seq profiles gene expression from individual nuclei, enabling transcriptomic analysis of tissues that are difficult to dissociate into intact cells, including frozen or archived material. Researchers choose it when whole-cell dissociation is impractical or when nuclear transcripts are the desired readout.
- `47923` **Reverse Transcription & cDNA Synthesis** — Reverse transcription converts RNA templates into complementary DNA using a reverse transcriptase, primed by oligo-dT, random primers, or gene-specific primers. Researchers choose it when RNA must be stabilized as cDNA for downstream amplification, library construction, or transcript quantification.
- `47924` **Viral Vector Transduction** — Viral vector transduction introduces genetic material into target cells using viral particles, enabling stable or transient expression of shRNAs, cDNAs, reporters, or CRISPR components. Researchers choose it when they need efficient delivery across hard-to-transfect cells or sustained expression for perturbation and lineage-tracing studies.
- `47925` **Lipid Extraction** — Lipid extraction separates lipids from aqueous and non-lipid components of a sample using organic solvents, yielding a lipid fraction suitable for downstream quantification or analysis. Researchers choose it when preparing cells, tissues, or other matrices for measurement of total lipids or specific lipid classes.
- `47926` **Tissue Embedding** — Tissue embedding infiltrates and surrounds specimens with a supporting medium so they can be sectioned or imaged while preserving structure. Researchers choose it when samples need mechanical support for microtomy, cryosectioning, or resin-based fluorescence and electron microscopy workflows.
- `47927` **Protein Lysis & Solubilization** — Protein lysis and solubilization disrupts cells and extracts proteins into solution for downstream analysis. Researchers choose it when preparing lysates for assays, fractionation, or proteomic workflows, with buffer composition adjusted to preserve the target protein's activity or interactions.
- `47928` **Plant Biochemical Assay** — Plant biochemical assays measure chemical constituents, enzyme activities, or staining reactions in plant tissues to assess physiological state, stress responses, or developmental processes. Researchers choose these assays when a specific biochemical or histochemical readout is needed to complement phenotypic or genetic observations.
- `47929` **Model-organism Husbandry** — Covers the routine care and propagation of model organisms, including feeding, watering, housing, acclimation, breeding, and synchronized culture. Researchers use it to establish and maintain healthy, reproducible stocks before experimental manipulation.
- `47930` **Proteomics Sample Prep** — Proteomics sample prep covers the steps that turn cells, tissues, or purified complexes into peptides suitable for mass spectrometry, including lysis, protein extraction, reduction and alkylation, digestion, and optional labelling or fractionation. Researchers choose it when they need to identify or quantify proteins from a defined sample, from single complexes to whole proteomes.
- `47931` **Cryopreservation** — Cryopreservation preserves cells, organisms, and biological samples at low temperature for long-term storage. Researchers use it to maintain cell lines, archive strains, and prepare samples for downstream cryo-based analysis or shipment.
- `47932` **Gel Purification of DNA** — Gel purification separates DNA fragments by agarose gel electrophoresis and recovers a specific size band from the gel matrix. Researchers use it when a defined fragment must be isolated from mixed products, primers, or other bands, such as after restriction digestion, PCR, or library preparation.
- `47933` **Viral Infection & Focus Assays** — Viral infection and focus assays quantify infectious virus by inoculating susceptible cells and detecting infected foci, often with antibody or reporter-based readouts. Researchers use them to titrate viral stocks, assess neutralization, and measure replication-competent virus in samples.
- `47934` **Environmental/eDNA Sampling** — Environmental/eDNA sampling collects biological material from air, water, sediment, soil, or surfaces to detect organisms present in a habitat without direct capture. Researchers choose it for biodiversity inventories, pathogen or indicator monitoring, and detection of species that are difficult to observe directly.
- `47935` **Receptor/Ligand Binding Assay** — Receptor/ligand binding assays measure the interaction between a receptor and its ligand, typically to determine affinity, kinetics, or binding specificity. Researchers choose this approach when they need to quantify binding under defined conditions, including whole-cell or cell-free formats.
- `47936` **Agrobacterium-mediated Plant Transformation** — Agrobacterium-mediated transformation delivers DNA into plant cells via bacterial infection, enabling stable integration or transient expression. Researchers use it for generating transgenic lines, transient assays, virus-induced gene silencing, and studying gene function in diverse plant species.
- `47937` **Viral Molecular Detection** — Viral molecular detection covers the purification and concentration of virus particles from environmental, faecal, sediment, and clinical samples, followed by molecular assays to identify and characterise viral nucleic acid. Researchers choose it when they need to detect or type viruses directly rather than rely on culture or serology.
- `47938` **Multiplexed Tissue Imaging** — Multiplexed tissue imaging detects multiple markers within a single tissue section while preserving spatial context. Researchers choose it to map cell types, states, and tissue architecture across heterogeneous samples in one experiment.
- `47939` **Targeted Mutagenesis (TAM)** — Targeted mutagenesis introduces defined sequence changes at a chosen genomic locus, enabling construction of point mutants, deletions, and reporter or variant alleles in bacterial, mouse, and mammalian systems. Researchers choose it when a specific genetic alteration is needed to test gene function or model a variant.
- `47940` **ChIP-seq/Chromatin Profiling** — Chromatin profiling methods map protein-DNA interactions, nucleosome positions, and chromatin accessibility genome-wide. Researchers choose these approaches to locate transcription factor binding sites, define chromatin states, or resolve chromatin architecture in bulk or single cells.
- `47941` **Neuronal Differentiation** — Neuronal differentiation converts stem cells or somatic cells into neuron-like cells that express neuronal markers, extend processes, and form functional synapses. Researchers use it to obtain cultured neurons for morphological, electrophysiological, and imaging-based assays of synaptic, mitochondrial, and organelle function.
- `47942` **FISH Technique** — Fluorescence in situ hybridisation detects specific DNA or RNA sequences in fixed cells and tissue by hybridising labelled probes and visualising them by fluorescence microscopy. Researchers use it to localise sequences within intact cellular and tissue architecture, including whole-mount preparations and cultured cells.
- `47943` **Enzymatic Labeling** [common step] — Enzymatic labeling uses an enzyme's catalytic activity to attach a detectable label or to convert a substrate into a measurable product. Researchers choose it when they need to visualize or quantify enzyme activity, label surface proteins, or measure metabolite concentrations in biological samples.
- `47944` **Correlative Light-Electron Microscopy** — Correlative light-electron microscopy pairs fluorescence imaging of labeled molecules with electron microscopy of the same specimen, allowing fluorescent signals to be mapped onto ultrastructural context. Researchers choose it when molecular identity must be assigned within detailed cellular architecture.
- `47945` **RNA In Situ Hybridization** — RNA in situ hybridization detects specific RNA transcripts within intact cells or tissue sections by hybridizing labelled probes to target sequences. Researchers use it to localize RNA spatially while preserving tissue morphology, including multiplexed detection of individual transcripts.
- `47946` **Click Chemistry Labeling** — Click chemistry labeling covalently attaches tags, fluorophores, or affinity handles to biomolecules through bioorthogonal reactions such as azide-alkyne cycloaddition. Researchers choose it when selective, mild conjugation is needed on proteins, nucleic acids, or labeled metabolites in complex samples.
- `47947` **Microsphere/Particle Synthesis** — Microsphere and particle synthesis produces dispersed colloidal or polymeric particles with controlled composition and size, using approaches such as reduction, emulsion, membrane emulsification, or nanoprecipitation. Researchers choose it to generate nanoparticles, nanogels, or droplets for drug delivery, imaging, catalysis, or in vitro reconstitution.
- `47948` **In-vivo PK Sampling & Bioanalysis** — In-vivo PK sampling and bioanalysis collects blood or plasma at defined times after dosing and quantifies drug concentrations to characterize absorption, distribution, and clearance. Researchers use it when they need time-resolved exposure data from living animals or human subjects.
- `47949` **Tissue Clearing** — Tissue clearing renders biological specimens optically transparent by removing or matching refractive index of lipids and other light-scattering components, enabling deep imaging of internal structures by light and fluorescence microscopy. Researchers choose it when intact three-dimensional architecture must be visualized without physical sectioning.
- `47950` **Mitochondrial Function Assay** — Mitochondrial function assays measure respiration, complex activity, morphology, mtDNA turnover, and flux in live or fixed samples. Researchers choose them to assess oxidative phosphorylation, mitochondrial quality control, and organelle dynamics across cell types and organisms.
- `47951` **Kinase Activity Assay** — A kinase activity assay measures the catalytic activity of a kinase by detecting phosphorylation of a substrate or a coupled readout of nucleotide consumption. Researchers use it to quantify kinase function, compare activity across samples or conditions, and support kinetic or inhibitor studies.
- `47952` **Extracellular Vesicle Isolation** — Extracellular vesicle isolation separates vesicles from biological fluids, conditioned media, or tissue preparations. Researchers choose it when downstream analysis requires vesicle-enriched fractions for characterization, staining, or protein study.
- `47953` **Glycogen/Carbohydrate Assay** — The glycogen/carbohydrate assay quantifies glycogen or total carbohydrate in biological samples, typically by colorimetric detection after extraction or hydrolysis. Researchers choose it when carbohydrate content must be measured alongside lipid, glucose, or metabolite assays in the same sample set.
- `47954` **Gibson DNA Assembly** — Gibson DNA Assembly joins DNA fragments with overlapping end sequences in a single isothermal reaction using an exonuclease, a polymerase, and a ligase. Researchers choose it to assemble multiple fragments or insert DNA into a vector without restriction digestion and ligation.
- `47955` **Viral Genome Sequencing** — Viral genome sequencing recovers and characterizes genetic material from viruses in cultured isolates, purified preparations, or metagenomic samples. Researchers use it to identify viruses, assemble genomes, and support phylogenetic or variant analysis. It suits studies requiring sequence-level resolution of viral populations.
- `47956` **Protein Aggregation Assay** — Protein aggregation assays detect and quantify aggregated or fibrillar protein species, often using fluorescence, imaging, or light scattering readouts. Researchers use them to follow aggregation kinetics, assess aggregate clearance, or characterise phase-separated and amyloid-like assemblies in vitro and in biological samples.
- `47957` **RNA-Protein Crosslinking (CLIP)** — RNA-protein crosslinking covalently links RNAs to interacting proteins in intact cells, typically with UV light, enabling purification and sequencing of bound RNA segments. Researchers use it to map protein-RNA binding sites and identify interaction partners in vivo.
- `47958` **Biofilm Assay** — A biofilm assay quantifies microbial biofilm formation, typically by growing cells in wells or on surfaces, staining attached biomass, and measuring retained signal. Researchers use it to assess how treatments, surfaces, or growth conditions affect biofilm development and to compare biofilm phenotypes among strains.
- `47959` **Streptavidin Purification** — Streptavidin purification isolates streptavidin or biotinylated molecules through the high-affinity streptavidin–biotin interaction. Researchers use it to capture biotin-tagged proteins, nucleic acids, or complexes for downstream assays and enrichment.
- `47960` **Mitochondrial Isolation** — Mitochondrial isolation separates mitochondria from other cellular components using differential centrifugation and density-gradient steps. Researchers choose it when they need an enriched mitochondrial fraction for proteomics, enzyme activity assays, protein solubility studies, or structural analysis.
- `47961` **Small Molecule Synthesis** — Small molecule synthesis covers the preparation of defined organic and organometallic compounds through controlled chemical reactions, including derivatization reagents, fluorinated compounds, polymers, and functional probes. Researchers choose it when a specific molecular structure must be built or modified for downstream applications such as labeling, materials assembly, or biological treatment.
- `47962` **eDNA/Metabarcoding Sampling** — Environmental DNA and metabarcoding sampling collects genetic material from water, soil, or other environmental matrices, typically through filtration or direct preservation, followed by nucleic acid extraction and amplification of marker genes. Researchers choose it to survey organisms or microbial communities without direct capture, including rare or difficult-to-observe taxa.
- `47963` **T7 Transcription** — T7 transcription uses bacteriophage T7 RNA polymerase to synthesize RNA from a DNA template carrying a T7 promoter. Researchers use it to produce RNA for probes, guide RNAs, mRNA constructs, and polymerase activity assays.
- `47964` **End Labeling** [common step] — End labeling adds a detectable or reactive moiety to the terminus of a nucleic acid molecule, using enzymatic or chemical means. Researchers use it to prepare probes, quantify specific lesions, map RNA or DNA termini, and render fragment ends suitable for downstream ligation or detection.
- `47965` **Peptide Synthesis** — Peptide synthesis builds peptides from amino acid building blocks, either in solution or on a solid support. Researchers use it to obtain defined peptides for assays, binding studies, and immunization when a specific sequence is needed.
- `47966` **Autophagy Flux Assay** — Autophagy flux assays measure the progression of autophagic cargo through the pathway, typically by combining reporters or substrates with lysosomal inhibition to distinguish delivery from degradation. Researchers choose them to assess whether a perturbation alters autophagic activity rather than simply autophagosome numbers.
- `47967` **Lysosomal Activity Assay** — The Lysosomal Activity Assay measures lysosomal function using readouts such as DQ-BSA fluorescence, LAMP1-positive puncta quantification, or substrate cleavage. Researchers choose it to assess lysosomal degradation capacity and endolysosomal integrity in cells or purified fractions.
- `47968` **Ubiquitination Assay** — Ubiquitination assays detect and characterize covalent attachment of ubiquitin to substrate proteins, using purified components or cell lysates. Researchers use them to test E3 ligase activity, substrate specificity, and chain formation, or to enrich ubiquitinated proteins for downstream analysis.
- `47969` **Click Chemistry** — Click chemistry is a set of modular, high-yield reactions used to covalently join two molecular partners under mild, bio-orthogonal conditions. Researchers choose it when they need selective labeling, conjugation, or ligation of biomolecules without interfering with native cellular chemistry.
- `47970` **Random Primer Method** [common step] — Random primers are short oligonucleotides of mixed sequence that anneal throughout a nucleic acid template, allowing DNA polymerase to initiate synthesis at many sites. This enables uniform labeling or amplification of DNA, including degraded or fragmented samples, and is used to generate probes or prepare libraries for sequencing.
