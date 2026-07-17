# 工作台数据源权威文档（AI AUTO MATCH）

> SciReAgent 平台 · 研究员工作台数据产生原理的唯一权威文档
>
> **文档定位**：读这一篇，就能完整理解「工作台产品的化学属性、商业单元、知识实体三类数据是如何产生的」——涵盖五数据源的设计目的、定义、接口、字段关系、传递与校验、兜底、呈现，以及历程中踩过的坑与形成的共识。
>
> **文档版本**：2026-07-02 | 基于实测与代码核查（P1~P4 全部完成，1197 passed / 10 skipped / 0 failed）
>
> **2026-07-16 修订说明**：AI AUTO MATCH 数据链调查（Phase 1~4）对 jena 源做了系统性污染测绘与代码溯源，本次据此定点修订两处：① **附录 B**「无需二次爬虫」结论**已被推翻**（详见附录 B 顶部横幅）；② **§4.5 / §5.1** 澄清 **`catalog_no` 才是 Bioz 查询与精确匹配的硬锚点**，`systematic_name` 是展示 + 理论锚点（代码实测：Bioz 用 `search_by_sku(catalog_no)`）。完整依据见 `verification/jena_field_extractability_contract.md` 及配套审计报告。
>
> **核心命题**：平台的数据由「五数据源获取 + 研究员标注」共同形成。研究员工作流只有两条产品创建路径——**从 Word 文档导入新建**（部分属性已具备，AUTO MATCH 补齐）或**手动新建**（输入 CAS/name 等唯一标识，AUTO MATCH 推导其余）。五数据源（PubChem / ChEMBL / PubMed / BioProCorpus / jena / Bioz）均通过 AUTO MATCH 统一接入，研究员不直接从任何数据源选择导入。

---

## 0. 文档阅读指南

| 你是 | 先看 |
|------|------|
| 新人入门（先理解全局） | §1（三类产物）、§2（全景图）、§3（接口契约） |
| 编码预填/Apply 逻辑 | §3（接口）、§4（五源详解）、§7（字段溯源表） |
| 编码知识图谱/落库 | §5（数据流校验）、§3.2（adopt 端点） |
| 排查"为什么这个字段是这个值" | §7（字段溯源速查表）、§5（传递与校验） |
| 排查"接口慢/挂/限速" | §5.6（缓存与容错），另见 `DATASOURCE_RELIABILITY.md` |
| 想了解为什么这么设计 | §8（历程与坑） |
| 评估要不要加新数据源 | §9（已淘汰源）、§2.2（选型原则） |

---

## 1. 设计目的：工作台数据产生的三类产物

工作台每个产品（Product）的数据，按**产生方式**分为三类。理解这三类的分工，是理解整个数据源体系的前提。

### 1.1 化学属性（chemical identity）

> **回答「这个产品是什么化学物质」**

| 字段 | 产生源 | 落库字段 |
|------|--------|---------|
| CAS 号 | **PubChem** synonyms 抽取（CAS 在 PubChem 以 synonym 存储） | `Product.cas` |
| SMILES / InChI / InChIKey | **PubChem**（ChEMBL fallback） | `Product.smiles` / `inchi` |
| 分子式 / 分子量 | **PubChem**（ChEMBL fallback） | `Product.formula` / `molecular_weight` |
| IUPAC 名 / LogP / TPSA / HBD/HBA/RotB | **PubChem**（ChEMBL fallback） | （展示用，部分落 Product） |
| Lipinski 五规则 | **本地 RDKit 计算**（基于上述属性） | （仅展示） |

**铁律**：化学结构的**唯一权威是 PubChem**。jena/Bioz 都不碰化学结构。CAS 号只能由 PubChem 解析写入，禁止从未经验证的源直接填 `Product.cas`。

### 1.2 商业单元（commercial & logistical specs）

> **回答「这个产品作为商品怎么卖、怎么存、怎么运」**

| 字段 | 产生源 | 落库字段 |
|------|--------|---------|
| 产品名 / 目录号 | 研究员手填 或 Word 导入 | `Product.name` / `Product.catalog_no` |
| 纯度（purity） | **jena**（副产品）或 Word 导入 | `Product.purity` |
| 浓度（concentration） | **jena**（副产品，需语义分类）或 Word 导入 | `Product.concentration` |
| 储存 / 运输 / 保质期 | **jena**（副产品，jena 最独占的物流三件套） | `Product.storage` / `Product.shipping` / `Product.shelf_life` |
| 分类（L1/L2） | **jena** category_path 或研究员选择 | `Product.category_l1` / `category_l2` |
| SKU（包装/价格） | 研究员手填 或 Word 导入 | `SKU` 表 |

**特点**：商业单元的规格字段是 **jena 在 AUTO MATCH 中的副产品**——jena 的核心价值是提供查询锚点（systematic_name），但顺手返回的 purity/storage 等规格字段对预填表单极有价值。

### 1.3 知识实体（knowledge entities）

> **回答「这个产品关联哪些文献、应用、方法、协议」**

核心链路（不可变）：`ResearchGoal → Application → Method → Protocol → Product → SKU`

| 实体 | 产生源 | 桥接表 |
|------|--------|--------|
| Reference（参考文献） | **Bioz**（产品级结构化文献）+ PubMed（元数据兜底） | `ProductReference` |
| Application（应用场景） | 人工 + PubMed/Bioz 关键词反向匹配 | （通过 Method 间接关联） |
| Method（实验方法） | PubMed 关键词 + Bioz techniques | `ProductMethod` |
| Protocol（实验协议） | **BioProCorpus**（本地语料库） | `MethodProtocol` + `ProductMethod` |

**铁律**：所有数据源生成的知识实体**都不直接写库**，只生成「待审草案」。落库由研究员在工作台确认后执行（§5.4）。Bioz 文献落库走专门的 `adopt-bioz-refs` 端点（§3.2）。

### 1.4 三类产物的产生路径总图

