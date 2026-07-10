# 知识资产设计文档

> SciReagent 知识图谱体系 — 实体分类、关联关系、依赖、呈现、生成与校验机制
>
> 文档版本：2026-06-27　|　基于代码实际实现
>
> 核心链路（不可变）：`ResearchGoal → Application → Method → Protocol → Product → SKU`

---

## 1. 设计目的

SciReagent 是面向**生物化学领域**的科学试剂平台。当前首批产品线聚焦于**核苷酸与点击化学**，产品分类与知识体系正在逐步扩展中（抗体、酶、荧光染料、试剂盒等已在规划路线图，见 `KNOWLEDGE_ROADMAP.md`）。如果产品库只是一张「名称-CAS-价格」的表，那它和普通电商没有区别。**知识资产体系的存在，是为了把试剂从「可售物」升级为「可理解的科研实体」**，具体达成三件事：

1. **沉淀科研语义** — 把「为什么做（研究目标）→ 在哪用（应用场景）→ 怎么做（方法/协议）→ 用什么（产品）」这条科研认知链，固化成可检索、可追溯、可复用的数据资产，而非散落在研究员脑中和论文里的隐性知识。

2. **建立产品与知识的双向锚定** — 产品不再是孤立的 SKU，而是挂在知识图谱上的语义节点：一个产品「是某个方法的试剂」「被某篇文献支持」「与某产品兼容」。反之，知识实体也通过产品获得商业落地。

3. **提供统一数据底座** — 首页、产品详情、搜索、知识图谱可视化、AI 推荐工具，全部从同一套知识图谱读取，避免数据孤岛和多头维护。

一句话：**知识资产是平台的"大脑"，产品是"身体"，两者通过桥接表神经相连。**

---

## 2. 知识分类

知识资产分为三大类，分布在三个 Django app 中。

### A. 知识实体（`knowledge` app）— 描述"科研世界是什么、怎么做"

| 实体 | 角色 | 关键字段 | 状态模型 |
|------|------|---------|---------|
| **ResearchGoal** 研究目标 | 顶层科研意图 | name, slug, summary, priority | StatusMixin |
| **Application** 应用场景 | 按用途分组方法 | research_goal(FK), summary, display_priority | StatusMixin + FTS |
| **Method** 科研方法 | 工作流家族 | application(FK), purpose, advantages, limitations, cost_band, timeline | StatusMixin + FTS |
| **Protocol** 实验协议 | 版本化实验步骤 | method(FK), version, objective, materials, reagents, equipment, troubleshooting, expected_results | PublicationStatus + FTS |
| **ProtocolStep** 协议步骤 | 有序原子操作 | protocol(FK), step_no, title, body, duration_seconds, warnings | — |
| **Reference** 参考文献 | 规范化引用 | title, authors, journal, year, doi(unique), pmid(unique), source_type | FTS |
| **Compatibility** 兼容性规则 | 规则定义 | code(unique), scope, rule_type, severity, expression_json, summary | StatusMixin |

### B. 商业实体（`commerce` app）— 知识链末端的具体可售物

| 实体 | 角色 |
|------|------|
| **Product** 产品 | 知识链的商业终点，含 cas/smiles/formula/structure_svg 等化学属性 |
| **SKU** 库存单元 | 产品的可售规格（pack_size/price） |

### C. 桥接表（`bridges` app）— 给关系赋予语义

桥接表不是简单的多对多连接表，每张都携带**语义字段**，这是知识图谱"有质量"的关键：

| 桥接表 | 连接 | 语义字段 |
|--------|------|---------|
| **ProductMethod** | Product ↔ Method | `role`（reagent/buffer/control/enzyme/label/solvent）、`evidence_level`（low/medium/high/curated）、`display_order` |
| **MethodProtocol** | Method ↔ Protocol | `featured`、`status`、`display_order` |
| **ProductReference** | Product ↔ Reference | `citation_role`（primary/supporting/validation/background）、`display_order` |
| **ProductCompatibility** | Product ↔ Product + Compatibility 规则 | `verdict`（compatible/incompatible/conditional/warning）、`notes` |
| **ProductProduct** | Product ↔ Product | `relation_type`（substitute/complement/alternate/bundle/related）、`direction`（one_way/bidirectional）、`strength` |

