# 美国实验室 B2B 采购门户 PRD

> 文档归属：SciReAgent / 产品经理许清楚（Xu）
> 配套权威设计文档：`PO采购流程与供应商网站功能设计.md`（下称"设计文档"）
> 配套设计系统：`docs/DESIGN_STANDARDS.md`（下称"DESIGN_STANDARDS"）
> 技术栈：Django 5.1.3 + DRF（View→Service→Model，API 信封 `{success,data,meta}`）/ Vue3 + Vite + Pinia
> 文档状态：PRD v0.1（待主理人评审 + 待确认问题清单闭环）

---

## 0. 范围与前置约束（约束性，PRD 必须遵守）

- **本次构建范围**：设计文档第二（客户自助端）、三（内部管理端）、四（自动化邮件）、五（DB 落地）部分。
- **不构建范围**：设计文档第一（客户内部审批链）、第七（供应商向大学注册）部分，仅作背景上下文，不落地。
- **状态机（已确认，阶段0）**：采用"发货后开票"。顺序为
  `PO_RECEIVED`（待审初态）→ `CONFIRMED` → `IN_PRODUCTION`（定制件可选）→ `SHIPPED` → `DELIVERED` → `INVOICED` → `PAID` → `COMPLETED`。`Net30` 从发票日计算。
- **新依赖（技术依赖，待安装）**：邮件 `django-anymail`；PDF `reportlab`。
- **异步策略（已确认，架构已否决 Celery）**：邮件采用 Outbox 模式 + cron 管理命令。零新依赖、不阻塞请求、可重试。
- **复用优先**：现有 `Order` 模型已含 `po_number` / `po_contact` / `payment_terms`(NET30) / `payment_due_date` / `shipping_*` / `billing_*` / 状态机，以及 `Quote` / `Invoice` / `PaymentRecord` / `ShippingRecord`。本 PRD 一律"复用扩展"，不重建。
- **已否决技术**：Celery / FastAPI / GraphQL / Neo4j / Microservices。

---

## 1. 产品目标

为美国实验室客户（研究员 / 博士后 / 博士生等 Requestor）构建一套自助式 B2B 采购门户，并与 SciReAgent 内部管理后台打通：客户侧完成商品浏览、报价询价、PO 提交与文件上传、订单状态实时追踪、发票下载与历史查询；内部侧完成 PO 审核、库存备货、发货、开票、收款（AR）全流程，并由状态变更自动触发邮件通知。目标是通过复用现有 `Order`/`Invoice`/`ShippingRecord`/`Product`/`Coa` 等模型与 DRF 接口，在不引入新架构的前提下，把"大学实验室 → 试剂供应商"的采购协同迁移到线上、透明化、可追溯。

---

## 2. 用户故事

### 角色 A：客户侧 Requestor（对应 `accounts.User`，role 默认 `researcher`）
1. 作为 Requestor，我希望在商品页按 CAS 号 / 货号 / 纯度 / 价格区间搜索与筛选，并查看实时库存徽标与 COA/SDS 下载，以便快速确认可买性。
2. 作为 Requestor，我希望把商品加入购物车并先生成 Quote（报价单），确认价格后再关联 Quote 号提交 PO，符合美国实验室"先 Quote 后 PO"的习惯。
3. 作为 Requestor，我希望在提交 PO 页录入 PO 号、机构、bill-to/ship-to 地址、联系人、基金号、运输方式，并拖拽上传大学系统生成的 PDF 版 PO，提交后系统生成 Sales Order。
4. 作为 Requestor，我希望在订单追踪页看到 `PO_RECEIVED → CONFIRMED → IN_PRODUCTION → SHIPPED → DELIVERED → INVOICED → PAID → COMPLETED` 各节点与时间戳，以及在 Shipped 节点看到 Tracking # 与承运商。
5. 作为 Requestor，我希望在发票页按时间倒序查看发票号、开票日、Net30 到期日、付款状态（Unpaid/Paid/Overdue 颜色标识），并下载 Invoice PDF。
6. 作为 Requestor，我希望在历史订单页按 PO 号 / 货号 / 日期范围搜索，批量导出 CSV/PDF，并一键 Re-order（P2）将相同商品放回购物车生成新 Quote。