```
研究员触发 AI AUTO MATCH（Word 导入 或 手动输入 CAS/name）
    │
    ├─① PubChem/ChEMBL ──────► 化学属性（CAS/SMILES/MW/Lipinski）
    │
    ├─② jena 本地索引 ────────► 商业单元规格（purity/storage/shipping）
    │   │                        + systematic_name 锚点
    │   ▼
    ├─③ Bioz widget API ◄───── 知识实体·Reference（产品级文献 + IF + 引用上下文）
    │   （用 ② 的 catalog_no 查）
    │
    ├─④ PubMed E-utilities ──► 知识实体·Application/Method 关键词反向匹配
    │
    └─⑤ BioProCorpus 本地 ──► 知识实体·Protocol（试剂/设备/步骤）
    │
    ▼
五 section 草案（chemical / jena / bioz / literature / protocols）
    │
    ▼ 研究员审核 → Apply / Adopt / Import
Product + Reference + Application/Method/Protocol（落库）
    │
    ▼
COA / SDS 生成（依赖已落库的完整数据）
```

---

## 2. 数据源全景

### 2.1 五数据源清单（按职能）

| # | 数据源 | 类型 | 职能 | 接入状态 | 实现文件 |
|---|--------|------|------|:--------:|---------|
| 1 | **PubChem** | 外部 API | 化学结构权威源（CAS/SMILES/分子式/MW/Lipinski） | ✅ | `pubchem_enhancer.py` |
| 2 | **ChEMBL** | 外部 API | 化学结构 fallback（修饰核苷酸偶联物） | ✅ | `pubchem_enhancer.py:_chembl_search` |
| 3 | **PubMed** | 外部 API | 文献元数据 + 应用/方法关键词 | ✅ | `pubmed_client.py` / `literature_recommender.py` |
| 4 | **BioProCorpus** | 本地语料库 | 实验协议（试剂/设备/步骤） | ✅ | `protocol_recommender.py` |
| 5 | **jena** | 本地索引（策略 B） | AUTO MATCH 锚点（systematic_name→Bioz）+ 规格副产品 | ✅ | `jena_matcher.py` / `jena_index.py` |
| 6 | **Bioz** | 外部 API | 产品级结构化文献（含 IF + 引用上下文） | ✅ | `bioz_client.py` / `bioz_pipeline.py` |

> **已评估并淘汰**：ChEBI（修饰核苷酸 0% 覆盖）、CAS Common Chemistry（0% 覆盖且功能被 PubChem 覆盖）。详见 §9。

### 2.2 选型三原则

1. **核心领域命中率优先**：平台首批产品线为核苷酸/点击化学，数据源必须对这个领域有实际覆盖。
2. **功能不重叠**：每个源必须有其它源无法替代的独占职能。
3. **接入成本可控**：公开/无 Key 优先，本地缓存优先。

### 2.3 各源一句话定位

| 数据源 | 它能做什么 | 它不能做什么 |
|--------|-----------|-------------|
| PubChem | 解析结构/CAS/MW（**化学属性唯一权威**） | 无产品规格、无应用描述、无实验方法 |
| ChEMBL | PubChem 查不到时的结构补充（修饰核苷酸偶联物反而更优） | 无产品规格、无 CAS 数据 |
| PubMed | 文献元数据（title/authors/PMID/DOI/关键词） | 无产品级关联、无评分、无引用上下文 |
| BioProCorpus | 实验协议富内容（试剂/设备/步骤） | 无文献、无产品关联 |
| jena | **提供 systematic_name 锚点（撬动 Bioz）**+ 规格副产品 | 不落库成 Product、化学结构非权威、无文献 |
| Bioz | 按产品 SKU 查关联文献（含 IF + 引用上下文） | 化学结构、产品规格、**CAS 不可查** |

---

## 3. AI AUTO MATCH 接口契约

研究员工作台 `ProductEditPage.vue` 的「🤖 AI AUTO MATCH」按钮，一次调用 `POST /products/enrich/` 返回五个 section。落库分三条路径，分别对应化学属性、知识实体（文献/协议）。

### 3.1 一站式 enrich 端点

**`POST /api/v1/products/enrich/`** —— `ProductEnrichView`（`apps/commerce/api/v1/ai_views.py:267`）

**请求**：
```jsonc
{
  "product_name": "JBS Beads-for-Seeds",   // 产品名（可选）
  "cas": "",                                // CAS（可选）
  "smiles": "",                             // SMILES（可选）
  "inchi": "",                              // InChI（可选）
  "product_id": 42                          // 产品 ID（可选，传入则回写 ref_id）
}
```

标识符优先级：`CAS > name > SMILES > InChI`（取第一个非空作主标识符查 PubChem）。

**响应**（信封 `{success, data, meta}`，`data` 含五 section）：
```jsonc
{
  "chemical": { ... },      // §4.1 — PubChem/ChEMBL 化学属性 + Lipinski
  "jena":     { ... },      // §4.5 — 规格凭证 + 归一化规格
  "bioz":     { ... },      // §4.6 — 文献证据（依赖 jena 命中）
  "literature": { ... },    // §4.3 — PubMed 文献 + 知识链匹配
  "protocols": [ ... ]      // §4.4 — BioProCorpus 协议
}
```

**五 section 独立容错**：任一 section 失败不影响其他（各用 try/except 兜底，失败返回空结构）。

**ref_id 回写**（P3-1）：传入 `product_id` 时，后端查该产品已关联的 Reference（按 doi/pmid），给 `literature.references` 和 `bioz.references` 中已落库的条目加 `ref_id` 字段，供前端显示「已关联」徽章。

### 3.2 Bioz 文献落库端点（P2）

**`POST /api/v1/products/<pk>/adopt-bioz-refs/`** —— `ProductAdoptBiozRefsView`

把 Bioz references 批量落库到 `Reference` + `ProductReference`。

