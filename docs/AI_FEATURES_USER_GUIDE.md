# AI AUTO MATCH 功能参考指南

> 面向**使用者**的参考文档：讲清 AI AUTO MATCH 是什么、怎么用、背后接了哪些数据源、数据怎么流转。
> 原独立的「AI Tools」面板已合并进 AUTO MATCH（见 §1.5），现在只有一个 AI 入口。
> 技术实现细节见 `FIVE_DATASOURCES.md`（数据源权威叙事）与 `AI_AUTO_MATCH.md`（早期接口专题）。
>
> 文档基于 2026-07-17 最新数据撰写：jena 生产源 **1998** 条、Bioz 覆盖 **485/1998 = 24.3%**、AUTO MATCH 实测变形 **0**。

---

## 〇、一分钟总览

| 功能 | 给谁用 | 入口 | 一句话 |
|------|--------|------|--------|
| **AI AUTO MATCH** | 研究员（工作台） | 产品编辑页「🤖 AI AUTO MATCH」按钮 | 一键自动匹配：输入任一标识，一次返回化学属性（含跨字段 Mismatches / 相似化合物）+ 规格预填 + Bioz 文献 + 知识链 + 协议 |

> **只有一个 AI 入口**：原「AI Tools」面板（Validate / Protocols / Literature 三标签）已合并进 AUTO MATCH，见 §1.5。
>
> 共同点：**系统只建议、不强制**。所有回填均为「只填空字段」，研究员已填的值不会被覆盖；落库由研究员确认后执行。

---

## 一、AI AUTO MATCH

### 1.1 定义

AI AUTO MATCH 是研究员工作台产品编辑页的**一键式自动匹配功能**。研究员在新建或编辑产品时，
只要输入了产品的任一唯一性标识（产品名 / CAS / SMILES / InChI），点一下按钮，
系统在**一次请求**内完成五件事并返回预览卡片：

1. **化学属性补全** — 从 PubChem / ChEMBL 解析分子式、分子量、SMILES、InChI、CAS、Lipinski 五规则；
2. **jena 规格预填** — 从本地 jena 索引匹配出纯度 / 储存 / 运输 / 保质期 / 分类等副产品规格；
3. **Bioz 文献证据** — 用 jena 的 `catalog_no` 查 Bioz widget，返回产品级结构化文献（含影响因子 + 引用上下文）；
4. **知识链预填** — 从 PubMed 提取应用/方法关键词，反向匹配本地 Application / Method 实体；
5. **实验协议推荐** — 从本地 BioProCorpus 检索相关实验协议（试剂/设备/步骤）。

### 1.2 怎么用

| 步骤 | 操作 |
|------|------|
| 前置 | 表单至少填了 `name` / `cas` / `smiles` / `inchi` 之一（按钮在这些字段全空时禁用） |
| 触发 | 点「🤖 AI AUTO MATCH」按钮（前端 `ProductEditPage.vue` → `enrichProduct()`） |
| 等待 | 典型 5–30 秒（CAS 最快，需分词降级的产品名较慢；前端 timeout 90s） |
| 查看 | 五 section 按「凭证→证据→知识图谱」顺序渲染：chemical → jena → bioz → knowledge chain → literature/protocols |
| 回填 | 点「Apply All to Form」一键回填——**只填空字段**，不覆盖已填值 |
| 落库 | Bioz 文献点「Adopt」经 `adopt-bioz-refs` 落库；协议点「Import」经 `import-protocol` 落库 |

### 1.3 接口契约

```
POST /api/v1/products/enrich/
请求：{ product_name?, cas?, smiles?, inchi?, product_id? }
响应（信封 {success,data,meta}）：
{
  "chemical":   { found, source(pubchem/chembl), cid, cas_resolved, properties{}, lipinski{}, mismatches[], similar_compounds[] },
  "jena":       { matched, match_key, catalog_no, systematic_name, cas_number,
                  normalized: { purity, storage_condition, shipping_condition,
                                shelf_life, concentration, category_l1 } },
  "bioz":       { queried, vendor, catalog_no, equivalence, needs_review,
                  disclaimer, total, references[] },
  "literature": { applications[], methods[], references[], matched_apps[], matched_methods[],
                  unmatched_app_keywords[], unmatched_method_keywords[] },
  "protocols":  [ { id, source, title, score, reagents, equipment, materials, steps[], method_hint } ]
}
```

