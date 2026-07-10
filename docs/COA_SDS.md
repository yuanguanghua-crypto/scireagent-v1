# COA / SDS 文档自动生成功能技术文档

> 试剂合规文档 — 分析证书（COA）与安全数据表（SDS）自动生成
>
> 文档版本：2026-06-27 | 基于代码实际实现，非设计稿

---

## 1. 功能概述

COA（分析证书）与 SDS（安全数据表）是试剂行业采购的**硬性合规要求**。每批产品必须附带这两份文档，采购人员据此判断产品是否适合实验用途、实验室能否安全处置。

SciReAgent 平台的目标是：**研究员完成产品信息录入 + AI AUTO MATCH 预填后，审核确认即可一键生成 COA 和 SDS PDF**，无需人工排版或逐字录入安全数据。

---

## 2. 系统定位与数据依赖

### 2.1 在整体链路中的位置

```
数据源层（PubChem / ChEMBL / PubMed / BioProCorpus / 供应商爬虫）
        │
        ▼
AI AUTO MATCH 预填 ──► 产品属性字段 + 知识资产
        │
        ▼
研究员审核确认（唯一质量闸门，最终权威）
        │
        ▼
前端呈现（访问者/采购人员 阅读、下载）
        │
        ▼
COA / SDS 自动生成（基于完整数据 + 模板）
```

**COA/SDS 的输出质量完全取决于上游数据完整性。** 产品属性字段和知识资产的完整性（AI AUTO MATCH 预填 + 手动补充 + 审核确认）是 COA/SDS 能自动化生成的前提条件。

> 详见：`AI_AUTO_MATCH.md`（功能 §1-3）和 `KNOWLEDGE_ASSETS.md`（生成机制 §6.4、校验机制 §7）

### 2.2 两份文档的数据依赖差异

| 文档 | 数据来源 | 外部 API 依赖 | 人工干预点 |
|------|----------|:---:|------|
| **COA** | 产品快照（create 时复制 Product）+ QC 实测值（人工录入） | 无 | QC 录入 + 审批签署 |
| **SDS** | PubChem（CAS → GHS 分类 + 属性 + 16节数据）+ 类别通用安全模板兜底 | ⚠️ 有 | PubChem 不可用时选类别模板 + 审批 |

**核心差异**：COA 不依赖任何外部 API，数据可控；SDS 的 GHS 数据硬依赖 PubChem，当前是最大脆弱点（见 §6.2）。

---

## 3. 数据模型（`documents/models.py`）

4 张表，全部在 `apps/documents` app 中。

### 3.1 Batch（批次）

| 字段 | 类型 | 说明 |
|------|------|------|
| sku | FK → SKU | 哪个 SKU 的批次 |
| lot_number | CharField(50, unique) | 批次号，如 `SC8001-L2026001` |
| produced_at | DateField | 生产日期 |
| retest_at | DateField(null) | 复检日期 |

### 3.2 Coa（分析证书）

| 字段 | 类型 | 说明 |
|------|------|------|
| batch | OneToOne → Batch | 一批一 COA |
| doc_id | CharField(50, unique) | 文档编号，如 `COA-SC8001-2026-001` |
| status | DRAFT / APPROVED / PUBLISHED | 状态机 |
| product_name / catalog_number / cas_number / molecular_formula / molecular_weight / storage_condition | CharField | **产品快照**（冗余，保证历史 COA 不变脸） |
| appearance_spec / purity_spec / water_content_spec | CharField | **产品级 spec 标准**（从 Product 复制） |
| appearance_result / purity_result / purity_method / water_content_result / melting_point / specific_rotation / residual_solvents / heavy_metals | CharField | **批次实测值**（人工录入） |
| nmr_result / lcms_result | TextField / CharField | 色谱结果 |
| hplc_conditions / lcms_conditions | TextField | 色谱条件 |
| qc_analyst / qa_approval / approved_at | CharField / DateTimeField | 签署信息 |
| pdf_path | CharField(500) | PDF 存储路径 |

### 3.3 SdsRevision（SDS 修订版）

| 字段 | 类型 | 说明 |
|------|------|------|
| product | FK → Product | 哪个产品的 SDS |
| revision_no | IntegerField | 修订版本号 |
| revised_at | DateField | 修订日期 |
| signal_word | CharField(20) | GHS 信号词：Warning 或 Danger |
| pictograms / hazard_codes / precaution_codes | TextField(JSON) | GHS 象形图 / 危险代码 / 防范代码 |
| section_data | TextField(JSON) | **完整 16 节 SDS 数据**（JSON 字符串） |
| pdf_path | CharField(500) | PDF 存储路径 |