**请求**：
```jsonc
{
  "references": [
    { "article_title": "...", "authors": ["A","B"], "journal": "...",
      "pub_date": "2023-01-15", "doi": "10.1/x", "pmid": "123", "techniques": "..." }
  ],
  "citation_role": "supporting"    // primary/supporting/validation/background
}
```

**去重逻辑**（`bioz_adopter.py`）：
- Reference 去重：`DOI > PMID > title iexact` 降级查重（都已存在则复用，不重复创建）
- ProductReference 去重：按 `(product, reference, citation_role)` 唯一约束
- authors 字段兼容 list（bioz 真实返回）和 string，list 自动拼成逗号字符串
- 单条失败不中断整体（收集 errors），事务包裹

**响应**：`{ adopted, skipped, created_refs, linked_refs, errors }`

### 3.3 协议落库端点（既有）

**`POST /api/v1/products/import-protocol/`** —— `ProductImportProtocolView`

把 BioProCorpus 协议落库为 `Method` + `Protocol` + `ProtocolStep` 并关联产品。幂等（同 slug 不重复创建）。

---

## 4. 五源详解

### 4.1 PubChem（化学结构权威源）

| 维度 | 说明 |
|------|------|
| 端点 | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/` |
| 接入 | Python `pubchempy`（`pcp.get_compounds()`） |
| 认证 | 无 Key，官方限速 5 req/s |
| 缓存 | L1 DataSourceCache（TTL 30 天）+ L2 Redis，cache-aside |
| 容错 | L3 统一客户端（超时 + 重试 + 令牌桶，§5.6） |

**输入**：identifier（CAS / name / SMILES / InChI）+ namespace
**输出**：`cid, molecular_formula, molecular_weight, canonical_smiles, isomeric_smiles, iupac_name, inchi, inchikey, xlogp, tpsa, h_bond_donor/acceptor_count, rotatable_bond_count, complexity, exact_mass, charge, heavy_atom_count, synonyms` + 本地计算的 Lipinski

**关键性质**：
- CAS 在 PubChem 以 **synonym** 形式存储，用 `name/{CAS}` 查是标准做法；用正则 `^\d{2,7}-\d{2}-\d$` 从 synonyms 提取 CAS
- 对修饰核苷酸**名称搜索常命中母体**（如 `Biotin-16-ddUTP`→`dUTP`），分词降级时尤甚；CAS 搜索无此问题
- 同义词（synonyms）Phase A 起透传，供 jena_matcher 增量匹配

### 4.2 ChEMBL（化学结构 fallback）

| 维度 | 说明 |
|------|------|
| 端点 | `https://www.ebi.ac.uk/chembl/api/data/molecule/search` |
| 超时 | 30 秒（搜索端点响应慢） |
| 触发 | PubChem 主标识符查不到 + 分词降级仍查不到时自动 fallback |

**输出**：与 PubChem 统一 schema 包装，`fallback_used=True`，前端显示「Not found in PubChem — results from ChEMBL」。

**关键性质**：
- 对修饰核苷酸**偶联物**覆盖反而优于 PubChem（实测）
- ⚠️ **ChEMBL 无 CAS 数据**——`cas_resolved` 字段在 ChEMBL 路径返回 `None`（P4 修复，§8.1 坑）。`canonical_smiles` 仍在 `properties` 中正常返回，但不会冒充 CAS

### 4.3 PubMed（文献元数据 + 知识链）

| 维度 | 说明 |
|------|------|
| 端点 | NCBI E-utilities（`esearch.fcgi` + `esummary.fcgi`） |
| 限速 | 无 Key 3 req/s（`min_interval=0.35s`）；有 Key 10 req/s |
| 超时 | 15 秒 |

**输入**：产品（name / CAS / 别名）
**输出**：文献列表（pmid/title/doi/authors）+ 应用关键词（17 模式）+ 方法关键词（21 模式）

**4 策略搜索**：产品名精确 → 别名（`PRODUCT_SYNONYMS` 表）→ CAS → 全文兜底。

**知识链反向匹配**：提取的关键词反向匹配本地 `Application`/`Method` 表（name/summary/purpose/slug 的 icontains），返回 `matched_*`（可关联）与 `unmatched_*_keywords`（需新建）。

**与 Bioz 分工**：PubMed 覆盖广但无产品关联；Bioz 精准（论文真用了试剂）但覆盖窄。两者互补。

### 4.4 BioProCorpus（协议源 · 策略 B 本地索引）

| 维度 | 说明 |
|------|------|
| 类型 | 本地 JSON 语料库（~175 MB，3 个文件） |
| 位置 | `backend/data/bioprocorpus/`（未入 git，需 `scripts/download_bioprocorpus.py` 下载） |
| 索引 | **进程级单例**（`get_shared_retriever`），AppConfig.ready 预热 |
| 落库 | ❌ 永不直接落库成 Product/Protocol；搜索结果需经 `import-protocol` 端点入库 |

**输入**：查询词（产品名/方法名）
**输出**：协议列表（id/title/source/abstract/url/score）+ 富内容（reagents/equipment/materials/steps）

**关键性质**：纯关键词匹配（非语义搜索），长尾可能漏匹配。搜索结果中 `id` 为字符串（如 `p1`），前端 Apply 时用 `Number.isInteger(p.id)` 过滤——只有经 `import-protocol` 入库拿到数字 DB ID 后才能关联产品。

### 4.5 jena（AUTO MATCH 锚点供给 · 策略 B 本地索引）

| 维度 | 说明 |
|------|------|
| 角色 | AUTO MATCH 的**跨源查询锚点供给者**（硬锚点 `catalog_no` 驱动 Bioz `search_by_sku`；`systematic_name` 为展示/理论锚点）+ 规格副产品 |
| 类型 | 供应商爬虫产出（JSONL，本地静态数据集，项目外工作区） |
| 产出 | `jena_products_v2.jsonl`（2098 条，31 字段） |
| 索引 | **进程级单例**（`get_shared_jena_index`），惰性构建 |
| 落库 | ❌ **永不落库成 Product**（策略 B，与 BioProCorpus 同构） |
| 缓存 | L1 DataSourceCache（`jena_match` 桶，TTL 30 天，jena 数据静态） |

