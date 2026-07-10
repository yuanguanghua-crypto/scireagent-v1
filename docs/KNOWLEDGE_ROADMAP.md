# 知识资产演进路线图（Roadmap）

> 本文件是知识资产体系的**演进 backlog**，记录已识别但**尚未实施**的改造方向。
>
> 与 `KNOWLEDGE_ASSETS.md`（描述"现在是什么"的权威基线）配合使用：
> - 本文件 = "应该有什么"（待落地）
> - 主文档 = "现在有什么"（已落地）
>
> **工作流**：从本文件挑一条 → 讨论方案 → 实施验证 → 完成后把该条移入主文档。
>
> 文档版本：2026-06-27　|　基于 2026-06-27 架构评审

---

## 优先级约定

| 级别 | 含义 | 触发条件 |
|------|------|---------|
| **P0** | 架构级改造，阻塞下一产品线扩展 | 抗体/酶/染料进来前必须解决 |
| **P1** | 重要补强，影响数据质量与可用性 | 可在迭代中择机实施 |
| **P2** | 优化项，改善体验/性能 | 资源允许时做 |

---

## 第一部分：业务与知识建模（生物科学视角）

> 当前链 `ResearchGoal→Application→Method→Protocol→Product` 是**方法论导向**（怎么做实验）。对化学生物学试剂是合理起点，但扩展到更广的生物化学领域时有结构性缺口。

### 🔴 P0

#### [BIO-P0-1] 引入"生物学语义"维度（疾病 / 生物过程 / 靶点 / 通路）
- **问题**：生物试剂的核心价值不是"怎么用"，而是"在生物体系中影响/标记了什么"。例如 5-Ethynyl-dUTP(EdU) 当前只能挂在"Click Chemistry→Cell Labeling"方法下，但**"细胞增殖"这个生物学过程没有实体承载**，只藏在 Application 名字字符串里。
- **影响**：无法回答"研究癌症/感染/神经退行时能用哪些试剂"这类转化导向的高价值问题；首页/搜索无法按生物学场景导航。
- **方向**：补一条平行于方法论链的生物学链：
  ```
  Disease / BiologyProcess（疾病/生物过程，如 Cell Proliferation）
        ↓ acts_on
  Target / Pathway（靶点/通路，如 DNA Replication）
        ↓
  （现有）Method → Protocol → Product
  ```
- **待决策**：新增 2-3 个实体 vs 用现有 Application 的扩展字段承载。

#### [BIO-P0-2] Product 模型支持生物试剂子类型
- **问题**：当前 Product 偏"小分子化学试剂"（cas/smiles/formula/molecular_weight）。扩展到 **抗体**（克隆号、宿主物种、IHC/IF/WB 验证、效价）、**酶**（活性单位 U/mL、比活、单位定义）、**荧光染料**（Ex/Em 波长、消光系数、量子产率）、**试剂盒/细胞系**时，要么加一堆 nullable 字段污染模型，要么无法承载。
- **影响**：每加一条产品线就要改 Product 表，且不同试剂类型的特有属性无处安放。
- **方向**：引入 `product_type` 分类 + 类型化扩展机制（JSON 属性包 / 子模型表 / EAV）。核苷酸/点击化学为 type=chemical，预留 antibody/enzyme/dye/kit。
- **待决策**：JSON 扩展字段（灵活但弱约束）vs 子模型表（强约束但表多）。

### 🟡 P1

#### [BIO-P1-1] Protocol 增加结构化"输入样本 → 输出产物"
- **问题**：Protocol 的输入（起始样本：细胞系/组织/DNA 模板/浓度）和输出（预期产物：标记产物/文库/产率）目前散在 objective/expected_results 文本里。
- **影响**：实验复现最关键的信息不可结构化查询；无法做"给定输入样本→推荐协议"的反向检索。
- **方向**：Protocol 增加 `inputs`(JSON/结构化) 和 `outputs` 字段，或建 ProtocolIO 关联表。

