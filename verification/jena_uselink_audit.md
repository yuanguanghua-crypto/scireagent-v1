# Jena 数据源 · AI Auto Match 使用链路审计报告

> 阶段：第三步「验使用链路」（前两步：① jena 数据可信度测绘 ② 身份字段数据准确性审计）
> 原则：先确认实际用了 jena 哪些数据 → 已确保其真实准确（身份字段 91% 干净）→ 现验「使用方式 / 使用链路」是否准确。
> 方法：只读。复刻生产 `jena_index.find_by_name`（源码 174-187 行，逐字一致）加载真实 `jena_products_v2.jsonl`，量化双向子串匹配歧义。
> 未改动任何数据 / 代码。

---

## 一、核心结论（先给答案）

**链条「半有效」：**
- ✅ **当平台录入名 = jena 中存在的精确完整名**（如 `ATPγS`、`dATP - Solution`）→ `find_by_name` exact 优先 → 精准，bioz 锚点正确。
- ❌ **当平台录入名是通用名 / 子串**（如 `ATP`、`dATP`、`UTP`、`Buffer`、`Salt`）→ 无精确命中，partial 按**文件顺序取首条**（非最相似）→ **高概率错配**，且 `match_key` 不区分「精确 / 子串」，view 层无分流闸门 → 错误结果直接进匹配草案 + bioz 证据链。

**这恰好印证你的方法论：** 数据本身干净（91%）是「必要非充分条件」；即便身份字段修干净了，**匹配算法（双向子串 + 取首条）本身仍会在通用名查询时错配**。数据与算法两层必须同时成立，链条才精准。

---

## 二、实测证据（真实数据，非推测）

### 2.1 歧义率 43%
遍历全部 2098 条，用「自身产品名」回查 `find_by_name`：
- **908 条（43%）返回 >1 候选** —— 即近一半 jena 产品的名字会被其他产品作为子串命中。
- 例：`GTPγS` 同时被 `Mant-GTPγS` / `dGTPγS` / `EDA-GTPγS-ATTO-540Q` 命中；`ATPγS` 被 `N6-Benzyl-ATPγS` / `Mant-ATPγS` 等命中。
- 反向含义：任何「比产品全名更短」的查询，在这 908 条里极易落入歧义区。

### 2.2 子串错配实锤（matcher 实际取首条 limit=1）
| 平台录入名 | matcher 返回（错配） | 风险 |
|---|---|---|
| `ATP` | `2'MeSe-ATP` (NU-928) | 用户要 ATP，给到硒代衍生物 |
| `dATP` | `dATPγS` (NU-265) | 硫代类似物，生化性质不同 |
| `UTP` | `5-AcOHg-dUTP` (UTPNU-910) | **汞代衍生物**，高危 |
| `Salt` | `GppNHp - Sodium salt` (NU-1048) | 完全无关产品 |
| `EDTA` | `Tris-EDTA Buffer pH 7.6` (BU-121) | 缓冲液而非纯 EDTA |

根因：`find_by_name` 逻辑 `name_lower in pn or pn in name_lower` 无词边界、无相似度阈值；partial 按 `_records` 文件顺序返回，取首条 = 文件首条而非语义最相似。

### 2.3 四个结构性薄弱点（代码事实）
1. **双向子串无阈值**（jena_index.py:184）→ 短词任意命中多个产品。
2. **match_key 不区分精确 / 子串**（jena_matcher.py:64）→ 返回仅 `cas` / `name` / `synonym:xxx` 三档，消费端无法识别「子串侥幸命中」。
3. **view 无分流闸门**（ai_views.py:356-444）→ jena 与 bioz 结果原样返回，无论 match_key 高低、bioz 是否 `needs_review`，均无「自动采纳 vs 人工复核」分流。
4. **bioz 证据锚点脆弱**（bioz_pipeline.py 用 `jena.catalog_no` 查询）→ 若 matcher 子串误命中到错误记录（catalog=C2），bioz 用 C2 查文献 → **整条证据链建立在错误锚点上**。

