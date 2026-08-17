# step2 · 14 条 formula↔MW 待确认记录 · PubChem 收口裁定

> 数据源：`backend/data/jena/jena_products_v2.jsonl`（2098 条）  
> 裁定脚本：`verification/jena_formula_mw_pubchem.py`（正确解析器 + PubChem PUG-REST）  
> 全量复扫：用正确解析器后，**真正的 formula↔MW 矛盾 = 12 条**（step1 报告称 14，系解析器误报夸大）

## 裁定汇总

| verdict | 计数 | 含义 |
|---------|-----:|------|
| `GENUINE_INTERNAL_CONTRADICTION` | 11 | jena 公式与 MW 自身矛盾（正确解析器仍不符），PubChem 未收录 |
| `OK_CONFIRMED` | 2 | PubChem 确认 jena MW 正确；step1 误报 |
| `JENA_FORMULA_WRONG` | 1 | jena MW 对但公式字段错 |

## 逐条裁定

| catalog_no | anchor | jena formula | jena MW | 正确解析器MW | PubChem formula | PubChem MW | verdict | note |
|-----------|--------|--------------|--------:|--------------|---------------|------------|---------|------|
| NU-1706-AZ594 | name | 'C50H60N6O21P2S4 (free acid)' | 1207.12 | 1271.24 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=1271.24 vs stored=1207.12)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂 |
| NU-285-AZ660 | name | 'C56H79N5O39P6S2 (free acid)' | 1792.39 | 1696.21 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=1696.21 vs stored=1792.39)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂 |
| NU-283-AZ660 | name | 'C55H78N6O38P6S2 (free acid)' | 1777.38 | 1681.20 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=1681.20 vs stored=1777.38)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂 |
| NU-284-AZ660 | name | 'C56H78N8O38P6S2 (free acid)' | 1817.4 | 1721.22 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=1721.22 vs stored=1817.40)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂 |
| NU-1610-RHO13 | name | 'C54H67N10O1P3S (free acid)' | 1253.16 | 997.18 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=997.18 vs stored=1253.16)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂商 |
| NU-829-TAM | name | 'C41H48N9O16P (free acid)' | 889.86 | 953.86 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=953.86 vs stored=889.86)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂商  |
| NU-282-AZ660 | name | 'C56H78N8O37P6S2 (free acid)' | 1801.4 | 1705.22 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=1705.22 vs stored=1801.40)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂 |
| NU-807-JOE | name | 'C39H42Cl2N7O21P3 (free acid)' | 1007.1 | 1108.62 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=1108.62 vs stored=1007.10)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂 |
| CSS-117 | cas | 'CH3CH(OH)CH 2 C(CH 3 ) 2 OH' | 118.17 | 118.18 | C6H14O2 | 118.17 | `OK_CONFIRMED` | PubChem 确认 jena MW 正确(formula=C6H14O2, MW=118.17)；step1 系解析器误报 |
| NU-10705 | name | 'C17H22N5O12P' | 581.31 | 519.36 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=519.36 vs stored=581.31)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂商  |
| GTPNU-1245 | name | 'C11H19N5O17P3 (free acid)' | 617.19 | 586.21 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=586.21 vs stored=617.19)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂商  |
| GTPNU-1241 | name | 'C10H17N5O17P3 (free acid)' | 603.16 | 572.19 | - | - | `GENUINE_INTERNAL_CONTRADICTION` | 正确解析器仍矛盾(calc=572.19 vs stored=603.16)；PubChem 未收录(多为专有染料/标记物)→需依 source_url 厂商  |
| CO-301 | cas | 'C16H18ClN3S*H2O' | 319.85 | 337.87 | C16H18ClN3S | 319.9 | `JENA_FORMULA_WRONG` | jena MW 与 PubChem 一致(319.85≈319.90)，但 jena 公式(C16H20Cl1N3O1S1)≠PubChem(C16H18Cl1 |
| BU-111 | cas | 'MgSO4*7H2O' | 246.48 | 246.47 | H14MgO11S | 246.48 | `OK_CONFIRMED` | PubChem 确认 jena 公式(H14MgO11S=MgSO4·7H2O)与 MW(246.48)均正确；本步解析器初版未处理 *nH2O 水合物误报，修正后自洽 |

## 全量真正矛盾清单（正确解析器，共 12 条）

> 含 14 条待确认之外的真实矛盾（若有），用于收口 step1 指标。

- NU-1706-AZ594
- NU-285-AZ660
- NU-283-AZ660
- NU-284-AZ660
- NU-1610-RHO13
- NU-829-TAM
- NU-282-AZ660
- NU-807-JOE
- NU-10705
- GTPNU-1245
- GTPNU-1241
- CO-301

## 结论与修正（经反方审查用）

**1. 对我此前判断的修正。** 我在 step1 收尾时曾推测「这 14 条多数是解析器误报」。实际裁定后证明该推测**错误**：14 条里只有 **2 条是解析器误报**（CSS-117 是 step1 不会解析结构式；BU-111 是本步初版未处理 `*nH2O` 水合物），其余 **12 条是真实的 formula↔MW 问题**。jena 这一端的化学属性字段确有实质缺陷，不是误报虚高。

**2. 12 条真实问题的性质划分。**

| 类别 | 条数 | catalog_no | 性质 | 是否由 PubChem 坐实 |
|---|---|---|---|---|
| 公式串错误（MW 正确） | 1 | CO-301 | jena 公式多写了 `*H2O`（算作水合物），但 MW=319.85 与 PubChem 无水物 C16H18ClN3S 一致 → 公式字段错，数值 MW 对 | ✅ 坐实（公式错） |
| 自身内部矛盾（PubChem 未收录） | 11 | NU-1706-AZ594 / NU-285/283/284/282-AZ660 / NU-1610-RHO13 / NU-829-TAM / NU-807-JOE / NU-10705 / GTPNU-1245 / GTPNU-1241 | jena 自己的 `molecular_formula` 与 `molecular_weight` 互相矛盾（正确解析器仍不符）。这些多为 Jena Bioscience 专有染料/标记核苷酸，PubChem 不收录，无法由外部权威坐实真伪 | ❌ 无法由 PubChem 裁定 |

**3. 对 11 条「自身内部矛盾」的合理假说（待 source_url 厂商 datasheet 确认，非定论）。**
这些公式大多标注 `(free acid)`，但存储 MW 与「free acid」理论值偏差 50–260 Da。最可能的解释是：**公式写的是游离酸形式，而 MW 存的是某种盐型/反离子形式**（如钠盐、三乙铵盐、锂盐），即两个字段描述的是同一物质的「不同形态」，彼此不自洽。无论哪种形态才是真值，这**本身就是一处数据缺陷**——系统内部 formula 与 MW 指向了不同分子式。PubChem 不收录这些专有物，故必须由 `source_url` 回抓厂商 datasheet 人工裁定究竟该以哪个为准、并统一两字段。

**4. 对 jena 信任度的含义。**
- 凡 PubChem 能触达的 3 条（CSS-117、BU-111 全对；CO-301 的 MW 对、公式串错），jena 的**数值 MW 经得起权威比对**；暴露的问题集中在「公式写法/水合物注释」这类**文本格式**层面，而非数值造假。
- 11 条专有物暴露的是 jena **字段间不自洽**的缺陷，性质上属于「清洗时公式与 MW 取自不同来源/形态未对齐」。这与我们最初定位的「jena 处于数据链后端、可信度最低」一致，但**不等于 jena 化学声明「对世界错」**——只是它自己两个字段对不上，需 datasheet 收口。
- 后续建议：① 对 CO-301 直接修公式串；② 对 11 条专有物依 `source_url` 回抓、统一 formula/MW 形态（即 step2b：规格/属性抽样回抓厂商页）；③ 在 `jena_index._parse` 中补「formula 自洽性」闸门，索引构建期即拦截这类内部矛盾。

**5. 复算口径说明（避免被误读）。** 「全量真正矛盾 = 12 条」指用**正确解析器**（已修括号分组、`(free acid)` 注释剥离、`*nH2O` 水合物）复扫 2098 条后，formula 推导 MW 与存储 MW 仍超 5%/5Da 容差的记录数。step1 报告的 14 因初版解析器局限被夸大；修正后真实数为 12（11 内部矛盾 + 1 公式串错），2 条已证为误报。