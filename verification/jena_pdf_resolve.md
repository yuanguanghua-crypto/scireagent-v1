# jena PDF 封口裁定报告（Step 2b-A：MISMATCH_AMBIG 三方对照）

> 方法：对 step2b 标记的 15 条 distinct 记录，回抓 Jena 官网 Datasheet (PDF)，
> 用 PDF 厂商权威规格与 jsonl（爬虫产物）、live_html（step2b 已抽）三方对照裁定。

> 脚本：`verification/jena_pdf_resolve.py`（pypdf 解析，不修改任何 jena 数据）。


## 一、jsonl 错误类型分布（字段级）

| jsonl 状态 | 计数 | 含义 |
|-----------|-----:|------|
| `JSONL_OK` | 44 | jsonl 与 PDF 权威值完全一致（含空格） |
| `JSONL_TRUNC` | 33 | jsonl 是 PDF 值的碎片/截断（爬虫截取词尾） |
| `JSONL_WRONG_NODE` | 11 | jsonl 与 PDF 完全无关（抓错 DOM 节点：导航/描述 junk 词） |
| `JSONL_OK_NORM` | 9 | 内容等价，仅格式/空格差（无空格粘连糙版） |
| `JSONL_MISMATCH` | 6 | jsonl 与 PDF 内容不同（非粘连非截断非碎片） |
| `JSONL_GLUE` | 1 | jsonl 含权威值 + 多余文本（字段粘连超集） |

## 二、live_html 抽取准确性分布（字段级）

| live 状态 | 计数 | 含义 |
|----------|-----:|------|
| `LIVE_NA` | 58 | live_html 未抽到值（页面无该字段或抽取器未命中） |
| `LIVE_OK` | 44 | live_html 抽到的值与 PDF 权威值完全一致（抽取准确） |
| `LIVE_MISMATCH` | 1 | live_html 抽到的值与 PDF 不符 |
| `LIVE_OK_NORM` | 1 | live_html 值内容等价，仅格式差 |

## 三、逐记录裁定（PDF 权威值 + jsonl 错误定位）

### NU-994  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| form | ation | solid | solid Color: white to off-white Spectrosco… | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 93 % (HPLC) |  | ≥ 93 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C14H20N5O12P3 (free acid) |  | C14H20N5O12P3 (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 543.26 |  | 543.26 g/mol (free acid) Exact Mass: 543.0… | `JSONL_TRUNC` | `LIVE_NA` |

