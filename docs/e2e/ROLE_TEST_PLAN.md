# 角色 × 流程 × 页面 —— 测试方案（2026-10-22）

> 上游基线：`ROLE_CAPABILITY_MATRIX.md`（角色/权限/页面事实）+ `PAGE_ROLE_MATRIX.json`（页面×角色实测）。
> 本文只回答一件事：**这些格子里哪些没人测、怎么补、补到什么程度算够。**
> 机器可读输入：`ROLE_CAPABILITY_MATRIX.json`、`PAGE_API_MAP.json`、`PAGE_ROLE_MATRIX.json`。

---

## 1. 靶子：12 个受损格 + 4 类覆盖缺口

**来自 §8 的实测**（`page_role_matrix.py`）：19 个内部台页面里，对 `is_staff=False` 的内部人
**3 个进去就空白（DEAD）、9 个只能看不能改（READONLY）、7 个正常**。

| # | 页面 | 受损身份 | 判定 | 直接原因 |
|---|---|---|---|---|
| 1 | `/ops/orders` | procurement, admin_role | **DEAD** | `GET /admin/orders/` ← `IsAdminUser` |
| 2 | `/ops/orders/:id` | procurement, admin_role | **DEAD** | `GET /admin/orders/:id/` ← `IsAdminUser` |
| 3 | `/workspace/verified` | procurement, admin_role | **DEAD** | `GET /verified/` ← `IsStaffUser` |
| 4 | `/workspace`（统计卡） | procurement, admin_role | READONLY | `GET /admin/dashboard-stats/` ← `IsStaffUser` |
| 5 | `/workspace/products` | procurement, admin_role | READONLY | 写 0/7 ← `IsAdminOrReadOnly` |
| 6 | `/workspace/products/*/edit` | procurement, admin_role | READONLY | 写 **0/21** |
| 7 | `/workspace/goals` | 同上 | READONLY | 写 0/2 |
| 8 | `/workspace/applications` | 同上 | READONLY | 写 0/2 |
| 9 | `/workspace/methods` | 同上 | READONLY | 写 0/2 |
| 10 | `/workspace/protocols` | 同上 | READONLY | 写 0/2 |
| 11 | `/workspace/references` | 同上 | READONLY | 写 0/2 |
| 12 | `/workspace/knowledge-intake` | 同上 | READONLY | `POST /knowledge-intake/` ← `IsAdminUser` |

**四类覆盖缺口**（下面是"为什么现有测试没抓到"）：

| 缺口 | 证据 |
|---|---|
| **A. 现有 procurement 用例只验"没被踢"，不验"页面有没有数据"** | `frontend/e2e/internal-access-procurement.spec.cjs:31-37` 的断言只有两条：`url 含 /workspace` + `#app.innerHTML.length > 200`。**3 个 DEAD 页面都能通过**（AdminLayout 的侧栏渲染出来了，表格是空的，长度轻松过 200） |
| **B. 夹具只有 3 个身份** | `helpers/auth.cjs` 仅 `loginAsStaff`/`loginAsCustomer`/`loginAsProcurement`。**admin_role、superuser、org_admin、unverified 一个都没有** |
| **C. 金额链路零断言** | 全仓 `frontend/e2e/*.spec.cjs` 里 `subtotal` 只出现在 `state-branches-po.spec.cjs:650` 的**注释**中。`price → 购物车小计 → 订单总额 → 发票金额` 一次都没断言过 |
| **D. 角色权限分配流程在产品里不存在** | `accounts/api/v1/urls.py` 14 条路由无角色分配；`ProfileUpdateSerializer` 白名单不含 `role`/`is_staff`（`serializers.py:277-285`，已核安全）；只有 Django admin |

> 已核并**排除**的两个候选 P0（记录以免后人重复怀疑）：
> - `TransactionService.create_order`（`services.py:40-52`）**信任客户端传的 `unit_price`** —— 但全仓**只有测试在调**，无生产调用方 ⇒ 当前不可达，属"留给后人的地雷"，不是活的漏洞。
> - `checkout_views.py:93` **硬编码 `currency='USD'`**，而 `SKU.currency` 支持 USD/CNY/EUR —— 但 dev 库 **596 个 SKU 全为 USD、992 张订单全为 USD** ⇒ 当前无错误数据，属**潜在**缺陷（§6 有守卫用例）。

---

## 2. 四层设计（为什么不能只靠一层）