> 例：同一个产品对同一个方法，可以是 `role=reagent, evidence_level=curated`（人工审核过的试剂用途），也可以是 `role=control`（对照用途）—— `unique_together = (product, method, role)` 允许多重语义共存。

---

## 3. 关联关系

### 3.1 核心链（纵向，1:N 父子链）

```
ResearchGoal ──1:N──▶ Application ──1:N──▶ Method ──1:N──▶ Protocol ──1:N──▶ ProtocolStep
   研究目标              应用场景           科研方法          实验协议           协议步骤
```

每级都是 `ForeignKey(on_delete=CASCADE)`，父删则子删。这是知识体系的"骨架"。

### 3.2 横向桥接（产品接入知识链）

```
                    ┌─── ProductMethod (role, evidence) ───┐
                    │                                       ▼
   Product ◄───────►│                                    Method
                    │                                       ▲
                    ├─── MethodProtocol (featured) ─────────┤
                    │                                       │
                    ├─── ProductReference (citation_role) ──► Reference
                    │
                    └─── ProductProduct (relation_type) ───► Product
                                  ProductCompatibility (verdict + Compatibility 规则)
```

### 3.3 关系基数与方向速查

| 关系 | 类型 | 方向 | 唯一性约束 |
|------|------|------|-----------|
| ResearchGoal → Application | 1:N | 单向 | — |
| Application → Method | 1:N | 单向 | — |
| Method → Protocol | 1:N | 单向 | — |
| Protocol → ProtocolStep | 1:N | 单向 | (protocol, step_no) |
| Product ↔ Method | M:N | 双向 | (product, method, role) |
| Method ↔ Protocol | M:N | 双向 | (method, protocol) |
| Product ↔ Reference | M:N | 双向 | (product, reference, citation_role) |
| Product ↔ Product | M:N | 可单向/双向 | (source, target, relation_type) |
| Product ↔ Product + Compatibility | M:N | 双向 | (source, target, compatibility) |

---

## 4. 依赖关系

### 4.1 写入顺序是硬约束

所有写入通道都必须遵守依赖顺序，**先父后子，先实体后桥接**：

```
① ResearchGoal  →  ② Application  →  ③ Method  →  ④ Protocol(+ProtocolStep)
                                                        ↓
                            ⑤ Product / SKU  ←─────────┘
                                  ↓
                   ⑥ 桥接表 (ProductMethod / MethodProtocol / ProductReference ...)
```

违反顺序（如先建 Method 再建其 Application）会导致外键解析失败。

### 4.2 ID 映射机制

JSON 导入时，源数据用字符串 ID 互相引用（如 `"method_id": "m_click"`）。编排器维护一个 `_id_map` 字典，在每级实体落库后，把字符串 ID 映射到数据库 PK，供下一级 FK 解析：

```python
_id_map = {
    'ResearchGoal': {'rg_rna': 1},      # JSON 字符串 ID → DB PK
    'Application':  {'app_fluor': 5},
    'Method':       {'m_click': 12},
    ...
}
```

### 4.3 幂等键（重复导入不报错、不重复）

| 实体/桥接 | 幂等键 | 机制 |
|-----------|--------|------|
| 所有知识实体 | `slug` | `update_or_create(slug=...)` |
| Protocol | `(method, slug, version)` | `unique_together` |
| ProtocolStep | `(protocol, step_no)` | `unique_together` |
| Reference | `doi` / `pmid` | 字段 `unique=True`（天然去重） |
| 所有桥接表 | 组合字段 | `unique_together` |

---

## 5. 呈现关系（知识如何被消费）

知识资产通过 5 个 API 场景呈现给用户，全部只读，全部带状态过滤。

### 5.1 首页（`site_home`）

`GET /api/v1/site/` 返回首页所有区域的复合数据：

| 区域 | 数据来源 | 过滤/排序 |
|------|---------|-----------|
| hero | 固定标题 + 建议搜索词 | — |
| stats | 聚合计数（products/skus/methods/protocols） | status 过滤 |
| categories | Product.category_l1 分组计数 | — |
| knowledge | RG/App/Method/Protocol 计数 | — |
| featured_* | 精选应用/方法/产品/方案 | `display_priority` 降序 |
| graph_preview | 知识图谱预览 | 调 `build_graph(depth=2)` |