### EDA-6-T  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 10 mM - 11 mMpH: 7.5 ±0.5Spectroscopic Pro… | 10 mM - 11 mM | 10 mM - 11 mM pH: 7.5 ±0.5 Spectroscopic P… | `JSONL_TRUNC` | `LIVE_OK` |
| form | ation | solution in water | solution in water | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C13H22N7O14P3S (free acid) |  | C13H22N7O14P3S (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 625.34 |  | 625.34 g/mol (free acid) Exact Mass: 625.0… | `JSONL_TRUNC` | `LIVE_NA` |

### NU-832-BIO  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 5.0 mM - 5.5 mMpH: 7.5 ±0.5BIOZ Product Ci… | 5.0 mM - 5.5 mM | 5.0 mM - 5.5 mM pH: 7.5 ±0.5 Jena Bioscien… | `JSONL_MISMATCH` | `LIVE_OK` |
| form | ation | solution in water | solution in water Color: colorless to slig… | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C26H40N9O9PS (free acid) |  | C26H40N9O9PS (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 685.69 |  | 685.69 g/mol (free acid) | `JSONL_TRUNC` | `LIVE_NA` |

### RNT-018  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| concentration | 2.0 – 2.2 μg/μl (A280, ɛ = 140 L mmol -1  … | 2.0 – 2.2 μg/μl (A280, ɛ = 140 L mmol | 2.0 – 2.2 µg/µl (A280, ɛ = 140 L mmol -1 c… | `JSONL_TRUNC` | `LIVE_OK` |
| storage_condition | store at -20 °C |  | avoid freeze/thaw cycles | `JSONL_MISMATCH` | `LIVE_NA` |
| shipping_condition | shipped on gel packs |  | shipped on gel packs | `JSONL_OK` | `LIVE_NA` |
| purity | ≥ 95 % (SDS-PAGE) |  | ≥ 95 % (SDS-PAGE) | `JSONL_OK` | `LIVE_NA` |
| form | liquid |  | liquid | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months |  | 12 months | `JSONL_OK` | `LIVE_NA` |

### RNT-008  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| concentration | 2.0 – 2.2 μg/μl (A280, ɛ = 140 L mmol -1  … | 2.0 – 2.2 μg/μl (A280, ɛ = 140 L mmol | 2.0 – 2.2 µg/µl (A280, ɛ = 140 L mmol -1 c… | `JSONL_TRUNC` | `LIVE_OK` |
| storage_condition | store at -20 °C |  | avoid freeze/thaw cycles | `JSONL_MISMATCH` | `LIVE_NA` |
| shipping_condition | shipped on gel packs |  | shipped on gel packs | `JSONL_OK` | `LIVE_NA` |
| purity | ≥ 95 % (SDS-PAGE) |  | ≥ 95 % (SDS-PAGE) | `JSONL_OK` | `LIVE_NA` |
| form | liquid |  | liquid | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months |  | 12 months | `JSONL_OK` | `LIVE_NA` |

### HEL-299  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| concentration | Lot specific. Determined by Bradford assay… | Lot specific. Determined by Bradford assay… | Lot specific. Determined by Bradford assay… | `JSONL_TRUNC` | `LIVE_OK` |
| storage_condition | store at -80 °C |  | avoid freeze/thaw cycles | `JSONL_MISMATCH` | `LIVE_NA` |
| shipping_condition | shipped on dry ice |  | shipped on dry ice | `JSONL_OK` | `LIVE_NA` |
| form | liquid (Supplied in 0.1 M glycine buffer p… |  | liquid (Supplied in 0. 1 M glycine buffer … | `JSONL_TRUNC` | `LIVE_NA` |
| shelf_life | 12 months |  | 12 months | `JSONL_OK` | `LIVE_NA` |

### NU-807-ROX  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic P… | 1.0 mM - 1.1 mM | 1.0 mM - 1. 1 mM pH: 7.5 ±0.5 Spectroscopi… | `JSONL_TRUNC` | `LIVE_OK` |
| form | ation | solution in water | solution in water Color: red-violet | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C49H58N9O17P3 (free acid) |  | C49H58N9O17P3 (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 1137.97 |  | 1137.97 g/mol (free acid) | `JSONL_TRUNC` | `LIVE_NA` |

### NU-807-RHO12  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic P… | 1.0 mM - 1.1 mM | 1.0 mM - 1. 1 mM pH: 7.5 ±0.5 Spectroscopi… | `JSONL_TRUNC` | `LIVE_OK` |
| form | ation | solution in water | solution in water | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C57H79N10O16P3 (free acid) |  | C57H79N10O16P3 (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 1253.23 |  | 1253.23 g/mol (free acid) Exact Mass: 1252… | `JSONL_TRUNC` | `LIVE_NA` |

### NU-807-THIO12  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic P… | 1.0 mM - 1.1 mM | 1.0 mM - 1. 1 mM pH: 7.5 ±0.5 Spectroscopi… | `JSONL_TRUNC` | `LIVE_OK` |
| form | ation | solution in water | solution in water | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C45H59N10O15P3S (free acid) |  | C45H59N10O15P3S (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 1105.0 |  | 1105.00 g/mol (free acid) | `JSONL_TRUNC` | `LIVE_NA` |

### NU-851-RHO14  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic P… | 1.0 mM - 1.1 mM | 1.0 mM - 1. 1 mM pH: 7.5 ±0.5 Spectroscopi… | `JSONL_TRUNC` | `LIVE_OK` |
| form | ation | solution in water | solution in water Color: blue | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C57H67Cl4N10O9P (free acid) |  | C57H67Cl4N10O9P (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 1209.0 |  | 1209.00 g/mol (free acid) Exact Mass: 1206… | `JSONL_TRUNC` | `LIVE_NA` |

### EN-178recombinant  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °Cavoid freeze/thaw cycles | store at -20 °C | avoid freeze/thaw cycles | `JSONL_GLUE` | `LIVE_MISMATCH` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 20 mg/mlActivity:  > 600 units/ml | 20 mg/ml | 20 mg/ml Applications: Digestion of protei… | `JSONL_MISMATCH` | `LIVE_OK` |
| form | ation | Proteinase K solution (20 mg/ml) in 10 mM … | Proteinase K solution (20 mg/ml) in 10 mM … | `JSONL_TRUNC` | `LIVE_OK` |
| purity | free of RNases and DNases |  | free of RNases and DNases | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months |  | 12 months | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 28.9 |  | 28.9 kDa CAS#: 39450-01-6 EC number: 254-4… | `JSONL_TRUNC` | `LIVE_NA` |

### CPL-151  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| shipping_condition | Accessories | shipped at ambient temperature | shipped at ambient temperature | `JSONL_WRONG_NODE` | `LIVE_OK` |
| shelf_life | n/a | n/a | n/a | `JSONL_OK` | `LIVE_OK` |
| form | ation | box of 10 plates | box of 10 plates The Swissci Hanging Drop … | `JSONL_TRUNC` | `LIVE_OK` |
| storage_condition | store at ambient temperature |  | store at ambient temperature | `JSONL_OK` | `LIVE_NA` |

### NU-829-BIO  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| storage_condition | store at -20 °CShort term exposure (up to … | store at -20 °C | store at -20 °C Short term exposure (up to… | `JSONL_OK_NORM` | `LIVE_OK` |
| shipping_condition | Accessories | shipped on gel packs | shipped on gel packs | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 5.0 mM - 5.5 mMpH: 7.5 ±0.5Spectroscopic P… | 5.0 mM - 5.5 mM | 5.0 mM - 5.5 mM pH: 7.5 ±0.5 Spectroscopic… | `JSONL_TRUNC` | `LIVE_OK` |
| form | ation | solution in water | solution in water Color: colorless to slig… | `JSONL_TRUNC` | `LIVE_OK` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months after date of delivery |  | 12 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C26H42N9O10PS (free acid) |  | C26H42N9O10PS (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 703.71 |  | 703.71 g/mol (free acid) Exact Mass: 703.2… | `JSONL_TRUNC` | `LIVE_NA` |

### NU-860-BIO  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| shipping_condition | Accessories | shipped on dry ice | shipped on dry ice | `JSONL_WRONG_NODE` | `LIVE_OK` |
| concentration | 5.0 mM - 5.5 mMpH: 7.5 ±0.5Spectroscopic P… | 5.0 mM - 5.5 mM | 5.0 mM - 5.5 mM pH: 7.5 ±0.5 Spectroscopic… | `JSONL_TRUNC` | `LIVE_OK` |
| form | ation | solution in water | solution in water Color: colorless to slig… | `JSONL_TRUNC` | `LIVE_OK` |
| storage_condition | store at -20 °C |  | store at -20 °C | `JSONL_OK` | `LIVE_NA` |
| purity | ≥ 95 % (HPLC) |  | ≥ 95 % (HPLC) | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 6 months after date of delivery |  | 6 months after date of delivery | `JSONL_OK` | `LIVE_NA` |
| molecular_formula | C23H37N10O16P3S (free acid) |  | C23H37N10O16P3S (free acid) | `JSONL_OK` | `LIVE_NA` |
| molecular_weight | 834.58 |  | 834.58 g/mol (free acid) Exact Mass: 834. … | `JSONL_TRUNC` | `LIVE_NA` |

### PCR-353  —  JSONL_HAS_ERROR

| 字段 | jsonl（爬虫） | live_html | PDF 权威 | jsonl 错误 | live 状态 |
|------|-------------|-----------|----------|-----------|-----------|
| concentration | 1 unit/μl | 1 unit/μl | 1 unit/µl Description: Thermolabile UNG is… | `JSONL_TRUNC` | `LIVE_OK` |
| form | liquid (Supplied in 20 mM Tris-HCl pH 8.0,… | liquid (Supplied in 20 mM Tris-HCl pH 8.0,… | liquid (Supplied in 20 mM Tris-HCl pH 8.0,… | `JSONL_OK_NORM` | `LIVE_OK_NORM` |
| storage_condition | store at -20 °C |  | avoid freeze/thaw cycles | `JSONL_MISMATCH` | `LIVE_NA` |
| shipping_condition | shipped on gel packs |  | shipped on gel packs | `JSONL_OK` | `LIVE_NA` |
| shelf_life | 12 months |  | 12 months | `JSONL_OK` | `LIVE_NA` |


## 四、结论

- 回抓 **15 条 distinct 记录**（覆盖 step2b 的 34 条 MISMATCH_AMBIG 字段），其中 **15 条 jsonl 确有错误/格式问题**，**0 条 jsonl 与 PDF 完全一致**（边界误判）。
- **MISMATCH_AMBIG 的真实根因拆解（字段级）**：
  - 字段粘连 / 格式糙（JSONL_GLUE + JSONL_OK_NORM）：**10** 条 —— jsonl 把相邻规格/描述 glued 在一起、或仅缺空格（如 `store at -20 °CShort term...`、浓度 `11 mmpH:7.5`）；
  - 截断碎片（JSONL_TRUNC）：**33** 条 —— 爬虫截取到词尾碎片（如 `form="ation"` 系统性截断、molecular_weight 仅存数字）；
  - 抓错 DOM 节点（JSONL_WRONG_NODE）：**11** 条 —— 抓了导航/描述 junk 词（如 `shipping="Accessories"`，对应 step1 根因 #1）；
  - 其它内容不符（JSONL_MISMATCH）：**6** 条 —— 细分：storage 被通用模板 `-20°C/-80°C` 覆盖（真实为 `avoid freeze/thaw cycles`，爬虫套用通用值未抓真实条件）**4** 条；concentration 粘连超集（含 BIOZ 引用/活性描述）**2** 条。
- **live_html 抽取（step2b）在可对照字段上准确**：LIVE_OK/OK_NORM 共 **45** 条（占可对照字段 45/46）；仅 **1** 条 LIVE_MISMATCH（EN-178 storage：live 同样抽到通用 "store at -20 °C" 错误标语，与 jsonl 同源，PDF 权威为 "avoid freeze/thaw cycles"）——说明 step2b 的 live 选择器也会命中该通用标语，需修正。
- 这与 step1 的 151 条浓度散文 + 20 条 shipping="Accessories" + 21 条储存/保质期占位共享同一**元根因**：爬虫对商业规格字段用宽松 DOM 选择器、且抽取后**无"值是否像合法规格"的校验闸门**就直接落库。
- 全程未修改任何 jena 数据；PDF 仅下载到 `verification/pdfs/` 做解析分析（验证产物）。