### 角色 B：内部 Sales Rep（对应 `accounts.User.role = procurement`）
1. 作为 Sales Rep，我希望在 PO 审核台看到按时间倒序的新到 PO 队列（PO 号/客户/机构/金额），并能预览上传的 PO PDF、逐行查看库存可用量、对库存不足行高亮，再执行 Approve / Reject（Reject 需填原因）。
2. 作为 Sales Rep，我希望在库存与备货台对订单商品做库存匹配（可满足/缺货量）、锁定库存（Allocate，扣减不可被其他 PO 占用）、对合成型产品生成生产工单（WO）、确认 ETD 并同步到客户端。
3. 作为 Sales Rep，我希望在发货台录入快递单号与承运商（FedEx/UPS/DHL）、上传每批次 COA、自动生成 Packing List、上传冷链温度记录（P2）、点击 Mark as Shipped 触发客户通知邮件并状态更新。
4. 作为 Sales Rep，我希望在发票台对待开票的已发货订单一键生成带 `INV-YYYY-NNNN` 编号的 Invoice PDF、选择 Net30/Net45、Send Invoice 邮件发送给客户 AP 联系人。
5. 作为 Sales Rep，我希望在收款台看到按 Due Date 排序的开票未收款列表（超期红色）、AR Aging（30/60/90）视图、Mark as Paid（含到账日期/金额）、部分付款核销（P2）、Send Reminder 催款邮件。

### 角色 C：内部 Admin（对应 `accounts.User.role = admin`）
1. 作为 Admin，我希望拥有 Sales Rep 全部内部操作权限，并能分配 / 改派 PO 对应的 Sales Rep（设计文档节点 A "分配内部 Sales Rep 下拉选人"）。
2. 作为 Admin，我希望能查看 / 导出全局 PO 队列、AR Aging 报表、发票与收款汇总，用于财务对账。
3. 作为 Admin，我希望能配置系统邮件模板、Net 默认条款、Outbox 重试策略与 cron 频率，并手动重发失败邮件。

---

## 3. 需求池（按 P0 / P1 / P2 分级）

> 分级依据设计文档第六部分 MVP，并按阶段0确认范围裁剪。

### P0（必须有）
- **P0-1 商品目录 + COA 下载**：复用 `commerce.Product`（CAS / `catalog_no` / `purity` / `concentration` / `storage` / `shipping` / `lead_time` / `structure_svg`）、`commerce.SKU`（`price`、`inventory_status`、`pack_size`）、`documents.ProductDocument`（`document_type='coa'` / `'msds'`）、`documents.Coa`（`pdf_path`、`status='published'`）。搜索/筛选走现有商品 API。
- **P0-2 PO 提交流程（含 PO 文件上传）**：客户端表单 → 生成 `Order`（初态 `PO_RECEIVED`）。复用 `Order.po_number` / `po_contact` / `payment_terms` / `payment_due_date` / `shipping_*` / `billing_*` / `notes` / `OrderItem` + `Basket` 购物车。PO PDF 上传需新增附件存管（见 §4 / §6 待确认）。
- **P0-3 订单状态追踪**：订单追踪页按确认状态机渲染节点+时间戳。需扩展 `Order.Status` 与 `Order.VALID_TRANSITIONS`（见 §5 复用标注 / §6 待确认）。
- **P0-4 Invoice PDF 自动生成**：复用 `Invoice` + `reportlab` 一键生成 PDF。`Invoice.due_date` 由 `issued_at + Net30` 推导；`payment_due_date` 同步。

