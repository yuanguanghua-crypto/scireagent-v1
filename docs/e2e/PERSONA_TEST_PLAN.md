# 拟人化测试方案（Persona Test Plan）

**版本** V1.0 · 2026-10-22 · **索引源** `SITE_ROLE_OPERATION_MANUAL.md`（角色章节 + 第 12 章页面索引）
**配套** `GLOBAL_TEST_PLAN_V3.md`（全局方案，本文件是它的 L4 层）

---

## 0. 什么叫"拟人化测试"

**不是**"用浏览器把按钮点一遍"。是：

> 一个**带明确目标的真人**，从进入系统到完成目标，走**完整的真实路径**——
> 包括前置条件、等待、失败后重试、以及"他会去点、但其实他不该点"的那些东西。

### 三条硬规（缺一条就不算拟人化）

| # | 规则 | 反例（真实发生过） |
|---|---|---|
| **1** | **业务结果优先，UI 文案不作数** —— UI 说"成功"必须查 API/DB 侧证 | `/settings` 改密码：弹"feature will be available soon"（语气像成功），实际**零请求、密码没变** |
| **2** | **越权必测** —— 每个 persona 都要试 3 条"他不该能做的事" | 采购能进 19 个内部台，其中 3 页进去是空的、9 页只能看不能改 |
| **3** | **可重复** —— 连跑两次不能炸（幂等或自动清理） | 用固定 PO 号提交，第二次跑撞唯一约束 |

### 与传统 E2E 的分工

| | 传统 E2E（L3） | 拟人化（L4） |
|---|---|---|
| 范围 | 一个页面的一个功能 | 一条**跨页跨角色**的真人任务链 |
| 判据 | 页面状态（元素出现、toast 文案） | 业务状态（订单状态机推进、库里的行、金额） |
| 关注点 | 功能对不对 | **交接处**对不对（客户提了单，采购能不能看到） |

---

## 1. 八个 persona（一页看全）

> 账号来自独立探测栈（`probe_*` / `probe_ouser_*`），**不碰开发库**。搭建见说明书附录 H。
> 每个 persona 对应说明书的一章，照着读即可。

| ID | 谁 | 账号 | 真实目标（他上班要干的事） | 起点 | 成功判据（业务层） |
|---|---|---|---|---|---|
| **P1** | 匿名访客 | 无 | 找到想要的试剂、问个价 | 未登录 | 询价单落库；购物车有行 |
| **P2** | 已注册未验证 | `probe_unverified` | 把账号激活 | 注册完没点邮件 | 拿到验证链接 → 能登录 |
| **P3** | researcher 客户 | `probe_ouser_a` | 下单、查进度、拿发票 | 已登录、有机构 | 订单进 `confirmed`/`po_received`；PDF 能下 |
| **P4** | 机构管理员 | `probe_orgadmin` | （他以为能管机构） | 已登录 | **实测：与 P3 完全一样，没有任何额外能力** |
| **P5** | procurement 采购 | `probe_procure` | 把订单履约完：审批→发→开票→收钱 | 已登录 | 订单推进到 `paid`；AR 金额归零 |
| **P6** | admin(role) | `probe_adminrole` | 给新客户指派销售 | 已登录 | 订单 `assigned_rep` 落库 |
| **P7** | staff 内容运营 | `probe_staff` | 把一个新产品从零弄上架 | 已登录 | 产品 `status=active` 且前台可见；SDS/COA `published` |
| **P8** | superuser | `probe_super` | 给同事开权限 | 已登录 | 对方 `is_staff=true` 且**重登后**看到工作台 |

---

## 2. 逐 persona 任务脚本

> 断言列里 `→` 表示"查 API 或 DB 侧证"；`✗` 表示预期失败（缺陷锁定）。

### P1 匿名访客（说明书 §1，10 条流程）

**人设**：某高校博士生，第一次来，想找一支带荧光的 ATP 类似物，顺便问个批量价。

