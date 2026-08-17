# jena 内在校验报告（A 类：不可能 / 畸形，零外部依赖）

> 数据源：`backend/data/jena/jena_products_v2.jsonl`  

> 记录总数：**2098** ｜ 命中记录：**236**（11.2%） ｜ 异常条目：**254**  

> 分层：确定性损坏 **178** ｜ 结构性 **62** ｜ 待确认 **14**  

> 生成脚本：`verification/jena_intrinsic_check.py`（不依赖 PubChem / 不联网）


## Tier 1 · 确定性损坏（爬虫/清洗引入，高置信）

> 违反字段契约或内部算术，无需外部真值即可判定为错误。

| 异常类型 | 计数 | 说明 |
|---------|-----:|------|
| `concentration:too_long` | 151 | concentration 超长（>40字符，描述泄漏） |
| `shipping:unmappable` | 20 | shipping_condition 无法归一化（Accessories=错位污染） |
| `encoding:nbsp` | 6 | 含 NBSP(U+00A0) 非常规空白 |
| `cas:checksum_invalid` | 1 | cas_number 校验位(mod-10)不通过（清洗损坏） |

## Tier 2 · 结构性 / 匹配不可用（非损坏，但需关注）

> 数据本身未必错，但格式使匹配器无法使用，或仅为通用说明占位。

| 异常类型 | 计数 | 说明 |
|---------|-----:|------|
| `cas:multi_value` | 41 | cas_number 含多值/盐注释（匹配器单值键无法使用） |
| `storage:unmappable` | 18 | storage_condition 为通用说明占位，无温度 |
| `shelf_life:unmappable` | 3 | shelf_life 为通用说明占位 |

## Tier 3 · 待 step2 外部确认（疑似，需 PubChem 裁定）

> 离线无法判定，疑似内部矛盾，需 step2 用 PubChem 比对确认。

| 异常类型 | 计数 | 说明 |
|---------|-----:|------|
| `mw:mw_formula_mismatch` | 14 | formula 理论 MW 与存储 MW 矛盾（离线疑似，step2 确认） |

## A7 product_name 重复（碰撞风险，信息级）

> 共 **14** 个 product_name 出现重复（jena 用 catalog_no 作主键，名字重复仅提示 name 匹配碰撞风险）。

- 5-methyl-ctp
- ap4g
- atto 655 protein labeling kit
- highyield t7 mrna synthesis kit (me1ψ-utp)
- horizontal microloops e
- inclined microloops e
- klenow fragment
- lexsinduce3 expression kit
- lexsy in vitro translation kit
- lexsycon2.1 expression kit
- pfu-x core kit
- silicone grease
- tnp-atp
- vertical microloops e

## 异常记录明细（节选前 80 条，全量见 CSV）

