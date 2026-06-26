# AI AUTO MATCH 功能技术文档

> 研究员工作台 · 产品编辑页一键自动匹配与预填
>
> 文档版本：2026-06-25　|　对应提交：`2c9fd08`、`112db9a`
>
> 适用对象：研究员工作台 ProductEditPage.vue 中 `🤖 AI AUTO MATCH` 面板

---

## 1. 功能概述

**AI AUTO MATCH** 是研究员工作台产品编辑页的一个一键式自动匹配功能。研究员在新建或编辑产品时，只要输入了产品的任一唯一性标识字段（产品名称 / CAS 号 / SMILES / InChI），点击按钮，系统会在一次请求内完成三件事：

1. **化学属性自动补全** — 从 PubChem / ChEMBL 解析出分子式、分子量、SMILES、InChI、CAS、LogP、TPSA、氢键供体/受体数等，并本地计算 Lipinski 五规则；
2. **知识链预填** — 从 PubMed 文献中提取应用场景与实验方法关键词，反向匹配本地知识库中已有的 Application / Method 实体，并预勾选关联；
3. **实验协议推荐** — 从本地 BioProCorpus 语料库检索相关实验协议，返回试剂、设备、步骤等富内容。

返回结果以预览卡片形式展示，研究员确认后点 `Apply All to Form` 一键回填表单。**系统只建议、不强制**：所有回填均为「只填空字段」，已由研究员填写的值不会被覆盖。

---

## 2. 使用场景与角色

| 维度 | 说明 |
|------|------|
| 使用角色 | 研究员（`is_staff=True`） |
| 触发位置 | `/workspace/products/:id/edit` 与 `/workspace/products/new` |
| 前置条件 | 表单中至少填了 name / cas / smiles / inchi 之一 |
| 典型耗时 | CAS 号约 5 秒；精确产品名约 15 秒；需分词降级的产品名约 30 秒 |
| 适用阶段 | 新建（未保存）与编辑（已保存）均可用 |

> 注意：后端 `ProductEnrichView` 当前声明的权限为 `IsAdminUser`（superuser），而前端工作台面向研究员（staff）。若研究员账号非 superuser，调用会被 401 拦截。这是已知的权限对齐问题，详见 §9。

---

## 3. 整体架构与调用链路

```
┌──────────────────────────────────────────────────────────────┐
│  前端 ProductEditPage.vue                                      │
│  runPubchemEnrich()  ──enrichProduct()──┐                    │
└──────────────────────────────────────────┼────────────────────┘
                                           │ POST /api/v1/products/enrich/  (timeout 90s)
                                           ▼
┌──────────────────────────────────────────────────────────────┐
│  后端 ProductEnrichView.post()  (apps/commerce/api/v1/ai_views.py) │
│                                                                │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────────┐ │
│  │ PubChemEnh-  │   │ LiteratureRecom- │   │ ProtocolRecom-  │ │
│  │ ancer        │   │ mender           │   │ mender.retriever│ │
│  │              │   │                  │   │                 │ │
│  │ ① PubChem API│   │ ③ PubMed API     │   │ ④ BioProCorpus  │ │
│  │ ② ChEMBL API │   │ ⑤ 本地知识库 DB  │   │   本地 JSON 文件 │ │
│  └──────────────┘   └──────────────────┘   └─────────────────┘ │
│                                                                │
│  返回 { chemical, literature, protocols }                      │
└──────────────────────────────────────────────────────────────┘
```

**一次 HTTP 调用，三类结果聚合返回**，研究员无需分别点击三次按钮。三类结果相互独立，任一失败不影响其他两类（各服务用 try/except 兜底）。

---

## 4. 数据源详解

AI AUTO MATCH 串接了 5 个数据源（3 个外部 API + 2 个本地数据）。

### 4.1 PubChem（外部 API · 主数据源）