**匹配逻辑**（`match_jena`，cas→name→synonyms 真级联）：
1. identifier 形如 CAS → 先按 CAS 查 jena 索引
2. miss → 按 name 查（`index.lookup` 模糊匹配）
3. miss → 按 synonyms 逐条模糊匹配（限 20 条）

**输出**：
```jsonc
{
  "matched": true,
  "match_key": "name",           // cas / name / synonym:xxx
  "catalog_no": "ATPNU-250",     // 硬锚点：驱动 Bioz search_by_sku
  "product_name": "...",
  "systematic_name": "...",      // 展示 + 理论锚点（非 Bioz 查询入参）
  "cas_number": "1927-31-7",     // 可能为 null（jena CAS 覆盖仅 15.8%）
  "normalized": {
    "purity": "≥ 95% (HPLC)",
    "storage_condition": "-20°C",
    "shipping_condition": "Cold Pack",
    "shelf_life": "12 months",
    "concentration": "100 mM",
    "category_l1": "nucleotides_nucleosides"
  }
}
```

**核心价值 = 双锚点，且 `catalog_no` 才是硬锚点**（2026-07-16 修订）：

- **`catalog_no`（硬锚点，代码实测的真实驱动键）**：Bioz 消费链路实际调用 `search_by_sku(catalog_no)`（如 `ATPNU-250`）驱动查询与精确匹配——这是**代码里真正跑通的锚点**。因此 `catalog_no` 的抽取正确性 = jena 独占价值的**闸门**，一旦被污染（如与其它字段粘连）就直接击穿整条 Bioz 链路。
- **`systematic_name`（展示 + 理论锚点）**：作为可读的规范化学名用于呈现，并在理论上可与文献命名对齐；但它**不是** Bioz 查询的实际入参。此前本节「核心价值 = systematic_name 锚点」的表述**已被推翻**——真实链路以 SKU（catalog_no）驱动。
- CAS 查不了 Bioz（实测），product_name 命中率低；1 个正确的 `catalog_no` 撬动 1 个跨厂家文献池（如 dATP 一次返回 514 snippets）。

> 依据：`verification/jena_field_extractability_contract.md` §4.5/§5.1 冲突勘误；bioz_pipeline 代码走 `search_by_sku`。

**关键共识（§8 详述）**：
- jena **不是产品创建入口**——研究员不会从 jena 选择新建产品
- jena **不碰化学结构**——CAS 独占性 = 0%（全在 PubChem），jena 的 CAS 仅作匹配键
- 规格字段是**副产品**——对 COA/SDS 有用，但对「构建知识资产」贡献为零

> **历史教训**：jena 曾被错误归为策略 C（批次落库），落库 2098 条到 Product 表。该方向已撤销（2026-06-28），代码删除，2098 条清除。详见 §8.2。

### 4.6 Bioz（产品级文献源）

| 维度 | 说明 |
|------|------|
| 角色 | 跨供应商产品级结构化文献（含 IF + 引用上下文） |
| 端点 | `back-badge-8.bioz.com/get_widget_data_ex_v9/`（widget API） |
| 查询 | **必须供应商名（cx）+ SKU（qx）**；**CAS 不可用**（实测不索引） |
| 认证 | 不需 Origin/Referer 头（旧文档误导，实测去掉仍 200） |
| 超时 | 30 秒 |
| 触发 | **依赖 jena 命中**——用 jena 的 `catalog_no` 作 qx 查询 |

**编排链**（`bioz_pipeline.fetch_bioz_evidence`）：
```
jena_result（必须有 catalog_no）
   │
   ├─① check_equivalence（化学等同性校验，§5.3）
   │     返回 {equivalence, needs_review}
   │
   ├─② BiozClient.search_by_sku(catalog_no, vendor)
   │     → 原始文献记录
   │
   ├─③ sanitize_record（厂商无关化净化，§5.5）
   │     删厂商名变体 + catalog_group 全 SKU 变体 + Bioz 标签
   │
   └─④ 按 IF 降序 + 年份降序排序
```

**输出**（bioz section）：
```jsonc
{
  "queried": true,
  "vendor": "Jena Bioscience",
  "catalog_no": "ATPNU-250",
  "equivalence": "weak",          // exact/name_match/weak/mismatch
  "needs_review": true,           // 研究员必须复核的标志
  "disclaimer": "文献基于同化学实体匹配，非特定厂商产品引用...",
  "total": 3,
  "references": [
    {
      "article_title": "...", "authors": ["Julia D.", ...],  // list 形态
      "journal": "Scientific Reports", "impact_factor": 4.379,
      "pmid": "26960569", "pmcid": "...", "doi": "...", "pub_date": "2023-01-15",
      "techniques": "X-ray crystallography",
      "image_urls": [...],        // 含 caption
      "long": "...", "medium": "...", "short": "...",  // 三级引用上下文（已净化）
      "catalog_group": "...", "catalog_number": "..."
    }
  ]
}
```

**依赖门控**：
- jena 未匹配 → `{queried: false, reason: "no_jena_match"}`（前端不渲染 bioz section）
- jena 匹配但无 catalog_no → `{queried: false, reason: "no_catalog_no"}`
- Bioz API 失败 → `{queried: true, error: ..., references: []}`

**关键性质**：
- **必须用 SKU/systematic_name 查**，CAS 不可用（§8.3 坑）
- 文献**跨供应商可复用**（化学实体层）——dATP 跨 12 家共享 514 snippets
- `equivalence=weak` / `needs_review=true` 是常态（厂商+货号查询、CAS 不可用），前端必须显著标注

---

## 5. 数据流：传递 · 校验 · 兜底

### 5.1 jena 跨源锚点链（2026-07-16 勘误）

