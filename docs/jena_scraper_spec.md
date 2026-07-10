# Jena Bioscience 爬虫产出物数据规格

> 本文档为 jena_scraper 爬虫程序的**输出约束**，定义每一个产出字段的名称、类型、必填性、数据要求和清洗规则。
>
> **重要更新（2026-06-28）**：经五数据源综合分析（见 `FIVE_DATASOURCES.md`），确认：
> - jena 数据**不进 Product 表**——它归策略 B（本地索引常驻），作为 AI AUTO MATCH 的锚点供给层（systematic_name 驱动 Bioz）+ 规格副产品预填。研究员不会从 jena 选择新建产品。
> - jena 最大价值 = **systematic_name 锚点**（撬动 Bioz 文献池）；规格字段（purity/storage）是副产品。
> - `citations` 字段**移除**——文献改走 Bioz `search_result` API（跨厂家可复用，覆盖更全）。
> - `description` / `handling_notes` 降级为可选（Bioz snippets 可提供更好的用途描述）。
> - `systematic_name` 提升为**最关键字段**（跨源查询锚点，96.6% 覆盖）。
>
> **历史教训**：本规格曾包含「批次导入 Product 表」的约束（CAS 双校验根、幂等键 catalog_no 等），基于错误的策略 C 定位。该方向已撤销，相关导入代码（`jena_importer.py` / `import_jena_products` command）已删除。本规格现仅约束**爬虫产出物本身**（供 AI AUTO MATCH 索引服务读取），不再约束导入落库。
>
> 约束来源：
> - 用途：AI AUTO MATCH 索引服务读取（策略 B，仿 BioProCorpus）
> - 数据约束：化学结构权威性（CAS/SMILES/分子式/MW 必须经 PubChem 验证，jena 不直接写入 Product）
> - 数据约束：范围限制（仅 Nucleotides / Click Chemistry / Molecular Biology 三线产品进入平台知识图谱）
> - 清洗约束：7 条强制清洗规则 + concentration 语义分类

---

## 一、输出格式

- **格式**：JSONL，每行一条 JSON 记录
- **空值**：所有字段无值均填 `null`（不用空字符串 `""`）
- **字段名**：固定命名，不允许自由命名（见下方各节）
- **编码**：UTF-8
- **时间**：`crawled_at` 用 UTC ISO 8601 格式

---

## 二、基础标识字段（必抓）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `jena_catalog_no` | string | ✅ | 主货号，如 `"NU-1001"` | 去除首尾空格 |
| `jena_catalog_no_s` | string/null | — | 小包装货号变体，如 `"NU-1001L"` | 无则 null |
| `jena_catalog_no_l` | string/null | — | 大包装货号变体，如 `"NU-1001-10ML"` | 无则 null |
| `product_name` | string | ✅ | 页面产品标题，如 `"dATP - Solution"` | 去除首尾空格 |
| `systematic_name` | string/null | — | 系统命名/IUPAC，如 `"5-Mercuryacetate-2'-deoxyuridine-5'-triphosphate, Triethylammonium salt"` | **优先抓取，注意字段名不统一（Systematic name / IUPAC Name / Chemical name 均可能）** |
| `source_url` | string | ✅ | 产品详情页 URL | 完整 URL，不缩短 |

> **关键约束（双校验根-purge）**：CAS 号的权威来源是 PubChem。`systematic_name` 是 jena 供应商标注的系统命名，与 PubChem 的 compound data 共同参与 DUPLICATE_PURGE 校验——两套名称必须一致才通过；不一致时以 PubChem 为准，`systematic_name` 仅作余标注。

---

## 三、化学结构字段（必抓）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `cas_number` | string/null | — | CAS 号，格式 `XXXXXXX-XX-X` | **（见下方「CAS 号双校验根」专项约束）** |
| `molecular_formula` | string/null | — | 分子式 | **只保留 `(free acid)` 之前的裸露式**，如 `"C10H16N5O12P3"`，去掉 `(free acid)` / `(salt)` 后缀 |
| `molecular_weight` | float/null | — | 分子量数值 | **只取 free acid 的数值**，去掉 `g/mol` 单位 |
| `exact_mass` | float/null | — | 精确质量 | 只取数值，去掉单位 |