| 层 | 手段 | 覆盖 | 请求数次 | flake 风险 | 防的是什么 |
|---|---|---|---|---|---|
| **L1** 权限矩阵快照 | 直接调权限类求值 + 黄金文件 | **336 端点 × 8 身份 = 2688 格** | **0** | 无 | 权限口径被悄悄改掉 |
| **L2** 路由守卫单测 | 纯函数 `isInternal` + node --test | 19 内部页 + 10 客户页 × 8 身份 | 0 | 无 | 前端守卫回退（2026-10-14 那次事故） |
| **L3** 页面功能 E2E | Playwright + **断言数据** | 12 个受损格 | 中 | 中 | "能进但没数据/按钮死" |
| **L4** 业务流程 E2E | Playwright + API 落地断言 | 用户点名的 10 条流程 | 高 | 中 | 端到端断链、金额算错 |

**为什么 L1 用求值而不是 HTTP**：336 端点 × 8 身份 = 2688 次请求，每次都要造 token、保证 FK 存在（否则 404 会被误读成"权限过了"）、还要绕 `ALLOWED_HOSTS`/`EnvelopeRenderer`。而 `has_permission` 的求值是纯计算、秒级、零环境依赖。
**代价（必须承认）**：L1 测不到 `has_object_permission`（机构隔离）和 `get_queryset` 收窄（客户只能看自己的单）—— 这两块由 L4 承担。

---

## 3. L1 实现：权限矩阵快照 + 不变量

**文件**：`backend/apps/core/tests/test_role_matrix.py`（约 120 行）
**数据**：`docs/e2e/role_matrix.golden.json`（由 `role_capability_probe.py --json` 生成）

两档断言，**故意分开**：

| 档 | 内容 | 变了怎么办 | 为什么分开 |
|---|---|---|---|
| **golden**（锁现状） | 2688 格全量对比 | FAIL，必须 `--update` 重生成并在 commit message 写清"为什么改权限" | 防**无意的**漂移。若把"现状"当"期望"，修 bug 时会被自己的断言挡住；若只锁现状不锁边界，又会把缺陷一起冻住 |
| **invariants**（锁边界） | 只写 5 条确信的 | FAIL，**不允许 update**，必须改代码 | 防"修 bug 时顺手把安全边界放开" |

invariants 只有 5 条（**宁可少写，不写没把握的**）：

```python
INVARIANTS = [
    # 匿名不得有任何业务写能力（除登录/注册/询价/匿名购物车这 7 个）
    ('anon',           'POST',   '/api/v1/products/',           403),
    # 普通客户不得写产品/知识实体
    ('researcher',     'PUT',    '/api/v1/products/1/',         403),
    ('researcher',     'POST',   '/api/v1/methods/',            403),
    # 非 staff 内部人不得做 COA/SDS 审核（这是 staff 专属职责）
    ('procurement',    'GET',    '/api/v1/verified/',           403),
    # 超管专属能力不得下放
    ('staff',          'DELETE', '/api/v1/products/1/hard-delete/', 403),
]
```

**验收线**：`pytest apps/core/tests/test_role_matrix.py` 1 秒内跑完；故意把 `IsAdminOrReadOnly` 改成 `role in (...)`，测试必须变红并打印出受影响的端点数（用变异测试自证，见 `scripts/mutate_and_verify.py`）。

---

## 4. L2 实现：路由守卫表驱动单测

**文件**：`frontend/src/utils/__tests__/internalAccess.test.mjs`（node --test，与既有纯函数单测同风格）
**被测对象**：`frontend/src/utils/internalAccess.js` 的 `isInternal()`（纯函数，无 Vue 依赖）

表驱动，8 身份 × 2 断言：

| 身份 | `isInternal` 应为 | 能进 `/workspace` | 能进 `/ops/orders` |
|---|---|---|---|
| 匿名 / 未验证 / researcher / org_admin | `false` | ❌ 跳 `/` | ❌ 跳 `/` |
| procurement / admin_role / staff / superuser | `true` | ✅ | ✅ |

**为什么值得单独写**：这一层 2026-10-14 **真实坏过** —— router 改了、9 个页面组件各留一份旧守卫，路由放行后被页面层踢回，修复实际无效（见 `internal-access-procurement.spec.cjs:1-10` 的注释）。纯函数单测比 E2E 快 1000 倍且不会 flake。

**验收线**：把 `INTERNAL_ROLES` 改成 `['procurement']`，测试必须变红（admin_role 那格）。

---

## 5. L3 用例清单：12 个受损格怎么测