> **重要勘误**：本节旧标题为「systematic_name 跨源锚点链」，并称 systematic_name 是连接五源的「主键」。经 Phase 1~4 代码溯源，这一表述**不准确**——Bioz 链路实际以 **`catalog_no`** 驱动（`search_by_sku`，见下方「实际查询链」第 417 行），systematic_name 承担的是**跨源命名对齐（PubChem 方向）+ 展示**职责。下图与下文已按真实链路修正。

jena 向不同下游提供**不同的锚点**，需分开看，切勿混为单一「主键」：

```
                    jena 匹配记录
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                        ▼
    catalog_no            systematic_name           规格字段
  （硬锚点，SKU）      （展示 / 命名对齐锚点）       （副产品）
        │                      │                        │
        ▼                      ▼                        ▼
      Bioz                  PubChem                  jena 自身
 search_by_sku          （化学名对齐辅助）         （COA/SDS 用）
 （真实驱动键）
```

**为什么 Bioz 用 catalog_no 而非 systematic_name**：代码实测 Bioz 走 `search_by_sku(jena.catalog_no)`，SKU 是供应商目录里的唯一编号，命中稳定；systematic_name 是理论上可对齐文献命名的候选，但**不是** Bioz 的实际入参。因此 catalog_no 的抽取正确性是 jena 独占价值的闸门。

**systematic_name 的真实用途**：系统命名（如 `2'-Deoxyadenosine-5'-triphosphate, Sodium salt`）在 PubChem 方向的命名对齐与前端展示上优于商品简称（`dATP - Solution`）。

**为什么不用 CAS**：Bioz 不索引 CAS（实测）；jena CAS 覆盖仅 15.8%。

**实际查询链**（enrich view 内）：
```
研究员输入 cas/name
   │
   ├─ chemical = PubChemEnhancer.resolve(cas or name)   → 化学属性
   │     · chemical.cas_resolved（PubChem 路径有 CAS，ChEMBL 路径 None）
   │
   ├─ jena = match_jena(cas or name, synonyms)          → 锚点 + 规格副产品
   │     · cas→name→synonyms 真级联
   │
   ├─ bioz = fetch_bioz_evidence(jena, platform_cas)    → 文献证据
   │     · 用 jena.catalog_no 查 Bioz widget
   │     · check_equivalence(platform_cas, jena.cas_number)
   │
   ├─ literature = LiteratureRecommender.recommend(name) → PubMed 文献 + 知识链
   └─ protocols = ProtocolRetriever.search(name)         → BioProCorpus 协议
```

### 5.2 CAS 三源冲突校验（P3-2）

CAS 可来自三个源：`form.cas`（手填/Word）、`chemical.cas_resolved`（PubChem）、`jena.cas_number`（jena）。三者非空且不一致时，研究员可能误用错误 CAS。

**前端纯计算检测**（`ProductEditPage.vue`）：
```js
casSources = [表单, PubChem, jena] 中非空者
casConflict = casSources 去 dash 后 ≥2 个不同值
```

**呈现**：chemical preview 下方显示黄色警示条「⚠ CAS 来源不一致」，列出三源值。**不阻断** Apply（研究员权威，告知模式非硬阻断——与「发布不硬阻断」铁律一致）。

**P4 修复的意义**：cas_resolved 在 ChEMBL 路径返回 None（不再冒充 SMILES），此校验才语义正确。否则 ChEMBL fallback 时会把 SMILES 当成一个"CAS 源"参与比较，误报冲突。

### 5.3 化学等同性校验（Bioz 文献适用性）

jena_matcher 是 name+synonyms **模糊匹配**，「名字像」≠「同一化学物质」。只有 CAS 严格一致才算同物，Bioz 文献才完全适用。`check_equivalence(platform_cas, jena_cas, match_key)`（`bioz_equivalence.py`）：

| 条件 | equivalence | needs_review | 含义 |
|------|-------------|:------------:|------|
| 双方 CAS 都有且等同 | **exact** | 否 | Bioz 文献完全适用 |
| 双方 CAS 都有但不一致 | **mismatch** | 是 | 罕见，jena 命中但与平台不符 |
| 一方有 CAS（match_key=cas/synonym） | name_match | 是 | 无法 CAS 证实，按 name 降级 |
| 双方都无 CAS（match_key=name） | **weak** | 是 | 仅 name 模糊命中，文献可能不适用 |

`needs_review=true` 时前端 Bioz section 显示显著黄底警示条。

**cas_normalize 的防御作用**：`cas_normalize` 去 dash 比较，**非 CAS 形态（如 SMILES、产品名）返回 None**。这兜住了历史坑——即便 ChEMBL 路径曾把 SMILES 塞进 cas_resolved，等同性校验也会把 SMILES 当"无 CAS"处理，不会误判为 mismatch。P4 后这个防御仍是第二道保险。

### 5.4 去重链（落库时）

Bioz Adopt 落库时的三重去重（`bioz_adopter.py`）：

```
每条 bioz reference
   │
   ├─① Reference 去重（降级查重）
   │     DOI 命中 → 复用
   │     PMID 命中 → 复用
   │     title iexact 命中 → 复用
   │     都没有 → 新建 Reference
   │
   └─② ProductReference 去重
         按 (product, reference, citation_role) 唯一约束
         get_or_create → 已存在则 skipped，新建则 adopted
```

**关键**：同一 Reference 可关联多个产品（ProductReference 各建一条）；同一产品重复 Adopt 同一文献会 skipped（幂等）。

### 5.5 厂商无关化净化（Bioz 法律硬约束）

Bioz 引用上下文原文带「Jena Biosciences, NU-1138」，原样挂我们产品页有**法律风险 + 尴尬**（别家名字）。`bioz_sanitizer.sanitize_record` 强制净化：

- 删厂商名变体（Jena Bioscience / Jena Biosciences / Jenabioscience）
- 删 `catalog_group` 全 SKU 变体
- 删 Bioz 标签（`<c>`/`<t>`/`<cdd>`）
- **保留**：化学物质名 + 浓度

