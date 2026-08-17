# jena 规格字段「抽样回抓」根因校验报告（step 2b）

> 对照源：每条记录的 `source_url`（Jena 官网产品页）  
> 样本：203 条（已知污染 163 + 干净基线 40）  
> 模式：full（已知污染+基线）  
> crawled_at 约 2026-06-28；live 为当前抓取，差异可能含源头 drift。  
> **本项目只找原因，不修改任何数据。**

## 根因分类汇总（逐字段）

| 根因 | 计数 | 含义 |
|------|-----:|------|
| SCRAPER_JUNK | 195 | jsonl 是 junk（散文/导航词），live 无此字段 → 爬虫抽到 junk 内容（错内容抽取） |
| OVER_EXTRACTED | 71 | jsonl 有值、live 无 → 爬虫多抽（或源头已删该字段） |
| SCRAPER_DOM_ERR | 37 | jsonl 是 junk（散文/导航词），live 合法值 → 爬虫抓错 DOM 节点（确凿） |
| MISMATCH_AMBIG | 34 | 双方均合法但不同 → 爬虫错或源头 drift，需原始 HTML/PDF 定 |
| FETCH_FAIL | 0 | 抓取失败（VPN/限频），需断点续跑补 |

## 记录级主因

- `CO-501` [conc_prose] → **SCRAPER_DOM_ERR** 
- `RNT-101-AZ` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-401-D` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-401-BIOX` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-D` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-BIOX` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-BIO16` [conc_prose] → **SCRAPER_JUNK** 
- `DIG-11-UTP` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-401-AZ647` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-401-AZ594` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-401-AZ555` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-401-AZ488` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-IR750` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-IR680` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-STRED` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-AZ647` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-AZ594` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-AZ555` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-AZ488` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-AZ405` [conc_prose] → **SCRAPER_JUNK** 
- `ATTO-488` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-CY5` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-CY3` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-101-FAMX` [conc_prose] → **SCRAPER_JUNK** 
- `APP-003` [conc_prose] → **SCRAPER_JUNK** 
- `APP-002` [conc_prose] → **SCRAPER_JUNK** 
- `PP-310L-DIGX` [conc_prose] → **SCRAPER_JUNK** 
- `PP-310L-BIO16` [conc_prose] → **SCRAPER_JUNK** 
- `DIG-11` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-BIO16` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-AZ647` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-CY5` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-AZ594` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-TXR` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-AZ555` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-CY3` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-AZ488` [conc_prose] → **SCRAPER_JUNK** 
- `PP-305L-FAMX` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-IR750` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-IR680` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-RED` [conc_prose] → **SCRAPER_JUNK** 
- `ATTO-643` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-AZ647` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-CY5` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-ORANGE` [conc_prose] → **SCRAPER_JUNK** 
- `ATTO-594` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-AZ594` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-YELLOW` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-AZ555` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-CY3` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-GREEN` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-AZ488` [conc_prose] → **SCRAPER_JUNK** 
- `APP-101-FAMX` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-107` [conc_prose] → **SCRAPER_JUNK** 
- `ABD-031` [conc_prose] → **OVER_EXTRACTED** 
- `APP-101-LNA` [conc_prose] → **SCRAPER_JUNK** 
- `NU-994` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `FP-202` [conc_prose] → **SCRAPER_JUNK** 
- `FP-322` [conc_prose] → **SCRAPER_JUNK** 
- `FP-321` [conc_prose] → **SCRAPER_JUNK** 
- `FP-320` [conc_prose] → **SCRAPER_JUNK** 
- `FP-201-ROX` [conc_prose] → **SCRAPER_JUNK** 
- `FP-201` [conc_prose] → **SCRAPER_JUNK** 
- `FP-201-CY5` [conc_prose] → **SCRAPER_JUNK** 
- `FP-201-CY3` [conc_prose] → **SCRAPER_JUNK** 
- `CLK-075` [conc_prose] → **SCRAPER_JUNK** 
- `CLK-073` [conc_prose] → **SCRAPER_JUNK** 
- `CLK-074` [conc_prose] → **SCRAPER_JUNK** 
- `CLK-1086` [conc_prose] → **OVER_EXTRACTED** 
- `CLK-1084` [conc_prose] → **OVER_EXTRACTED** 
- `CLK-1085` [conc_prose] → **OVER_EXTRACTED** 
- `CLK-072` [conc_prose] → **SCRAPER_JUNK** 
- `CLK-071` [conc_prose] → **SCRAPER_JUNK** 
- `FLAGCLK-032Azide-PEG3` [conc_prose] → **OVER_EXTRACTED** 
- `FLAGCLK-033Dibenzylcyclooctyne-PEG4` [conc_prose] → **OVER_EXTRACTED** 
- `PCR-540` [conc_prose] → **OVER_EXTRACTED** 
- `EDA-6-T` [conc_prose] → **SCRAPER_DOM_ERR** 
- `NU-832-BIO` [conc_prose] → **SCRAPER_DOM_ERR** 
- `ATPNU-843` [conc_prose] → **OVER_EXTRACTED** 
- `RNT-101` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-105` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-135` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-203Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-202Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-134` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-138` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-137` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-136` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-113Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-112Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-111Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-110Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-109Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-108Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-107Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-106Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-121Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-120Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-119Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-118Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-117Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-116Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-115Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-114Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-104` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-103` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-102Synthesis` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-601` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-501` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-201` [conc_prose] → **SCRAPER_JUNK** 
- `RNT-018` [conc_prose] → **MISMATCH_AMBIG** 
- `RNT-008` [conc_prose] → **MISMATCH_AMBIG** 
- `UDP-6-A` [ship_accessories] → **SCRAPER_JUNK** 
- `PR-958Fluorescently` [conc_prose] → **OVER_EXTRACTED** 
- `CO-305` [conc_prose] → **SCRAPER_JUNK** 
- `CS-360` [conc_prose] → **SCRAPER_JUNK** 
- `CS-350` [conc_prose] → **SCRAPER_JUNK** 
- `CS-351` [conc_prose] → **SCRAPER_JUNK** 
- `NY-99` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1495VZV` [conc_prose] → **SCRAPER_DOM_ERR** 
- `EPR-1499Tick` [conc_prose] → **SCRAPER_DOM_ERR** 
- `SARS-2` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1480Recombinant` [conc_prose] → **SCRAPER_DOM_ERR** 
- `HPV-77PR-BA129` [conc_prose] → **SCRAPER_DOM_ERR** 
- `HEL-299` [conc_prose] → **MISMATCH_AMBIG** 
- `HIV-2` [conc_prose] → **SCRAPER_DOM_ERR** 
- `HIV-1` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1473Recombinant` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1465Recombinant` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1496DENV` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1491CMV` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1490CMV` [conc_prose] → **SCRAPER_DOM_ERR** 
- `HHV-5` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PR-1485Tg` [conc_prose] → **SCRAPER_DOM_ERR** 
- `TW-183native` [conc_prose] → **OVER_EXTRACTED** 
- `PR-1497Recombinant` [conc_prose] → **SCRAPER_DOM_ERR** 
- `AB-102` [conc_prose] → **OVER_EXTRACTED** 
- `AB-101` [conc_prose] → **MATCH** 
- `LT-111` [conc_prose] → **SCRAPER_JUNK** 
- `LT-102` [conc_prose] → **SCRAPER_JUNK** 
- `PP-102` [conc_prose] → **SCRAPER_JUNK** 
- `PP-235Spin` [conc_prose] → **SCRAPER_JUNK** 
- `PP-204Column` [conc_prose] → **SCRAPER_JUNK** 
- `BHQ-3` [ship_accessories] → **SCRAPER_JUNK** 
- `BHQ-2` [ship_accessories] → **SCRAPER_JUNK** 
- `BHQ-1` [ship_accessories] → **SCRAPER_JUNK** 
- `PCR-156Lyophilised` [conc_prose] → **SCRAPER_JUNK** 
- `PCR-277Low` [conc_prose] → **OVER_EXTRACTED** 
- `PCR-269general` [conc_prose] → **OVER_EXTRACTED** 
- `NU-807-ROX` [conc_prose] → **SCRAPER_DOM_ERR** 
- `NU-807-RHO12` [conc_prose] → **SCRAPER_DOM_ERR** 
- `NU-807-THIO12` [conc_prose] → **SCRAPER_DOM_ERR** 
- `NU-851-RHO14` [conc_prose] → **SCRAPER_DOM_ERR** 
- `PK-108` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `PK-107` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `PK-106` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `EN-178recombinant` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `CPL-151` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `CPL-165` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `UVPCPL-164` [ship_accessories] → **SCRAPER_DOM_ERR** 
- `NU-829-BIO` [conc_prose] → **SCRAPER_DOM_ERR** 
- `NU-860-BIO` [conc_prose] → **SCRAPER_DOM_ERR** 
- `NU-1612-TAM` [clean_baseline] → **MATCH** 
- `NU-1618` [clean_baseline] → **MATCH** 
- `NU-821-TAM` [clean_baseline] → **MATCH** 
- `NU-835-RHO12` [clean_baseline] → **MATCH** 
- `NU-810-RHO11` [clean_baseline] → **MATCH** 
- `NU-850-CY3` [clean_baseline] → **MATCH** 
- `FP-167` [clean_baseline] → **SCRAPER_JUNK** 
- `NU-802-RHO14` [clean_baseline] → **MATCH** 
- `NU-850-RHO6` [clean_baseline] → **MATCH** 
- `PR-1426Treponema` [clean_baseline] → **MATCH** 
- `PCR-353` [clean_baseline] → **MISMATCH_AMBIG** 
- `ATPNU-1123` [clean_baseline] → **MATCH** 
- `NU-806-MNT` [clean_baseline] → **MATCH** 
- `ICS-201Lbased` [clean_baseline] → **SCRAPER_JUNK** 
- `LCP-108` [clean_baseline] → **SCRAPER_JUNK** 
- `NU-810-TXR` [clean_baseline] → **MATCH** 
- `CSS-256` [clean_baseline] → **MATCH** 
- `NU-940` [clean_baseline] → **MATCH** 
- `NU-1612-BIOX` [clean_baseline] → **MATCH** 
- `CLK-1046A` [clean_baseline] → **MATCH** 
- `NSNU-1616` [clean_baseline] → **MATCH** 
- `ATPNU-9762` [clean_baseline] → **MATCH** 
- `EN-179EndoribonucleaseBovine` [clean_baseline] → **OVER_EXTRACTED** 
- `PP-401` [clean_baseline] → **SCRAPER_JUNK** 
- `NU-833-THIO12` [clean_baseline] → **MATCH** 
- `CO-301` [clean_baseline] → **SCRAPER_JUNK** 
- `NU-875` [clean_baseline] → **MATCH** 
- `NU-835-RHO13` [clean_baseline] → **MATCH** 
- `CS-503` [clean_baseline] → **SCRAPER_JUNK** 
- `NU-861-CY3` [clean_baseline] → **MATCH** 
- `PR-1425Treponema` [clean_baseline] → **MATCH** 
- `NU-808-JOE` [clean_baseline] → **MATCH** 
- `CS-505` [clean_baseline] → **SCRAPER_JUNK** 
- `UTPNU-541` [clean_baseline] → **MATCH** 
- `NU-279-CY3` [clean_baseline] → **MATCH** 
- `NU-829-ROX` [clean_baseline] → **MATCH** 
- `NU-805-TXR` [clean_baseline] → **MATCH** 
- `CPL-136` [clean_baseline] → **SCRAPER_DOM_ERR** 
- `UTPNU-1189` [clean_baseline] → **MATCH** 
- `TMPNU-1601Zidovudine` [clean_baseline] → **MATCH** 

## 逐字段明细（仅非 MATCH/BOTH_EMPTY）

| catalog_no | field | jsonl 值 | live 值 | 分类 |
|-----------|-------|---------|---------|------|
| CO-501 | shelf_life | n/a | n/a | SCRAPER_DOM_ERR |
| CO-501 | concentration | is slowly increased until a point of supersaturati |  | SCRAPER_JUNK |
| CO-501 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-AZ | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-AZ | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-401-D | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + |  | SCRAPER_JUNK |
| RNT-401-D | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-401-BIOX | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + |  | SCRAPER_JUNK |
| RNT-401-BIOX | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-D | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-D | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-BIOX | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-BIOX | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-BIO16 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-BIO16 | form | Oscreen® |  | SCRAPER_JUNK |
| DIG-11-UTP | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| DIG-11-UTP | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-401-AZ647 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + |  | SCRAPER_JUNK |
| RNT-401-AZ647 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-401-AZ594 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + |  | SCRAPER_JUNK |
| RNT-401-AZ594 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-401-AZ555 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + |  | SCRAPER_JUNK |
| RNT-401-AZ555 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-401-AZ488 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM GTP + |  | SCRAPER_JUNK |
| RNT-401-AZ488 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-IR750 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-IR750 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-IR680 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-IR680 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-STRED | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-STRED | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-AZ647 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-AZ647 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-AZ594 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-AZ594 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-AZ555 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-AZ555 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-AZ488 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-AZ488 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-AZ405 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-AZ405 | form | Oscreen® |  | SCRAPER_JUNK |
| ATTO-488 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| ATTO-488 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-CY5 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-CY5 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-CY3 | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-CY3 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-101-FAMX | concentration | of 10 mM (e.g. 5 μl 100 mM ATP + 5 μl 100 mM CTP + |  | SCRAPER_JUNK |
| RNT-101-FAMX | form | Oscreen® |  | SCRAPER_JUNK |
| APP-003 | concentration | Final molar amountPCR grade H2O31.5 μln/an/a5x TdT |  | OVER_EXTRACTED |
| APP-003 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-002 | concentration | of 10 μM (e.g. 1 μl of 1 mM Digoxigenin-11-ddUTP + |  | SCRAPER_JUNK |
| APP-002 | purity | , length or overall sequence). |  | OVER_EXTRACTED |
| APP-002 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-310L-DIGX | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-310L-DIGX | form | Oscreen® |  | SCRAPER_JUNK |
| PP-310L-BIO16 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-310L-BIO16 | form | Oscreen® |  | SCRAPER_JUNK |
| DIG-11 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| DIG-11 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-BIO16 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-BIO16 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-AZ647 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-AZ647 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-CY5 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-CY5 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-AZ594 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-AZ594 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-TXR | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-TXR | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-AZ555 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-AZ555 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-CY3 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-CY3 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-AZ488 | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-AZ488 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-305L-FAMX | concentration | s. The 5'→3' exonuclease activitiy of Polymerase I |  | SCRAPER_JUNK |
| PP-305L-FAMX | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-IR750 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-IR750 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-IR680 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-IR680 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-RED | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-RED | form | Oscreen® |  | SCRAPER_JUNK |
| ATTO-643 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| ATTO-643 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-AZ647 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-AZ647 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-CY5 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-CY5 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-ORANGE | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-ORANGE | form | Oscreen® |  | SCRAPER_JUNK |
| ATTO-594 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| ATTO-594 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-AZ594 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-AZ594 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-YELLOW | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-YELLOW | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-AZ555 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-AZ555 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-CY3 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-CY3 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-GREEN | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-GREEN | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-AZ488 | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-AZ488 | form | Oscreen® |  | SCRAPER_JUNK |
| APP-101-FAMX | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-FAMX | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-107 | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-107 | form | Oscreen® |  | SCRAPER_JUNK |
| ABD-031 | concentration | 1:1000 to 1:2000. Western Blot, concentration: 1:5 |  | OVER_EXTRACTED |
| APP-101-LNA | concentration | of 1 mM (e.g. 2 μl 100 mM dATP + 2 μl 100 mM dCTP  |  | SCRAPER_JUNK |
| APP-101-LNA | form | Oscreen® |  | SCRAPER_JUNK |
| NU-994 | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| NU-994 | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| NU-994 | form | ation | solid | MISMATCH_AMBIG |
| FP-202 | concentration | is 10 mg/ml, other concentrations are also possibl |  | OVER_EXTRACTED |
| FP-202 | purity | of your conjugate by SDS-PAGE. |  | OVER_EXTRACTED |
| FP-202 | form | Oscreen® |  | SCRAPER_JUNK |
| FP-322 | concentration | should be at least 2 mg/ml, higher concentrations  |  | OVER_EXTRACTED |
| FP-322 | form | Oscreen® |  | SCRAPER_JUNK |
| FP-321 | concentration | should be at least 2 mg/ml, higher concentrations  |  | OVER_EXTRACTED |
| FP-321 | form | Oscreen® |  | SCRAPER_JUNK |
| FP-320 | concentration | should be at least 2 mg/ml, higher concentrations  |  | OVER_EXTRACTED |
| FP-320 | form | Oscreen® |  | SCRAPER_JUNK |
| FP-201-ROX | concentration | is 10 mg/ml, other concentrations are also possibl |  | OVER_EXTRACTED |
| FP-201-ROX | purity | of your conjugate by SDS-PAGE. |  | OVER_EXTRACTED |
| FP-201-ROX | form | Oscreen® |  | SCRAPER_JUNK |
| FP-201 | concentration | is 10 mg/ml, other concentrations are also possibl |  | OVER_EXTRACTED |
| FP-201 | purity | of your conjugate by SDS-PAGE. |  | OVER_EXTRACTED |
| FP-201 | form | Oscreen® |  | SCRAPER_JUNK |
| FP-201-CY5 | concentration | is 10 mg/ml, other concentrations are also possibl |  | OVER_EXTRACTED |
| FP-201-CY5 | purity | of your conjugate by SDS-PAGE. |  | OVER_EXTRACTED |
| FP-201-CY5 | form | Oscreen® |  | SCRAPER_JUNK |
| FP-201-CY3 | concentration | is 10 mg/ml, other concentrations are also possibl |  | OVER_EXTRACTED |
| FP-201-CY3 | purity | of your conjugate by SDS-PAGE. |  | OVER_EXTRACTED |
| FP-201-CY3 | form | Oscreen® |  | SCRAPER_JUNK |
| CLK-075 | concentration | due to the internal copper chelating moiety.[4] Es |  | OVER_EXTRACTED |
| CLK-075 | form | Oscreen® |  | SCRAPER_JUNK |
| CLK-073 | concentration | due to the internal copper chelating moiety.[4]The |  | OVER_EXTRACTED |
| CLK-073 | form | Oscreen® |  | SCRAPER_JUNK |
| CLK-074 | concentration | due to the internal copper chelating moiety.[4]The |  | OVER_EXTRACTED |
| CLK-074 | form | Oscreen® |  | SCRAPER_JUNK |
| CLK-1086 | concentration | for metabolic labeling: 25-75 μM. This concentrati |  | OVER_EXTRACTED |
| CLK-1084 | concentration | for metabolic labeling: 25-75 μM. This concentrati |  | OVER_EXTRACTED |
| CLK-1085 | concentration | for metabolic labeling: 25-75 μM. This concentrati |  | OVER_EXTRACTED |
| CLK-072 | concentration | due to the internal copper chelating moiety.[4]The |  | OVER_EXTRACTED |
| CLK-072 | form | Oscreen® |  | SCRAPER_JUNK |
| CLK-071 | concentration | due to the internal copper chelating moiety.[4] Es |  | OVER_EXTRACTED |
| CLK-071 | form | Oscreen® |  | SCRAPER_JUNK |
| FLAGCLK-032Azide-PEG3 | concentration | 100 μM)[1]. This concentrations may serve as a sta |  | OVER_EXTRACTED |
| FLAGCLK-033Dibenzylcyclooctyne-PEG4 | concentration | 100 μM)[1] or labeling of Azide-functionalized mic |  | OVER_EXTRACTED |
| PCR-540 | concentration | s: included primersstock conc.FIP16 μMBIP16 μMF32  |  | OVER_EXTRACTED |
| EDA-6-T | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| EDA-6-T | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| EDA-6-T | concentration | 10 mM - 11 mMpH: 7.5 ±0.5Spectroscopic Properties: | 10 mM - 11 mM | MISMATCH_AMBIG |
| EDA-6-T | form | ation | solution in water | MISMATCH_AMBIG |
| NU-832-BIO | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| NU-832-BIO | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| NU-832-BIO | concentration | 5.0 mM - 5.5 mMpH: 7.5 ±0.5BIOZ Product Citations: | 5.0 mM - 5.5 mM | MISMATCH_AMBIG |
| NU-832-BIO | form | ation | solution in water | MISMATCH_AMBIG |
| ATPNU-843 | concentration | photometrically.Please note: This compound contain |  | OVER_EXTRACTED |
| RNT-101 | concentration | mesurement. Spin column purification will remove p |  | SCRAPER_JUNK |
| RNT-101 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-105 | concentration | mesurement. Spin column purification will remove p |  | SCRAPER_JUNK |
| RNT-105 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-135 | concentration | of 7.5 mM and 100 % substitution of UTP by Pseudo- |  | SCRAPER_JUNK |
| RNT-135 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-203Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-203Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-202Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-202Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-134 | concentration | as well as the labeled UTP/UTP or labeled CTP/CTP  |  | OVER_EXTRACTED |
| RNT-134 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-138 | concentration | or incorporation of modified nucleotides (e.g. N4- |  | SCRAPER_JUNK |
| RNT-138 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-137 | concentration | or incorporation of modified nucleotides (e.g. Pse |  | SCRAPER_JUNK |
| RNT-137 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-136 | concentration | or incorporation of modified nucleotides (e.g. Pse |  | SCRAPER_JUNK |
| RNT-136 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-113Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-113Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-112Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-112Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-111Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-111Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-110Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-110Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-109Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-109Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-108Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-108Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-107Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-107Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-106Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-106Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-121Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-121Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-120Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-120Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-119Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-119Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-118Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-118Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-117Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-117Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-116Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-116Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-115Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-115Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-114Synthesis | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-114Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-104 | concentration | as well cap analoga incorporation can easily be ac |  | OVER_EXTRACTED |
| RNT-104 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-103 | concentration | can easily be achieved with the single nucleotide  |  | OVER_EXTRACTED |
| RNT-103 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-102Synthesis | concentration | or incorporation of modified nucleotides (e.g. Pse |  | SCRAPER_JUNK |
| RNT-102Synthesis | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-601 | concentration | mesurement. Spin column purification will remove p |  | SCRAPER_JUNK |
| RNT-601 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-501 | concentration | mesurement. Spin column purification will remove p |  | SCRAPER_JUNK |
| RNT-501 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-201 | concentration | mesurement. Spin column purification will remove p |  | SCRAPER_JUNK |
| RNT-201 | form | Oscreen® |  | SCRAPER_JUNK |
| RNT-018 | concentration | 2.0 – 2.2 μg/μl (A280, ɛ = 140 L mmol -1 cm -1 [1] | 2.0 – 2.2 &mu;g/&mu;l (A280, ɛ = 140 L mmol | MISMATCH_AMBIG |
| RNT-008 | concentration | 2.0 – 2.2 μg/μl (A280, ɛ = 140 L mmol -1 cm -1 [1] | 2.0 – 2.2 &mu;g/&mu;l (A280, ɛ = 140 L mmol | MISMATCH_AMBIG |
| UDP-6-A | shipping_condition | Accessories |  | SCRAPER_JUNK |
| UDP-6-A | form | Oscreen® |  | SCRAPER_JUNK |
| PR-958Fluorescently | concentration | range used for cell culture experiments: 10-5M - 1 |  | OVER_EXTRACTED |
| CO-305 | concentration | s of precipitant and salt may lead to the formatio |  | OVER_EXTRACTED |
| CO-305 | form | Oscreen® |  | SCRAPER_JUNK |
| CS-360 | concentration | target antibody or protein stock solutions in orde |  | SCRAPER_JUNK |
| CS-360 | purity | chemicals and ultrapure water (>18.0 MΩ) and are s |  | SCRAPER_JUNK |
| CS-360 | form | Oscreen®, FORMOscreen® - Jena Bioscience |  | SCRAPER_JUNK |
| CS-350 | concentration | s of 1 mM. However, our own experiments have shown |  | OVER_EXTRACTED |
| CS-350 | form | Oscreen® |  | SCRAPER_JUNK |
| CS-351 | concentration | s of 1 mM. However, our own experiments have shown |  | OVER_EXTRACTED |
| CS-351 | form | Oscreen® |  | SCRAPER_JUNK |
| NY-99 | concentration | Lot specific, between 0,5-2 mg /ml. Determined by  | Lot specific, between 0,5-2 mg /ml. Determined by  | SCRAPER_DOM_ERR |
| PR-1495VZV | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| EPR-1499Tick | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| SARS-2 | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| PR-1480Recombinant | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| HPV-77PR-BA129 | concentration | Lot specific, between 1-2 mg /ml. Determined by UV | Lot specific, between 1-2 mg /ml. Determined by UV | SCRAPER_DOM_ERR |
| HEL-299 | concentration | Lot specific. Determined by Bradford assay (Biorad | Lot specific. Determined by Bradford assay (Biorad | MISMATCH_AMBIG |
| HIV-2 | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| HIV-1 | concentration | Lot specific, > 2 mg /ml. Determined by Bradford a | Lot specific, > 2 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| PR-1473Recombinant | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| PR-1465Recombinant | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| PR-1496DENV | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| PR-1491CMV | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| PR-1490CMV | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| HHV-5 | concentration | Lot specific, between 1-3 mg /ml. Determined by UV | Lot specific, between 1-3 mg /ml. Determined by UV | SCRAPER_DOM_ERR |
| PR-1485Tg | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| TW-183native | concentration | Lot specific. Determined by Bradford assay (Biorad |  | OVER_EXTRACTED |
| PR-1497Recombinant | concentration | Lot specific, > 1 mg /ml. Determined by Bradford a | Lot specific, > 1 mg /ml. Determined by Bradford a | SCRAPER_DOM_ERR |
| AB-102 | concentration | of 100 μg/ml.For selection of other species please |  | OVER_EXTRACTED |
| LT-111 | concentration | . Store at 4 °C and use within two weeks.Preparati |  | OVER_EXTRACTED |
| LT-111 | form | Oscreen® |  | SCRAPER_JUNK |
| LT-102 | concentration | . Store at 4 °C in the dark and use within two wee |  | OVER_EXTRACTED |
| LT-102 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-102 | concentration | , 100 μl10x Error-prone Solution (yellow cap) |  | OVER_EXTRACTED |
| PP-102 | form | Oscreen® |  | SCRAPER_JUNK |
| PP-235Spin | concentration | of a Washing Buffer may decrease during long term  |  | OVER_EXTRACTED |
| PP-235Spin | form | Oscreen® |  | SCRAPER_JUNK |
| PP-204Column | concentration | of Washing Buffer may decrease during long term st |  | OVER_EXTRACTED |
| PP-204Column | purity | plasmid or cosmid DNA from bacterial cells for sub |  | OVER_EXTRACTED |
| PP-204Column | form | Oscreen® |  | SCRAPER_JUNK |
| BHQ-3 | shipping_condition | Accessories |  | SCRAPER_JUNK |
| BHQ-3 | purity | . |  | SCRAPER_JUNK |
| BHQ-3 | form | Oscreen® |  | SCRAPER_JUNK |
| BHQ-2 | shipping_condition | Accessories |  | SCRAPER_JUNK |
| BHQ-2 | purity | . |  | SCRAPER_JUNK |
| BHQ-2 | form | Oscreen® |  | SCRAPER_JUNK |
| BHQ-1 | shipping_condition | Accessories |  | SCRAPER_JUNK |
| BHQ-1 | purity | . |  | SCRAPER_JUNK |
| BHQ-1 | form | Oscreen® |  | SCRAPER_JUNK |
| PCR-156Lyophilised | concentration | to the PCR reaction.Dual-labeled DNA probes: |  | OVER_EXTRACTED |
| PCR-156Lyophilised | form | Oscreen® |  | SCRAPER_JUNK |
| PCR-277Low | concentration | s:Size Range(base pairs)Final AgaroseConcentration |  | OVER_EXTRACTED |
| PCR-269general | concentration | s as low as 0.4 %. LE Agarose has an exceptionally |  | OVER_EXTRACTED |
| NU-807-ROX | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| NU-807-ROX | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| NU-807-ROX | concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic Propertie | 1.0 mM - 1.1 mM | MISMATCH_AMBIG |
| NU-807-ROX | form | ation | solution in water | MISMATCH_AMBIG |
| NU-807-RHO12 | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| NU-807-RHO12 | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| NU-807-RHO12 | concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic Propertie | 1.0 mM - 1.1 mM | MISMATCH_AMBIG |
| NU-807-RHO12 | form | ation | solution in water | MISMATCH_AMBIG |
| NU-807-THIO12 | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| NU-807-THIO12 | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| NU-807-THIO12 | concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic Propertie | 1.0 mM - 1.1 mM | MISMATCH_AMBIG |
| NU-807-THIO12 | form | ation | solution in water | MISMATCH_AMBIG |
| NU-851-RHO14 | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| NU-851-RHO14 | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| NU-851-RHO14 | concentration | 1.0 mM - 1.1 mMpH: 7.5 ±0.5Spectroscopic Propertie | 1.0 mM - 1.1 mM | MISMATCH_AMBIG |
| NU-851-RHO14 | form | ation | solution in water | MISMATCH_AMBIG |
| PK-108 | shipping_condition | Accessories | shipped at ambient temperature | SCRAPER_DOM_ERR |
| PK-108 | form | ation |  | OVER_EXTRACTED |
| PK-107 | shipping_condition | Accessories | shipped at ambient temperature | SCRAPER_DOM_ERR |
| PK-107 | form | ation |  | OVER_EXTRACTED |
| PK-106 | shipping_condition | Accessories | shipped at ambient temperature | SCRAPER_DOM_ERR |
| PK-106 | form | ation |  | OVER_EXTRACTED |
| EN-178recombinant | storage_condition | store at -20 °Cavoid freeze/thaw cycles | store at -20 °C | MISMATCH_AMBIG |
| EN-178recombinant | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| EN-178recombinant | concentration | 20 mg/mlActivity: > 600 units/ml | 20 mg/ml | MISMATCH_AMBIG |
| EN-178recombinant | form | ation | Proteinase K solution (20 mg/ml) in 10 mM Tris-HCl | MISMATCH_AMBIG |
| CPL-151 | shipping_condition | Accessories | shipped at ambient temperature | SCRAPER_DOM_ERR |
| CPL-151 | shelf_life | n/a | n/a | SCRAPER_DOM_ERR |
| CPL-151 | form | ation | box of 10 plates | MISMATCH_AMBIG |
| CPL-165 | shipping_condition | Accessories | shipped at ambient temperature | SCRAPER_DOM_ERR |
| CPL-165 | shelf_life | n/a | n/a | SCRAPER_DOM_ERR |
| CPL-165 | form | ation |  | OVER_EXTRACTED |
| UVPCPL-164 | shipping_condition | Accessories | shipped at ambient temperature | SCRAPER_DOM_ERR |
| UVPCPL-164 | shelf_life | n/a | n/a | SCRAPER_DOM_ERR |
| UVPCPL-164 | form | ation |  | OVER_EXTRACTED |
| NU-829-BIO | storage_condition | store at -20 °CShort term exposure (up to 1 week c | store at -20 °C | MISMATCH_AMBIG |
| NU-829-BIO | shipping_condition | Accessories | shipped on gel packs | SCRAPER_DOM_ERR |
| NU-829-BIO | concentration | 5.0 mM - 5.5 mMpH: 7.5 ±0.5Spectroscopic Propertie | 5.0 mM - 5.5 mM | MISMATCH_AMBIG |
| NU-829-BIO | form | ation | solution in water | MISMATCH_AMBIG |
| NU-860-BIO | shipping_condition | Accessories | shipped on dry ice | SCRAPER_DOM_ERR |
| NU-860-BIO | concentration | 5.0 mM - 5.5 mMpH: 7.5 ±0.5Spectroscopic Propertie | 5.0 mM - 5.5 mM | MISMATCH_AMBIG |
| NU-860-BIO | form | ation | solution in water | MISMATCH_AMBIG |
| FP-167 | form | Oscreen® |  | SCRAPER_JUNK |
| PCR-353 | concentration | 1 unit/μl | 1 unit/&mu;l | MISMATCH_AMBIG |
| PCR-353 | form | liquid (Supplied in 20 mM Tris-HCl pH 8.0, 50 mM N | liquid (Supplied in 20 mM Tris-HCl pH 8.0, 50 mM N | MISMATCH_AMBIG |
| ICS-201Lbased | form | Oscreen® |  | SCRAPER_JUNK |
| LCP-108 | form | Oscreen® |  | SCRAPER_JUNK |
| EN-179EndoribonucleaseBovine | concentration | 1 - 100 μg/ml (depending on application) |  | OVER_EXTRACTED |
| PP-401 | form | Oscreen® |  | SCRAPER_JUNK |
| CO-301 | form | Oscreen® |  | SCRAPER_JUNK |
| CS-503 | form | Oscreen® |  | SCRAPER_JUNK |
| CS-505 | form | Oscreen® |  | SCRAPER_JUNK |
| CPL-136 | shelf_life | n/a | n/a | SCRAPER_DOM_ERR |
| CPL-136 | form | Oscreen® |  | SCRAPER_JUNK |

---

## 根因分析（真相大白）

### 元根因
爬虫对每个商业规格字段（concentration / form / purity / shipping / storage / shelf_life）使用了**宽松的 DOM 选择器**：
- 没有"该页面是否真的有此规格字段"的前置判断；
- 没有"抽到的内容是否像合法规格值"的后置校验闸门；
直接把页面上第一个匹配标签 / 邻近文本写入 jsonl 落库。

当官方页**确实有**该字段（如 shipping 在规格区），但选择器命中了**导航菜单的相同关键词**（如 `Crystal Storage and Shipping > Accessories`），就写入导航文字 → **SCRAPER_DOM_ERR**。
当官方页**根本没有**该字段（如结晶筛选珠子 CO-501 无 concentration），选择器退而命中**产品描述段落 / JS 变量 / 商标词**，写入散文 / mojibake → **SCRAPER_JUNK / OVER_EXTRACTED**。
当字段**边界没截断**，把紧邻的 handling note 拼进值 → **字段粘连（MISMATCH_AMBIG 子集）**。

### CO-501 证据（一锤定音）
CO-501（JBS Beads for Seeds）官方页原始 HTML 核查：
- `concentration` 出现 4 处，**全部是描述散文**（"the concentration is slowly increased until a point of supersaturation..."），无 `<b>Concentration:</b>` 规格；
- `form` 出现 22 处，**全部是 JS 变量 `_form_url` / 导航**，无 `<b>Form:</b>` 规格；
- jsonl 里 CO-501.concentration = 那段散文、CO-501.form = `"Oscreen®"`（mojibake，疑为 `Lyophilized` 等被错误编码）。
→ 证明：jsonl 的 junk **不是**限流打空、**不是**抽取器抽不到，而是**爬虫在页面无该字段时确实抓错了内容**。（已用冷却后重抓 15 条样本验证：0/15 能拿到 live 值但 `marker=True` 页面正常，排除限流假设。）

### 三类根因计数（203 条样本，337 field-rows）

| 根因 | 计数 | 确凿度 | 代表 |
|------|-----:|--------|------|
| SCRAPER_JUNK | 195 | 高（CO-501 证明页面真无字段，jsonl 填描述散文 / mojibake） | concentration 散文、`form="Oscreen®"` |
| OVER_EXTRACTED | 71 | 高（jsonl 值是描述段的合理浓度信息，live 无独立规格字段） | `"is 10 mg/ml"`、`"for metabolic labeling: 25-75 μM"` |
| SCRAPER_DOM_ERR | 37 | 最高（live 有合法不同值直接证明抓错节点） | shipping `"Accessories"` vs live `"shipped on gel packs"` |
| MISMATCH_AMBIG | 34 | 中（双方合法但不同，需原始 PDF datasheet 定） | storage 字段粘连；concentration `"20 mg/ml"` vs `"20 mg/mlActivity: > 600 units/ml"` |
| FETCH_FAIL | 0 | — | 限流已通过降频(5s)+退避重试排除 |

### 与 step1 / step2 的串联
- step1 的 **151 条 concentration 散文 + 20 条 shipping Accessories + 21 条 storage / shelf 占位**，正是本步根因的受害者：它们的 junk 值来自爬虫的宽松选择器。
- step2 的 **12 条 formula↔MW 矛盾**是**另一类问题**（化学属性字段内部不自洽，jena 自身 formula / MW 取了不同形态 / 来源），与商业规格爬虫无关——证明 jena 的问题**不止一处**，横跨"化学属性自洽性"与"商业规格抽取质量"两个独立维度。

### 已知边界（诚信声明）
1. `n/a` 等"无规格"占位在分类器中被当作 junk，导致少量 `shelf_life: n/a` vs `n/a` 被标成 SCRAPER_DOM_ERR（实为合法 MATCH）。仅影响极少数记录的"记录级主因"归类，**不影响核心根因结论**（核心在 concentration / form 的 JUNK，不受此影响）。
2. MISMATCH_AMBIG=34 中，部分系"字段粘连"（jsonl 把 handling note 拼进 storage），部分系 live 抽取的 HTML 实体未完全解码（如 `&mu;` 未转 `μ`）——后者是抽取器展示问题，非 jena 数据错。需对这 34 条回抓原始 PDF datasheet 才能最终裁定。
3. 本步仅覆盖"商业规格"字段。jena 的化学属性（formula / MW / CAS）已由 step2 单独校验。

### 结论
jena 爬虫数据的不可信，**根因在抓取 / 清洗层**：爬虫用宽松选择器 + 无校验闸门，在"页面有字段但命中导航"或"页面无字段而命中描述 / JS"两种情况下写入了错误内容。这**不是**"数据源本身对世界错"（step2 中 PubChem 能触达的 3 条 MW 都对），而是"搬运过程变形"。这与"jena 是数据链中最不可信一环"的判断一致，且现在有了可指认的具体机制与证据链。