版本控制：SDS 通过 `Product.current_sds` FK 指针指定当前版本，消除 `isCurrent` 多行 true 的竞态。

### 3.4 PubChemCache（PubChem 数据缓存）

| 字段 | 类型 | 说明 |
|------|------|------|
| cas_number | CharField(20, db_index) | CAS 号 |
| cid | IntegerField(null) | PubChem CID |
| data_json | TextField | 完整 PubChem 返回数据 |
| fetched_at | DateTimeField | 获取时间 |

---

## 4. COA 工作流

### 4.1 三步流程

```
create_coa(SKU→Batch + Coa draft)
    │   ① 从 Product 复制快照（name/cas/formula/mw/storage）
    │   ② 从 Product.purity 复制 spec 标准
    │   ③ 生成 doc_id = COA-{catalog_no}-{year}-{seq}
    ▼
update_coa_qc_results(coa_id, qc_data)
    │   人工录入批次实测值（appearance/purity/water/melting_point...）
    ▼
approve_coa(coa_id, qc_analyst, qa_approval)
        审批 + 生成 PDF + 保存路径
```

### 4.2 关键设计：产品快照冗余

`create_coa` 时从 Product **复制** name/cas/formula/mw/storage/purity 到 Coa 快照字段。**不实时 FK 引用 Product**。

**为什么**：产品后续改名改规格，历史 COA 不变。合规文档必须锁定签发时的产品状态，这是行业的硬性要求。

### 4.3 QC spec vs result 分离

- **spec**（标准）：从 Product 复制，同批次所有 COA 共享同一标准
- **result**（实测）：人工录入，每批次独立
- PDF 表格据此自动判 PASS/FAIL

---

## 5. SDS 工作流

### 5.1 两步流程

```
generate_sds(product_id)
    │   ① 查 PubChemCache（CAS → CID → GHS + 属性 + 16节）
    │   ② 未命中则调 PubChem API → 写缓存
    │   ③ 无法获取时 → 按产品类别(category_path)匹配类别通用 SDS 模板库
    │   ④ 创建 SdsRevision(draft) + section_data
    ▼
approve_sds(revision_id)
        生成 PDF + 设为 Product.current_sds
```

### 5.2 数据来源层级（三级降级链）

SDS 数据按产品拥有的标识符降级获取，**完全解耦对 CAS 的硬依赖**：

```
优先级 1：产品有 CAS → PubChem CAS 查询
         （GHS 分类来自真实 CID，高置信）
          ↓ CAS 未知/无法获取
优先级 2：产品有 SMILES / InChI / 产品名 → PubChem 按对应 namespace 查询
         （GHS 可能为母体数据，中置信，标注可能存在偏差）
          ↓ 上述均不可用
优先级 3：按 category_path 匹配类别通用 SDS 模板库
         （基于产品类别预置典型 GHS 数据，低置信）
          ↓ 类别也无匹配
兜底：    GENERIC_SAFETY_NOTES 通用补充模板
         （section 4/5/6/13/15/16 基础安全说明，极低置信，标注"基于同类化合物通用数据"）
```

[**优化**] 当前代码仅实现了优先级 1（CAS→PubChem），硬约束 `if not cas: raise ValueError`。优先级 2/3 的解耦逻辑待实施。见 §8.1。

### 5.3 数据来源与置信度标注

每份 SDS 在生成时应记录数据来源等级，供采购人员和研究员评估可信度：

| 等级 | 来源 | 标注 |
|------|------|------|
| **高** | CAS → PubChem CID 精确命中 | 「数据来源于 PubChem CID xxx（CAS xxx）」 |
| **中** | SMILES/名称命中 PubChem/ChEMBL | 「数据来源于 PubChem/ChEMBL，可能为该化合物母体数据，请核实」 |
| **低** | 类别通用模板 | 「基于 {产品类别} 通用安全数据，非该具体化合物注册数据」 |
| **极低** | GENERIC_SAFETY_NOTES 兜底 | 「通用安全补充说明，需人工补充具体化合物安全信息」 |

---

## 6. 已知问题与脆弱点

### 6.1 SDS 的 CAS 依赖（S0 致命缺陷）

`generate_sds` 在 `services/workflow.py:123` 硬约束：**无 CAS 直接 Raise ValueError**。

**影响**：无 CAS 产品（未注册 CAS 的修饰核苷酸偶联物、酶、混合物等）当前无法生成任何 SDS，直接违背"试剂必须出 SDS"的采购硬性要求。