> **分子量唯一原则**：如果页面上只有一个质量数值，直接抓。如果有多个，优先抓标注为 `(free acid)` 的，没有则抓第一个。

### CAS 号权威性约束（核心中的核心）

CAS 号的权威来源是 PubChem。`systematic_name` 是 jena 供应商标注的系统命名，作为**跨源查询锚点**驱动 PubChem/Bioz 查询——所有化学属性（CAS/SMILES/分子式/MW）的权威值都从 PubChem 获取，不直接导入外部源。

```
jena CAS 号（如有）→ PubChem 验证（name/{CAS} 查询）
                    → 验证通过 + 名称一致 → 可写入 Product.cas
                    → 验证通过 + 名称不一致 → 标记可疑，人工复核
                    → 验证失败 → 不写入，留 null
```

**禁止行为**：直接从 jena HTML 中提取的 CAS 号不经 PubChem 验证就写入 `cas` 字段。这是硬约束——所有非 PubChem 来源的化学属性都不允许直接进入化学结构字段。

**关于 jena CAS 独占性**：jena 有 CAS 的 299 个产品全部能在 PubChem 查到（独占性=0%，WorkBuddy 验证确认）。因此 jena 的 CAS 不是「新化合物知识」，只是「PubChem 已有化合物的供应商标注」，用作精确查询的锚点而非数据源。

---

## 四、产品规格字段（必抓）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `purity` | string | ✅ | 纯度声明 | 原样保留，如 `"≥ 99 % (HPLC)"`——**不要只抓数字**，方法学是重要的合规信息 |
| `concentration` | string/null | — | 浓度 | **必须含量纲才保留**：`mM`、`M`、`μM`、`%`、`w/v` 等；**去污染规则：值含 photometrically / HPLC / PAGE / solid / clear aqueous solution → 置 null** |
| `form` | string | ✅ | 物理形态 | 如 `"solid"`、`"solution in water"`、`"clear aqueous solution"` |
| `color` | string/null | — | 颜色描述 | 如 `"white to off-white"` |
| `ph` | string/null | — | pH 值 | **只取数字部分**，如 `"8.5 ±0.2 (22 °C)"` → `"8.5 ±0.2"`；如无法分离则存整串 |

> **concentration 去污染核心规则（见下方 7 条清洗规则 第 1 条）**：浓度 ≠ 纯度测定方法。值中含 `photometrically` / `spectrophotometrically` / `HPLC` / `PAGE` 且不含量纲 → 判定为污染，置 null。

---

## 五、光谱特性字段（选抓）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `lambda_max` | float/null | — | 最大吸收波长 | 只取数值，如 `259.0`，去掉单位 `nm`；无则 null |
| `extinction_coefficient` | float/null | — | 消光系数 | 只取数值，如 `15.1`；无则 null |
| `measurement_condition` | string/null | — | 光谱测量条件 | 如 `"Tris-HCl pH 7.5"`；无则 null |

> 上述光谱字段仅含发色团的产物有数据，大部分蛋白/酶类可能无这些数据。**无数据时填 null，不要猜测或推算。**

---

## 六、储存与物流字段（必抓）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `storage_condition` | string | ✅ | 储存条件 | 原样保留，如 `"store at -20 °C"` |
| `shipping_condition` | string | ✅ | 运输条件 | 原样保留，如 `"shipped on gel packs"` |
| `shelf_life` | string | ✅ | 保质期 | 原样保留，如 `"12 months"`、`"6 months after date of delivery"` |
| `handling_notes` | string/null | — | 操作注意事项 | 从 Description 段落中提取操作提示，如 `"Please centrifuge briefly before opening (volume ≤2 ml)"`；无则 null |

---

## 七、知识资产字段（必抓）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `description` | string/null | 🟢 可选 | 产品用途自然语言描述 | 提取页面 Description 段落全文，不截断。**价值已降级**——Bioz snippets 能提供更好的跨厂家用途描述 |
| ~~`citations`~~ | ~~array~~ | ❌ **已移除** | ~~供应商收录的文献引用~~ | **文献改走 Bioz widget API**——按 catalog_no 查，跨厂家可复用，覆盖比单 SKU 抓全一个数量级（详见 `FIVE_DATASOURCES.md` §4.6、§5.1）|
| `application_tags` | string/null | 🟡 可选 | 应用标签（分号分隔） | 去除 `...` 截断前缀。**边际价值**——作 PubMed 搜索种子词，不能直接映射 Application 实体 |