### P1（尽快加）
- **P1-1 库存实时匹配**：基于 SKU / Batch 的可用量与占用量（**新增库存量模型，见 §6**）在审核台 / 备货台计算可满足 / 缺货量；`OrderItem` 行展示 `inventory_status`。
- **P1-2 Quote → PO 流程**：复用 `Quote` / `QuoteItem`，提交 PO 时可关联已发出 Quote 号（`Order` 需新增 `quote` 外键或 `quote_no` 字段，见 §4）。
- **P1-3 自动通知邮件**：Outbox 模式 + cron 管理命令（依赖 `django-anymail`）。触发点见设计文档第四部分（PO 提交 / 审核通过 / Shipped / Delivered / 发票发出 / 到期前 7 天 / 超期 30 天）。**新增 `EmailOutbox` 模型与 `send_outbox_emails` 管理命令**。
- **P1-4 AR Aging 报表**：基于 `Invoice` + `PaymentRecord` 聚合 30/60/90 天账龄；`Invoice.is_overdue` 已可复用。

### P2（锦上添花）
- **P2-1 冷链温度记录上传**：发货台文件上传（节点 C），存管方案见 §6 待确认。
- **P2-2 部分付款**：复用 `PaymentRecord`（FK→`Invoice`，已支持多笔）+ Invoice 余额字段（**需新增 `balance_due` / 派生**，见 §4）。
- **P2-3 Re-order 一键复购**：历史订单 → 重建 `Basket` → 生成新 `Quote`。
- **P2-4 客户自助注册供应商**：注册流程（设计文档第七部分背景，仅 P2 自助注册入口），涉及 `Organization` 创建与资料录入。

---

## 4. 功能点清单（对照设计文档节点）

> 标注说明：`[复用]` = 直接复用现有模型/字段/接口；`[扩展]` = 在现有模型上新增字段或调整；`[新增]` = 新增模型/接口。
> 凡 `[复用]`/`[扩展]` 涉及的字段名均来自本次实际 Read 到的模型，未编造接口名。

### 客户侧 节点 1：商品页
| 设计字段/交互 | 实现依据 | 标注 |
|---|---|---|
| CAS/货号/品名/纯度/规格 | `Product.cas` / `catalog_no` / `name` / `purity` / `concentration` | `[复用]` |
| 目录价 / 批量折扣阶梯 | `SKU.price`；批量折扣阶梯**当前模型无字段** | `[复用]` 价格 + `[待确认]` 折扣阶梯是否建模 |
| COA 下载 / MSDS 下载 | `ProductDocument`(`document_type='coa'|'msds'`)；`Coa.pdf_path`；`Product.current_sds` | `[复用]` |
| 库存状态 In Stock/Made to Order/Lead Time | `SKU.inventory_status` + `Product.lead_time` | `[复用]` |
| 结构式 SVG | `Product.structure_svg` | `[复用]` |
| 搜索/筛选（纯度、修饰类型、价格区间） | 现有商品列表 API + 全文检索 | `[复用]` |

### 客户侧 节点 2：购物车 / Quote Cart
| 设计字段/交互 | 实现依据 | 标注 |
|---|---|---|
| 货号/品名/数量/单价/小计 | `Basket` + `SKU` + `Product` | `[复用]` |
| Total 实时计算 | 前端计算 | `[复用]` |
| Request a Quote 按钮 | `Quote` / `QuoteItem`（status=DRAFT→SUBMITTED） | `[复用]` |
| Checkout with PO（关联已有 Quote） | `Order` 需关联 Quote | `[扩展]` 新增 `Order.quote` 外键 / `quote_no` |