净化后字段：`long`/`medium`/`short`（三级引用上下文）。

**Bioz score 丢弃**：score 基于具体 SKU，对我们产品无意义，必须丢弃；改用 `impact_factor` + 年份排序。

**免责声明**：每条 bioz section 带 `disclaimer`：「文献基于同化学实体匹配，非特定厂商产品引用。展示实验证据需研究员确认后纳入正式产品文档。」

### 5.6 缓存与容错（L1/L2/L3 三层）

详细设计见 `DATASOURCE_RELIABILITY.md`，此处摘要：

| 层 | 机制 | 状态 |
|----|------|:----:|
| **L1 DB**（DataSourceCache） | 按源+标识符存原始 API 响应，TTL 分级（PubChem 30天 / Bioz 14天） | ✅ |
| **L2 Redis** | 热数据短期缓存 + 限速窗口 | ✅ |
| **L3 统一客户端**（`core/datasource_client.py`） | 超时(必传) + tenacity 重试(429/503 指数退避) + 令牌桶限速 | ✅ |
| **全局兜底** | `socket.setdefaulttimeout(30)` 防裸调用挂死 | ✅ |

**stale 兜底**：API 失败时，即使缓存过期也返回旧值，标记 `is_stale=True`（优于报错）。

**三路独立容错**：enrich 的五 section 各自 try/except，任一失败返回空结构，不影响其他 section。

---

## 6. 前端呈现（ProductEditPage.vue）

### 6.1 五 section 渲染顺序

AI AUTO MATCH 面板内，结果按「凭证→证据→知识图谱」数据流排列：

```
[AI AUTO MATCH 按钮]
  ① chemical preview（化学属性表 + Lipinski + CAS 冲突警示条）
  ② 🧪 JenaMatchSection（规格凭证 + 归一化规格表 + Apply 按钮）
  ③ 📚 BiozEvidenceSection（文献证据 + IF + Adopt 按钮）
  ④ 🧬 Knowledge Chain Matches（PubMed 知识链反向匹配）
  ⑤ 📚 Literature / 🧪 Protocols（PubMed 文献 + BioProCorpus 协议）
  [Apply All to Form]
```

jena 和 bioz 拆为**独立子组件**（`components/JenaMatchSection.vue` / `BiozEvidenceSection.vue`），便于 P2 复用 Adopt 交互。

### 6.2 Apply 逻辑（化学属性 + 规格 + 知识链）

`applyAllEnrichResults()` 一键回填，**只填空字段**（不覆盖已填，研究员权威）：

1. **化学属性**：`canonical_smiles → form.smiles`、`inchi/formula/molecular_weight`、`cas_resolved → form.cas`（各带 `if (!form.xxx)` 守卫）
2. **知识链 matched methods**：推入 `methodIds`
3. **知识链 matched apps**：级联加载该 App 下所有 Method 一并推入
4. **Protocols**：只关联有数字 DB ID 的（BioProCorpus 字符串 id 需先 import-protocol）
5. **jena 归一化规格**（P1）：`purity/storage/shipping/shelf_life/category_l1` 仅填空

回填后 toast：`Applied: properties, N methods, N protocols, N jena specs`。

### 6.3 Adopt 交互（Bioz 文献落库，P2）

`BiozEvidenceSection` 提供：
- 顶部「Adopt all (N)」主按钮（批量落库全部文献）
- 每条文献卡片 per-ref「Adopt」小按钮（选择性落库）
- 已 Adopt 的卡片显示「✓ 已落库」，按钮置灰（track `adoptedSet`）
- 新建产品（未保存，无 productId）时按钮 disabled，提示「先保存产品」

落库后 toast：`Adopt 完成: 3 新建 / 1 已存在`。

### 6.4 CAS 冲突警示条（P3-2）

chemical preview 表格下方，三源 CAS 不一致时显示黄色警示条，列三源值。不阻断。

### 6.5 已关联徽章（P3-1）

bioz/literature references 中已落库的（`ref_id` 非空）：
- BiozEvidenceSection：显示「✓ 已关联 #N」链接（替代 Adopt 按钮）
- Literature 区：文献前显示「✓ #N」链接

链接指向 `/references/<id>`，研究员可点击确认。

### 6.6 状态展示规则

| 场景 | 展示 |
|------|------|
| 单结果（chemical） | 属性预览表 + Lipinski + Apply All |
| 多候选（chemical） | 候选列表（研究员手选） |
| ChEMBL fallback | 黄色徽章「Not found in PubChem — results from ChEMBL」 |
| jena 命中 | 凭证表 + 归一化规格表 + Apply 按钮 |
| jena 未匹配 | 浅灰提示「jena 索引未匹配」 |
| bioz needs_review | 黄底警示条「该证据需人工复核」 |
| equivalence=weak | 红色徽章 |
| 未找到（chemical） | search_hint 提示改用 CAS 或手动输入 |

---

## 7. 字段溯源速查表

### 7.1 Product 字段 → 数据源

| 字段 | 主源 | 备源 | 说明 |
|------|------|------|------|
| `name` / `catalog_no` | 研究员/Word | — | 唯一标识输入 |
| `cas` | **PubChem** | — | 只能 PubChem 解析；jena CAS 不进此字段 |
| `smiles` / `inchi` / `formula` / `molecular_weight` | **PubChem** | ChEMBL | 化学结构权威 |
| `synonyms` | 研究员 | PubChem iupac | jena systematic_name 可作锚点 |
| `purity` / `concentration` | **jena** | Word | jena 副产品；concentration 需语义分类 |
| `storage` / `shipping` / `shelf_life` | **jena** | Word | jena 最独占的物流三件套 |
| `category_l1` / `category_l2` | **jena** category_path | 研究员 | — |
| `overview` | Bioz snippets | jena | Bioz 更优 |
| `seo_title` / `seo_description` | 本地 AI 生成 | — | 发布时自动生成 |