⚠️ **前置分叉**：第 5–12 号格（能看不能改）到底该是"隐藏按钮"还是"点了给提示"，**是产品决策，不是测试能决定的**。
测试不能先于决策写断言 —— 所以本节拆成两块。

### 5.1 可直接写用例的（行为已确定）

| # | 用例 | 身份 | 断言 | 类型 |
|---|---|---|---|---|
| L3-1 | 打开 `/ops/orders` | procurement | **现状**：表格 0 行 + 至少 1 个 403 响应 | **characterization** |
| L3-2 | 打开 `/ops/orders/1` | procurement | **现状**：主区域无订单数据 + 403 | characterization |
| L3-3 | 打开 `/workspace/verified` | procurement | **现状**：列表 0 行 + 403 | characterization |
| L3-4 | 打开 PO 审核台 → 点 `Assign Rep` | procurement | **现状**：请求 403，**无任何用户提示**（死按钮） | characterization |
| L3-5 | 打开 PO 审核台 → 点 `Assign Rep` | **admin_role** | **成功**：`assigned_rep` 落库（唯一独有能力） | functional |
| L3-6 | 遍历 19 个内部页 | researcher | 全部跳回 `/` | regression（已有，保留） |
| L3-7 | 遍历 10 个客户侧页 | org_admin | 与 researcher **逐项一致**（含 4 个写操作成功） | functional |

**关于 characterization（锁定缺陷现状）这个选择**：
不用 `test.fixme`/`skip` —— 那会静默跳过、永远没人回来。
写成"断言当前是坏的"，缺陷一修好测试**立刻变红**，强制当事人来更新本表。这是"可执行的待办"，不是"被遗忘的跳过"。每个这样的用例头部必须写：
```js
// ★ 本用例锁定的是【当前缺陷】，不是期望行为。
//   修复 PR 必须同时改这里 + ROLE_CAPABILITY_MATRIX.md §8。
```

**断言纪律（针对缺口 A）**：`#app.innerHTML.length > 200` **禁止再用**。必须断言到数据层：
- 表格行数（`.el-table__row` count）或明确的空态文案
- 关键字段文本（订单号、金额）
- 网络层：用 `page.on('response')` 收集 403，断言"没有预期之外的 403"

### 5.2 卡在产品决策上的（决策后才能写）

| # | 页面 | 我的建议决策 | 若采纳，用例断言 |
|---|---|---|---|
| 1 | `/ops/orders`（采购） | **放开读** —— 采购本来就要看订单；`/admin/orders/` 与 `/orders/` 两套 API 应统一 | 采购能看到全部订单（跨机构），但**不能**推进状态 |
| 2 | `/workspace/verified`（采购） | **从菜单移除** —— 知识实体审核是 staff 职责，不是采购 | 侧栏无该入口；直接输 URL 被踢回 |
| 3 | `/workspace` 统计卡（采购） | **后端放开只读**，或前端降级为不请求 | 统计卡显示数字而非错误态 |
| 4 | 产品/知识实体 9 个只读页（采购） | **前端按能力渲染**：写按钮隐藏（不是禁用）—— 禁用会让采购以为"自己不会用" | 页面上不存在写按钮；URL 直连写接口仍 403 |
| 5 | `KnowledgeIntake`（采购） | 同上，从菜单移除 | — |

> 4 号是这批里唯一需要**新增前端机制**的：目前前端只有 `requiresAdmin` 一档，无法表达"能进但只读"。
> 最小改法：`internalAccess.js` 再导出一个 `canWriteInternal()`（口径 = `is_staff`），菜单/按钮统一调它。
> 这与后端 `IsAdminOrReadOnly` 的判据**完全一致**，不会引入第四种口径。

---

## 6. L4 逐流程用例清单（用户点名的 10 条）

图例：`✅ 有` = 已有 spec 覆盖 · `⚠ 弱` = 只覆盖了部分维度 · `❌ 无` = 零覆盖