> 结构图（structure_svg）在序列化时强制过 `sanitize_svg()` 防 XSS。

### 5.2 产品详情（`ProductDetailAPIView`）

`GET /api/v1/products/<id>/detail/` 一次聚合产品的全部知识上下文：

```
Product ──┬── applications  （经 ProductMethod → Method → 上溯 Application）
          ├── protocols     （经 ProductMethod → MethodProtocol → Protocol）
          ├── references    （经 ProductReference → Reference）
          ├── related       （经 ProductProduct）
          ├── faq           （faq_generator 运行时派生）
          └── compatibility （方法/协议/产品兼容性）
```

### 5.3 知识图谱（`graph_service.build_graph`）

`GET /api/v1/graph/?type=product&id=1&depth=3` — 从任一实体出发，BFS 遍历生成子图：

- 起点：product / application / method / protocol / reference
- 每层用 `NEIGHBOR_FETCHERS[type]` 取邻居（沿桥接表和 FK 双向走）
- 边带语义标签：`used_in / cited_in / belongs_to / has_protocol / used_by / part_of / has_method / cited_by / has_application`
- 输出 Cytoscape.js 格式 `{nodes:[{id,type,label,slug}], edges:[{source,target,relationship}]}`，前端懒加载渲染

### 5.4 搜索（双引擎）

| 端点 | 引擎 | 说明 |
|------|------|------|
| `/search/?q=` | icontains | 5 类实体并行模糊匹配，各 top 10 |
| `/search/grouped/?q=` | **PostgreSQL FTS** / SQLite icontains | 自动切换：PG 用 `SearchVectorField + GinIndex + SearchRank` 排序；SQLite 降级为加权 icontains |
| `/search/suggest/?q=` | icontains | 自动补全，Product top 5 + Method top 3 |

### 5.5 AI 工作台（`/workspace/`）

| 工具 | 端点 | 消费的知识资产 |
|------|------|--------------|
| Validate | `/products/<id>/validate/` | PubChem + BioProCorpus 交叉校验产品 |
| Recommend Protocols | `/products/<id>/recommend-protocols/` | BioProCorpus 协议检索 |
| Recommend Literature | `/products/<id>/recommend-literature/` | PubMed + 反向匹配知识实体 |
| AI AUTO MATCH | `/products/enrich/` | 三路聚合（化学属性 + 文献 + 协议） |

---

## 6. 生成机制（知识如何被创建）

共 6 条录入通道，分两类：**直接写库**（1-3）和 **AI 推荐待审**（4，不直接写库）。

### 6.1 Knowledge Intake（JSON 编排）

- **端点**：`POST /api/v1/knowledge-intake/`（`IsAdminUser`）
- **文件**：`apps/knowledge/api/v1/intake_views.py` + `core/json_importer.py`
- **输入**：`{research_goals[], applications[], methods[], protocols[], ...}`
- **机制**：按 `IMPORT_ORDER = [ResearchGoal, Application, Method, Protocol, Product, SKU]` 硬编码顺序写入，全程 `get_or_create` / `update_or_create` 幂等
- **前置**：`validate_graph_json()` 先跑校验，不通过则不写库

### 6.2 import_knowledge_graph 命令

- **命令**：`python manage.py import_knowledge_graph <file.json> [--dry-run]`
- **特点**：比 Intake 更重，额外处理 **ProtocolStep 创建**、**Bridge 表启发式关联**（中英文关键词推断 Product↔Method）、**Product 只填空字段**（不覆盖已有数据）

### 6.3 CSV 批量导入

- **文件**：`core/csv_importer.py`
- **范围**：仅 Product + SKU，不触及知识实体
- **机制**：列名规范化 + 别名映射 + `@transaction.atomic` + 按 catalog_no 分组

### 6.4 AI 推荐（不直接写库，落库需 admin 审批）