---

## 八、文档与链接字段（必抓）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `category_path` | string | ✅ | 分类路径，竖线分隔 | 原样保留，**不删末端冗余的产品名副本**——保留原始信息，下游处理去重 |
| `datasheet_pdf_url` | string/null | — | 数据手册 PDF 链接 | 完整 URL；无则 null |
| `msds_pdf_url` | string/null | — | SDS PDF 链接 | 完整 URL；无则 null |
| `structural_formula_url` | string/null | — | 结构图 URL | 完整 URL；无则 null |

---

## 九、价格与变体字段（可选）

| 字段名 | 类型 | 必填 | 数据要求 | 清洗规则 |
|--------|------|:---:|----------|----------|
| `price_eur_s` | float/null | — | 小包装 EUR 价格 | **欧式→国际格式**：`95,30` → `95.30`（先去千分位点，再逗号变小数点）；不要输出字符串 |
| `price_eur_l` | float/null | — | 大包装 EUR 价格 | 同上 |
| `amount_s` | string/null | — | 小包装规格 | 如 `"1 ml (100 mM)"`；无则 null |
| `amount_l` | string/null | — | 大包装规格 | 同上 |
| `color` | string/null | — | 颜色 | 如 `"clear aqueous solution"`；无则 null |

---

## 十、元数据字段（必抓）

| 字段名 | 类型 | 必填 | 数据要求 |
|--------|------|:---:|----------|
| `crawled_at` | string(ISO datetime) | ✅ | UTC 时间戳，如 `"2026-06-28T08:14:55.347469+00:00"` |

---

## 十一、7 条强制清洗规则（爬虫必须内置实现）

| # | 规则 | 实现方法 |
|---|------|----------|
| 1 | **concentration 去污染** | 白名单正则：`re.search(r'(\d+\.?\d*\s*(mM|M|μM|%|w/v|mg/ml))', value)` → 无匹配则 null |
| 2 | **application_tags 去截断** | `re.sub(r'^\.{2,}\s*', '', value)` |
| 3 | **CAS 格式校验** | `re.fullmatch(r'\d{2,7}-\d{2}-\d', value)` → 不匹配则 null |
| 4 | **分子式去后缀** | `re.sub(r'\s*\((free acid|salt|sodium salt|ammonium salt|lithium salt).*$', '', value, flags=re.I)` |
| 5 | **分子量去单位** | `re.sub(r'\s*(g/mol|Da|u).*$', '', value)` → 转 float |
| 6 | **价格格式转换** | `float(value.replace('.', '').replace(',', '.'))` — 先去掉千分位点，再逗号变小数点 |
| 7 | **全局去空格** | `value.strip()` — 所有字段通用 |

---

## 十二、字段优先级汇总

| 优先级 | 字段集合 | 说明 |
|--------|----------|------|
| **P0（必抓，生死线）** | `jena_catalog_no`, `product_name`, `source_url`, `cas_number`, `molecular_formula`, `molecular_weight`, `purity`, `form`, `storage_condition`, `shipping_condition`, `shelf_life`, `datasheet_pdf_url`, `msds_pdf_url`, `crawled_at` | 缺失则整批数据价值大降 |
| **P1（必抓，高价值）** | `systematic_name`, `exact_mass`, `concentration`, `ph`, `lambda_max`, `extinction_coefficient`, `measurement_condition`, `description`, `citations`, `application_tags`, `category_path`, `structural_formula_url` | 本次页面对照发现的差距项，也是协同校验和 COA/SDS 的关键输入 |
| **P2（建议抓）** | `price_eur_s`, `price_eur_l`, `amount_s`, `amount_l`, `catalog_no_s`, `catalog_no_l`, `color`, `handling_notes` | 补充产品信息和商业数据 |

---

## 十三、禁止行为

