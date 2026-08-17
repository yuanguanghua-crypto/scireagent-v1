# jena 字段可抽取性 & 可信度契约（重写爬虫的权威输入）

> SciReAgent · AI AUTO MATCH 数据链调查 Phase 4（"先知道能拿到什么可信数据"）
> 文档日期：2026-07-16
> 前置文档：`jena_identity_audit.md`（身份字段审计）、`jena_uselink_audit.md`（使用链路审计）、`jena_match_fix_design.md`（层 B 修复设计）
> 实证样本：`verification/sample_pages/*.html`（6 个真实 jena 产品页：核苷酸 ATPNU-250、RNA 聚合酶 RNT-018、晶体 beads CO-501、抗生素 AB-106、蛋白酶 EN-181、荧光试剂盒 PP-305）

---

## 0. 总原则（用户铁律）

> **字段和值只有正确才有价值，而不是多获得了多少数据。数据的量没有价值，可能只是污染。**

这条原则直接改写爬虫哲学：

- 新爬虫目标 **不是"多抓字段"**，而是 **"只抓能可靠结构化抽取的字段，抓不到就留空（null），绝不硬填"**。
- 每个字段必须有 **明确的 DOM 锚点** + **抽取即校验闸门**。锚点缺失或值不像合法值 → 留空，不进结果。
- 化学属性类字段 **根本不归 jena 爬**（权威源是 PubChem），抓了就是污染。

---

## 1. 实证基础（6 个真实页面的结论）

### 1.1 规格落在固定 DOM 容器，跨品类 100% 一致
- 所有 6 页的规格标签（Molecular Formula / Molecular Weight / CAS# / Purity / Form / Concentration / pH / Storage Condition(s) / Shipping / Shelf Life 等）**100% 位于 `div.col-md-12.productdetails`**（也被 `div.col-md-9.content-inner-right.productview` 包裹同一内容）。
- 品类不同只影响"哪些标签存在"（试剂盒 PP-305 仅有 Shipping/Storage/Shelf Life/Color），但 **容器恒定**。
- 标签字符串**稳定逐字一致**（与 scraper_v3 的 `field_label_map` 完全吻合）。

### 1.2 主层 BS4 抽取是结构可靠的
- 在容器内用 `<b>Label</b>` + 紧随文本 抽取，6 页抓到的全是**正确值**（例：ATPNU-250 `C 10 H 17 N 6 O 13 P 3 (free acid)`、`100 mM - 110 mM`、`pH 7.5 ±0.5`）。

### 1.3 污染的唯一来源 = 全页 fallback 正则
- `scraper_v3.py:870-896` 的 fallback 正则（`\bForm\s*[:#]?\s*` 等）在 BS4 未命中时扫描**整页文本**。
- 实证：ATPNU-250 正文含 "**Form**ation"，全 6 页含 "Crystal Storage and **Shipping**" 导航串 → fallback 命中这些 → 产出 `form="ation"`、`shipping="Accessories"`、concentration 散文。
- **根因修复 = 删除全页 fallback，把抽取限定到 `div.productdetails` 容器。**

### 1.4 catalog 的可靠锚点是价格表/变体列表家族前缀，不是 URL slug
- 真实 jena 产品 URL 是描述性 slug（如 `.../8-6-amino-hexyl-amino-camp`），**不含 catalog 号**；catalog 只存在于价格表（含 size 变体 NU-250S/L）与变体列表（`div.productsblock > a > span.catalogno`：NU-851-680 等）。
- base catalog **恒在价格表/变体列表的家族前缀**（如 `NU-851` 共享 `NU-851-680`/`-CY5`），不在 URL、不在页面其他正文。→ catalog 必须从价格表/变体列表家族前缀派生；slug 仅作 fallback，**不可作裁判**（活体校验 07-16 实证：真实页 slug 全无 catalog）。

### 1.5 formula/mw 不应由 jena 提供（已核实）
- `FIVE_DATASOURCES.md` §1.1 铁律：化学结构唯一权威是 PubChem，jena 不碰。
- `scraper_v3` 虽爬了 formula/mw 进 v2，但**消费端从不读**（matcher 把它们丢进 extras，enrich 的化学属性来自 `pubchem_enhancer`）。→ jena 的 formula/mw 是死数据，12 条公式↔MW 矛盾对链路零影响，但纯属"多余数据=污染"。