---

## 三、防御设计：三层协同（与上一轮身份字段闸门闭环）

### 层 A · 数据准确（上轮已交付，此处回顾）
- 身份字段闸门：catalog 以 source_url 为裁判、cas 过 mod-10、category 去导航泄漏；不过闸进 `jena_quarantine.jsonl`，`jena_index.build()` 只读 certified。
- 价值：保证 bioz 查询用的 catalog 真实存在（避免查空 / 查错），并消除 173 条 catalog 粘连污染。

### 层 B · 使用链路算法（本轮新增，治「算法过松」）
1. **match_key 细化四档**：`cas`（高）/ `exact_name`（高）/ `substring_name`（低）/ `synonym:xxx`（低）。
2. **子串命中 ≠ 单条采纳**：当匹配类型为 `substring_name` 或候选数 >1，返回**候选列表** + 低置信标记，而非单条首条。
3. **view 层按置信分流**（ai_views.py）：
   - 高置信（cas / exact_name）→ 可进入「已匹配草案」自动预填；
   - 低置信（substring_name / synonym）→ **进「待人工复核」队列，不直接预填**，操作员点确认才采纳。
4. **bioz provenance 透传**：返回里带 `evidence_anchor_catalog_no` + `match_confidence`，前端明示「文献基于 jena 匹配的 catalog_no=X」；bioz 自带 `equivalence`（strong/weak）+ `needs_review` 一并透传，不隐藏。

### 层 C · 呈现层（工作台操作员视角）
- **匹配依据卡**：命中字段 + 匹配类型（精确 / 子串 / 同义）+ 置信档色标。
- **多候选列表**：低置信 / 多候选时展示候选供操作员挑选，而非隐藏。
- **规格值来源标签**：每个预填值标「Jena 爬虫 · 低置信」vs「PubChem · 已校验」。
- **Bioz 文献标注锚点**：显示锚定 catalog_no + 等同性 + DISCLAIMER（基于同化学实体，非特定厂商）。
- **批次污染率熔断指示**：工作台显示当前 jena 批次污染率 + 上次校验时间。

### 熔断机制
- 定时跑身份字段校验（层 A）+ 匹配抽样回抓；超阈值 → 自动暂停 jena 依赖（降级为「无 jena 证据」模式）并告警，污染到不了消费端。

---

## 四、对三问的直接回答

**Q1 链条是否有效、结果是否精准？**
- 数据层：身份字段 91% 干净（上轮已证），基础条件成立。
- 算法层：**未成立**。精确名精准，通用名 / 子串名会错配且无人拦截。需落层 B 修复才整体精准。

**Q2 呈现如何更准确清晰？**
- 匹配依据卡 + 多候选列表 + 来源标签 + bioz 锚点透传 + 低置信醒目色（amber）+ 批次污染率熔断指示（层 C）。让操作员「看得见为什么匹配、信多少、该不该确认」。

**Q3 如何确保 jena 不污染整体功能？**
- 三层协同：层 A 数据闸门（不过闸不进索引）+ 层 B 算法置信分流（低置信不自动采纳）+ 层 C 呈现透明化。双库隔离（raw vs certified）+ 熔断降级兜底。治本在修 `scraper_v3.py` 873-884 行正则 + 加摄入校验（不影响上述三层生效）。

---

## 五、待办（均未执行，遵循「先真相大白再谈修」）
1. 层 B-1：`match_key` 细化四档（改 jena_matcher.py + jena_index.find_by_name 返回匹配类型）。
2. 层 B-2：子串 / 多候选返回候选列表而非首条。
3. 层 B-3：ai_views.py 按置信分流（高置信自动预填，低置信进待复核）。
4. 层 B-4：bioz_pipeline 透传 provenance。
5. 测试：`jena_match_ambiguity.py` 已落入 `verification/`，可作回归基准（修复后子串查询应不再错误返回单条首条）。

**审计脚本**：`verification/jena_match_ambiguity.py`（零依赖复刻生产逻辑，可重复跑）。