#### [BIO-P1-2] 协议步骤与具体产品/SKU 的结构化关联
- **问题**：ProtocolStep.required_materials 是纯文本，**无法从某一步反查用到哪个 Product/SKU**。
- **影响**：无法根据协议自动生成采购清单、算成本、查库存——这三个是试剂平台的高价值功能。
- **方向**：建 `ProtocolStepProduct` 桥接表（step × product × quantity × role）。

#### [BIO-P1-3] 知识关联的证据溯源
- **问题**：`ProductMethod.evidence_level = curated` 只是个枚举，不记录**是谁、何时、基于哪篇 Reference**审核的。知识图谱的"可信度"断了。
- **影响**：知识资产无法追溯来源，长期可信度衰减。
- **方向**：桥接表增加 `curated_by / source_reference(FK→Reference) / reviewed_at` 字段。

#### [BIO-P1-4] 兼容性扩展到方法级（method-method）
- **问题**：Compatibility.scope 只覆盖 product-product/product-method/product-protocol，没有 method-method（方法能否串联成工作流，如"先 click 反应→再荧光检测"）。
- **方向**：scope 增加 `method-method`，表达工作流编排约束。

### 🟢 P2

#### [BIO-P2-1] Reference 结构化"实验结论"
- **问题**：Reference 只存元数据（标题/作者/DOI），缺"这篇文献用该产品做了什么实验、得到什么结论"的结构化关联。
- **方向**：ProductReference 增加 `finding_summary / experiment_context` 字段。

#### [BIO-P2-2] 疾病/应用领域顶层分类
- **问题**：ResearchGoal 是"研究方向"，无疾病维度（该试剂用于癌症/感染病检测等）。
- **方向**：与 [BIO-P0-1] 合并设计时一并考虑。

---

## 第二部分：数据结构与技术实现

### 🔴 P0

#### [TECH-P0-1] Compatibility 规则引擎落地或移除
- **问题**：`Compatibility.expression_json` 存了规则 JSON（如 `{"min_purity":95, "temp_range":[-20,4]}`），但**全代码库没有任何引擎消费它**；`ProductCompatibility` 表 0 条数据，功能未落地。
- **影响**：已建未用的技术债，模型字段误导（看起来支持规则引擎，实际不工作）。
- **方向**：二选一——(a) 实现运行时规则引擎（解析 expression_json 执行判定）；(b) 若短期不做，先从模型移除或标记为 reserved。

#### [TECH-P0-2] Protocol.references 文本字段 → 结构化桥接表
- **问题**：Protocol 有 `references = TextField`（PMID/DOI 文本），Serializer 用正则反查 Reference 表。脆弱：文本易错、无法关联引用角色、无法做元数据 join。
- **影响**：文献与协议的关联不可靠。（之前评估时决定不做，但仍是数据完整性弱点，建议重新评估。）
- **方向**：建 `ProtocolReference` 桥接表（类似 ProductReference，带 citation_role）。

#### [TECH-P0-3] SDS 数据获取解耦 CAS 硬依赖
- **问题**：`generate_sds()` 在 `workflow.py:123` 硬约束 `if not cas: raise ValueError('产品没有 CAS 号，无法生成 SDS')`。无 CAS 产品（未注册 CAS 的修饰核苷酸偶联物、酶、混合物等）当前无法生成任何 SDS，直接违背试剂采购硬性要求。
- **影响**：随着产品线扩展到抗体/酶/染料，无 CAS 产品比例可能超过 50%，SDS 生成能力直接决定能否上线销售。
- **方向**：实现三级降级链：
  1. CAS → PubChem（现有高置信路径，保留）
  2. SMILES / InChI / 产品名 → PubChem/ChEMBL（中置信，标注偏差风险）
  3. category_path → 类别通用 SDS 模板库（低置信）
  4. GENERIC_SAFETY_NOTES 通用兜底（极低置信）
- **子任务**：重构 `generate_sds()` 拆除 CAS 硬约束；建 `category_sds_templates.py`；SdsRevision 增加 `data_confidence` + `data_source_detail` 字段；SDS PDF 增加数据来源标注栏。