| 维度 | 说明 |
|------|------|
| 用途 | 化学属性解析的唯一主源 |
| 接入方式 | Python 库 `pubchempy`（`pcp.get_compounds()`） |
| 端点 | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/` |
| 作用 | 根据标识符解析出化合物的完整分子属性与 CAS |
| 限速 | PubChem 官方约 5 req/s；无 API key |
| 超时 | pubchempy 默认 |

**支持的 namespace**（标识符类型）：`name` / `smiles` / `inchi` / `inchikey` / `cid` / `formula`

### 4.2 ChEMBL（外部 API · fallback）

| 维度 | 说明 |
|------|------|
| 用途 | PubChem 查不到时的自动降级源 |
| 接入方式 | 直接 HTTP（`requests.get`） |
| 端点 | `https://www.ebi.ac.uk/chembl/api/data/molecule/search` |
| 作用 | 对修饰核苷酸等 PubChem 覆盖差的化合物提供候选 |
| 超时 | 30 秒（ChEMBL 搜索端点响应慢，已从 10s 调至 30s） |

ChEMBL 返回结果按与 PubChem 统一的 schema 包装，`fallback_used=True`，前端会显示 `Not found in PubChem — results from ChEMBL` 提示。

### 4.3 PubMed（外部 API · 文献源）

| 维度 | 说明 |
|------|------|
| 用途 | 检索产品相关文献，提取应用/方法关键词 |
| 接入方式 | 直接 HTTP，NCBI E-utilities |
| 端点 | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (`esearch.fcgi` + `esummary.fcgi`) |
| 作用 | 4 策略搜索 → 返回文献标题/作者/PMID/DOI |
| 限速 | 无 API key 时 3 req/s（代码内 `min_interval=0.35s`）；有 key 时 10 req/s |
| 超时 | 15 秒 |

### 4.4 BioProCorpus（本地 JSON 语料库 · 协议源）

| 维度 | 说明 |
|------|------|
| 用途 | 实验协议推荐 |
| 接入方式 | 本地文件读取 + 内存索引 |
| 位置 | `backend/data/bioprocorpus/` |
| 作用 | 关键词匹配返回相关实验协议，含试剂/设备/步骤富内容 |

**实际加载的文件**（`_find_source_files()` 逻辑，排除基准文件）：

| 文件 | 大小 | 加载 |
|------|------|------|
| Bio-protocol.json | ~86 MB | ✅ |
| Protocol-io.json | ~72 MB | ✅ |
| Protocol-exchange.json | ~17 MB | ✅ |
| GEN.json / ERR.json / ORD.json / PQA.json | 基准文件 | ❌ 代码不读 |

> 数据来源：HuggingFace 公开数据集 `bowenxian/BioProBench`，可通过 `scripts/download_bioprocorpus.py` 重新下载。当前未纳入 git（大文件超 GitHub 限制）。

### 4.5 本地知识库（Django DB · 反向匹配源）

| 维度 | 说明 |
|------|------|
| 用途 | 把 PubMed 提取的关键词反向匹配到已有 Application / Method 实体 |
| 接入方式 | Django ORM（`Application`、`Method` 模型） |
| 作用 | 区分「已可关联的知识实体」与「需新建的关键词」 |
| 匹配字段 | `name` / `summary` / `purpose` / `slug` 的 `icontains` 模糊匹配 |

---

## 5. 后端实现

### 5.1 API 端点

| 方法 | 端点 | 视图 | 说明 |
|------|------|------|------|
| POST | `/api/v1/products/enrich/` | `ProductEnrichView` | **AI AUTO MATCH 主入口**，一次返回 chemical + literature + protocols |

响应统一走信封格式 `{success, data, meta}`，`data` 结构：

```jsonc
{
  "chemical":   { "found", "properties", "source", "cid", "cas_resolved", "candidates", "fallback_used", "lipinski" },
  "literature": { "applications", "methods", "references", "protocols",
                  "matched_apps", "matched_methods",
                  "unmatched_app_keywords", "unmatched_method_keywords" },
  "protocols":  [ { "id", "source", "title", "abstract", "url", "score",
                     "reagents", "equipment", "materials", "steps", "method_hint" } ]
}
```