| catalog_no | product | field | issue | tier | snippet |
|-----------|--------|-------|-------|------|---------|
| CO-501 | JBS Beads-for-Seeds | concentration | concentration:too_long | corruption | is slowly increased until a point of supersaturation is reached. Us... |
| SNU-209 | Mant-GTPγS | cas_number | cas:multi_value | structural | 136749-24-1, 136749-26-3 |
| NU-402 | GppCp | cas_number | cas:multi_value | structural | 13912-93-1, 10470-57-2 (sodium salt) |
| NU-214 | Mant-AppNHp | cas_number | cas:checksum_invalid | corruption | 85287-56-6 |
| NU-433 | ADPβS | cas_number | cas:multi_value | structural | 35094-45-2 (free acid), 73536-95-5 (lithium salt) |
| NU-907 | dTpNHpp | cas_number | cas:multi_value | structural | 141171-14-4 (free acid) |
| NU-439 | dCpNHpp | cas_number | cas:multi_value | structural | 791761-70-1 (free acid) |
| NU-264 | CpNHpp | cas_number | cas:multi_value | structural | 497064-76-3 (free acid) |
| NU-440 | dGpNHpp | cas_number | cas:multi_value | structural | 756797-73-6 (free acid) |
| NU-443 | dApNHpp | cas_number | cas:multi_value | structural | 753429-25-3 (free acid) |
| NU-449 | ApNHpp | cas_number | cas:multi_value | structural | 114635-42-6 (free acid), 114635-43-7 (Tetrasodium salt) |
| NU-421 | ApCpp | cas_number | cas:multi_value | structural | 7292-42-4 (acid), 1343364-54-4 (Trisodium salt) |
| NU-447 | dCMPαS | cas_number | cas:multi_value | structural | 63225-09-2 (component: 64145-27-3) |
| RNT-101-AZ | HighYield T7 Azide RNA | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-401-D | HighYield T7 Desthiobi | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + 5 μl 100 mM UTP ... |
| RNT-401-BIOX | HighYield T7 Biotin11  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + 5 μl 100 mM UTP ... |
| RNT-101-D | HighYield T7 Desthiobi | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-BIOX | HighYield T7 Biotin11  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-BIO16 | HighYield T7 Biotin16  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| DIG-11-UTP | HighYield T7 Digoxigen | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-401-AZ647 | HighYield T7 AZDye647  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + 5 μl 100 mM UTP ... |
| RNT-401-AZ594 | HighYield T7 AZDye594  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + 5 μl 100 mM UTP ... |
| RNT-401-AZ555 | HighYield T7 AZDye555  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + 5 μl 100 mM UTP ... |
| RNT-401-AZ488 | HighYield T7 AZDye488  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + 5 μl 100 mM UTP ... |
| RNT-101-IR750 | HighYield T7 IR750 RNA | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-IR680 | HighYield T7 IR680LT R | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-STRED | HighYield T7 STAR RED  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-AZ647 | HighYield T7 AZDye647  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-AZ594 | HighYield T7 AZDye594  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-AZ555 | HighYield T7 AZDye555  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-AZ488 | HighYield T7 AZDye488  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-AZ405 | HighYield T7 AZDye405  | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| ATTO-488 | HighYield T7 Atto488 R | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-CY5 | HighYield T7 Cy5 RNA L | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-CY3 | HighYield T7 Cy3 RNA L | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| RNT-101-FAMX | HighYield T7 Fluoresce | concentration | concentration:too_long | corruption | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + 5 μl 100 mM GTP ... |
| NU-1706-AZ594 | pCp-AZDye594 | mw_formula | mw:mw_formula_mismatch | deferred | formula='C50H60N6O21P2S4 (free acid)' mw=1207.12 |
| APP-003 | 3'-End Oligonucleotide | concentration | concentration:too_long | corruption | Final molar amountPCR grade H2O31.5 μln/an/a5x TdT Reaction Buffer1... |
| APP-002 | DIG 3'-End Oligonucleo | concentration | concentration:too_long | corruption | of 10 μM (e.g. 1 μl of 1 mM Digoxigenin-11-ddUTP + 99 μl PCR-grade ... |
| PP-310L-DIGX | Digoxigenin NT Labelin | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-310L-BIO16 | Biotin16 NT Labeling K | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| DIG-11 | HighFidelity Digoxigen | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-BIO16 | HighFidelity Biotin16  | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| PP-305L-AZ647 | AZDye647 NT Labeling K | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305 | Atto680 NT Labeling Ki | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305L-CY5 | Cy5 NT Labeling Kit | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305L-AZ594 | AZDye594 NT Labeling K | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305L-TXR | TexasRed NT Labeling K | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305L-AZ555 | AZDye555 NT Labeling K | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305L-CY3 | Cy3 NT Labeling Kit | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305L-AZ488 | AZDye488 NT Labeling K | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| PP-305L-FAMX | Fluorescein NT Labelin | concentration | concentration:too_long | corruption | s. The 5'→3' exonuclease activitiy of Polymerase I removes nucleoti... |
| APP-101-IR750 | HighFidelity IR750 PCR | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-IR680 | HighFidelity IR680LT P | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-RED | HighFidelity RED PCR L | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| ATTO-643 | HighFidelity ATTO643 P | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-AZ647 | HighFidelity AZDye647  | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-CY5 | HighFidelity Cy5 PCR L | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-ORANGE | HighFidelity ORANGE PC | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| ATTO-594 | HighFidelity ATTO594 P | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-AZ594 | HighFidelity AZDye594  | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-YELLOW | HighFidelity YELLOW PC | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-AZ555 | HighFidelity AZDye555  | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-CY3 | HighFidelity Cy3 PCR L | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-GREEN | HighFidelity GREEN PCR | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-AZ488 | HighFidelity AZDye488  | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| APP-101-FAMX | HighFidelity Fluoresce | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |
| NU-285-AZ660 | zeta-(6-Aminohexyl)-dT | mw_formula | mw:mw_formula_mismatch | deferred | formula='C56H79N5O39P6S2 (free acid)' mw=1792.39 |
| NU-283-AZ660 | zeta-(6-Aminohexyl)-dC | mw_formula | mw:mw_formula_mismatch | deferred | formula='C55H78N6O38P6S2 (free acid)' mw=1777.38 |
| NU-284-AZ660 | zeta-(6-Aminohexyl)-dG | mw_formula | mw:mw_formula_mismatch | deferred | formula='C56H78N8O38P6S2 (free acid)' mw=1817.4 |
| NU-1610-RHO13 | EDA-GTPγS-ATTO-Rho13 | mw_formula | mw:mw_formula_mismatch | deferred | formula='C54H67N10O1P3S (free acid)' mw=1253.16 |
| NU-829-TAM | 8-(6-Aminohexyl)-amino | mw_formula | mw:mw_formula_mismatch | deferred | formula='C41H48N9O16P (free acid)' mw=889.86 |
| NU-282-AZ660 | zeta-(6-Aminohexyl)-dA | mw_formula | mw:mw_formula_mismatch | deferred | formula='C56H78N8O37P6S2 (free acid)' mw=1801.4 |
| NU-807-JOE | 8-(6-Aminohexyl)-amino | mw_formula | mw:mw_formula_mismatch | deferred | formula='C39H42Cl2N7O21P3 (free acid)' mw=1007.1 |
| RNT-107 | HighYield T7 mRNA Synt | concentration | concentration:too_long | corruption | can easily be achieved with the single nucleotide format.A 20 μl re... |
| NU-1138 | 5-Methyl-CTP | cas_number | cas:multi_value | structural | 327174-86-7 (acid) |
| ABD-031 | anti-Sp100 | concentration | concentration:too_long | corruption | 1:1000 to 1:2000. Western Blot, concentration: 1:500. |
| CSS-117 | MPD - 100 % v/v | mw_formula | mw:mw_formula_mismatch | deferred | formula='CH3CH(OH)CH 2 C(CH 3 ) 2 OH' mw=118.17 |
| PK-104 | JBS Magic Triangle | cas_number | cas:multi_value | structural | 35453-19-1 (5-Amino-2,4,6-triiodoisophthalic acid), 1310-66-3 (Lith... |
| APP-101-LNA | HighFidelity LNA PCR L | concentration | concentration:too_long | corruption | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP + 2 μl 100 mM dGT... |

> 其余 174 条见 `jena_intrinsic_report.csv`。