[**优化**] 解决方向：解耦 CAS 硬依赖，按 §5.2 三级降级链实现。优先级为当前最高。

### 6.2 PubChem 对修饰核苷酸的覆盖率与准确性

`PubChemCache` + `PubChemEnhancer` 的实测结果（`ai-auto-match-test-results.md`，27 个产品）：

| 指标 | 数据 |
|------|------|
| 名称搜索准确率 | ~60-70%，分词降级频繁命中母核 |
| 命中母体典型案例 | Biotin-16-ddUTP → dUTP（MW 差 ~300 Da） |
| 精确搜索无警告 | `fallback_used=false` 不代表命中正确 |
| ChEMBL fallback | 对修饰核苷酸偶联物覆盖反而优于 PubChem |

**影响**：即使有 CAS，PubChem 返回的 GHS 数据也可能是错误母体的安全分类，导致 SDS 安全信息不准确。

### 6.3 无 CAS 产品的比例上限

当前 Product 模型 `cas` 字段可 blank。估算（基于 Jena 数据）：核苷酸偶联物、酶、抗体、试剂盒等大概率无 CAS。随着产品线扩展，无 CAS 产品的比例可能超过 50%。

---

## 7. API 端点

### 7.1 COA

| 方法 | 端点 | 视图 | 说明 |
|------|------|------|------|
| POST | `/api/v1/coas/create-coa/` | `create_coa` | SKU → Batch + Coa draft |
| PUT | `/api/v1/coas/{id}/qc-results/` | `update_coa_qc_results` | 更新 QC 实测值 |
| POST | `/api/v1/coas/{id}/approve/` | `approve_coa` | 审批 + 生成 PDF |
| GET | `/api/v1/coas/{id}/download/` | — | 下载 PDF |

### 7.2 SDS

| 方法 | 端点 | 视图 | 说明 |
|------|------|------|------|
| POST | `/api/v1/sds-revisions/generate/` | `generate_sds` | CAS → PubChem → SdsRevision |
| POST | `/api/v1/sds-revisions/{id}/approve/` | `approve_sds` | 审批 + PDF + current_sds |
| GET | `/api/v1/sds-revisions/{id}/download/` | — | 下载 PDF |

### 7.3 数据管理

| 方法 | 端点 | 说明 |
|------|------|------|
| CRUD | `/api/v1/batches/` | Batch 管理 |
| CRUD | `/api/v1/coas/` | COA 管理 |
| CRUD | `/api/v1/sds-revisions/` | SDS 管理 |
| CRUD | `/api/v1/pubchem-cache/` | PubChem 缓存管理 |

---

## 8. 优化待办清单

[所有 [优化] 条目迁移至 `KNOWLEDGE_ROADMAP.md` 统一管理，完成时移入 `KNOWLEDGE_ASSETS.md`]

### 8.1 SDS 数据获取解耦 CAS（P0）

当前 `generate_sds` 硬依赖 `CAS → PubChem`。需实现三级降级链（§5.2）：

1. **CAS → PubChem**（现有高置信路径，保留）
2. **SMILES / InChI / 产品名 → PubChem/ChEMBL**（中置信，需标注偏差）
3. **category_path → 类别通用 SDS 模板库**（低置信，需建立模板库）

**子任务**：
- 重构 `generate_sds()` 拆除 CAS 硬约束（`workflow.py:123` → 改为可选项）
- 实现 `_fetch_sds_data_by_category(category_path)` 方法（§5.2 三级）
- 建立 `backend/apps/documents/services/category_sds_templates.py`（类别模板库，初始覆盖产品线：Nucleotides & Nucleosides、Click Chemistry、Molecular Biology、Crystallography & Cryo-EM、Proteins、LEXSY Expression、RNA Technologies、Probes & Epigenetics）
- 在 `SdsRevision` 模型增加 `data_confidence` 字段（高/中/低/极低）和 `data_source_detail`（CID / 类别模板名等）
- SDS PDF 模板增加数据来源标注栏

[迁移至 KNOWLEDGE_ROADMAP.md 条目编号：TBD]

### 8.2 类别通用 SDS 模板库（P1，依赖 8.1）

按产品线预置典型 GHS 分类、危险性陈述、建议措施、储存/处置/灭火信息。模板结构需对齐 SDS 16 节格式。

**子任务**：
- 定义模板 schema（16 节中每节的置信度分级）
- 初始模板覆盖当前 8 条产品线（基于 Jena 数据 + 行业通用知识）
- 研究员可在工作台编辑模板（非只读），修改后标注"自定义"