| 步 | 操作（真实动作） | 页面 | 断言 | 侧证 |
|---|---|---|---|---|
| 1 | 打开首页，点一个分类胶囊 | `/` | 跳到 `/products?category=` | URL 参数含分类 slug |
| 2 | 在列表里按名称排序 | `/products` | 首条按字母序 | DOM 首行文本 |
| 3 | 打开一个产品详情 | `/products/:id` | 出现 SKU 表 + CAS + 结构式 | `→ GET /products/{id}/detail` 200 |
| 4 | 点 `Add to Cart`（未登录） | 同上 | toast `Added to cart` | `→ GET /basket` 有 1 行（靠 X-Session-Key） |
| 5 | 去 `/checkout` | `/checkout` | **被拦到登录页** | URL 含 `/login?redirect=/checkout` |
| 6 | 改主意：点 `Request Quote` 填询价 | `/quote-request` | 提交成功 | `→ POST /quote-requests/` 201；库里有记录 |
| 7 | 空必填再提交一次 | 同上 | **被前端拦下**（不提交） | 断言**无网络请求** |

**越权探测（他绝不该做成）**：

| 试什么 | 期望 | 实测现状 |
|---|---|---|
| 打开 `/orders` | 跳登录 | ✅ 会跳 |
| 打开 `/workspace` | 跳登录 | ✅ 会跳 |
| `GET /api/v1/admin/orders/` | **401** | ✅ 401 |
| `POST /api/v1/products/` | **401** | ✅ 401 |

**已知坑**：匿名购物车靠 `X-Session-Key`，换浏览器就丢；登录后本地购物车**不会自动并入**账户（`mergeLocalBasket` 零调用）。

---

### P2 已注册未验证（说明书 §2）

**人设**：刚注册，没注意要验证邮件；第二天来登录。

| 步 | 操作 | 断言 | 侧证 |
|---|---|---|---|
| 1 | 用 `probe_unverified` 登录 | 页面出现 `Your email address is not verified...` | `→ POST /auth/login` **403**，`meta.error.detail` 含 "not verified" |
| 2 | 点 `Resend verification email` | **✗ 预期：什么都没发生** | 断言**零网络请求、页面文本不变**（缺陷锁定，见说明书 §11.2 #2） |
| 3 | 用一个有效 token 访问 `/api/v1/auth/me` | 若持有 token 则 200 | 证明"权限层不看 email_verified" |

**为什么要锁这个缺陷**：运营和客服一定会收到"我没收到验证邮件"的工单；
一旦有人修了重发按钮，这条用例必须变红提醒更新文档。

---

### P3 客户下单到拿发票（说明书 §3，13 条流程）

**人设**：实验室采购助理，用课题组经费买东西，需要发票报销。

| 步 | 操作 | 断言 | 侧证 |
|---|---|---|---|
| 1 | 登录 → 首页 | 落到 `/` | localStorage 有 token，`is_staff=false` |
| 2 | 加购 2 个不同 SKU | 购物车 2 行 | `→ GET /basket` count=2 |
| 3 | `/checkout` 填收货 + 选 PO 支付 + 填 PO 号 | 提交成功，跳订单详情 | `→ GET /orders/{id}/` status=`confirmed`；`grand_total` = 各行单价×数量之和 |
| 4 | 打开 `/orders` | 能看到刚下的单 | 列表首行 order_no 一致 |
| 5 | 走 PO 路径：`/po/submit` 带附件提交 | 顶部条显示 `Order No: ORD-…` | `→ GET /orders/{id}/` status=`po_received`；`→` 附件数 1 |
| 6 | `/po/addresses` 新建一个地址 | 列表出现 | `→ GET /addresses/` 含该 attention |
| 7 | `/wishlist` 收藏一个产品 | 显示已收藏 | `→ GET /wishlist/` product_ids 含之 |
| 8 | `/po/downloads` 下载发票 | **✗ 目前无发票可下**（需内部先开票） | 与 P5 接力后再测 |

**越权探测**：