| 服务 | 数据源 | 输出 | 落库入口 |
|------|--------|------|---------|
| **LiteratureRecommender** | PubMed API | 文献 + 提取的应用/方法关键词 + `_match_against_db` 反向匹配已有 Application/Method | 人工关联 |
| **ProtocolRecommender** | BioProCorpus 本地语料库（14,675 条） | 匹配协议 + 试剂/设备/步骤富内容 | `/products/import-protocol/` |
| **DVR Agent** | FSM 神经符号推理 | 自动生成 5 步协议草案 + 三层校验报告 | 调用方负责 |
| **AI AUTO MATCH** | PubChem + ChEMBL + PubMed + BioProCorpus | 化学属性 + 知识链 + 协议预填 | admin 审核后落库 |

> **关键设计**：AI 推荐与落库严格解耦。所有 AI 服务只返回建议，绝不直接写库，避免幻觉数据污染知识图谱。

### 6.5 COA/SDS 自动生成（合规文档交付）

- **文件**：`apps/documents/` (COA/SDS models + services + views)
- **机制**：基于产品属性字段和知识资产的完整数据，通过 ReportLab PDF 库自动生成 COA 和 SDS PDF。
- **SDS 数据来源**：CAS → PubChem（高置信）→ PubChem/ChEMBL 按 SMILES/名称（中置信）→ 类别通用模板库（低置信）→ GENERIC_SAFETY_NOTES（极低置信兜底）。
- **COA 数据来源**：产品快照（冗余复制，保证历史不变）+ QC 实测值（人工录入）。
- **不存库**：PDF 文件存于服务器文件系统，路径记录在模型 `pdf_path` 字段。
- **SDS 版本控制**：通过 `Product.current_sds` FK 指针指定当前版本，消除 `isCurrent` 多行 true 的竞态。

> **关键设计**：COA/SDS 是数据完整性的下游交付物。SDS 的 GHS 数据质量取决于 PubChem 对目标化合物的覆盖与准确性（参见 `COA_SDS.md` 和 `AI_AUTO_MATCH.md` §9.1）。无 CAS 产品通过类别通用模板兜底保证合规底线，同时标注数据置信度。

### 6.6 faq_generator（运行时派生）

- **文件**：`apps/commerce/services/faq_service.py`
- **机制**：从产品关联的 Method → Application → Protocol 实体关系，用 8 个固定问题模板（用途/兼容方法/储存/协议/纯度/分子量/活细胞/体外转录）实时生成 FAQ
- **不存库**：每次请求动态生成，同时输出 schema.org FAQPage JSON-LD 给 SEO

### 6.7 seed_test_data（测试样例）

- **命令**：`python manage.py seed_test_data [--clear]`
- **机制**：9 步顺序写入完整样例（4 RG / 7 App / 8 Method / 8 Protocol / 10 Product / 16 SKU + 全套桥接）
- **标记**：所有 slug 以 `__test__` 开头，`--clear` 按依赖反序清理

---

## 7. 校验机制

分 5 层，纵深防御。

### 7.1 模型层（数据完整性）

- `unique_together`：桥接表组合唯一、Protocol(method,slug,version)、ProtocolStep(protocol,step_no)
- `SlugField(unique=True)`：实体 slug 全局唯一
- `MaxValueValidator`：ResearchGoal.priority ≤ 9999
- FK `on_delete=CASCADE`：保证引用完整性

### 7.2 Service 层（业务校验）

| 校验器 | 校验内容 |
|--------|---------|
| **ProductValidator** | 跨源校验产品：PubChem 查 CID → SMILES 正则化比较 → 标记 mismatch；BioProCorpus 交叉检索协议 |
| **ProtocolVerifier**（DVR Agent 内） | 三层：scientific（steps≥2）/ completeness（materials+safety 存在）/ safety（危险品表，如叠氮类必须出现在 safety 章节） |
| **validate_graph_json** | 导入前 JSON schema 校验 + 字段校验 + 交叉引用检查 |

### 7.3 Serializer 层（塑形 + 派生校验）

- 以读塑形为主（`Meta.fields` 显式声明，禁止 `__all__`）
- **派生校验示例**：`ProtocolDetailSerializer.get_references` 从 Protocol.references 文本正则抽取 DOI/PMID，反查 Reference 表动态桥接
- Brief serializers（`ApplicationBriefSerializer` 等）给详情页轻量聚合

### 7.4 View 层（权限 + 上传）