---

## 2. 字段分层（A 必可靠 / B 不归 jena / C 低信任填充）

### A 类 — 锚点字段（驱动 auto match 链，必须可靠结构化抽取）

| 字段 | DOM 锚点（实证） | 抽取方法 | 校验闸门 | 信任 |
|------|----------------|---------|---------|------|
| `jena_catalog_no` | 价格表/变体列表家族前缀（span.catalogno 或 table cell） | extract_family_catalog 取最长共享前缀、剥离 size/变体后缀；slug 仅 fallback；discover catalog 不参与 | 必须出现在价格表/变体列表候选源，否则 QUARANTINE | 高（家族前缀自权威） |
| `source_url` | 抓取的 URL 本身 | 直接记录 | 非空 | 高 |
| `datasheet_pdf_url` / `msds_pdf_url` | 页面 PDF 链接（含 `/PDF/` 或 datasheet/msds 文本） | 提取 `<a href>` 匹配 PDF | 非空即记录，否则 null | 高 |
| `product_name` | `<h1>` | `soup.find('h1').get_text()` | 非空、非导航 | 高 |
| `systematic_name` | `<h1>` 后首个 `<p>` 副标题 | h1 父节点的下一个 `<p>` 文本 | 非空即记录；缺失则回退 product_name | 高（Bioz 锚点） |
| `category_path` | 面包屑 "You are here" div | 取面包屑文本 | **剥离导航段**（Accessories/Home/Cart/Login/Search/About/Contact/You are here）；再 map_category_l1，未映射则 null | 中（需清洗） |
| `price_eur_s/l` `amount_s/l` | 价格表 `Cat. No. | Amount | Price (EUR)` | 解析表格行 | 价格含 `€`/数字；amount 含单位(μl/mg/nmol) | 中 |

### B 类 — 化学属性（**不归 jena 爬**，权威源 PubChem/ChEMBL）

| 字段 | 处理 |
|------|------|
| `molecular_formula` `molecular_weight` `exact_mass` `lambda_max` `extinction_coefficient` `measurement_condition` | **从 jena schema 删除**，改由 PubChem 在 enrich 阶段回填。理由：① 权威源是 PubChem；② 消费端不读 jena 版；③ 抓了产生 12 条矛盾+污染类。 |
| `cas_number`（特例） | **保留爬取**（它在容器内可靠、且被 matcher 当优先级 1 匹配键 + Bioz 等同性输入）。但：过 **mod-10 校验位**；失败 → **null（不信任，不 quarantine，因 cas 是次级键）**；写入 Product.cas 仍以 PubChem 为准。 |

### C 类 — 商业规格（副产品，低信任，仅填空不覆盖）

| 字段 | DOM 锚点 | 抽取 | 校验（不像合法值→null） | 信任 |
|------|---------|------|----------------------|------|
| `purity` `form` `color` `concentration` `ph` `storage_condition` `shipping_condition` `shelf_life` | `div.productdetails` 内 `<b>Label</b>` | 容器限定抽取 | concentration 须含单位(mM/M/μM/%/x)；storage/shipping 须含温度或 ambient/gel packs；form 自由文本但标记 low | **低**（只填空字段，研究员权威） |

> C 类在契约里标记 `spec_source='jena_scraper'` + `spec_confidence='low'`，消费端沿用现有"只填空、不覆盖"逻辑，并可在 UI 标注"jena 爬虫·低置信·待厂商页复核"。

---

## 3. 根因修复（对应 scraper_v3.py 的具体改动）

| # | 现状（scraper_v3） | 改为 |
|---|------------------|------|
| R1 | `:870-896` 全页 fallback 正则 | **删除**。抽取只发生在 `container = soup.find('div', class_='productdetails') or soup.find('div', class_='productview')`；标签未在容器内命中 → 留 null |
| R2 | catalog 从 URL slug 派生（**错**：真实页 slug 无 catalog，活体校验 07-16 推翻） | base catalog = **价格表/变体列表家族前缀**（extract_family_catalog 取最长共享前缀）；slug 仅 fallback；discover catalog_number 不参与（粘连源） |
| R3 | category_path 整段面包屑（含 Accessories 导航） | 解析后 **strip 导航段**，再 map_category_l1；未映射 → null |
| R4 | cas 直接落库 | 落库前 **mod-10 校验**；失败 → null |
| R5 | 爬 formula/mw/exact_mass/λmax/ε 进 jsonl | **schema 删除这些字段**（交给 PubChem） |
| R6 | 抽取无"值是否像合法值"判断 | 每字段加 §2 校验；不像 → null（不硬填） |