1. **不覆盖字段含义**：`concentration` 只能存浓度，纯度测定方法（`photometrically`）不能塞进来
2. **不截断长文本**：`description`、`citations`、`application_tags` 必须完整提取——页面前端 truncate 是前端行为，爬虫要拿到原始值
3. **不混入无关数字**：CAS 字段只存 CAS 格式的数字，Lot No. 等编号不进此字段
4. **CAS 不写入未经 PubChem 验证的值**：这是 Druid 架构的硬约束，见「CAS 号双校验根约束」节
5. **不用空字符串 `""` 代替 null**：下游需要区分「未知」和「工厂标注为空」

---

## 十四、示例输出（NU-1001 完整产品记录）

```json
{
  "jena_catalog_no": "NU-1001",
  "jena_catalog_no_s": "NU-1001L",
  "jena_catalog_no_l": "NU-1001-10ML",
  "product_name": "dATP - Solution",
  "systematic_name": "2'-Deoxyadenosine-5'-triphosphate, Sodium salt",
  "source_url": "https://www.jenabioscience.com/nucleotides-nucleosides/nucleotides-by-structure/unmodified-nucleotides/dntps/single-solutions/nu-1001-datp-solution",
  "cas_number": "1927-31-7",
  "molecular_formula": "C10H16N5O12P3",
  "molecular_weight": 491.18,
  "exact_mass": 490.996,
  "purity": "≥ 99 % (HPLC)",
  "concentration": "100 mM - 110 mM",
  "form": "clear aqueous solution",
  "color": null,
  "ph": "8.5 ±0.2",
  "lambda_max": 259.0,
  "extinction_coefficient": 15.1,
  "measurement_condition": "Tris-HCl pH 7.5",
  "storage_condition": "store at -20 °C",
  "shipping_condition": "shipped on gel packs",
  "shelf_life": "12 months",
  "handling_notes": "Please centrifuge briefly before opening",
  "description": "dATP, PCR-grade is supplied as ultrapure aqueous solution (pH 8.5) and suitable for all molecular biology applications including PCR/qPCR, reverse transcription, DNA labeling and DNA sequencing.",
  "application_tags": "PCR; qPCR; Reverse Transcription; DNA Labeling; DNA Sequencing",
  "category_path": "Nucleotides & Nucleosides|Nucleotides by Structure|Unmodified Nucleotides|dNTPs|Single Solutions|dATP - Solution",
  "datasheet_pdf_url": "https://www.jenabioscience.com/images/PDF/NU-1001.0005.pdf",
  "msds_pdf_url": "https://www.jenabioscience.com/images/MSDS/NU-1001_MSDS.0004.pdf",
  "structural_formula_url": "https://www.jenabioscience.com/images/Structures/NU-1001.png",
  "price_eur_s": 95.30,
  "price_eur_l": 666.60,
  "amount_s": "1 ml (100 mM)",
  "amount_l": "10 ml (100 mM)",
  "catalog_no_s": "NU-1001L",
  "catalog_no_l": "NU-1001-10ML",
  "crawled_at": "2026-06-28T14:00:00.000000+00:00"
}
```

---

## 十五、集成约束备忘

| 约束 | 说明 |
|------|------|
| **化学结构权威性** | CAS/SMILES/分子式/MW 的权威来源是 PubChem，不直接导入外部源；jena 的化学属性值仅作校验用 |
| **systematic_name 是跨源锚点** | jena 最关键的产出，96.6% 覆盖；驱动 PubChem（化学结构）和 Bioz（文献）查询 |
| **范围限制** | 仅 Nucleotides / Click Chemistry / Molecular Biology 三线产品进入平台知识图谱 |
| **产品规格可直通** | jena 的产品规格（purity/concentration/storage/shipping/shelf_life）属于供应商维度数据，可直接写入对应字段，不经过 PubChem 校验 |
| **concentration 需语义分类** | 酶活单位（units/μl）/ 浓缩倍数（x）/ 小分子浓度（mM）/ 污染（photometrically）需分类处理 |
| **CAS 独占性=0** | jena CAS 号 100% 可在 PubChem 查到（WorkBuddy 验证确认），jena CAS 仅作精确查询锚点 |
| **文献走 Bioz** | `citations` 已从爬虫范围移除，文献改走 Bioz search_result API（按 systematic_name 查，跨厂家可复用）|
| **现有数据已达标** | 现有 jsonl 无需二次爬虫，仅需清洗（见 FIVE_DATASOURCES.md 附录 B）|