### 5.2 PubChemEnhancer（化学属性）

**文件**：`backend/apps/commerce/services/validators/pubchem_enhancer.py`

核心方法 `resolve_to_properties(identifier, namespace)`：

1. 按 namespace 调 `_search_by_namespace()` → pubchempy `get_compounds()`
2. 若无结果且 namespace=name，做 `_fallback_search_by_tokens()`（分词降级，跳过 `biotin/utp/dutp` 等常见词）
3. 若仍无结果 → ChEMBL fallback `_chembl_search()`
4. 单结果 → 从 Compound 对象直接提取属性（避免二次 API 调用）
5. 多结果 → 返回候选列表 `candidates`（前端让用户选）
6. CAS 从 PubChem 同义词列表用正则 `^\d{2,7}-\d{2}-\d$` 提取

返回字段包括：`cid, molecular_formula, molecular_weight, canonical_smiles, isomeric_smiles, iupac_name, inchi, inchikey, xlogp, tpsa, h_bond_donor_count, h_bond_acceptor_count, rotatable_bond_count, complexity, exact_mass, charge, heavy_atom_count`。

`check_lipinski(properties)` 本地计算五规则：MW≤500、LogP≤5、HBD≤5、HBA≤10、RotBonds≤10。

### 5.3 LiteratureRecommender（文献与知识链）

**文件**：`backend/apps/knowledge/services/literature_recommender.py`

`recommend(product, top_k=5)` 流程（product 可为字符串/对象/None）：

1. `PubMedClient.search_by_product()` 4 策略搜索：
   - 策略 1：产品名精确搜 `[Title/Abstract]`
   - 策略 2：别名搜索（`PRODUCT_SYNONYMS` 表 + 核心词提取）
   - 策略 3：CAS 号
   - 策略 4：产品名全文兜底
2. 每篇文献标题提取：
   - 应用场景关键词（17 模式：cell labeling、sequencing、PCR…）
   - 实验方法关键词（21 模式：click chemistry、CuAAC、NMR…）
3. `_match_against_db()` 反向匹配本地 Application / Method 表（name/summary/purpose/slug 的 icontains）
4. 返回 `matched_apps/matched_methods`（可关联）与 `unmatched_*_keywords`（需新建）

### 5.4 ProtocolRecommender（协议推荐）

**文件**：`backend/apps/knowledge/services/protocol_recommender.py`

`BioProCorpusIndexer` 启动时从 3 个 JSON 文件构建内存索引（含 id/title/source/text/keywords/abstract/url/hierarchical_protocol/method）。`ProtocolRetriever.search()` 流程：

1. 查询词分词为 term 集合
2. 对每条协议计算相关度评分（`_compute_relevance`）
3. 按 score 降序取 top_k
4. `include_content=True` 时富内容提取：
   - 试剂：`# Reagents` → `# Solutions` → `# Recipes` fallback
   - 设备：`# Equipment`
   - 材料：`# Biological materials` → `# Materials` → `# Laboratory supplies` fallback
   - 步骤：从 `hierarchical_protocol` 提取层级步骤

---

## 6. 前端实现

### 6.1 触发与输入

**文件**：`frontend/src/views/workspace/ProductEditPage.vue` + `frontend/src/api/aiTools.js`

```js
// aiTools.js — 单次调用，timeout 90s
export function enrichProduct({ name, cas, smiles, inchi } = {}) {
  return http.post('/products/enrich/', { product_name, cas, smiles, inchi }, { timeout: 90000 })
}
```

按钮启用条件：`!pubchemEnriching && (form.name || form.cas || form.smiles || form.inchi)` 任一非空。

### 6.2 结果展示