### 7.2 Reference 字段 → Bioz 映射

| Reference 字段 | Bioz 来源 | 说明 |
|----------------|-----------|------|
| `title` | `article_title` | 必填 |
| `authors` | `authors`（list → 逗号字符串） | bioz 返回 list |
| `journal` | `journal` | — |
| `year` | `pub_date` 提取 4 位年份 | 多格式兼容 |
| `doi` / `pmid` | `doi` / `pmid` | 唯一约束，去重键 |
| `source_type` | 固定 `journal` | — |

### 7.3 知识实体 → 数据源

| 实体 | 主源 | 落库路径 |
|------|------|---------|
| Reference | **Bioz** + PubMed | `adopt-bioz-refs`（Bioz）/ 手动 |
| Protocol | **BioProCorpus** | `import-protocol` |
| Method | PubMed 关键词 + Bioz techniques | 工作台手动 / inline 创建 |
| Application | 人工 + PubMed/Bioz 反向匹配 | 工作台手动 |
| ProductMethod 桥接 | AUTO MATCH matched_methods | Apply All |
| ProductReference 桥接 | Bioz Adopt | `adopt-bioz-refs` |

---

## 8. 历程与坑（关键共识）

这一节记录数据源探讨中踩过的坑与形成的共识，避免后人重蹈覆辙。

### 8.1 ChEMBL cas_resolved SMILES 冒充（P4，已修复）

**坑**：`pubchem_enhancer.py:454`（ChEMBL fallback 单结果路径）把 `canonical_smiles` 塞进 `cas_resolved` 字段，注释「will use SMILES as identity hint」。

**危害**：
- 前端 `applyPubchemProperties` 的 `if (chem.cas_resolved && !form.cas) form.cas = chem.cas_resolved` 会把 **SMILES 填入 CAS 字段** → 脏数据
- jena 用 `cas_resolved` 当 input_cas 查 jena 索引 → SMILES 查不到
- CAS 三源冲突校验（P3-2）会把 SMILES 当成一个"CAS 源"参与比较 → 误报

**修复**（2026-07-02）：`cas_resolved` 在 ChEMBL 路径返回 `None`。`canonical_smiles` 仍在 `properties` 中正常返回。前端空判断已天然短路。

**防御**：`cas_normalize` 的形态校验（非 CAS 形态返回 None）作为第二道保险，即便类似坑再现也不会污染 CAS 字段。

### 8.2 jena 策略 C→B 撤销（最大架构修正）

**坑**：jena 曾被归为策略 C（批次导入落库成 Product），实现了 `jena_importer.py` + `import_jena_products` command，落库 2098 条到 Product 表。

**为什么撤销**：
1. jena CAS 独占性 = 0%（299 个 CAS 全在 PubChem）→ jena 不是化合物知识源
2. 研究员不会从 jena 选择新建产品 → 落库的 2098 条成"孤儿数据"
3. jena 的真正价值是 systematic_name 锚点（撬动 Bioz），不在产品记录本身

**共识**：jena 改归**策略 B（本地索引常驻）**，与 BioProCorpus 同构。代码删除，2098 条清除。

**教训**：数据源选型要先问「它的独占价值是什么」，而非「它有什么数据就落什么」。落库是重决策，索引常驻是轻决策。

### 8.3 Bioz CAS 不可查询

**坑**：旧设想认为 Bioz search_result 是通用入口，CAS 可查。

**实测真相**：Bioz **不按 CAS 索引**。搜索 CAS `1927-31-7` 时页面显示「Missing: 1927 31 7」，回落到文本匹配返回错误产品。

**共识**：Bioz 必须用 **systematic_name / product_name / SKU** 查询。实际接入用 widget API（`back-badge-8.bioz.com/get_widget_data_ex_v9/`），参数为供应商名（cx）+ SKU（qx），依赖 jena 的 catalog_no。

### 8.4 Bioz 必须厂商无关化净化（法律硬约束）

**坑**：Bioz 引用上下文原文带「Jena Biosciences, NU-1138」，原样挂我们产品页 = 别家名字 + 法律风险。

**共识**：净化是硬约束，不是可选项。删厂商名变体 + catalog_group 全 SKU 变体 + Bioz 标签，保留化学物质名 + 浓度。Bioz score 基于具体 SKU 对我们无意义，必须丢弃，改用 IF 排序。每条文献带免责声明。

### 8.5 concentration 语义污染（jena 数据特性）

**坑**：jena 的 `concentration` 字段混入多种语义（12.6% 非小分子浓度）。

**分类规则**（预填前）：
| 语义类型 | 识别特征 | 处理 |
|---------|---------|------|
| 小分子浓度 | 含 mM/M/μM/%/w/v | 直接填 |
| 酶活性浓度 | 含 units/μl, units/ml | 标注或归 handling_notes |
| 浓缩倍数 | 含 x conc./2x/10x | 填入（自定义值） |
| 污染（纯度方法） | photometrically/HPLC/PAGE（不含量纲） | **置 null**，归 purity |

### 8.6 Bioz authors 是 list 不是 string

**坑**：P2 Adopt 落库时，`bioz_adopter._build_reference` 直接对 `authors` 调 `.strip()`，但 bioz 真实返回 authors 是 **list**（如 `["Julia Drebes", "Madeleine Künz", ...]`）→ 崩溃。

**修复**：兼容 list 和 string，list 自动拼成逗号字符串。教训：bioz 的字段类型要基于真实返回而非假设，e2e 验证必做。

### 8.7 关键共识清单

