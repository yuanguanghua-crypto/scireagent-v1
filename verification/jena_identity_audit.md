# jena 身份字段完整性审计（auto match load-bearing 字段）

- 数据源：`backend/data/jena/jena_products_v2.jsonl`（2098 条）
- 审计字段：catalog_no / cas_number / product_name / category_path
- 分类：BLOCK=污染须隔离；WARN=软风险待复核

## 汇总

- **四身份字段全干净（无 BLOCK）的记录数：1773（占 84%）← 可信任基线**
- 至少 1 个 BLOCK（污染须隔离）的记录数：**325**（占 15%）
- 仅 WARN（软风险待复核、不阻断）的记录数：**270**（占 12%）
- 主键 catalog_no 重复：无

## 各字段 BLOCK / WARN 记录数

| 字段 | BLOCK 记录数 | WARN 记录数 |
|---|---|---|
| catalog_no | 306 | 1 |
| cas_number | 1 | 0 |
| product_name | 0 | 0 |
| category_path | 18 | 424 |

## 问题细分（按 field × severity × issue）

| 字段 | 严重度 | 问题 | 条数 |
|---|---|---|---|
| category_path | WARN | unmapped_to_l1 | 423 |
| catalog_no | BLOCK | malformed | 306 |
| category_path | BLOCK | nav_leak | 18 |
| cas_number | BLOCK | mod10_checkdigit_fail | 1 |
| catalog_no | WARN | too_long | 1 |
| category_path | WARN | empty | 1 |

## 典型 BLOCK 样本（前 25 条）

**NU-214**
  - cas_number.mod10_checkdigit_fail = '85287-56-6'
**RNT-401-D**
  - catalog_no.malformed = 'RNT-401-D'
**RNT-101-D**
  - catalog_no.malformed = 'RNT-101-D'
**NU-1706-D**
  - catalog_no.malformed = 'NU-1706-D'
**NU-831-D**
  - catalog_no.malformed = 'NU-831-D'
**NU-821-D**
  - catalog_no.malformed = 'NU-821-D'
**NU-821-X**
  - catalog_no.malformed = 'NU-821-X'
**PP-310L-DIGX**
  - catalog_no.malformed = 'PP-310L-DIGX'
**PP-310L-BIO16**
  - catalog_no.malformed = 'PP-310L-BIO16'
**NU-835-D**
  - catalog_no.malformed = 'NU-835-D'
**PP-305L-AZ647**
  - catalog_no.malformed = 'PP-305L-AZ647'
**PP-305L-CY5**
  - catalog_no.malformed = 'PP-305L-CY5'
**PP-305L-AZ594**
  - catalog_no.malformed = 'PP-305L-AZ594'
**PP-305L-TXR**
  - catalog_no.malformed = 'PP-305L-TXR'
**PP-305L-AZ555**
  - catalog_no.malformed = 'PP-305L-AZ555'
**PP-305L-CY3**
  - catalog_no.malformed = 'PP-305L-CY3'
**PP-305L-AZ488**
  - catalog_no.malformed = 'PP-305L-AZ488'
**PP-305L-FAMX**
  - catalog_no.malformed = 'PP-305L-FAMX'
**TW-1**
  - category_path.nav_leak = 'Crystallography & Cryo-EM|Crystal Handling & Storage|Accessories|Tweezers| Serrated End Tweezers'
**GHA-1**
  - category_path.nav_leak = 'Crystallography & Cryo-EM|Crystal Handling & Storage|Accessories|Goniometer Head Adapter| Goniometer Head Adapter'
**CC-117**
  - category_path.nav_leak = 'Crystallography & Cryo-EM|Crystal Handling & Storage|Storage and Shipping|Uni-Pucks and Accessories| Double Puck Loading Dewar with Lid'
**CC-116**
  - category_path.nav_leak = 'Crystallography & Cryo-EM|Crystal Handling & Storage|Storage and Shipping|Uni-Pucks and Accessories| Puck Separator Tools'