| 状态 | 展示 |
|------|------|
| 搜索中 | 按钮文案 `Searching & matching…` |
| 单结果 | 属性预览表 + Lipinski 徽章 + 知识匹配区 + 文献列表 + 协议列表 + `Apply All to Form` |
| 多候选 | 候选列表（研究员手动选择） |
| 未找到 | `search_hint` 提示（建议改用 CAS 或手动输入 SMILES） |
| 出错 | 错误信息（红色） |
| fallback | 黄色 `word-warn` 标记 + `Not found in PubChem — results from ChEMBL` |

### 6.3 Apply All 应用逻辑

`applyAllEnrichResults()` 回填规则：

1. **化学属性**（只填空字段）：
   - `canonical_smiles → form.smiles`（仅当 form.smiles 为空）
   - `inchi → form.inchi`、`molecular_formula → form.formula`、`molecular_weight → form.molecular_weight`、`cas_resolved → form.cas`
2. **知识链 - matched methods**：推入 `methodIds`
3. **知识链 - matched apps**：级联加载该 App 下所有 Method 一并推入 `methodIds`
4. **Protocols**：只关联有数字 DB ID 的协议（BioProCorpus 搜索结果需先走 `import-protocol` 端点入库后才能关联）

回填后 toast 反馈：`Applied: properties, N methods, N protocols`。

---

## 7. 输入与输出规范

### 7.1 请求输入

```jsonc
POST /api/v1/products/enrich/
{
  "product_name": "5-Propargylamino-CTP",  // 产品名
  "cas": "73449-06-6",                      // CAS 号（可选）
  "smiles": "",                             // SMILES（可选）
  "inchi": ""                               // InChI（可选）
}
```

**标识符优先级**：`CAS > name > SMILES > InChI`。后端取第一个非空字段作为主标识符查询 PubChem。

### 7.2 响应输出

```jsonc
{
  "success": true,
  "data": {
    "chemical": {
      "found": true,
      "source": "pubchem",            // pubchem / chembl
      "namespace": "name",
      "cid": 702,
      "resolved_name": "ethanol",
      "cas_resolved": "64-17-5",
      "fallback_used": false,
      "candidates": [],               // 多结果时填充
      "properties": {
        "cid": 702,
        "molecular_formula": "C2H6O",
        "molecular_weight": 46.07,
        "canonical_smiles": "CCO",
        "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
        "iupac_name": "ethanol",
        "xlogp": -0.1, "tpsa": 20.23,
        "h_bond_donor_count": 1, "h_bond_acceptor_count": 1,
        "rotatable_bond_count": 0
      },
      "lipinski": { "passed": true, "violations": [], "details": { "mw_ok": true, ... } }
    },
    "literature": {
      "applications": ["labeling", "dna_labeling"],
      "methods": ["click_chemistry"],
      "references": [ { "pmid": "...", "title": "...", "doi": "...", "citation": "..." } ],
      "matched_apps":     [ { "keyword": "...", "matches": [{ "id": 1, "name": "...", "slug": "..." }] } ],
      "matched_methods":  [ { "keyword": "...", "matches": [{ "id": 5, "name": "...", "slug": "..." }] } ],
      "unmatched_app_keywords":     ["therapy"],
      "unmatched_method_keywords":  []
    },
    "protocols": [
      {
        "id": "p1", "source": "Bio-protocol", "title": "Click Chemistry with 5-Ethynyl-dUTP",
        "score": 3.5, "reagents": "...", "equipment": "...",
        "materials": "...", "steps": [ { "step_no": "1.1", "title": "...", "body": "..." } ],
        "method_hint": "Click Chemistry (CuAAC)"
      }
    ]
  },
  "meta": {}
}
```

---

## 8. 校验规则与降级策略

### 8.1 前端校验