| # | 共识 | 出处 |
|---|------|------|
| 1 | jena 是查询凭证层，不是产品数据源 | §8.2 |
| 2 | 化学结构唯一权威是 PubChem，jena/Bioz 不碰 | §1.1, §8.2 |
| 3 | Bioz 必须用 SKU/systematic_name 查，CAS 不可用 | §8.3 |
| 4 | Bioz 文献跨供应商可复用（化学实体层） | §4.6 |
| 5 | 厂商无关化净化是法律硬约束 | §8.4 |
| 6 | 化学等同性 CAS 校验决定 Bioz 文献适用性 | §5.3 |
| 7 | 知识资产落库严格解耦推荐（研究员确认） | §1.3 |
| 8 | AI 预填只填空字段，研究员是最终权威 | §6.2 |
| 9 | cas_resolved 只放真 CAS（P4） | §8.1 |
| 10 | 缓存键统一用 systematic_name（查询/缓存/知识链同主键） | §5.1, `DATASOURCE_RELIABILITY.md` |

---

## 9. 已评估并淘汰的数据源

| 数据源 | 评估结论 | 淘汰理由 |
|--------|---------|---------|
| **ChEBI** | 不集成 | 修饰核苷酸 0% 覆盖；化合物属性被 PubChem 覆盖。**潜在价值**：其 ontology 关系网（is_a/has_role）在未来做化合物语义推理时可重评估 |
| **CAS Common Chemistry** | 不集成 | 修饰核苷酸 0% 覆盖；功能（CAS→化合物）完全被 PubChem 覆盖；需 API Key + 有速率限制 |

> 这两个源在后续会话中**不应再被重新提议接入**，除非产品线扩展到代谢物/天然产物，或平台决定做化合物本体推理。

---

## 10. 配套文档索引

| 文档 | 内容 | 与本文档关系 |
|------|------|-------------|
| `CLAUDE.md` | 架构铁律、技术栈、权限、测试 | 上位约束 |
| `DATASOURCE_RELIABILITY.md` | 缓存/容错/降级/三种数据放置策略的深度设计 | §5.6 的展开（生产可靠性） |
| `AI_AUTO_MATCH.md` | AI AUTO MATCH 功能的接口/字段/降级（3 section 版） | §3 的早期专题参考（jena/bioz 部分已过时，以本文档为准） |
| `COA_SDS.md` | COA/SDS 自动生成（数据依赖、SDS 降级链） | 下游消费（依赖本文档的化学属性） |
| `KNOWLEDGE_ASSETS.md` | 知识图谱体系（实体、关系、生成、校验） | §1.3 的展开 |
| `jena_scraper_spec.md` | jena 爬虫产出物规格（字段+清洗规则） | §4.5 的数据规格 |
| `KNOWLEDGE_ROADMAP.md` | 优化待办（P0/P1/P2 分级） | 演进规划 |

---

## 附录 A：数据源 API 速查

| 数据源 | 端点 | 认证 | 限速 | 超时 | 缓存 TTL |
|--------|------|------|------|------|---------|
| PubChem | `rest/pug/compound/{namespace}/{id}/property/...` | 无 | 5 req/s | 10s | 30 天 |
| ChEMBL | `ebi.ac.uk/chembl/api/data/molecule/search` | Accept header | 1-2 req/s | 30s | 30 天 |
| PubMed | `eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch+esummary` | 无/可选 Key | 3 req/s | 15s | 14 天 |
| BioProCorpus | 本地文件 | — | — | — | 索引常驻 |
| jena | 本地 JSONL 索引 | — | — | — | 30 天（match 结果） |
| Bioz widget | `back-badge-8.bioz.com/get_widget_data_ex_v9/` | 无 | 待测 | 30s | 14 天 |

---

## 附录 B：jena 数据质量审计（2026-06-28）

> **⚠️ 2026-07-16 重大勘误**：本附录（含下方「无需二次爬虫」结论）的**覆盖率视角已被推翻**。
> 2026-06-28 的审计只统计了字段的**填充率（有值 = 达标）**，未校验值的**正确性**。Phase 1~4 污染测绘发现：
> - 身份字段仅 **91% 干净**，9% 污染（catalog 与其它字段粘连 173 条等），而 `catalog_no` 是 Bioz 硬锚点——污染即击穿链路；
> - 规格字段（form/purity/concentration…）的高覆盖率**大量来自全页 fallback 正则误抓**（scraper_v3.py 第 870-896 行），值不可信；
> - matcher 双向子串匹配歧义率 **43%**（取首条错配，如 ATP→2'MeSe-ATP）。
> **正确结论**：现有 jsonl **不满足**「值正确」标准，**需要**按根因（R1~R6）重爬产出干净数据集。原则：**字段和值只有正确才有价值，数据量本身没有价值，可能只是污染。**
> 权威依据：`verification/jena_field_extractability_contract.md`（重爬契约）+ 配套 identity/spec/ambiguity 审计报告。下表覆盖率数字仅作历史留存，**不得再作为「无需重爬」的论据**。

核心三线（Nucleotides 1281 + Molecular Biology 297 + Click Chemistry 78）：1656 条（78.9%）

| 独占价值字段 | 覆盖率 | 备注 |
|-------------|:------:|------|
| systematic_name | 96.6% | 有分子式化学品 97.9%；Click Chemistry 缺口 28 条用 product_name 兜底 |
| storage_condition | 99.8% | — |
| shipping_condition | 100% | — |
| shelf_life | 99.8% | — |
| form | 100% | — |
| purity | 80.3% | 含 HPLC/PAGE 方法学 |
| concentration | 80.2% | 值有效，语义需分类（§8.5） |
| ph | 84.2% | — |
| datasheet / msds URL | 96–99% | — |
| cas_number | 15.8% | 走 PubChem，无所谓（独占性=0） |

**结论（已于 2026-07-16 被推翻，见本附录顶部横幅）**：~~现有 jsonl 数据已满足 jena 的独占价值定位，无需二次爬虫。~~ → 修正为：现有 jsonl 只满足「有值」不满足「值正确」，**需按 R1~R6 根因重爬**产出干净数据集。

---

*文档日期：2026-07-02 | 基于实测与代码核查（P1~P4 全完成，1197 passed / 10 skipped / 0 failed）| 工作台数据源的唯一权威叙事文档*
