# PO 采购门户 · 功能设计行业对标审查（Industry Fit Review）

| 项 | 内容 |
|---|---|
| **审查对象** | `docs/po-portal/PRD.md`（PRD v0.1）+ `docs/po-portal/ARCHITECTURE.md`（架构设计 v1） |
| **审查目标** | 确认该功能设计 ①**是否符合实验室采购逻辑** ②**是否符合欧美（以美国为主）生化试剂 B2B 采购的行业通用流程** |
| **审查日期** | 2026-10-13 |
| **审查方法** | 外部行业惯例调研（多源公开检索交叉验证）+ 本项目设计文档事实抽取（带行号）；由主理人逐条对照判定 |
| **结论摘要** | 骨架符合行业惯例：**✅ 符合 6 条 / 🟡 部分符合 5 条 / ❌ 缺失 1 条**；另发现 **2 处设计文档内在不一致** |
| **文档状态** | **待主理人决策** —— 本审查只给结论与建议，**未改动任何设计文档、模型或代码** |

---

## 0. 结论速览

| # | 行业硬性惯例 | 本项目设计 | 判定 |
|---|---|---|---|
| 1 | 先 Quote 后 PO 是机构采购**默认路径** | 承认该习惯（PRD:34），但 Quote→PO 仅列 **P1**、`Order.quote` **可空**（ARCH:188） | 🟡 |
| 2 | 「无 PO 不发货 / 无 PO 不付款」，发票必带 PO 号 | `Order.po_number` + ARCH **R4 加 unique** | ✅ |
| **3** | **免税（sales tax exemption）** | **全文未提及**（仅有 `tax_total` 金额字段，无免税规则） | **❌** |
| 4 | bill-to / ship-to **分离** | ARCH **R8 新建 `Address` 表**（`type=BILLING/SHIPPING`） | ✅ |
| 5 | grant / 基金号标记 | `Order.grant_code`（ARCH:184） | ✅ |
| 6 | 新供应商注册（供应商向机构报 W-9 / ACH） | 属线下流程；PRD:14 已声明「供应商向大学注册」为**不构建范围** | ✅ |
| 7 | Net30 为默认账期，Net45/60 面向大客户 | NET30 默认 + 开票台可选 Net30/Net45 | ✅ |
| 8 | 30/60/90 账龄 + 分级催收 + **部分付款核销** | 账龄 ✅ 催款（到期前 7 天 / 超期 30 天）✅ **部分付款仅列 P2** | 🟡 |
| 9 | COA / SDS 随货或可下载 | 商品页下载 + 发货台**每批次 COA 上传** | ✅ |
| 10 | 冷链 / 干冰 / 危险品按 **UN 编号 + IATA/DOT** | 冷链 ✅ 干冰（运输方式）✅ **hazmat / UN 编号未建模** | 🟡 |
| 11 | 分批发 / backorder + **主动通知** | 分批发语义完整（ARCH:225-230） | ✅ |
| 12 | 登录后显示**账户价**、实时库存、reorder、双支付 | 库存 / lead time ✅ reorder(P2) ✅ PO+信用卡 ✅ **账户价 / 合同价未提及** | 🟡 |

**一句话结论**：**骨架是对的** —— PO 号强制、bill-to/ship-to 分离、Net30 + 30/60/90 账龄、每批次 COA、分批发语义（这一条做得比行业通行做法更严谨）、基金号，都是**懂行**的设计。**但有 1 个硬缺口（免税）会让美国大学客户在财务环节卡住**，另有 3 处需要补齐或提前排期。

---

## 1. 审查方法

### 1.1 两路取证

| 路 | 用途 | 做法 |
|---|---|---|
| **外部** | 建立「行业标尺」 | 对 6 个方面做多源公开检索并交叉比对（大学采购政策、供应商官网帮助中心、运输合规指南、AR 实务指南），产出 **12 条硬性惯例清单**（来源见附录 A） |
| **内部** | 提取「我方面貌」 | 通读 PRD 与 ARCHITECTURE，**原样抽取**设计事实并标注行号（来源见附录 B），**不使用行业知识补全** |

### 1.2 判定口径

| 判定 | 含义 |
|---|---|
| ✅ 符合 | 设计已覆盖该惯例，且与行业做法一致 |
| 🟡 部分符合 | 设计有相关能力但**不完整**，或**分级过低**（排到 P2 而行业视为必要） |
| ❌ 缺失 | 设计中完全未提及 |

### 1.3 本次审查的边界（如实声明）