### 客户侧 节点 3：提交 PO 页面（核心）
| 设计字段/交互 | 实现依据 | 标注 |
|---|---|---|
| PO Number（唯一性校验） | `Order.po_number`（`unique` 约束需加，当前非 unique） | `[扩展]` 增加唯一索引/校验 |
| Quote/Reference # 下拉 | 同上 `Order.quote` | `[扩展]` |
| Institution（下拉/手动） | `Organization`（含 `org_type=academic`）；注意 `country` 默认 `'China'`，需支持美国机构 | `[复用]` + `[扩展]` 国际化地址 |
| Billing Address 自动填充可编辑 | `Organization` 扁平地址字段 / `User` 扁平地址 | `[复用]` 见 §6 地址模型待确认 |
| Shipping Address（Building/Room/Street/City/State/ZIP） | `Order.shipping_name` / `shipping_address` / `shipping_phone` / `shipping_email` | `[复用]` |
| Contact Person 自动填充 | 当前登录 `User` → `Order.po_contact` | `[复用]` |
| Grant/Fund Code | `Order` 无此字段 | `[扩展]` 新增 `Order.grant_code` |
| Shipping Method（Ambient/Cold Pack/Dry Ice/Blue Ice） | `Product.shipping`（枚举一致） | `[扩展]` 新增 `Order.shipping_method`（可选，或复用 product 级） |
| PO 文件上传（PDF/图片拖拽） | 无现成字段 | `[新增]` 见 §6 PO 附件存管 |
| Special Instructions / Requested Delivery Date | `Order.notes` / 新增 `Order.requested_delivery_date` | `[复用]` + `[扩展]` |

> 提交后：生成 Sales Order，状态 `PO_RECEIVED`（**扩展 `Order.Status`，见 §5/§6**）。

### 客户侧 节点 4：订单追踪页面
| 设计节点 | 实现依据 | 标注 |
|---|---|---|
| PO Received / Order Confirmed / In Production / Shipped / Delivered / Invoiced / Payment Received / Complete | 需重构 `Order.Status` 与 `Order.VALID_TRANSITIONS` 为确认状态机 | `[扩展]` 状态机重定义 |
| 每状态时间戳 | `Order` 当前仅含 `created_at`/`updated_at`；需状态变更历史 | `[新增]` `StatusLog` 表（见 §6） |
| Shipped 节点 Tracking # + 承运商 | `ShippingRecord.carrier` / `tracking_number` / `tracking_url` / `shipped_at` | `[复用]` |
| Delivered 签收时间/签收人 | `ShippingRecord.delivered_at`（签收人需 `[扩展]`） | `[复用]+[扩展]` |
| Invoiced 发票号 + PDF | `Invoice.invoice_no` + PDF | `[复用]` |

### 客户侧 节点 5：发票与付款页面
| 设计字段/交互 | 实现依据 | 标注 |
|---|---|---|
| Invoice Number / 开票日期（倒序） | `Invoice.invoice_no` / `issued_at` | `[复用]` |
| PO Number 关联跳转 | `Invoice.order` → `Order.po_number` | `[复用]` |
| Invoice PDF 下载 | `reportlab` 生成 / 存管 | `[新增]` 生成 + `[复用]` 关联 |
| Payment Status（Unpaid/Paid/Overdue）颜色 | `Invoice.status`(DRAFT/ISSUED/PAID/OVERDUE/VOID) + `is_overdue` | `[复用]` |
| Payment Due Date（Net30 自动） | `Invoice.due_date`（由 `issued_at` 推导）；`Order.payment_due_date` 同步 | `[复用]` |
| Payment Method（ACH/Wire/Check）纯展示 | `PaymentRecord.method`(WIRE/CHECK/ONLINE) | `[复用]` 展示层映射 |

### 客户侧 节点 6：历史订单
| 设计字段/交互 | 实现依据 | 标注 |
|---|---|---|
| 搜索 PO/货号/日期范围 | `Order` + `OrderItem` 查询 | `[复用]` |
| 批量导出 CSV/PDF | 新增导出接口 | `[新增]` |
| Re-order（P2） | 重建 `Basket` → 新 `Quote` | `[扩展]` P2 |