| 试什么 | 期望 | 实测 |
|---|---|---|
| 读别的机构的地址 `GET /addresses/7/` | 404 | ✅ 404 |
| 改别人的地址 `PUT /addresses/7/` | 404 | ✅ 404 |
| 读别人的订单 `GET /orders/1258/` | 404 | ✅ 404 |
| 对别人的订单 accept 报价 | 403 | ✅ 403 |
| 下别人的发票 PDF | 403 | ✅ 403 |
| 改自己的 `role` | 不能（`/auth/profile` 白名单不含） | ✅ 字段被忽略 |

**已知坑**：`/settings` 改密码假成功；`Submit for Approval` 按钮与 `Place Order` 同目标且无审批接口。

---

### P4 机构管理员（说明书 §4）

**人设**：课题组组长，注册时建了机构，以为自己是"机构管理员"。

**这条 persona 的任务不是"完成某件事"，而是验证一个否定命题**：

| 步 | 操作 | 断言 |
|---|---|---|
| 1 | 登录 `probe_orgadmin` | `/settings` → `Account` 出现 `Admin` 徽章 |
| 2 | 逐个对比 P3 的 8 条能力 | **与 P3 逐项相同**（页面可达、读写端点计数一模一样） |
| 3 | 试"管理本机构成员" | **✗ 无此功能**（无端点、无入口） |
| 4 | 试"审核本机构地址" | **✗ 无此功能** |
| 5 | `→` 对比 `/api/v1/auth/me` 返回 | 只有 `is_org_admin=true` 不同，其余一致 |

**为什么要专门测**：`is_org_admin` 现在**对权限零影响**。如果不锁住，
将来有人给它加权限（哪怕是合理的），也**没有任何告警**。

---

### P5 采购履约（说明书 §5，6 条流程）

**人设**：采购专员，每天的工作就是把 PO 变成已收款的订单。

| 步 | 操作 | 断言 | 侧证 |
|---|---|---|---|
| 1 | `/ops/po/review` 看队列 | 有 `po_received` 的单 | `→ GET /orders/?status=po_received` 非空 |
| 2 | 点 `Approve` | 卡片消失 | `→` 该单 status=`confirmed`；`StatusLog` 新增 1 行 |
| 3 | `/ops/po/shipments` 选单 → 填 Carrier/Tracking → `Create Shipment` | 发货记录出现 | `→ GET /orders/{id}/` 有 shipments |
| 4 | 点 `Mark Shipped` | 状态变 shipped | `→` status=`shipped` |
| 5 | 填 `Received by` → `Mark Delivered` | 状态变 delivered | `→` status=`delivered`；shipment 有 received_by |
| 6 | `/ops/po/invoicing` → 选付款条件 → `Issue Invoice` | 出现发票号 | `→` order.invoice 非空、status=`invoiced` |
| 7 | 填 Amount/Method/Reference → `Record Payment` | 无报错 | `→ GET /invoices/{id}/` 有 PaymentRecord |
| 8 | `/ops/po/ar` 看账龄 | 该单不再出现在当前桶 | 金额减少 |
| 9 | `/ops/inventory` 入库 +10 | Available +10 | `→ GET /inventory/{id}/` available 增 10、流水 1 条 |

**越权探测**：

| 试什么 | 期望 | 实测 |
|---|---|---|
| 打开 `/ops/orders`（全库订单） | 403 + 误导性空态 | ✅ 不可用 |
| 打开 `/workspace/verified` | 403 | ✅ 不可用 |
| 保存产品 `PUT /products/1/` | 403 | ✅ 403 |
| 点 `Assign Rep` | 403 + 英文 toast | ✅ 403 |
| 把订单推到 `paid` | **无入口**（全站没有"标记已付"按钮） | ✗ 做不到 —— 这是**能力缺口**，不是缺陷 case |

**已知坑**：PO 审核台无 try/catch；`Record Payment` 金额为空时**静默 return**（连 toast 都没有）。

---

### P6 admin(role)（说明书 §6）

**人设**：销售主管，被授予 `role=admin` 但**没有** `is_staff`。