### 🟡 P1

#### [TECH-P1-1] 字段语义去重（Protocol vs ProtocolStep）
- **问题**：Protocol 有 `reagents/materials/equipment`（总览级 TextField），ProtocolStep 有 `required_materials`（步骤级 TextField），关系不清，容易不一致。
- **方向**：明确职责——Protocol 级做摘要、步骤级为权威；或统一到一处。与 [BIO-P1-2] 联动设计。

#### [TECH-P1-2] 软删除 + 审计追溯
- **问题**：全部 `on_delete=CASCADE` 硬删，误删无法恢复；`TimeStampedModel` 只有 created/modified，**无 who、无变更历史**。对"可信知识库"是硬伤。
- **方向**：引入 soft delete（is_deleted / deleted_at）+ 审计表或 django-simple-history 记录变更。

#### [TECH-P1-3] AI 推荐缓存层
- **问题**：PubChem / PubMed / BioProCorpus 反复调用，无缓存。`documents` app 的 `PubChemCache` 是个好开始，但 `enrich/validate/recommend` 三个 AI 端点都还没接入。
- **影响**：生产环境（尤其阿里云，外部 API 延迟 200-800ms+）性能差、被限速。
- **方向**：统一 Redis 缓存层，复用 PubChemCache 模式扩展到 PubMed/BioProCorpus。

### 🟢 P2

| ID | 问题 | 方向 |
|----|------|------|
| [TECH-P2-1] | structure_svg 存 DB | 迁移到对象存储/文件系统；缓存 sanitize 结果 |
| [TECH-P2-2] | search_vector SQLite 不可用 | 已知；开发降级 icontains，生产用 PG FTS。文档化即可 |
| [TECH-P2-3] | slug 全局 unique 冲突 | 改 (entity_type, slug) 组合唯一，或加 scope 前缀，适应多产品线 |
| [TECH-P2-4] | 图谱 BFS 无环/方向语义 | related_name 区分正反关系；显式环检测（当前靠 max_nodes 兜底） |
| [TECH-P2-5] | cost_band/timeline 无数据支撑 | 人工填的枚举缺验证数据；考虑接入实际报价/工时数据 |
| [TECH-P2-6] | 无多语言 | 全英文但部署面向中国用户；预留 i18n 字段 |
| [TECH-P2-7] | AI AUTO MATCH 无供应商数据源 | 爬虫获取的供应商数据（如 jena CAS/formula/应用）可作为第五数据源，与 PubChem/ChEMBL 交叉比对预填；但供应商无 CAS 的产品仍需类别模板兜底（参见 `COA_SDS.md` §8.5） |
| [TECH-P2-8] | PubChem 命中母体无自动警告 | AI AUTO MATCH 和 SDS 应利用 MW/精确质量交叉验证：候选 MW 与数据库已知值差异 > 阈值 → 标红警告。（参见 `AI_AUTO_MATCH.md` §9.1 和 `COA_SDS.md` §6.2） |

---

## 建议的实施顺序

1. **先做 P0 的讨论与设计**（不急于实施）：
   - [BIO-P0-1] + [BIO-P0-2] 是耦合的（生物学维度 + 产品子类型），建议**一起设计**——它们决定了知识图谱扩展到抗体/酶时的骨架。
   - [TECH-P0-1] + [TECH-P0-2] 可独立快速决策（实现 or 移除）。
   - **[TECH-P0-3] SDS 解耦 CAS** 是当前最紧迫的 P0 技术债——无 CAS 产品无法生成 SDS，直接阻碍产品上线。
2. **P1 跟随产品线扩展节奏**：[BIO-P1-2]（步骤-产品关联）和 [TECH-P1-1]（字段去重）联动，在第一个非化学试剂产品线进来前解决。
3. **P2 择机优化**。

---

*路线图日期：2026-06-27 | 完成的条目请移入 `KNOWLEDGE_ASSETS.md` 主文档*