| # | 流程 | 角色 | 页面 | 关键端点 | 现有 | 缺口 / 要加的用例 |
|---|---|---|---|---|---|---|
| 1 | **系统维护** | 运维（无 UI） | 无 | `/health/`、`config_parity`、`migration drill`、`permission_audit` | ✅ `test_health.py`；4 个脚本已进 CI（12 job） | 缺**运维可见的入口**（现在只能 curl）。是否建站内健康页 = 产品决策，暂不测 |
| 2 | **角色权限分配** | 超管 | **Django admin**（产品内无此功能） | 无 API | ❌ | **不自动化**（Django admin 自动化成本高、回归价值低）⇒ 归 **C 类：产品面不适用**，用运营手册 + 季度人工冒烟 |
| 3 | **产品导入**（Word/PDF 解析） | staff | `/workspace/products/new` | `POST /products/parse-word/` | ✅ `product-new-doc-import.spec.cjs`；后端 `test_word_parser.py` | ⚠ 缺**畸形文件**负向（空 docx / 超长 / 非 docx 冒充）；`parse-word` 是 `IsStaffUser` ⇒ 补 procurement 403 |
| 4 | **产品新建** | staff | 同上 | `POST /products/` + SKU + 知识链接 | ✅ 5 个 spec（`save-publish`/`form-validation`/`knowledge-links`/`sku`/`ai-automatch`/`negative`） | ⚠ 缺"保存后刷新仍在"的**幂等**断言；缺 procurement 全 21 写 403（5.2 #4） |
| 5 | **产品管理**（归档/恢复/停用/删除/批量） | staff | `/workspace/products` | `POST /products/:id/archive/`、`PATCH/DELETE /products/:id/`、`batch-restore` | ✅ 4 个 spec（`batch-writes`/`fixes`/`negative`/`readonly`） | ⚠ 缺**回收站 → 前台可见性**的联动断言（生产 125 产品全在回收站、前台可见 0 这个状态从未被用例锁定） |
| 6 | **知识实体新建** | staff | `/workspace/{goals,applications,methods,protocols,references}` | `POST` 各实体 | ✅ `workspace-entity-crud.spec.cjs`；`entity-fk-e2e.spec.js` | ⚠ 缺**四层 FK 一致性**（RG→AP→Method→Protocol）的端到端断言：建完 Protocol 能否从 Method 反查到 |
| 7 | **知识实体导入** | staff | `/workspace/knowledge-intake` | `POST /knowledge-intake/` | ✅ `knowledge-intake.spec.cjs`；`workspace-entry-intake.spec.cjs` | ✅ 覆盖较好；仅补 procurement 403 |
| 8 | **知识实体管理/修改** | staff | 同 6 | `PUT` 各实体 + `/verified/` 审核 | ✅ `workspace-verified-review.spec.cjs` | ⚠ 缺**改完后的下游可见性**：改了 Method 名称，产品详情页的 method 标签是否跟着变 |
| 9 | **价格及库存管理** | staff（价格）/ procurement（库存） | `/workspace/products/*/edit`（SKU 表）、`/ops/inventory` | SKU `price`、`POST /inventory/receipt/`、`/inventory/:id/adjust/` | ⚠ 库存 ✅ `ops-inventory.spec.cjs`；**价格 ❌ 零覆盖** | **P0**：缺口 C 的全部内容，见 6.1 |
| 10 | **订单管理** | staff + procurement | `/ops/orders`、`/ops/orders/:id`、4 个 PO desk | 13 个订单/发货/开票/收款端点 | ✅ 8 个 `po-*` spec + `po-lifecycle.fullflow.spec.cjs` | ⚠ 缺 **procurement 视角**（3 个 DEAD 页）；缺**金额传导**断言 |

### 6.1 价格及金额链路（唯一的 P0 新增用例组）

**为什么是 P0**：`subtotal`/`grand_total` 在全仓 E2E 里**一次都没被断言过**，而这条链跨 4 个模块
（commerce SKU → basket → transactions Order → Invoice），任何一环算错都是真金白银。

**已核实的实现**（写用例时按这个来，不是猜的）：

| 环节 | 实现 | 位置 |
|---|---|---|
| 下单金额来源 | **服务端按 SKU 现价**（客户端传的被覆盖） | `checkout_views.py:58`、`services.py:138-141` |
| 订单行快照 | `OrderItem.unit_price` + `subtotal`，`save()` 重算小计 | `models.py:196-218` |
| 税费 | 恒 0（免税机构走 `tax_exempt_id`，当前不影响金额） | `services.py:154-156` |
| 币种 | 订单写死 `currency='USD'`；SKU 支持 USD/CNY/EUR | `checkout_views.py:93` vs `commerce/models.py:239-250` |

**用例**：