### 内部侧 节点 A：PO 审核台
| 设计字段/操作 | 实现依据 | 标注 |
|---|---|---|
| PO 新到队列（倒序） | `Order` 过滤 `status=PO_RECEIVED` | `[复用]` |
| PO 号/客户/机构/金额 | `Order.po_number` / `user` / `organization` / `grand_total` | `[复用]` |
| 上传 PO 文件预览 | `[新增]` PO 附件（见 §6） | `[新增]` |
| 商品明细逐行 + 库存可用量 | `OrderItem` + SKU 库存量（**新增库存量模型**） | `[复用]+[新增]` |
| 库存不足行高亮 | 同库存量 | `[新增]` |
| Approve / Reject（原因） | 状态机 `PO_RECEIVED→CONFIRMED` / `→CANCELLED` | `[扩展]` 状态机 |
| 分配 Sales Rep 下拉 | `User.role=procurement`；`Order` 需新增 `assigned_rep` 外键 | `[扩展]` 新增 `Order.assigned_rep` |

### 内部侧 节点 B：库存与备货台
| 设计字段/操作 | 实现依据 | 标注 |
|---|---|---|
| 订单商品 × 库存匹配表 | `OrderItem` + 库存量 | `[复用]+[新增]` 库存量模型 |
| Lead Time 估算（缺货项） | `Product.lead_time` / `SKU.lead_time` | `[复用]` |
| Allocate Inventory（锁定扣减） | 需可用量/占用量字段 + 原子扣减 | `[新增]` 库存量模型 + 服务逻辑 |
| Create Production WO（合成型） | 关联内部合成计划 **当前无模型** | `[待确认]` WO 是否本期建模 |
| ETD 确认 → 同步客户端 | `Order` 新增 `etd` / `ShippingRecord.estimated_delivery` | `[扩展]` |

### 内部侧 节点 C：发货台
| 设计字段/操作 | 实现依据 | 标注 |
|---|---|---|
| 待发货列表（按 ETD） | `Order.status=CONFIRMED/IN_PRODUCTION` + ETD | `[复用]` |
| Shipping Address 复核可编辑 | `Order.shipping_*` | `[复用]` |
| 快递单号 + 承运商下拉 | `ShippingRecord.tracking_number` / `carrier` | `[复用]` |
| COA 上传（每批次） | `documents.Coa` / `ProductDocument` | `[复用]` |
| Packing List 自动生成 | `[新增]` 模板（reportlab） | `[新增]` |
| Temperature Logger 上传（P2） | 文件上传 | `[新增]` P2（见 §6） |
| Mark as Shipped → 通知邮件 + 状态更新 | `Order→SHIPPED` + Outbox | `[扩展]+[新增]` |

### 内部侧 节点 D：发票台
| 设计字段/操作 | 实现依据 | 标注 |
|---|---|---|
| 已发货未开票列表（按发货日） | `Order.status=SHIPPED/DELIVERED` 且 `invoice` 为空 | `[复用]` |
| 自动填充 PO/订单/商品/金额 | `Order` + `OrderItem` | `[复用]` |
| 发票号规则 `INV-YYYY-NNNN` | `Invoice.invoice_no` 生成器 | `[扩展]` 编号规则 |
| Net30/Net45 下拉 | `Order.payment_terms` 当前默认 NET30，需在 Invoice 上可选 | `[扩展]` `Invoice.payment_terms` |
| Invoice PDF 自动生成 | reportlab | `[新增]` |
| Send Invoice（邮件） | Outbox → 客户 AP 联系人 | `[新增]` + `[复用]` |

### 内部侧 节点 E：收款台
| 设计字段/操作 | 实现依据 | 标注 |
|---|---|---|
| 开票未收款列表（按 Due Date，超期红） | `Invoice` 过滤未付 + `is_overdue` | `[复用]` |
| AR Aging（30/60/90） | `Invoice.due_date` + `PaymentRecord` 聚合 | `[新增]` 聚合接口（复用模型） |
| Mark as Paid + 到账日期 + 金额 | `PaymentRecord` + `Invoice.status=PAID` / `paid_at` | `[复用]` |
| 部分付款（P2） | 多笔 `PaymentRecord`；需 `Invoice.balance_due` | `[扩展]` P2 |
| Send Reminder 催款邮件 | Outbox 模板 | `[新增]` |