- 五 section **各自容错**：任一失败返回空结构，不影响其它。
- `ref_id` 回写：传入 `product_id` 时，已落库的文献会带 `ref_id`（前端显示「✓ 已关联」）。

### 1.4 已知注意点

- **权限对齐**：`ProductEnrichView` 当前权限是 `IsAdminUser`（superuser）；工作台面向研究员（`is_staff`）。
  演示 admin 账号是 superuser 所以可用；生产中纯 staff 研究员会被 401。建议改 `IsStaffUser`（详见 `AI_AUTO_MATCH.md` §9.2）。
- **CAS 搜索最可靠**：精确匹配或 not found，无假阳性；产品名搜索对修饰核苷酸覆盖差（常命中母体），ChEMBL fallback 更优。
- **Bioz 需人工复核**：`equivalence=weak` / `needs_review=true` 是常态（厂商+货号查询、CAS 不可用），界面会显著黄底警示。

---

### 1.5 AI TOOLS 已合并进 AUTO MATCH（2026-07-17）

原独立的「AI Tools」面板（`AiToolsPanel.vue`，后台产品编辑页三标签页）及其 6 个分字段端点
（`validate/`、`recommend-protocols/`、`recommend-literature/` 及其 `-unsaved` 版本）已**删除**。
原因：与 AUTO MATCH 能力高度重叠，且双入口容易让研究员困惑"该用哪个"。

合并方式：
- **Validate 的独有能力已并入 AUTO MATCH 的 `chemical` 段**：
  - `chemical.mismatches` — cas/smiles 跨字段一致性（是否指向同一物质）；
  - `chemical.similar_compounds` — PubChem 相似化合物列表。
  它们显示在 AUTO MATCH 化学卡片的「高级匹配详情」折叠区（⚠ Cross-field Mismatches / 🔗 Similar Compounds）。
- **Protocols / Literature 本就是 AUTO MATCH 的输出**（协议更全面，含 `recommend_expanded`；文献同理），无需重复入口。
- 保留的独立端点（批量/渲染/落库，见 §二）不变。

> 现在只有一个 AI 入口：工作台产品编辑页的「🤖 AI AUTO MATCH」按钮。

---

## 二、其余 AI 端点（批量 / 渲染 / 落库）

| 端点 | 用途 |
|------|------|
| `POST /products/enrich-from-pubchem/` | 仅从 PubChem 解析化学属性（支持单产品 + `product_ids` 批量） |
| `POST /products/batch-validate/` | 批量化学校验（传 `product_ids`） |
| `POST /products/batch-recommend-literature/` | 批量文献推荐 |
| `POST /products/render-structure/` | RDKit 将 SMILES 渲染为出版级 SVG 结构图（返回 `svg` + `canonical_smiles`） |
| `POST /products/import-protocol/` | 把 BioProCorpus 协议落库为 Method + Protocol + ProtocolStep 并关联产品（幂等） |
| `POST /products/<pk>/adopt-bioz-refs/` | 把 Bioz 文献批量落库到 Reference + ProductReference（去重：DOI>PMID>title） |

---

## 三、数据源详解（6 个）

AUTO MATCH 串接 6 个数据源：**3 个外部 API + 2 个本地语料/索引 + 1 个本地知识库**。

### 3.1 PubChem — 化学结构权威源