[迁移至 KNOWLEDGE_ROADMAP.md]

### 8.3 SDS PDF 数据来源标注（P1，依赖 8.1）

SDS PDF 需在显著位置标明数据来源等级，让采购人员一目了然：
- "数据来源于 PubChem CID xxx（CAS xxx）"— 高置信
- "数据来源于 PubChem 名称匹配，可能为该化合物母体数据"— 中置信
- "基于 {类别} 通用安全数据，非该具体化合物注册数据"— 低置信

[迁移至 KNOWLEDGE_ROADMAP.md]

### 8.4 无 CAS 产品标注（P1）

在 Product 模型增加 `cas_not_applicable` BooleanField，标志"该产品本身无 CAS 注册"。

**用途**：区别「缺数据」和「天然不适用」。产品完整度评估不再将"无 CAS"误判为数据缺失。

[迁移至 KNOWLEDGE_ROADMAP.md]

### 8.5 AI AUTO MATCH 反向纳入供应商数据（P2）

如果供应商爬虫（如 jena）能提供 CAS，则作为 AI AUTO MATCH 的**第五数据源**，在产品预填阶段与 PubChem/ChEMBL 交叉比对。

**约束**：jena 数据仅用于核验和预填，不替代 PubChem 作为 SDS 数据源（SDS 仍须 PubChem 或模板库）。

[迁移至 KNOWLEDGE_ROADMAP.md]

### 8.6 PubChem 数据准确性增强（P2）

- 在 AI AUTO MATCH 和 SDS 生成中利用 MW/精确质量做**交叉验证**：PubChem 返回候选 → 拿候选 MW 比对数据库已知值 → 差异 > 阈值 → 标红警告
- 解决"精确搜索返回错误结果时无警告"的已知缺口

[迁移至 KNOWLEDGE_ROADMAP.md]

---

## 9. 依赖关系

### 9.1 与 AI AUTO MATCH

COA/SDS 的数据基础来自产品属性字段和知识资产，而这些数据的最主要填充方式是 AI AUTO MATCH。

- PubChem 数据 → 产品 `cas/smiles/formula/molecular_weight` + SDS 的 GHS 数据
- PubMed Literature → 知识链（Application/Method/Reference）
- BioProCorpus → Protocol 关联

> 详见：`AI_AUTO_MATCH.md` §1-5

### 9.2 与知识资产体系

COA/SDS 的 PDF 生成依赖产品已关联的知识实体：
- COA 的纯度/外观 spec 可源自 Product 关联的 Method
- SDS 的危险性描述可参考 Protocol 中的 safety 章节

> 详见：`KNOWLEDGE_ASSETS.md` §5（呈现关系）和 §6（生成机制）

---

## 10. 关键文件索引

| 层 | 文件 | 作用 |
|------|------|------|
| 模型 | `apps/documents/models.py` | Batch / Coa / SdsRevision / PubChemCache |
| 服务 | `apps/documents/services/workflow.py` | COA/SDS 工作流编排 |
| 服务 | `apps/documents/services/coa_generator.py` | COA PDF 生成（ReportLab） |
| 服务 | `apps/documents/services/sds_generator.py` | SDS PDF 生成（ReportLab，16 节） |
| 服务 | `apps/documents/services/pubchem_fetcher.py` | CAS → PubChem 数据获取 + 缓存 |
| API | `apps/documents/api/v1/views.py` | ViewSet + 自定义工作流端点 |
| API | `apps/documents/api/v1/serializers.py` | 6 个 Serializer |
| API | `apps/documents/api/v1/urls.py` | URL 路由 |
| 前端 | `frontend/public/coa-preview.html` | COA PDF 预览 |
| 前端 | `frontend/public/sds-preview.html` | SDS PDF 预览 |
| 前端 | `论文工作台集成` | TODO：Batch/COA/SDS 管理 UI（待前端集成） |

---

## 附：设计原则

1. **合规底线**：COA 和 SDS 是试剂采购的硬性要求，不能生成 = 无法销售。无 CAS 产品的 SDS 必须有兜底方案。
2. **数据溯源**：COA 产品快照冗余、SDS 数据来源标注，确保合规文档可追溯、可审计。
3. **研究员是最终权威**：AI AUTO MATCH 预填 / SDS 模板生成都是建议，研究员审核确认后才发布。
4. **降级兜底**：数据源不可靠或缺失时，优先保证文档可生成（类别模板兜底），其次保证数据标注诚实（置信度分级）。

---

*文档日期：2026-06-27 | 基于代码实际实现，非设计稿*