### 第四部分：自动化邮件（Outbox 模式）
| 触发事件 | 实现 | 标注 |
|---|---|---|
| PO 提交 | 客户确认 + Sales Rep 通知 | `[新增]` Outbox + 模板 |
| PO 审核通过 | Order Confirmation | `[新增]` |
| 状态变更 Shipped / Delivered | Tracking # / 收货确认 | `[新增]` |
| 发票发出 | 含 PDF 附件 | `[新增]` |
| 到期前 7 天 / 超期 30 天 | 定时扫描 + 升级通知 | `[新增]` cron |

---

## 5. 状态机与模型复用 / 扩展的关键事实（务必与开发对齐）

**现状（实际 Read 到的 `transactions/models.py`）：**
- `Order.Status` 现有值：`DRAFT / CONFIRMED / INVOICED / PAID / PROCESSING / SHIPPED / COMPLETED / CANCELLED / QUOTE_PENDING / QUOTED / QUOTE_ACCEPTED / QUOTE_REJECTED`。
- `Order.VALID_TRANSITIONS` 当前图：`draft→confirmed/quote_pending/cancelled`；`confirmed→invoiced/paid`；`invoiced→paid`；`paid→processing`；`processing→shipped`；`shipped→completed`；quote 分支独立。
- `Invoice` 为 `OneToOneField(Order)`，`ShippingRecord` 为 `OneToOneField(Order)`。

**确认状态机与现状的 Gap（需开发阶段落地，PRD 不写实现）：**
1. 确认的初态 `PO_RECEIVED` 在现状模型中**不存在**，需新增。
2. `IN_PRODUCTION`、`DELIVERED` 在现状模型中**不存在**（`Shipped`/`Delivered` 实际分散在 `ShippingRecord.Status`，且 `ShippingRecord` 是 OneToOne，与"分批多次发货"冲突），需统一到 `Order.Status` 重定义。
3. 现状 `VALID_TRANSITIONS` 与设计不一致（如 `confirmed→invoiced` 跳过发货，"发票后付款"顺序倒挂），须按 `PO_RECEIVED→CONFIRMED→IN_PRODUCTION→SHIPPED→DELIVERED→INVOICED→PAID→COMPLETED` 重建，并保留 `CANCELLED` 出口。
4. `ShippingRecord` 为 OneToOne，但设计文档节点 C 允许多次分批发货（shipments 可多次）；分批发货能力为 `[待确认]`（见 §6），若本期仅单次发货则可复用 OneToOne，否则需改 OneToMany。

**可安全复用的字段（直接来自模型）：**
- `Order`：`po_number`、`po_contact`、`payment_terms`(默认 NET30)、`payment_due_date`、`subtotal/tax_total/grand_total`、`currency`(USD)、`shipping_name/address/phone/email`、`billing_name/address`、`notes/internal_notes`。
- `OrderItem`：`product`/`sku`/`quantity`/`unit_price`/`subtotal`。
- `Invoice`：`invoice_no`、`status`、`issued_at`、`due_date`、`paid_at`、`subtotal/tax_total/grand_total`、`currency`、`payment_ref`、`is_overdue`。
- `PaymentRecord`：`method`(ONLINE/WIRE/CHECK)、`amount`、`reference`、`proof_file`、`status`、`verified_by`、`verified_at`（多笔→天然支持部分付款）。
- `ShippingRecord`：`status`、`carrier`、`tracking_number`、`tracking_url`、`shipped_at`、`estimated_delivery`、`delivered_at`。
- `Quote`/`QuoteItem`、`Basket`、`Wishlist`。
- `Product`/`SKU`/`ProductDocument`/`Coa`/`Batch`/`SdsRevision`（COA/SDS/库存状态/结构式）。
- `Organization`（含 `org_type=academic`）、`User`（`role=researcher/procurement/admin`，`is_org_admin`）。

---

## 6. 待确认问题清单（PRD 阶段开放项，须主理人决策）