**CC-115**
  - category_path.nav_leak = 'Crystallography & Cryo-EM|Crystal Handling & Storage|Storage and Shipping|Uni-Pucks and Accessories| Puck Dewar Loading Tool'
**CC-114**
  - category_path.nav_leak = 'Crystallography & Cryo-EM|Crystal Handling & Storage|Storage and Shipping|Uni-Pucks and Accessories| Puck Wand'
**CC-112**
  - category_path.nav_leak = 'Crystallography & Cryo-EM|Crystal Handling & Storage|Storage and Shipping|Uni-Pucks and Accessories| Bent Cryo Tong'
**CC-111**
**CC-110**
**CC-113**
**BHCK-1**
**SP-25L**
**SP-70V**
**SP-50V**
**SP-30V**
**SP-15V**
**SP-50I**
**SP-15I**
**SP-50H**
**SP-15H**
**SP-300LD**
**SP-200LD**
**SP-150LD**
**SP-100LD**
**SP-75LD**
**SP-50LD**
**SP-35LD**
**HTSCS-507Lkosmotropic**
**PR-969Proprotein**
**PR-968Proprotein**
**PR-967Asparaginyl**
**IEN-177recombinant**
**EN-179EndoribonucleaseBovine**
**EN-176Endonucleaserecombinant**
**EN-180also**
**EN-174Pandalus**
**IEN-142JBSpeed**
**IEN-141Isoschizomers**
**IEN-140Isoschizomers**
**IEN-139JBSpeed**
**BIEN-138Isoschizomers**
**BIEN-136Isoschizomers**
**BIEN-133Isoschizomers**
**IEN-129Isoschizomers**
**IEN-125Isoschizomers**
**IEN-124Isoschizomers**
**IEN-146Isoschizomers**
**IEN-123Isoschizomers**
**IEN-122Isoschizomers**
**CIEN-121Isoschizomers**
**IEN-120Isoschizomers**
**IEN-119Neoschizomers**
**IEN-118Isoschizomers**
**IEN-160Neoschizomers**
**AIEN-113Isoschizomers**
**EIIEN-144Isoschizomers**
**FIEN-110Isoschizomers**
**BIEN-108Isoschizomers**
**AIEN-107Isoschizomers**
**IEN-104Isoschizomers**
**IEN-101JBSpeed**
**SP-20LD**
**TTPNU-989Zidovudine**
**TMPNU-1601Zidovudine**
**CN-1070hmdC**
**CN-1069fdC**
**CN-1091cadC**
**UTPNU-1151s**
**UTPNU-1156s**
**NU-1014ATP**
**NU-1019ddATP**
**ATTO-532NU**
**NU-1020Premix**
**UTPNU-880m**
**ATPNU-8898-H**
**ATPNU-9538-H**
**ATPNU-1209Isoguanosine**
**GTPNU-11178-H**
**CTPNU-988ac**
**ATPNU-5462Cl**
**ATPNU-1101m**
**CTPNU-1138m**
**CLK-1046A**
**CLK-1302A-AZ**
**CLK-1301A-AZ**
**CLK-1288A-AZ**
**CLK-1059A**
**CLK-1300A-AZ**
**CLK-1283A-AZ**
**CTP-101M**
**CPL-152material**
**FLAGCLK-032Azide-PEG3**
**FLAGCLK-088Alkyne-PEG4**
**FLAGCLK-033Dibenzylcyclooctyne-PEG4**
**PCR-390Bst**
**PCR-541Kit**
**PCR-540Kit**
**NU-1170Cytarabine**
**NU-1171Cytarabine**
**NU-1111Vidarabine**
**NU-11578-H**
**GDPNU-11588-H**
**GMPNU-11538-H**
**GTPNU-11168-H**
**NU-11106-T**
**NU-12106-T**
**NU-11486-T**
**OANU-537m**
**EDA-6-T**
**UTPNU-9725moUTP**
**UTPNU-890me**
**NU-971-D**
**NU-957-D**
**NU-1607Sodium**
**NU-1608Sodium**
**NU-275Sodium**
**NU-1105Sodium**
**TTPNU-1604Stavudine**
**TMPNU-1603Stavudine**
**TCTPNU-1606Lamivudine**
**TCMPNU-1605Lamivudine**
**RNARNT-017Polyadenylic**
**RNT-203Synthesis**
**RNT-202Synthesis**
**RNT-006recombinant**
**RNT-113Synthesis**
**RNT-112Synthesis**
**RNT-111Synthesis**
**RNT-110Synthesis**
**RNT-109Synthesis**
**RNT-108Synthesis**
**RNT-107Synthesis**
**RNT-106Synthesis**
**RNT-121Synthesis**
**RNT-120Synthesis**
**RNT-119Synthesis**
**RNT-118Synthesis**
**RNT-117Synthesis**
**RNT-116Synthesis**
**RNT-115Synthesis**
**RNT-114Synthesis**
**RNT-102Synthesis**
**UDP-6-A**
**PR-958Fluorescently**
**TW-2**
**CEM-206**
**CEM-205**
**CEM-201**
**CEM-204**
**CEM-203**
**CEM-202**
**HTSCS-205L**
**HTSCS-207LPEG**
**HTSCS-209L**
**HTSCS-204L**
**HTSCS-206L**
**IICS-202Lbased**
**ICS-201Lbased**
**CS-114Lbased**
**CS-113Lbased**
**CS-112Lbased**
**CS-110Lbased**
**CS-109Lbased**
**CS-108Lbased**
**CS-107Lbased**
**CS-106Lbased**
**CS-105Lbased**
**CS-104Lbased**
**CS-103Lbased**
**CS-102Lbased**
**CS-101Lbased**
**HTSCS-203L**
**PR-1495VZV**
**PR-1450Tick**
**EPR-1499Tick**
**PR-1456SARS-C**
**PR-1455SARS-C**
**PR-1454SARS-C**
**MPR-1453SARS**
**PR-1452SARS**
**PR-1480Recombinant**
**HPV-77PR-BA129**
**PR-1420Hepatitis**
**PR-1419Hepatitis**
**PR-1473Recombinant**
**PR-1416Hepatitis**
**PR-1418Hepatitis**
**PR-1417Hepatitis**
**PR-1414Hepatitis**
**PR-1413Hepatitis**
**PR-1412Hepatitis**
**PR-1411Hepatitis**
**PR-1410Hepatitis**
**PR-1409Hepatitis**
**PR-1408Hepatitis**
**PR-1406Hepatitis**
**PR-1405Hepatitis**
**PR-1404Hepatitis**
**PR-1403Hepatitis**
**PR-1402Hepatitis**
**PR-1401Hepatitis**
**PR-1400Hepatitis**
**PR-1465Recombinant**
**PR-1449Epstain-B**
**PR-1448Epstain-B**
**EBNA-3A**
**PR-1496DENV**
**PR-1491CMV**
**PR-1490CMV**
**PR-1444Cytomegalovirus**
**PR-1443Cytomegalovirus**
**PR-1442Cytomegalovirus**
**PR-1428Treponema**
**PR-1427Treponema**
**PR-1426Treponema**
**PR-1425Treponema**
**PR-1424Treponema**
**PR-1423Treponema**
**PR-1422Treponema**
**PR-1421Treponema**
**PR-1485Tg**
**PR-1445Toxoplasma**
**TW-183native**
**PR-1451Chlamydia**
**PR-1497Recombinant**
**IL-2R**
**ML-108sterile**
**ML-105sterile**
**AB-106sterile**
**AB-105sterile**
**AB-104sterile**
**AB-103sterile**
**ML-412brain**
**ML-411sterile**
**LE-002Tobacco**
**EGE-1310pac**
**EGE-1310sat**
**EGE-1310neo**
**EGE-1310hyg**
**EGE-1310ble**
**EGE-1420blecherry**
**EGE-1410neo**
**EGE-1410ble**
**EGE-1410blecherry**
**PP-410Fluorescence**
**PP-409Fluorescence**
**PP-218Alkaline**
**PP-202Spin**
**PP-201Spin**
**PP-210Isolation**
**PP-235Spin**
**PP-204Column**
**PP-209Solution**
**PP-206Solution**
**PP-207Solution**
**PP-208Solution**
**PP-205Solution**
**PP-215Spin**
**PP-214Spin**
**PP-237DNA**
**PP-238DNA**
**PP-236DNA**
**EN-148Large**
**PCR-395Lyophilisate**
**PCR-398Lyophilisate**
**PCR-393Master**
**PCR-387Master**
**PCR-510One-S**
**PCR-525One-S**
**PCR-511First**
**PCR-505Reverse**
**PCR-169Lyophilised**
**PCR-159Lyophilised**
**UNGPCR-526RT**
**ROXPCR-522RT**
**PCR-520RT**
**UNGPCR-523RT**
**ROXPCR-513RT**
**ROXPCR-533Robust**
**ROXPCR-529Robust**
**PCR-173Lyophilised**
**PCR-156Lyophilised**
**UNGPCR-375Master**
**ROXPCR-374Master**
**ROXPCR-373Master**
**PCR-372Master**
**ROXPCR-365Master**
**ROXPCR-364Master**
**ROXPCR-362Master**
**ROXPCR-361Master**
**PCR-277Low**
**PCR-269general**
**PCR-237Kit**
**PCR-216Kit**
**PCR-214Kit**
**PCR-207Proofreading**
**PCR-204Thermostable**
**PCR-217Thermostable**
**PCR-165Red**
**PCR-167Master**
**PCR-108Master**
**PCR-164Red**
**PCR-166Master**
**PCR-110Master**
**NU-1024Premix**
**PCR-603T**
**EN-178recombinant**