| 维度 | 说明 |
|------|------|
| 用途 | 化学属性解析的**唯一主源**（CAS/SMILES/分子式/MW/Lipinski） |
| 接入 | Python 库 `pubchempy`（`pcp.get_compounds`） |
| 端点 | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/` |
| 认证 / 限速 | 无 Key，约 5 req/s |
| 缓存 | L1 DataSourceCache（TTL 30 天）+ L2 Redis |
| 标识符 | `name` / `smiles` / `inchi` / `inchikey` / `cid` / `formula`（CAS 用正则从 synonyms 提取） |

**用法要点**：CAS 在 PubChem 以 synonym 存储，用 `name/{CAS}` 查是标准做法；对修饰核苷酸**名称搜索常命中母体**，CAS 搜索无此问题。

### 3.2 ChEMBL — 化学结构 fallback

| 维度 | 说明 |
|------|------|
| 用途 | PubChem 查不到时的自动降级源（修饰核苷酸偶联物反而更优） |
| 端点 | `https://www.ebi.ac.uk/chembl/api/data/molecule/search` |
| 超时 | 30 秒 |

**用法要点**：触发条件 = PubChem 主标识符查不到 + 分词降级仍查不到。**ChEMBL 无 CAS 数据**——`cas_resolved` 在 ChEMBL 路径返回 `None`（不会冒充 CAS）。

### 3.3 PubMed — 文献元数据 + 知识链

| 维度 | 说明 |
|------|------|
| 用途 | 检索产品相关文献，提取应用/方法关键词，反向匹配本地知识库 |
| 接入 | NCBI E-utilities（`esearch` + `esummary`） |
| 限速 | 无 Key 3 req/s；有 Key 10 req/s |
| 超时 | 15 秒 |

**用法要点**：4 策略搜索（产品名精确 → 别名 → CAS → 全文兜底）；提取的关键词反向匹配本地 `Application`/`Method` 表，返回 `matched_*`（可关联）与 `unmatched_*_keywords`（需新建）。与 Bioz 分工：PubMed 覆盖广但无产品关联；Bioz 精准但覆盖窄。

### 3.4 BioProCorpus — 实验协议语料库（本地）

| 维度 | 说明 |
|------|------|
| 用途 | 实验协议推荐（试剂/设备/材料/步骤富内容） |
| 位置 | `backend/data/bioprocorpus/`（~175 MB，3 个 JSON；未入 git，需 `scripts/download_bioprocorpus.py` 下载） |
| 索引 | 进程级单例（`get_shared_recommender`），AppConfig.ready 预热 |
| 落库 | **永不直接落库**；搜索结果需经 `import-protocol` 端点入库 |

**用法要点**：纯关键词匹配（非语义搜索），长尾可能漏匹配。搜索结果 `id` 为字符串，前端用 `Number.isInteger(p.id)` 过滤——只有经 `import-protocol` 入库拿到数字 DB ID 后才能关联产品。

### 3.5 jena — AUTO MATCH 锚点供给（本地索引 · 策略 B）

| 维度 | 说明 |
|------|------|
| 角色 | AUTO MATCH 的**跨源查询锚点供给者**（硬锚点 `catalog_no` 驱动 Bioz；`systematic_name` 展示/理论锚点）+ 规格副产品 |
| 数据 | 爬虫产出 JSONL，当前生产源 **1998** 条（2026-07-17 合并：新 1318 + 旧合法缺失 680） |
| 索引 | 进程级单例（`get_shared_jena_index`），惰性构建，按文件指纹失效重 build |
| 落库 | **永不落库成 Product**（策略 B，与 BioProCorpus 同构） |
| 缓存 | L1 DataSourceCache（`jena_match` 桶，TTL 30 天） |

**匹配逻辑**（`match_jena`，cas→name→synonyms 真级联）：
1. identifier 形如 CAS → 先按 CAS 查 jena 索引；
2. miss → 按 name 查（`lookup` 模糊匹配，词边界命中 > 短名优先，歧义不盲取首条）；
3. miss → 按 synonyms 逐条模糊匹配（限 20 条）。

**输出**：`catalog_no`（硬锚点）/ `systematic_name` / `cas_number`（覆盖仅 ~16%）/ `normalized` 规格（purity/storage/shipping/shelf_life/concentration/category_l1）。