1. **Address 模型结构**：bill-to / ship-to 是否独立为 `Address` 表（一对多挂 `Organization`，如设计文档第五部分 `addresses` 所示），还是继续扁平复用 `Organization.address_line1/2/city/state/postal_code/country` + `Order.shipping_*` 快照？影响节点 3 自动填充与多地址管理。
2. **PO 附件存管**：复用假设的 `assets.PdfFile` 还是新增 `po_attachments` 模型（挂 `Order`，支持多文件 PDF/图片）？需确认 `assets` app 是否存在及其字段。
3. **status_log 表结构**：建议字段 = `order` FK、`from_status`、`to_status`、`timestamp`、`operator`(User)、`note`。是否独立表？是否同时记录内部操作（审核/分配/拒绝原因）？
4. **库存量模型归属**：可用量 / 占用量（allocated）放哪？`Batch` 当前**无数量字段**（仅 `lot_number/produced_at/retest_at`），需新增 `quantity`/`available`/`allocated` 字段或独立 `Inventory` 表（含 SKU/Batch/库位）。这是 P1 库存匹配与 Allocate 的前置依赖，须优先定。
5. **内部审核台权限边界**：Admin vs Procurement（Sales Rep）的操作边界——Reject、分配 Rep、改派、作废、AR 报表导出分别允许哪些角色？是否引入 Django permissions 或基于 `User.role` 的简单判断？
6. **分批发货**：本期是否支持 `ShippingRecord` 一对多（多次分批）？还是仅单次发货（复用现有 OneToOne）？影响节点 C 与状态机 `DELIVERED` 语义。
7. **批量折扣阶梯**：节点 1 的"批量折扣阶梯"当前模型无字段，是否本期建模（如 `SKUVolumePrice`）还是前端写死 / 延后？
8. **生产工单（WO）**：节点 B `Create Production WO` 是否本期建模？还是仅记录 ETD 占位、WO 留待后续内部系统？
9. **Invoice 编号规则**：`INV-YYYY-NNNN` 的序列号自增与并发安全（DB 序列 / `select_for_update`），是否本期实现原子编号？
10. **Net45 条款**：`Order.payment_terms` 默认 NET30，节点 D 需 Net45 选项；是否在 `Order` 与 `Invoice` 同时支持，且以 Invoice 为准？

---

## 7. UI 设计稿描述（引用 DESIGN_STANDARDS.md 规范）