| 规则 | 实现 |
|------|------|
| 必须有标识符 | 按钮在 name/cas/smiles/inchi 全空时 `disabled` |
| 防重复点击 | 搜索中按钮 `disabled` |
| 只填空字段 | Apply 回填时每个字段都带 `if (!form.xxx)` 守卫 |
| 协议只关联 DB ID | `Number.isInteger(p.id)` 过滤掉 BioProCorpus 字符串 id |

### 8.2 后端校验与降级

| 场景 | 策略 |
|------|------|
| PubChem 主标识符查不到 | name 降级为 `_fallback_search_by_tokens` 分词搜索 |
| 分词仍查不到 | 切 ChEMBL `_chembl_search()`（30s 超时） |
| CAS 搜不到但有 name | `ProductEnrichView` 中自动用 name 重试 |
| 单结果 vs 多结果 | 单结果直接给属性；多结果给 `candidates` 让用户选 |
| CAS 提取 | 从 PubChem synonyms 用正则 `^\d{2,7}-\d{2}-\d$` 提取 |
| 文献服务异常 | try/except 兜底，返回空结构不影响其他两类 |
| 协议服务异常 | 同上，返回空列表 |
| 限速 | PubMed 无 key 时 3 req/s（`min_interval=0.35s`） |

### 8.3 超时配置

| 位置 | 超时 |
|------|------|
| 前端 enrichProduct | 90 秒 |
| 后端 ChEMBL | 30 秒 |
| 后端 PubMed | 15 秒 |

### 8.4 数据准确性提示（已知）

据 27 个产品的实测（见 memory `ai-auto-match-test-results`）：

- **CAS 号搜索最可靠**，精确匹配或 not found，无假阳性
- **PubChem 名称搜索对修饰核苷酸覆盖差**，分词降级常返回母核（如 `Biotin-16-ddUTP` 命中 `dUTP`）
- **ChEMBL fallback 对修饰核苷酸覆盖更好**
- 「精确匹配」返回错误结果时 `fallback_used=false`，前端不会标黄——研究员需自行核验

---

## 9. 限制与注意事项

1. **权限对齐**：`ProductEnrichView` 用 `IsAdminUser`，工作台研究员（非 superuser）会被 401 拦截。建议改为 `IsStaffUser` 以与工作台定位一致。
2. **大文件未入 git**：BioProCorpus 的 7 个 JSON（共 ~540 MB）超 GitHub 限制，需在部署环境用 `scripts/download_bioprocorpus.py` 重新下载；代码实际只加载其中 3 个（~175 MB）。
3. **外部 API 可达性**：PubChem / ChEMBL / PubMed 在中国大陆延迟高（200-800ms+），生产建议加 Redis 缓存层或定时预热。
4. **协议推荐是纯关键词匹配**：非语义搜索，长尾或同义表述可能漏匹配。
5. **AI AUTO MATCH 只是建议**：所有回填均不强制、不覆盖，研究员是最终权威（遵循 CLAUDE.md 架构铁律）。

---

## 10. 关键文件索引

| 文件 | 作用 |
|------|------|
| `frontend/src/views/workspace/ProductEditPage.vue` | 前端面板 + `runPubchemEnrich` / `applyAllEnrichResults` |
| `frontend/src/api/aiTools.js` | `enrichProduct()` 等 API 封装 |
| `backend/apps/commerce/api/v1/ai_views.py` | `ProductEnrichView`（§267）一站式入口 |
| `backend/apps/commerce/services/validators/pubchem_enhancer.py` | PubChem + ChEMBL 化学属性 |
| `backend/apps/knowledge/services/literature_recommender.py` | PubMed 文献 + 知识链反向匹配 |
| `backend/apps/knowledge/services/pubmed_client.py` | NCBI E-utilities 4 策略搜索 |
| `backend/apps/knowledge/services/protocol_recommender.py` | BioProCorpus 协议检索 |
| `scripts/download_bioprocorpus.py` | 数据文件下载脚本 |

---

*文档日期：2026-06-25 | 基于代码实际实现，非设计稿*