**核心价值 = 双锚点，且 `catalog_no` 才是硬锚点**：Bioz 链路实际调用 `search_by_sku(catalog_no)`；一旦 `catalog_no` 被污染即击穿整条 Bioz 链路。jena **不是产品创建入口**、**不碰化学结构**（CAS 独占性=0%，全在 PubChem）。

### 3.6 Bioz — 产品级结构化文献（外部 API）

| 维度 | 说明 |
|------|------|
| 角色 | 跨供应商产品级结构化文献（含影响因子 IF + 引用上下文） |
| 端点 | `https://back-badge-8.bioz.com/get_widget_data_ex_v9/`（widget API） |
| 查询 | **必须供应商名（cx）+ SKU（qx）**；**CAS 不可用**（实测不索引） |
| 超时 | 30 秒 |
| 触发 | **依赖 jena 命中**——用 jena 的 `catalog_no` 作 qx 查询 |
| 覆盖 | 当前数据 **485/1998 = 24.3%** 有文献证据（双口径一致，failed=0） |

**用法要点**：
- 编排链：`check_equivalence`（化学等同性）→ `search_by_sku` → `sanitize_record`（厂商无关化净化）→ 按 IF+年份排序。
- **厂商无关化净化是法律硬约束**：删厂商名变体 + catalog_group 全 SKU 变体 + Bioz 标签，保留化学物质名 + 浓度；每条带免责声明。
- `equivalence=weak` / `needs_review=true` 是常态，前端显著黄底警示。
- 落库：`adopt-bioz-refs`，去重 DOI>PMID>title。

---

## 四、数据流转逻辑

### 4.1 工作台数据的三类产物

| 类 | 回答 | 主源 | 落库字段 |
|----|------|------|----------|
| **化学属性** | 是什么化学物质 | PubChem（ChEMBL fallback） | `cas` / `smiles` / `inchi` / `formula` / `molecular_weight` |
| **商业单元** | 怎么卖/存/运 | jena 副产品（或 Word 导入） | `purity` / `concentration` / `storage` / `shipping` / `shelf_life` / `category_l1` |
| **知识实体** | 关联哪些文献/应用/方法/协议 | Bioz + PubMed + BioProCorpus | `Reference` / `Application` / `Method` / `Protocol`（经桥接表） |

**铁律**：① 化学结构唯一权威是 PubChem，jena/Bioz 不碰；② 所有数据源生成的知识实体**都不直接写库**，只生成待审草案，落库由研究员确认。

### 4.2 AI AUTO MATCH 一站式数据流

```
研究员输入 cas / name / smiles / inchi
   │
   ├─① chemical = PubChemEnhancer.resolve(identifier)
   │       PubChem 查不到 → 分词降级 → ChEMBL fallback
   │       产出 cas_resolved / SMILES / MW / Lipinski
   │
   ├─② jena = match_jena(cas or name, synonyms)
   │       cas → name → synonyms 真级联
   │       产出 catalog_no(硬锚点) + 归一化规格副产品
   │
   ├─③ bioz = fetch_bioz_evidence(jena, platform_cas)
   │       用 jena.catalog_no 查 Bioz widget
   │       check_equivalence(platform_cas, jena.cas_number) → 适用性判定
   │
   ├─④ literature = LiteratureRecommender.recommend(name)
   │       PubMed 4 策略 → 应用/方法关键词 → 反向匹配本地知识库
   │
   └─⑤ protocols = ProtocolRetriever.search(name)
           BioProCorpus 关键词匹配 → 富内容协议
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

### 4.3 跨字段校验（原 AI TOOLS Validate）已并入 AUTO MATCH

`ProductValidator.validate()` 现在由 AUTO MATCH 的 `enrich` 复用：chemical 段额外返回
`mismatches`（cas/smiles 是否指向同一物质）与 `similar_compounds`（PubChem 相似化合物）。
原三标签页（Validate / Protocols / Literature）的分流与删除见 §1.5。

### 4.4 jena → Bioz 锚点链（最易出错的一段）

```
              jena 匹配记录
   ┌──────────────┼──────────────┐
   ▼              ▼              ▼