- 行业惯例来自**公开来源**，部分为定性描述（如「Net30 最常见」），各来源未给出统一可核验的定量比例；如需精确渗透率需另做定量调研。
- ATCC、Bio-Rad 的账户与下单流程**未取得一手页面佐证**，未采信第三方转述。
- 本审查**只判定「设计是否符合行业逻辑」，不评价实现质量**（实现层问题见另行记录）。

---

## 2. 硬缺口详述：免税（Sales Tax Exemption）

### 2.1 行业事实

- **美国公立高校依法免缴州 / 地方销售税**，且通常要求「必须用 University PO / P-Card 采购并直接付款给卖方」才可享受；供应商若索要凭证，机构提供**州免税证明**即可（如 Arizona Form 5000「研究用化学品 / 研发设备」专项免税证书、Rochester 免税号 125542 / NYS 免税证书）。
- **供应商侧义务**：**须接受免税证书并免收销售税**。主流平台印证：**VWR / Avantor 明确规定「Guest Profile 不享有 tax exempt 资格」**，开立账户时须提供免税号 —— 说明免税资格是与**账户/机构**绑定的属性。

### 2.2 本项目现状

- PRD 与 ARCHITECTURE **全文未提及**免税（`tax exemption` / `tax_exempt` / 免税）。
- 仅存在金额字段 `tax_total`（PRD:218），**但没有任何免税规则**。

### 2.3 风险

美国大学客户在结账 / 付款环节看到含税金额时，**通常会拒付税款或整单挂起**，需要人工介入对账 —— 即**这不是"锦上添花"，而是"能否成交"的前置条件**。

### 2.4 建议补法（最小改动）

| 项 | 内容 |
|---|---|
| 数据 | `Organization.tax_exempt_id`（免税号，可空） |
| 逻辑 | 提交 PO / 开票时按机构免税状态置 `tax_total = 0` |
| 票据 | Invoice PDF 上标注 `Tax Exempt ID`（行业惯例做法） |
| 优先级 | **P0** —— 建议不低于其他 P0 项 |

---

## 3. 部分符合项详述

### 3.1 Quote → PO 未成为默认路径（惯例 #1）

**行业事实**：机构 / 竞争性采购普遍把「询价（RFQ/Quotation）」作为流程第 1 步、PO 作为获批后步骤（如 Victoria University 采购程序明确 Step1 询价 → Step3 PO；Rochester 大学规定交易额超过阈值须先取竞争性报价）。**但对标准目录品，授权账户在线直接下单（信用卡或 PO）亦被广泛接受**，报价可「按需」而非强制。

**本项目现状**：PRD 角色 A 故事 2（PRD:34）明确描述「先生成 Quote，确认价格后再关联 Quote 号提交 PO」这一**客户习惯**；但 **P1-2 才把它列为 P1**（PRD:66），且 `Order.quote` 设计为**可空**（ARCH:188），PRD P0-2 提交流程（PRD:60）亦未要求 Quote 必填。

**判定**：🟡 —— **不强制是符合行业的**（标准品可直下单），但**建议在客户端 UI 上把「请求报价」做成一等公民**（与「用 PO 结账」并列），而不是埋在 P1。

### 3.2 部分付款分级过低（惯例 #8）

**行业事实**：收到部分款时应「**先核销、余额保持 open、记录短付原因**」，而非默认按最旧发票冲抵；这是 AR 的标准实务。

**本项目现状**：AR Aging 30/60/90 ✅（P1-4）、分级催款 ✅（到期前 7 天 / 超期 30 天，PRD:200），但**部分付款核销列为 P2**（PRD:45 / PRD:72 / PRD:190）。

**判定**：🟡 —— `PaymentRecord` 多笔天然支持部分付款（PRD:221），**建议把 `Invoice.balance_due` 的定案从 P2 提到 P1**；注意 ARCH §8.2 #3 尚待拍板「存储字段 vs 派生属性」。

### 3.3 hazmat / UN 编号未建模（惯例 #10）

**行业事实**：干冰 = **UN1845**（Class 9，空运须符合 IATA PI954，**包装必须透气**）；液氮 = UN1977；感染性物质 Category B = UN3373。危险品须按 DOT / IATA / IMDG 分类、标签、申报。

**本项目现状**：运输方式含 `Ambient / Cold Pack / Dry Ice / Blue Ice`（PRD:111）、`DRY_ICE`（ARCH:185）、冷链温度记录（P2）；但 **hazmat 分类与 UN 编号未建模**。