- `IsAdminOrReadOnly`：知识实体写操作仅 admin（superuser），读公开
- 文件上传：扩展名白名单（含 `.svg`）+ 10MB 限制，`_validate_uploaded_file()`

### 7.5 安全层（SVG 防注入）

`core/svg_sanitizer.py` 的 `sanitize_svg()` 三层清理：
1. 危险元素整段删除（script/iframe/embed/object/form...）
2. 危险属性过滤（on* 事件、javascript: 协议）
3. CDATA / XML 指令 / HTML 注释清理

**触发**：所有含 `structure_svg` 的 serializer 用 `SerializerMethodField + sanitize_svg()`。

### 7.6 状态机校验（贯穿读取路径）

两套状态机控制知识资产的可见性：

| 状态机 | 适用实体 | 状态值 |
|--------|---------|--------|
| `StatusMixin` | ResearchGoal / Application / Method / Compatibility | DRAFT / ACTIVE / DEPRECATED / ARCHIVED |
| `Protocol.PublicationStatus` | Protocol | DRAFT / PUBLISHED / SUPERSEDED / ARCHIVED（+ published_at / superseded_at 版本生命周期） |

**所有公开读取路径都带状态过滤**：首页只展示 `active` 应用/方法、`published` 协议；详情页、图谱遍历同理。

---

## 8. 关键架构原则

1. **依赖顺序是硬约束** — 所有写入通道都遵循 `RG→App→Method→Protocol→Bridge`，用 `_id_map` 做 ID 解析。
2. **幂等设计** — `update_or_create(slug=...)` / `get_or_create` 贯穿所有通道，重复导入不报错、不重复。
3. **AI 推荐与落库解耦** — LiteratureRecommender / ProtocolRecommender / DVR Agent 都不直接写库，只返回建议；落库由 admin 入口负责，避免幻觉污染。
4. **双搜索引擎** — search_grouped 自动按 DB 切换：PostgreSQL 用 FTS + SearchRank，SQLite 降级为加权 icontains。
5. **校验分层** — 模型 → Service → Serializer → View → 安全，五层纵深。
6. **状态机双套** — 通用 StatusMixin + Protocol 专用 PublicationStatus（带版本生命周期），控制知识资产可见性。
7. **expression_json 设计预留** — Compatibility 模型有 JSON 规则字段（如 `{"min_purity":95, "temp_range":[-20,4]}`），但代码库中尚未实现运行时规则引擎消费它，目前是存储 + 直读，为未来规则引擎预留接入点。

---

## 附：关键文件索引

| 层 | 文件 | 作用 |
|----|------|------|
| 模型 | `apps/knowledge/models.py` | 7 个知识实体 |
| 模型 | `apps/bridges/models.py` | 5 张语义桥接表 |
| 生成 | `core/json_importer.py` | JSON 导入编排内核 |
| 生成 | `apps/knowledge/management/commands/import_knowledge_graph.py` | 命令行导入（含 Bridge + 只填空） |
| 生成 | `core/csv_importer.py` | CSV 批量导入 |
| 生成 | `apps/knowledge/services/protocol_recommender.py` | BioProCorpus 协议推荐 |
| 生成 | `apps/knowledge/services/literature_recommender.py` | PubMed 文献 + 反向匹配 |
| 生成 | `apps/knowledge/services/dvr_agent.py` | DVR 协议自动生成 Agent |
| 生成 | `apps/commerce/services/faq_service.py` | FAQ 动态派生 |
| 校验 | `apps/commerce/services/validators/product_validator.py` | ProductValidator 跨源校验 |
| 校验 | `core/json_validator.py` | 导入前 JSON 校验 |
| 校验 | `core/svg_sanitizer.py` | SVG 防 XSS |
| 呈现 | `apps/knowledge/api/v1/site_views.py` | 首页 5 区域 |
| 呈现 | `apps/commerce/api/v1/views.py` | 产品详情聚合 |
| 呈现 | `apps/knowledge/services/graph_service.py` | 知识图谱 BFS |
| 呈现 | `apps/knowledge/api/v1/search_grouped_views.py` | 双引擎搜索 |

---

*文档日期：2026-06-27 | 基于代码实际实现，非设计稿*