catalog_no    systematic_name   规格字段
(硬锚点,SKU)  (展示/命名对齐)   (副产品)
   │              │              │
   ▼              ▼              ▼
 Bioz          PubChem         jena 自身
search_by_sku  (命名对齐)       (COA/SDS)
(真实驱动键)
```

**为什么用 catalog_no 而非 systematic_name / CAS**：Bioz 不索引 CAS（实测），product_name 命中率低；
`catalog_no` 是供应商目录唯一编号，命中稳定，1 个正确的 `catalog_no` 撬动 1 个跨厂家文献池
（如 dATP 一次返回数百条 snippets）。因此 **catalog_no 的抽取正确性 = jena 独占价值的闸门**。

### 4.5 字段溯源速查

| Product 字段 | 主源 | 备源 |
|--------------|------|------|
| `cas` / `smiles` / `formula` / `molecular_weight` | **PubChem** | ChEMBL |
| `purity` / `concentration` | **jena** | Word |
| `storage` / `shipping` / `shelf_life` | **jena** | Word |
| `category_l1` / `category_l2` | **jena** category_path | 研究员 |
| `name` / `catalog_no` | 研究员 / Word | — |
| Reference（文献） | **Bioz** + PubMed | `adopt-bioz-refs` |
| Protocol（协议） | **BioProCorpus** | `import-protocol` |
| Method / Application | PubMed 关键词 + Bioz techniques | 工作台手动 |

---

## 五、缓存、容错与降级（使用者须知）

| 机制 | 说明 |
|------|------|
| L1 DB 缓存 | 按源+标识符存原始响应，TTL 分级（PubChem 30天 / Bioz 14天） |
| L2 Redis | 热数据短期缓存 + 限速窗口 |
| L3 统一客户端 | 超时（必传）+ 指数退避重试（429/503）+ 令牌桶限速 |
| 全局兜底 | API 失败时即使缓存过期也返回旧值（标 `is_stale`），优于报错 |
| 三路独立容错 | enrich 五 section 各自 try/except，任一失败不影响其他 |
| 降级链 | PubChem → 分词降级 → ChEMBL；CAS miss 时 name 兜底 |

> 外部 API（PubChem/ChEMBL/PubMed/Bioz）在中国大陆延迟较高，首次查询可能 5–30 秒；
> 二次查询因 L1 缓存通常秒回。

---

## 六、给使用者的实操清单

- **想最快补全一个产品**：工作台填 CAS → 点「🤖 AI AUTO MATCH」→ Apply All。
- **想精修单点**：用 AUTO MATCH 化学卡片「高级匹配详情」里的 Cross-field Mismatches / Similar Compounds（即原 Validate 能力）。
- **产品名查不到化学属性**：改用 CAS 或手动填 SMILES（名称搜索对修饰核苷酸覆盖差）。
- **Bioz 没文献**：正常（当前仅 24.3% 覆盖）；或该产品 jena 未匹配到 catalog_no（界面会提示）。
- **Bioz 文献带黄底警示**：说明是「同化学实体匹配」需人工复核，非特定厂商引用。
- ** Apply 后某字段没变**：该字段你已填过——AUTO MATCH 只填空、不覆盖。

---

## 七、配套文档

| 文档 | 内容 |
|------|------|
| `FIVE_DATASOURCES.md` | 数据源权威叙事（设计目的/接口/字段关系/传递校验/坑） |
| `AI_AUTO_MATCH.md` | AUTO MATCH 早期接口专题（jena/bioz 部分以 FIVE_DATASOURCES 为准） |
| `jena_scraper_spec.md` | jena 爬虫产出物字段 + 清洗规则 |
| `JENA_SCRAPE_PROCESS_2026-07-17.md` | 本次全量爬取过程记录 |
| `COA_SDS.md` | COA/SDS 自动生成（依赖本文化学属性） |

*文档日期：2026-07-17 | 基于最新数据（jena 1998 条 / Bioz 24.3% / AUTO MATCH 变形 0）与代码核查*