> 全局遵循：主色 emerald `--color-primary`(#059669)、强调 amber `--color-accent`(#D97706)；卡片 4px 圆角（`§6.2`）；按钮 4px 圆角、Primary/CTA/Outline 三变体（`§6.1`）；状态标签一律中性灰边框 + 6px 语义色圆点（`§6.3`），**禁用彩色背景**；8px 基线网格（`§4.1`）；最大内容宽度 1200px 居中（`§4.2`）；字体 Inter + JetBrains Mono，CAS/货号/SKU 用 mono 12px（`§3`）；图标 Lucide（`§6.5`）。

### 7.1 提交 PO 页（节点 3）
- 布局：两栏 `grid 1fr 1fr gap 32px`（≤768px 折叠单栏）。左栏 PO 信息表单（PO Number、Quote 下拉、Institution、Grant Code、Shipping Method 单选组）；右栏地址（Billing 自动填充可编辑 + Shipping Building/Room/Street/City/State/ZIP）、Contact 自动填充、PO 文件拖拽上传区、Special Instructions、Requested Delivery Date。
- 组件：文本输入 + Outline 按钮 + 单选 chip（Shipping Method）；PO 上传用拖拽卡片（4px 圆角、1px border）；底部 CTA 按钮（amber `--color-accent` 填充，44px LG）"Submit PO"。
- 状态标签：表单校验错误用 `--color-danger` 文字；PO Number 唯一性校验失败内联提示。

### 7.2 订单追踪页（节点 4）
- 布局：顶部订单摘要 Card（PO 号 / 机构 / 金额 / 状态 Badge）；下方水平 Stepper，8 个节点 `PO_RECEIVED → CONFIRMED → IN_PRODUCTION → SHIPPED → DELIVERED → INVOICED → PAID → COMPLETED`。
- 状态标签（严格按 `§6.3`）：中性灰 border + 语义圆点——已完成节点圆点 `#22C55E`(success)，当前进行中 `#F59E0B`(warning/amber)，未到达 `#9CA3AF`(gray)。每个节点下方 mono 11px 时间戳。
- 子信息：Shipped 节点显示 `ShippingRecord.carrier` + `tracking_number`（mono）+ `tracking_url` 链接按钮（Outline）；Invoiced 节点显示 `invoice_no` + PDF 下载按钮（Primary）。

### 7.3 发票页（节点 5）
- 布局：列表 Card 流（倒序），每卡 property list（`§6.4`：100px label | 1fr value）。字段：Invoice Number(mono)、开票日期、PO Number(可点击跳订单)、Due Date(Net30 推导)、Payment Method(展示映射)、PDF 下载(Primary)。
- 付款状态 Badge（`§6.3`）：Unpaid=`#9CA3AF`、Paid=`#22C55E`、Overdue=`#DC2626`(danger)。注意 Overdue 用 danger 红（违反"禁用彩色背景"例外，状态语义需要——需在 DESIGN_STANDARDS 明确 Overdue 可用红点）。

### 7.4 PO 审核台（节点 A，内部管理）
- 布局：左列表（PO 队列，倒序，行含 PO 号/客户/机构/金额 + Status Badge）；右详情面板：PO PDF 预览（嵌入）、OrderItem 逐行表（SKU mono / 数量 / 单价 / 库存可用量）。
- 缺货行：左侧 amber(`#F59E0B`) 左边框 + ⚠️ Lucide 图标高亮（非彩色背景，用 border 提示）。
- 操作：Approve（Primary emerald）/ Reject（需弹窗填原因，Outline）；分配 Sales Rep 下拉（列出 `User.role=procurement`）。

### 7.5 发货台（节点 C，内部管理）
- 布局：待发货列表（按 ETD 排序）+ 选中订单详情。详情含 Shipping Address 复核（可编辑输入）、快递单号录入 + 承运商下拉（FedEx/UPS/DHL）、COA 上传（每批次，复用 `Coa`）、Packing List 生成按钮（Outline）、温度记录上传（P2）。
- 操作：Mark as Shipped（CTA amber）→ 触发 Outbox 邮件 + `Order→SHIPPED`。

### 7.6 发票台（节点 D，内部管理）
- 布局：已发货未开票列表（按发货日）+ 选中订单自动填充卡（PO/订单/商品/金额，property list，只读）。
- 控件：发票号（自动 `INV-YYYY-NNNN`，mono 展示）、Net 条款下拉（Net30/Net45）、Generate PDF（Primary）、Send Invoice（CTA amber，含 PDF 附件邮件）。

### 7.7 收款台（节点 E，内部管理）
- 布局：开票未收款列表（按 Due Date，超期行 danger 左边框）+ AR Aging 报表区（30/60/90 三栏聚合卡，tabular-nums）。
- 操作：Mark as Paid（弹窗：到账日期 + 金额）、Send Reminder（Outline 催款邮件）。

---

## 8. 技术与依赖（汇总，供研发排期）

- 新增依赖：`django-anymail`（邮件）、`reportlab`（PDF）。
- 邮件架构：Outbox 模式（新增 `EmailOutbox` 表：to / subject / body / attachment / status / retry_count / next_retry / sent_at）+ cron 管理命令（`send_outbox_emails`），无 Celery。
- 分层：View（DRF，信封 `{success,data,meta}`）→ Service（状态机、库存扣减、PDF 生成、邮件入队）→ Model（扩展/新增如上）。
- 复用优先：见 §4 / §5，不重建 `Order`/`Invoice`/`ShippingRecord`/`Quote`/`Product`/`Coa` 等。

---

*PRD 完。开放项见 §6，待主理人评审决策后进入研发。*