> 注：R1~R6 落实后，Step1~2b-A 锁定的全部变形（form=ation / shipping=Accessories / concentration 散文 / catalog 粘连 / storage 模板 / 12 条公式矛盾）**从源头消失**，无需下游 matcher 去消化脏值。

---

## 4. 摄入校验闸门（intake gate，决定"能不能进 certified 索引"）

只对 **A 类锚点** 设硬门（不过闸 → `jena_quarantine.jsonl`，不进 `jena_certified`）：

| 闸门 | 规则 | 不过闸后果 |
|------|------|-----------|
| G1 catalog | 非空 + **出现在价格表/变体列表候选源** + 形态合法（`^[A-Z]{2,}-?\d...`） | QUARANTINE（最致命，断 Bioz 查询+精确匹配） |
| G2 cas | 若非空须过 mod-10 | null（不 quarantine，次级键） |
| G3 category | 面包屑剥离导航段后非空 + 能 map L1（或留空） | 留空（不 quarantine） |
| G4 spec(C类) | 形态校验 | 不像→null（不 quarantine，低信任本就可空） |

> `jena_index.build()` 只读 `jena_certified`；quarantine 记录保留在 raw，供人工复核，绝不伪装成真数据混进匹配结果（这正是 v2 最大问题：垃圾伪装成真实字段）。

---

## 5. 重爬校验计划（"怎么确保最终 jena 数据准确"）

重跑 scraper（落实 R1~R6）产出新 jsonl 后，跑以下验证确认准确：

1. **`jena_identity_audit.py`（A 类门）**：期望 **catalog BLOCK=0、cas mod-10 失败=0、category 导航泄漏=0**。
2. **新增 `jena_spec_integrity.py`（C 类门）**：抽样 N 页回抓 live，在 `div.productdetails` 内重抽规格，与 jsonl 比对 → 期望 **0 不一致**（不再有 ation/Accessories/散文）。
3. **`jena_match_ambiguity.py`（链路边际）**：name 歧义率仍约 43%（这是数据固有，非污染）——但配合 `jena_match_fix_design.md` 的 B-2（子串返候选列表）已解决错配。
4. **formula/mw 断言**：新 jsonl **不含** formula/mw 字段（设计使然），enrich 时由 PubChem 提供 → 0 矛盾。
5. **接受阈值**：G1=0 阻断；G2/G3/G4 允许 null 但不允许错值；spec 抽样不一致率 = 0。

---

## 6. 与既有文档的冲突（需同步修订）

- `FIVE_DATASOURCES.md` §B 附录（"现有 jsonl 已满足 jena 独占价值，无需二次爬虫"）**基于 2026-06-28 的乐观审计，已被本次污染测绘推翻**。该附录应标注"已被 2026-07-16 污染审计否定"，并以本文档的 A/B/C 分层 + 重爬计划替代。
- 文档 §4.5 把 `systematic_name` 叙事为"核心锚点"，但代码实际用 `catalog_no` 驱动 Bioz（§5.3 + matcher）。契约维持：**catalog_no 是硬锚点（Bioz 查询+精确匹配），systematic_name 是展示+理论锚点**。

---

## 7. 一页速查（给重写爬虫的工程师）

```
抽取范围 = div.productdetails (fallback: div.productview)   # R1 删全页正则
catalog   = 价格表/变体列表家族前缀(extract_family_catalog), slug 仅 fallback   # R2
category  = 面包屑 strip 导航段 → map L1                     # R3
cas       = 爬(容器内可靠) + mod10 校验, 失败→null            # R4
formula/mw/λmax/ε = 不爬, 交 PubChem                         # R5
spec(C类) = 容器内<b>Label</b>抽取 + 形态校验, 不像→null       # R6
闸门      = catalog 不过→quarantine; 其余不像→null
原则      = 只留正确值, 缺失即 null, 绝不硬填
```

*本文档与 `jena_identity_audit.md` / `jena_uselink_audit.md` / `jena_match_fix_design.md` 共同构成"数据准确 → 使用链路准确"的完整调查闭环。均未修改任何生产数据/代码。*