| 步 | 操作 | 断言 | 侧证 |
|---|---|---|---|
| 1 | 登录 `probe_adminrole` | 能进 `/workspace` | localStorage `role=admin`、`is_staff=false` |
| 2 | `/ops/po/review` 填 **数字** Rep ID → `Assign Rep` | 成功 | `→ GET /orders/{id}/` `assigned_rep` = 该 id |
| 3 | 填**用户名** → `Assign Rep` | **✗ 目前 500**（应 400） | 断言响应码；这是缺陷锁定 |
| 4 | 试保存产品 | 403 | 与采购相同 |

**这条 persona 的意义**：验证"`role=admin` 的实际权限边界"——
它只比采购多**一个按钮**，并不能改产品、不能审 COA。

---

### P7 staff 产品从零上架（说明书 §7，最复杂的一条）

**人设**：内容运营，今天要把一支新试剂上架。

| 步 | 操作 | 断言 | 侧证 |
|---|---|---|---|
| 1 | `/workspace/products/new` | 完整性条显示 `✗ Incomplete` | 缺失项列出 Name/CAS/SMILES/Category/Default SKU |
| 2 | 填 Name/Catalog/CAS/SMILES/类目 | 完整性条变 `✓ Complete`（还差 SKU） | 实时变化 |
| 3 | `Word Import` 上传一份 docx | 字段被回填 | `→ POST /products/parse-word` 200；表单值变化 |
| 4 | `+ Add SKU` 填价格 100 USD | 出现一行，Default 勾上 | — |
| 5 | `Save Draft` | 保存成功 | `→ GET /products/{id}/` status=`draft`，SKU 1 条 |
| 6 | Section 9 `Generate SDS` | 生成草稿 | `→ GET /sds-revisions/?product_id=` 有 draft |
| 7 | `Approve & Publish SDS` | 变 published | `→` status=`published` |
| 8 | `Publish` | 产品上架 | `→` products list status=`active`；**前台 `/products` 能搜到** |
| 9 | 前台匿名访问产品详情 | 能看到，且 SDS 可下载 | `→ GET /products/{id}/detail` 200 |
| 10 | 建 verified 草稿 → `/workspace/verified` 审批 | 通过后在产品页出现 | `→ GET /products/{id}/methods/` 含该 method |

**越权探测**（用采购身份反向验证）：

| 试什么 | 期望 |
|---|---|
| 采购保存产品 | 403 |
| 采购审批 SDS | 403（`IsAdminOrReadOnly` 写要 staff） |
| 采购读 `/verified/` | 403 |

**已知坑**：`Completeness bar` 的缺失项**不可点击跳转**；改 Goal/AP 时若不显式带 `method_ids`，
`_sync_method_bridges` **会真删**原关联（先删后加语义）。

---

### P8 superuser 开权限（说明书 §8）

**人设**：IT 管理员，同事新入职要开运营权限。

| 步 | 操作 | 断言 | 侧证 |
|---|---|---|---|
| 1 | 打开 `/admin/` → Users → 搜索目标 | 找到 | — |
| 2 | 勾 `is_staff` → Save | 保存成功 | `→` 该用户 `is_staff=true` |
| 3 | **不重登**，让目标用户刷新工作台 | **✗ 仍看不到菜单** | localStorage 里 `is_staff` 还是旧值 |
| 4 | 目标用户 `Sign Out` 再登录 | 能看到 `/workspace` | localStorage `is_staff=true` |
| 5 | 用超管调 `POST /products/{id}/hard-delete/` | 200 且真删 | **注意不可逆**（仅在副本上做） |

**这条 persona 锁住的是一条运营常识**：改权限后**后端立即生效、前端要重登**。
不写清这条，客服会反复接"权限没生效"的工单。

---

## 3. 跨角色接力：订单全生命周期（3 人接力）

这是**最像真实业务**的一条，也是漏洞最容易藏的地方。

```
P3 客户                 P5 采购                      P3 客户
──────                  ──────                      ──────
/po/submit 提 PO  ──▶  /ops/po/review 审批  ──▶  /orders 看到 confirmed
                        /ops/po/shipments 发货 ──▶ /orders 看到 shipped + 可 Track
                        /ops/po/invoicing 开票 ──▶ /po/downloads 能下 PDF
                        Record Payment        ──▶ /orders 看到 invoice 状态
```