**判定**：🟡 —— 建议补 `SKU.hazmat_class` + `SKU.un_number`，并在发货单 / Packing List 上打印运输合规提示。

### 3.4 账户价 / 合同价缺失（惯例 #12）

**行业事实**：主流平台（Thermo Fisher、Sigma-Aldrich / Merck、VWR）均为「**未登录仅显示目录价，登录后显示账户 / 合同价**」，且实时库存与 lead time 也需登录可见。

**本项目现状**：有实时库存徽标与 lead time（PRD:33 / PRD:89）、reorder（P2）、PO + 信用卡双支付 ✅；但**只有 `SKU.price` 目录价**，未见机构级 / 合同价概念（批量折扣阶梯也被延后到 P2，ARCH:637）。

**判定**：🟡 —— 对大学大客户，**合同价 vs 目录价是常态**，缺这块会让客户看到「不对的价格」并质疑。建议 P1 补机构级价格，或在 UI 明确标注「合同价待议」。

---

## 4. 设计文档内在不一致（2 处）

> 这两条**不是行业问题**，是设计文档**自身前后矛盾**，建议先修正以免误导实现。

| # | 不一致 | 位置 | 建议 |
|---|---|---|---|
| 1 | **PRD 故事 2** 把「先 Quote 后 PO」写成客户**本能习惯**，但 **P1-2 把 Quote→PO 列为 P1** ⇒ 叙事与需求分级冲突（按故事它应是 P0） | PRD:34 vs PRD:66 | 二者取一：要么把 Quote→PO 提到 P0，要么在故事里弱化为「可选」 |
| 2 | **P2-4「客户自助注册供应商」** —— 行业术语 `vendor onboarding` 指「**供应商**向机构注册（报 W-9 / ACH / 银行信息）」，**方向正好相反** | PRD:74 | 改名（如「客户账户自助注册」），避免后续实现理解偏差 |

---

## 5. 建议动作（按性价比排序）

| 序 | 动作 | 优先级 | 影响 |
|---|---|---|---|
| 1 | **补免税**：`Organization.tax_exempt_id` + 结账 / 开票按机构免税状态置 `tax_total=0` + 发票标注 Tax Exempt ID | **P0** | 不补则美国大学客户**在财务环节卡住** |
| 2 | **补账户价 / 合同价**（或先 UI 标注「合同价待议」） | P1 | 大客户看到目录价会质疑 |
| 3 | **部分付款从 P2 提到 P1**（并拍板 `balance_due` 存储 vs 派生） | P1 | 行业视为必要 AR 能力 |
| 4 | **补 `SKU.hazmat_class` + `un_number`**，发货单打印运输合规提示 | P1/P2 | 卖危险品试剂时出货合规信息缺失 |
| 5 | **修正 2 处文档内在不一致**（§4） | P0（低成本） | 避免误导实现 |
| 6 | 客户端把「请求报价」与「用 PO 结账」做**并列一等公民** | P1 | 贴合机构采购习惯 |
| 7 | `Net60` 条款（当前仅 Net30 / Net45） | P2 | 面向更大型买方 / 公共部门 |

---

## 6. 与另一项已发现问题的关系（上下文，非本审查范围）

本审查只针对**设计是否符合行业逻辑**。另有一项**流程层发现**（已在别处记录）：PO 域在设计期**只做了「单方设计产出 + 架构师对模型的 R1~R8 勘误」，从未从各角色视角做过对抗性交叉审核**；且 `docs/TEST_PLAN_ORDER_FLOW.md` 预设的 78 个用例与 8 个 E2E 场景**已随实现演进而失效、E2E 从未落地**。
⇒ **建议把「分角色走查」制度化**（客户 / 采购 / 财务 / 管理员各走一遍全流程）—— 本次行业对标审查发现的缺口，正是这类走查应当命中的目标。

---

## 附录 A：行业惯例来源（外部调研）

> 说明：以下为本次检索所依据的公开来源类型与代表站点；部分结论为定性描述，各来源未给统一可核验的定量比例。