## 重跑爬虫 / 清洗时的 ingestion 校验闸门规范（VALIDATION_GATE_SPEC）

目标：最终形成的 jena 数据，凡被 auto match 消费的身份字段必须过闸，否则隔离（不进 certified 索引）。

| 字段 | 校验规则 | 失败处置 | 阶段 |
|---|---|---|---|
| catalog_no | **终极裁判=出现在自身价格表/变体列表（span.catalogno 或 table cell，即爬虫 extract_family_catalog 候选源）则合法**（含 SP-25L / NU-851-680 类变体字母）；不在候选源 → BLOCK→隔离（真实 jena 产品 URL 是描述性 slug、不含 catalog，slug 不可作裁判）；格式须过 `^[A-Z]{2,}-?\d+(?:-[A-Z0-9]{2,6})?$`；无空格；长度≤30 | 见左 | 摄入即查 |
| cas_number | 非空时过 `^\d{2,7}-\d{2}-\d$` + mod-10 校验位 | 格式 WARN/校验位 BLOCK→隔离 | 摄入即查 |
| product_name | 非空；无 ` > ` 面包屑箭头；无导航泄漏(accessories/home/login 等)；非散文(无句末标点或过长) | 面包屑/泄漏 BLOCK；散文 WARN | 摄入即查 |
| category_path | 非空；无导航泄漏（`|` 是 Jena 合法层级分隔符，不判污染）；能 map_category_l1 到已知 L1（否则分类留空不硬填） | 泄漏 BLOCK；未映射 WARN | 摄入即查 |
| 一致性(软) | catalog_no 必须出现在自身价格表/变体列表（爬虫抽取源）；真实 jena URL 不含 catalog，故 slug 不作裁判；抽取失败即 BLOCK（非 WARN，避免全文误隔离） | BLOCK→隔离 | 摄入即查 |
| 主键唯一 | catalog_no 全库唯一 | 重复 BLOCK→隔离 | 摄入即查 |

应用方式：scraper_v3.py 第 853-868 行提取后、写入 JSONL 前，插入本闸门；不过闸记录写入 `jena_quarantine.jsonl` 并打 `quality_flag`，不进入 `jena_products_v2.jsonl`（certified）。后端 `jena_index.build()` 仅读 certified 文件。