| # | 用例 | 断言 | 现状 |
|---|---|---|---|
| L4-P1 | 建产品 A（SKU 价 100，数量 2）→ 加购 → 下单 | 订单 `subtotal = grand_total = 200`；`OrderItem.unit_price = 100` | ❌ 无 |
| L4-P2 | **改** SKU 价为 150 → 新建订单 | 新订单单价 150；**旧订单仍 100**（快照生效） | ❌ 无 |
| L4-P3 | 购物车含 2 个不同 SKU（100×1 + 50×3） | 订单 `subtotal = 250`，2 行明细金额各自正确 | ❌ 无 |
| L4-P4 | 下单后 → PO 提交 → 开票 → 收款 | **发票金额 = 订单 `grand_total`**，收款记录累计不超过发票额 | ⚠ 部分（`po-lifecycle.fullflow.spec.cjs` 走通了流程，但未断言金额数值） |
| L4-P5 | 用**非 USD** 的 SKU 下单（若允许上架） | 订单 `currency` = SKU 币种，不是 USD | ❌ 无 → **预计 FAIL**，即 §1 的潜在缺陷 |
| L4-P6 | 客户端伪造 `unit_price`（把 100 改成 0.01）提交 | 服务端覆盖为 SKU 现价，落库单价 100 | ❌ 无 —— **已核**：`test_adversarial_fixes.py:42,51` 只覆盖数量溢出（`quantity=999999999`/`10000`），传的 `unit_price` 仍是真实价 `'10.00'`，**从未尝试伪造价格** |

---

## 7. 闸门与归属

沿用 `GLOBAL_TEST_DEFINITION.md §4.1` 的 A/B/C 口径，**每一格必须有承担者**：

| 层 | 归属 | 跑在哪 |
|---|---|---|
| L1 权限矩阵 | **A** | CI，每次 PR；改 golden 必须人工审 |
| L2 路由守卫 | **A** | CI（node --test，秒级） |
| L3 characterization（4 条锁定缺陷） | **B**（已知未修，有可执行动作） | `@local-only`，每次本地回归跑；**缺陷修好→变红→必须更新** |
| L3 functional（3 条） | **A** | CI |
| L4-P1~P4 | **A** | `@local-only`（依赖 dev 数据） |
| L4-P5（币种） | **B** | 不常跑；承担者 = "允许上架非 USD SKU 的 PR 必须同时跑本用例" |
| L4-P6（伪造单价） | **A** | 后端单测，CI |

**ratchet 口径（只拦新增）**：CI 只 FAIL 在**新增的**红灯和**新增的** golden 差异，不要求一次性把所有历史欠账清零 —— 否则会催生"假签名"（`GLOBAL_TEST_DEFINITION.md §4.1` 已明令禁止）。

---

## 8. 执行顺序（按依赖，不按工作量）

| 步 | 动作 | 产出 | 前置 |
|---|---|---|---|
| 1 | 补 4 个登录夹具 | `helpers/auth.cjs` +4 函数 | 需 dev 库有对应账号（`admin_role` 需 `is_staff=False`） |
| 2 | L1 权限快照 | `test_role_matrix.py` + `role_matrix.golden.json` | 无（只依赖探针） |
| 3 | L2 路由守卫单测 | `internalAccess.test.mjs` | 无 |
| 4 | L3 characterization 4 条 | `role-permission-pages.spec.cjs` | 步骤 1 |
| 5 | **产品决策 5 条**（§5.2） | 决策记录 → 改前端/后端 | ⬅ **唯一会卡住的地方** |
| 6 | L3 functional（决策后） | 同 spec 文件 | 步骤 5 |
| 7 | L4-P1~P4 金额链路 | `price-amount-chain.spec.cjs` | 步骤 1 |

**步骤 2、3 立刻可做，不依赖任何决策。** 步骤 5 是唯一需要人拍板的 —— 其余都能自主推进。

---

## 9. 本方案的边界（不测什么，为什么）

| 不测 | 原因 | 替代承担 |
|---|---|---|
| Django admin 的角色分配 | 无产品面 API/UI，自动化成本 >> 收益 | 运营手册 + 季度人工冒烟 |
| `has_object_permission`（机构隔离）与 `get_queryset` 收窄 | L1 静态求值测不到 | 归 L4 客户侧流程（客户 A 看不到客户 B 的订单） |
| 浏览器兼容 | 属另一维度（`CROSS_BROWSER_BASELINE.md`） | 已有 7 浏览器闸门 |
| 视觉/响应式 | 同上（`visual-tokens.spec.cjs`/`responsive.spec.cjs`） | 已有 |
| 性能 | 同上（`perf_gate.py` + `VOLUME_BENCHMARK.md`） | 已有 |