**每个交接点的断言（不看 UI，看数据）**：

| 交接 | 断言 |
|---|---|
| P3 → P5 | 采购的 `po_received` 队列里出现该单号；且**金额与客户侧一致** |
| P5 审批 → P3 | 客户侧 `GET /orders/{id}/` status 从 `po_received` → `confirmed` |
| P5 发货 → P3 | 客户侧能看到 `tracking_no`，且 `Track Package` 链接可点 |
| P5 开票 → P3 | 客户侧 `/po/downloads` 出现该发票；**PDF 内容金额 = 订单 grand_total** |
| P5 收款 → 状态 | ⚠️ **订单不会自动变 paid**（已知缺口），需人工 `Mark as Completed` |

**必须专门验的"接缝"**：客户下单时的**金额快照**——内部改 SKU 价格后，历史订单金额**不能变**。

---

## 4. 记录模板（每条 persona 跑完填一份）

```
persona: P5 procurement
日期/执行人：
环境：探测栈 8011 + DB 副本 db_probe.sqlite3
任务链：审批 → 发货 → 开票 → 收款 → AR → 库存

步骤结果：9/9 通过
越权探测：5/5 被正确拒绝
断链点：第 7 步 Record Payment 后订单仍 invoiced（预期内，见能力缺口 #1）

新发现缺陷：
  - [P5-1] xxx（现象 / 复现步骤 / 期望）

副作用核查：副本已删除（rm backend/db_probe.sqlite3）
```

---

## 5. 数据隔离与清理（必须遵守）

| 规则 | 原因 |
|---|---|
| 只跑在 `db_probe.sqlite3` **副本**上 | 写操作会污染开发库 |
| 副本文件名必须含 `probe`（脚本硬校验） | 防止误连 |
| 跑完 `rm backend/db_probe.sqlite3` | 99MB，别留着 |
| 生产**只读**，不做写 persona | 会污染真实数据且无回滚 |
| 同一 persona 连跑两次必须都能过 | 否则说明脚本用了固定单号/固定 id |

---

## 6. 与既有 spec 的复用关系（别重写）

> ⚠️ 下表"需要新增的"只是**摘要**；唯一 backlog 是 [`GAP_REGISTER.md`](./GAP_REGISTER.md)（23 条，带 P0/P1/P2）。
> 改这里时请同时看总账，避免两份清单打架。

| persona | 可直接复用 | 需要新增的 |
|---|---|---|
| P1 | `public-smoke`、`cart-page-interactions`、`register-wizard` | **询价提交**（P0-1，当前零覆盖） |
| P2 | `verify-improvements` | **登录 403 + 重发死链**（P0-2） |
| P3 | `po-lifecycle.api`、`po-addresses-crud`、`orders-pagination` | **下载中心 / 再次订购 / 收藏夹**（P0-4/5/6） |
| P4 | `permission-matrix` | **"与 P3 逐项相同"的对比用例**（P0） |
| P5 | `po-lifecycle.fullflow`、`ops-inventory`、`ops-po-desk-gaps` | AR 金额断言、Record Payment 空值静默 |
| P6 | — | **Assign Rep 成功 + 500 缺陷锁定**（P0-3） |
| P7 | `product-new-*`、`product-compliance-lifecycle`、`workspace-verified-review` | 前台可见性联动（上架后匿名能搜到） |
| P8 | — | **改权限后"不重登看不到菜单"** 这条（C 类，人工冒烟即可） |

---

## 7. 执行顺序建议

1. **先 P3 与 P5**（客户 + 采购）——覆盖订单主链路，出问题影响最大
2. **再 P1 与 P2**（获客与激活）——三条 P0 缺口在这里
3. **再 P7**（内容运营）——产品上架影响前台可见性
4. **最后 P4 / P6 / P8**（权限边界）——用来越权探测与权限回归