| 方面 | 代表来源 |
|---|---|
| 试剂采购链路 / 最佳实践 | benchchem.com（采购流程指南）、aresresearchlab.com（高纯试剂采购指南）、changyubio.com（供应商流程） |
| 「先询价后 PO」 | Victoria University Purchasing Procedure、rochester.edu（竞争性报价规定）、earthsciences.osu.edu、csusb 研究材料申请要求 |
| 「无 PO 不付款」政策 | gallaudet.edu（政策 2.06B）、bathspa.ac.uk、bath.ac.uk、policy.vu.edu.au、up.ac.za、marymount.edu |
| 免税 | cu.edu（免税指引 DR 0160 / DR 5002）、arizona.edu（Form 5000）、rochester.edu（免税号 125542）、ewu.edu、vwr.com（Guest 不享免税） |
| bill-to / ship-to 分离 | thermofisher.com（Order FAQ）、vwr.com、addgene.org、simplerbill.com、legalclarity.org |
| grant / 资金来源 | earthsciences.osu.edu（WORKTAG）、procurement.umich.edu（2 CFR 200）、buffalo.edu、csusb.qualtrics.com |
| 新供应商注册 | marymount.edu、uwyo.edu、fordham.edu、cornell.edu（PaymentWorks / Jaggaer） |
| 账期与 AR | dodopayments.com、invoicelabs.io、creditpulse.com、resolvepay.com、Sigma-Aldrich e-Commerce FAQ、addgene.org、arizona SAAM（Delinquent Debt Processing）、paidnice.com、monk.com |
| COA / SDS | thermofisher.com（产品文档）、vwr.com（C of A / SDS）、fishersci.com、neb.com、aresresearchlab.com |
| 冷链 / 危险品 | casrai.org、WHO 运输指南、cdc.gov、pha.gov.sa（干冰 UN1845 / IATA PI954；液氮 UN1977；UN3373） |
| 分批发 / backorder | crmlabstandard.com（TOS 1.21）、labxsci.com、vortexresearch.net、herbilabs.co.uk |
| 平台对标 | thermofisher.com（Account Dashboard / eProcurement）、fishersci.com、sigmaaldrich（e-Commerce FAQ）、vwr.com、addgene.org、neb.com |
| 反模式 | ranktracker.com、virtina.com、comgem.com、dakwp.com、aresresearchlab.com |

**未取得一手佐证**：ATCC、Bio-Rad 的账户与下单流程（仅命中第三方转述，未采信）。

---

## 附录 B：本项目设计事实来源（行号索引）

| 事实 | 出处 |
|---|---|
| 三角色定义 | `PRD.md:30-50`（A 客户 Requestor / B 内部 Sales Rep / C 内部 Admin） |
| 确认状态机（8 态） | `PRD.md:15-16`；`ARCHITECTURE.md:203-223`（canonical） |
| 状态机勘误（旧态 deprecated） | `ARCHITECTURE.md:20`（R5） |
| 分批发语义与 DELIVERED 判定 | `ARCHITECTURE.md:225-230` |
| 需求池 P0 / P1 / P2 | `PRD.md:58-62` / `PRD.md:64-68` / `PRD.md:70-74` |
| 客户侧六节点 | `PRD.md:83-141` |
| 内部侧节点 A~E | `PRD.md:143-191`；`ARCHITECTURE.md:481-515` |
| bill-to / ship-to 分离 | `PRD.md:35`、`PRD.md:107-108`；`ARCHITECTURE.md:23`（R8）、`:147`、`:189-190` |
| grant / 基金号 | `PRD.md:35`、`PRD.md:110`；`ARCHITECTURE.md:184`、`:436` |
| 免税（无） | — **全文未提及**（仅 `tax_total`，`PRD.md:218`） |
| 供应商注册 | `PRD.md:14`（列为不构建范围）、`PRD.md:74`（P2-4） |
| 账期与账龄与催款 | `PRD.md:44-45`、`PRD.md:68`、`PRD.md:200`；`ARCHITECTURE.md:85`、`:547-548` |
| COA / SDS | `PRD.md:59`、`:88`、`:169`、`:224` |
| 运输方式 / 冷链 | `PRD.md:111`、`PRD.md:43`、`PRD.md:71`、`PRD.md:171`；`ARCHITECTURE.md:185` |
| reorder | `PRD.md:38`、`:73`、`:141` |
| 库存与 lead time | `PRD.md:33`、`:65`、`:89`、`:149`；`ARCHITECTURE.md:162-163` |
| 权限边界 | `ARCHITECTURE.md:636`（§8.1 #5）、`:110`、`:183` |
| PRD §6 待确认 10 项 | `PRD.md:229-240` |
| ARCH §8.1 / §8.2 待拍板项 | `ARCHITECTURE.md:631-650` |

---

*本审查由主理人依据「外部行业惯例调研」与「本项目设计文档事实抽取」两路证据综合判定；判定口径与边界见 §1。文档状态：待主理人决策。*
