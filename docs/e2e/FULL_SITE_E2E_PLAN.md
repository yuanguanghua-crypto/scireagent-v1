# 全站 E2E 测试计划 — SciReAgent 前端（彻底完全覆盖版 v2）

> 目的：对**全站每个页面、每个交互元素（按钮 / 跳转 / 输入 / 选择 / 弹窗 / 下拉 / Tab / 上传 / 分页 / 排序 / Toast / 加载态）、每个权限角色、每个业务状态、每种视口、每个浏览器、全站可访问性**建立可重复运行的端到端覆盖。
> 技术栈：Playwright（`@playwright/test`）+ 真实 Chromium/Firefox/WebKit，`baseURL=http://localhost:5173`，后端 `http://localhost:8000`。
> 状态：**计划文档 v2（彻底覆盖级）**。实现按阶段 0→10 推进，每阶段完成需回归全绿后再进下一阶段。
> 配套清单：`docs/e2e/INTERACTION_INVENTORY.md`（全站交互元素逐页扫描，本计划 §2 引用）。

---

## 0. 来自 E2E 工作台的既论证教训（必须贯穿全程）

| # | 教训 | 落地规则 |
|---|------|---------|
| 1 | 子代理会被会话压缩 499 中断，回报丢失 | **E2E / pytest 由主理人亲自后台 Bash 跑**，不派子代理、不轻信其状态 |
| 2 | 「失败」≠「没干」，改动可能已落盘 | 用例失败先 `Read` 真实文件 + 跑测试核实 |
| 3 | 根因常比表象深（slug 必填 + URL 缺斜杠） | 修复治本；E2E 锁定终端行为（如「保存成功→弹窗关闭→跳转」） |
| 4 | Flaky 来自出网 AI 慢 / 下拉竞态 / 弹窗动画 | `retries:1` + 显式 `waitForSelector` + 长超时，**不用固定 sleep** |
| 5 | Ketcher React-in-Vue 白屏（依赖 Node `process`） | 已移除 `ketcher-react`，ProductEditPage 改自包含 SMILES 编辑器，E2E 不碰 ketcher |
| 6 | dev proxy target 实际 `:8000`（非 8001）；前端端口被占跳 5174/5175 | 跑前先校验 :8000 + :5173 真实运行 |
| 7 | 沙箱 safe-delete 拦 Vite 清 `dist`（>50 文件）→ build 被拦，dev server 正常 | 沙箱内只跑 dev server E2E；`npm run build` 留本地/CI |
| 8 | 运行前提：后端 :8000 + 前端 :5173 + admin 账号(is_staff) | 全量 E2E 前先起双服务、校验账号 |
| 9 | spec 内建数据须 `DELETE` 清理，保库干净 | 写操作用例必带 cleanup，保证可重复 |
| 10 | computed style 可断言设计令牌 | 把「全站设计系统一致」纳入 E2E 断言 |
| **11** | **组件库假设必须读真实代码** | **本项目几乎不用 Element-UI**（见 §2.1）。交互用原生 `<button>` + 自定义 `AppButton/AppInput/AppSelect` + `dialog-overlay` 弹层 + `DataPagination` + 自定义 `toast` + 原生 `alert/confirm`。**所有 helper / 选择器以真实 DOM 为准，不得假设 `el-*`** |

---

## 1. 现有资产盘点

- **配置**：`frontend/playwright.config.cjs` — `baseURL:5173`、`headless:true`、`timeout:30000`、`retries:1`、**单 chromium project、单视口 1280×720**（v2 需升级，见 §7）。
- **已有 8 个 spec**（零散覆盖，非全站）：homepage / product-detail-fields / cascader-workflow / verify-dialog-style / verify-dialog-a11y / verify-improvements / verify-field-normalize / cart-button-regression。
- **Helpers 雏形**（散落各 spec）：`loginAsStaff(page)`、`openCascader` / `selectCascaderPath`、`waitForProductSave`、`traceApi`、`request` 直连 API + Token（取自 `localStorage`）。
- **交互清单**：`docs/e2e/INTERACTION_INVENTORY.md`（v2 新增，逐页扫描 52 个 .vue 文件）。

---

## 2. 全站覆盖范围（彻底级）

### 2.0 七维覆盖定义

每个页面/交互元素须从以下维度覆盖（缺任一维即"未彻底覆盖"）：

| 维度 | 含义 | E2E 手段 |
|------|------|---------|
| **I 交互** | 每个按钮/输入/选择/弹窗/下拉/Tab/上传/分页/排序/Toast/加载态都被触发并断言结果 | 元素级用例（见 §4 各阶段） |
| **P 权限** | 4 角色（匿名/customer/staff/admin）× 每受限页的 expected 行为 | §2.3 权限矩阵 + 阶段 6 |
| **S 状态** | 业务状态分支（PO 8 态 / 订单旧态 / 产品 active·draft·discontinued）UI 差异 | §2.4 状态矩阵 + 阶段 7 |
| **R 响应式** | 桌面/笔记本/平板/移动 4 视口下布局不崩、关键交互可用 | §10 视口矩阵 + 阶段 8 |
| **V 视觉** | 全站设计令牌（emerald 主色 / amber / 4px 圆角 / 中性 badge+点 / 字体）一致 | computed style 断言（§0#10）+ 阶段 9 |
| **A 可访问性** | 全站 WCAG：label 关联 / 对比度 / 焦点顺序 / aria | axe-core 扫描（§11）+ 阶段 10 |
| **B 浏览器** | chromium / firefox / webkit 行为一致 | 多 project（§7）+ 阶段 9 |

### 2.1 交互元素清单（引用 INTERACTION_INVENTORY.md）

**技术特征（关键，推翻 Element-UI 假设）**：
- 按钮：原生 `<button>` + `<AppButton>`（约 52 文件普遍使用），**无 `<el-button>`**。
- 下拉/选择：少量 `el-select`（仅 ResearchGoalIndex / AppsPage / MethodsPage / ProtocolsPage / workspace/ProductEditPage）；多选/分类多用原生 `<select>` 或 `AppSelect`。
- 弹窗：**无 `el-dialog`**，改用 `v-if="showXxx"` + `<div class="dialog-overlay">` 自定义弹层（ProductsPage / ProductEditPage / MethodsPage / ProtocolsPage / GoalsPage / AppsPage / ReferencesPage / PoAddressList）。
- 表格/分页：无 `el-table`；列表页用原生 `<table>` + `<th class="sortable" @click>` 排序，分页统一 `<DataPagination>`（`:total`/`:page-size`/`@current-change`）。
- Toast：自定义 `toast`（`toast.success/.error`）；部分页用页内 `<div class="toast/ki-toast/save-msg">`；校验失败用原生 `alert()`/`confirm()`。**无 `ElMessage`/`ElMessageBox`**。
- 加载态：`v-loading` 指令 + `<LoadingSpinner>` 组件。

**交互密度 Top（E2E 优先级，详见 inventory）**：
1. `workspace/ProductEditPage.vue` — 37 按钮 / 50 v-model / 2 弹层 / 表单校验（最密集）
2. `products/ProductEditPage.vue` — 9 按钮 / 35 v-model（**遗留版，疑已被 workspace 版取代**）
3. `admin/AdminProductEdit.vue` — 11 按钮 / 33 v-model / 上传 / 表单校验
4. `workspace/ProductsPage.vue` — 15 按钮 / 3 弹层 / 可排序表格
5. `SettingsPage` / `PoSubmit` / `CheckoutPage` / `CartPage` — 多字段表单 + 校验

**弹窗/弹层清单（自定义 dialog-overlay）**：ProductsPage(`showBatchLinkPanel`/`showArchiveDialog`/`showDeleteDialog`)、ProductEditPage(`showPublishDialog`/`showInlineEditor`)、MethodsPage/ProtocolsPage/GoalsPage/AppsPage/ReferencesPage(`showEditor`)、PoAddressList(`showForm`)、CartPage(`showSubmitApproval`)。

**Toast 断言点**：`CartPage.toast.success('Item removed from cart')`、`ProductDetail.toast.success('Added to cart')`/`toast.error('Failed to add')`、`AppsPage/MethodsPage.toast.error('Save failed: ...')`、各编辑页 `saveMessage`/`ki-toast`/`successMessage` 横幅、`PoSubmit/PoAddressList/OrderDetailPage/AdminOrderDetail` 用原生 `alert()`/`confirm()`。

### 2.2 路由 × 七维覆盖矩阵（45 页面）

> 完整交互元素见 INTERACTION_INVENTORY.md。此处标注每页需覆盖的维度与优先级（P0 必做 / P1 重要 / P2 增强）。

**公开页（无需登录）**
| 路由 | 页面 | I | P | S | R | V | A | B | 优先级 |
|------|------|---|---|---|---|---|---|---|--------|
| `/` | HomePage | 搜索/导航/分类 pills/CTA | — | — | ✓(移动汉堡) | ✓ | ✓ | ✓ | P0 |
| `/login` `/register` | Login/Register | 输入校验/提交/跳转/3步注册 | guest 已登录重定向 | — | ✓ | ✓ | ✓ | P0 |
| `/search` | SearchPage | 搜索输入/结果点击/空态 | — | — | ✓ | ✓ | ✓ | P0 |
| `/applications`+`:id` | AppIndex/Detail | 列表搜索+分页 / 详情关联跳转 | — | — | ✓ | ✓ | ✓ | P0 |
| `/methods`+`:id` | MethodIndex/Detail | 过滤 chips+分页 / 详情关联 | — | — | ✓ | ✓ | ✓ | P0 |
| `/protocols`+`:id` | ProtocolIndex/Detail | 过滤+分页 / 14列可排序表 | — | — | ✓ | ✓ | ✓ | P0 |
| `/products`+`:id` | ProductIndex/Detail | 分类 pills / Tab 切换 / Add to Cart / 数量± / SKU 行 / 文档链接 | — | 产品 active·draft·discontinued | ✓ | ✓ | ✓ | P0 |
| `/research-goals`+`:id` | RGIndex/Detail | 状态 el-select 筛选 / 详情 | — | — | ✓ | ✓ | ✓ | P0 |
| `/quote-request` | QuoteRequestPage | 多字段表单 / 提交(匿名可) / 成功横幅 | — | — | ✓ | ✓ | ✓ | P1 |
| `/cart` | CartPage | 数量改/删除/提交审批/结算跳转 / toast | — | — | ✓ | ✓ | ✓ | P1 |
| `/:pathMatch` | NotFound | 返回首页跳转 | — | — | ✓ | ✓ | ✓ | P0 |

**认证用户页（requiresAuth）**
| 路由 | 页面 | I | P | S | R | V | A | B | 优先级 |
|------|------|---|---|---|---|---|---|---|--------|
| `/settings` | SettingsPage | 20 输入 / 保存 / saveMessage 横幅 | 仅认证 | — | ✓ | ✓ | ✓ | P1 |
| `/checkout` | CheckoutPage | 12 输入 / 多步 / v-loading / 提交 | 仅认证 | — | ✓ | ✓ | ✓ | P1 |
| `/orders`+`:id` | OrderList/Detail | 列表分页 / 详情时间线 / alert 错误 | 仅认证 | 订单旧态展示 | ✓ | ✓ | ✓ | P1 |
| `/po/submit` | PoSubmit | 行项目动态表单 / 上传 / alert 校验 / 提交 | 仅认证(customer) | PO 8 态起点 | ✓ | ✓ | ✓ | P1 |
| `/po/orders`+`:id` | PoOrderList/Detail | 列表分页 / 详情时间线+发票+发货+附件 | 仅认证(customer) | PO 8 态全展示 | ✓ | ✓ | ✓ | P1 |
| `/po/addresses` | PoAddressList | CRUD / showForm 弹层 / confirm 删除 | 仅认证(customer) | — | ✓ | ✓ | ✓ | P1 |
| `/po/reorder` | PoReorder | 复制行项目 / 重订 | 仅认证(customer) | — | ✓ | ✓ | ✓ | P2 |
| `/po/downloads` | PoDownloadCenter | 下载链接 / 列表 | 仅认证(customer) | — | ✓ | ✓ | ✓ | P2 |

**管理员页（requiresAdmin，is_staff）**
| 路由 | 页面 | I | P | S | R | V | A | B | 优先级 |
|------|------|---|---|---|---|---|---|---|--------|
| `/workspace`(dashboard) | DashboardPage | 概览卡片 / 快捷入口 / LoadingSpinner | 仅 admin | — | ✓ | ✓ | ✓ | P1 |
| `/workspace/products` | ProductsPage | 15 按钮 / 3 弹层 / 可排序表 / 过滤 | 仅 admin | — | ✓ | ✓ | ✓ | P1 |
| `/workspace/products/new`+`:id/edit` | ProductEditPage | **37 按钮 / 50 输入 / 发布弹层 / 上传 / 校验** | 仅 admin | 产品发布态 | ✓ | ✓ | ✓ | P0 |
| `/workspace/goals` `/applications` `/methods` `/protocols` `/references` | 各管理页 | 增删改 / showEditor 弹层 / toast.error | 仅 admin | — | ✓ | ✓ | ✓ | P1 |
| `/workspace/knowledge-intake` | KnowledgeIntake | 12 输入 / 产品下拉 / ki-toast | 仅 admin | — | ✓ | ✓ | ✓ | P1 |
| `/admin/orders`+`:id` | AdminOrders/Detail | 过滤 / 状态流转 / alert 错误 / AiToolsPanel | 仅 admin | 订单旧态(legacy) | ✓ | ✓ | ✓ | P1 |
| `/admin/po/review` | PoReviewDesk | 待审列表 / approve/reject/assign-rep | 仅 admin | PO 审核态 | ✓ | ✓ | ✓ | P1 |
| `/admin/po/shipments` | PoShipmentDesk | 创建 ShippingRecord(多批发) / mark-shipped/delivered | 仅 admin | PO 发货态 | ✓ | ✓ | ✓ | P1 |
| `/admin/po/invoicing` | PoInvoicingDesk | 对 DELIVERED 开票 / 开票字段 | 仅 admin | PO 开票态 | ✓ | ✓ | ✓ | P1 |
| `/admin/po/ar` | PoArReport | AR aging 30/60/90 展示 | 仅 admin | — | ✓ | ✓ | ✓ | P2 |
| `/admin/po/organizations` | PoOrgManagement | 机构/地址/订单查看 | 仅 admin | — | ✓ | ✓ | ✓ | P2 |

> 注：`admin/AdminProductsPage`、`admin/AdminProductEdit` **无独立路由**（AdminLayout nav 内链），经 `/workspace/products` 入口覆盖；`products/ProductEditPage` 为遗留版，确认是否被 `workspace/ProductEditPage` 取代（见 §5 K5）。

### 2.3 权限矩阵（4 角色 × 受限页）

角色：①匿名（无 token）②customer（is_staff=False，requiresAuth）③staff（is_staff=True，即 admin 账号）④admin（同 staff，requiresAdmin）。

| 页面类型 | 匿名 | customer | staff | admin |
|---------|------|----------|-------|-------|
| 公开页（无 meta） | ✓ 可访问 | ✓ | ✓ | ✓ |
| `guest:true`（/login /register） | ✓ | 已登录→重定向(测目标) | 已登录→重定向 | 已登录→重定向 |
| `requiresAuth`（/settings /checkout /orders /po/*） | → `/login?redirect=<原路径>` | ✓ | ✓ | ✓ |
| `requiresAdmin`（/admin/* /workspace/*） | → `/login?redirect=<原路径>` | AdminLayout 重定向(测实际目标/无权限提示) | ✓ | ✓ |

**阶段 6 须逐页穷举上表**，断言：重定向 URL 含 `redirect=`、customer 访问 admin 页被拦、staff 可进。K4（匿名写返回 403 而非 401）锁定。

### 2.4 状态分支矩阵

**PO / Order 8 态**（驱动 PO 门户 + Admin 订单 UI 差异）：
`PO_RECEIVED → CONFIRMED → IN_PRODUCTION → SHIPPED → DELIVERED → INVOICED → PAID → COMPLETED`，外加 `CANCELLED`。
- 每态须测：状态标签文案+色（中性边框+语义色点）、该态可用按钮集、禁用项、时间线 StatusLog 节点。
- 需后端 seed 不同状态订单（写 `seed_e2e` 或 factory）逐态构造。
- 多批发：SHIPPED（部分发货）/ DELIVERED（全部签收）语义（见 ARCHITECTURE.md）。

**产品 status**：`active` / `draft` / `discontinued`：
- 列表/详情展示差异、ProductEditPage 发布按钮可用性、discontinued 是否仍可加购（断言预期）。

**订单旧态（legacy，deprecated）**：`DRAFT` / `QUOTE_*` / `PROCESSING` 仅存量数据展示，不测新流程（旧 admin 视图已停用，见 PRD）。

### 2.5 全局守卫与跳转链（E2E 必测）

- `router.beforeEach`：`requiresAuth` 无 token → `/login?redirect=<fullPath>`；`requiresAdmin` 无 token 同样拦截，非 staff 由 AdminLayout 重定向。
- `guest:true` 页已登录重定向目标（测实际跳转，避免回环）。
- 高频跳转目标：产品/方法/协议/应用/目标 详情↔列表、购物车→结算、PO 各节点、Workspace 各子路由、登录回调 `redirect`。

---

## 3. 测试架构

### 3.1 目录与文件组织
```
frontend/e2e/
  helpers/
    auth.cjs          # loginAs(role): anonymous|customer|staff|admin
    api.cjs           # apiContext(token) + data factory (createProduct/deleteProduct/createAddress/createPoOrderInState/...) + cleanup
    interactions.cjs  # 基于真实 DOM 的 helper（§3.2）
    console.cjs       # attachConsoleErrorCollector(page) → 返回错误数组，test 末尾断言 0
    a11y.cjs          # runAxe(page) 封装（§11）
  fixtures.cjs        # 已知数据基线 + AI mock 响应
  inventory-driven/    # 按 inventory 每页生成的 spec（阶段 1~5）
    public.spec.cjs auth.spec.cjs workspace.spec.cjs po-portal.spec.cjs admin.spec.cjs
  permission-matrix.spec.cjs   # 阶段 6
  state-matrix.spec.cjs        # 阶段 7
  responsive.spec.cjs          # 阶段 8（按视口）
  browsers.spec.cjs            # 阶段 9（跨浏览器冒烟）
  a11y.spec.cjs                # 阶段 10
  (保留既有 8 个 spec，迁移通用 helper 后逐步并入)
```

### 3.2 交互 Helper（基于真实组件，非 el-*）
- `clickButton(page, {text?, testId?, role?})`：按文本 / `data-testid` / `role=button` 定位点击（兼容原生 `<button>` 与 `<AppButton>`）。
- `openDialog(page, trigger)` / `closeDialog(page, {esc?, overlay?, cancelText?})`：等 `.dialog-overlay` 可见 / 按 ESC 或点遮罩或取消按钮关闭。
- `fillField(page, labelOrTestId, value)`：按 `<label>` 文本或 `data-testid` 填 `AppInput`/原生 input。
- `selectNative(page, selectEl, value)` / `selectApp(page, trigger, optionText)`：原生 `<select>` 与 `AppSelect`。
- `waitForToast(page, text)`：等 `.toast`/`.save-message`/`.ki-toast` 含文本（成功/错误分别断言）。
- `handleDialog(page, {accept})`：`page.on('dialog')` 处理原生 `alert`/`confirm`（PoSubmit/PoAddressList/OrderDetailPage/AdminOrderDetail 用）。
- `waitForLoadingGone(page)`：等 `v-loading` / `.loading-spinner` 消失。
- `sortByColumn(page, thText)`：点 `<th class="sortable">` 并断言排序。
- `paginate(page, {page})`：点 `DataPagination` 对应按钮。
- **data-testid 约定（建议，非强制）**：为彻底覆盖稳定性，建议前端对关键交互加 `data-testid`（属 P2 增强；未加前用文本/role 定位）。

### 3.3 Mock 策略（出网 AI 端点）
- 对 `**/api/v1/products/enrich/` 与 `**/api/v1/products/recommend-*` 等出网端点，用 `page.route()` + `route.fulfill({ status:200, json: <fixture> })` 隔离网络抖动。
- mock fixture 放 `e2e/fixtures/ai-responses.json`（enrich 5 段 + recommend 返回）。
- 仅「真实 AI 联调」专项用例关闭 mock、真实等待（长超时）。

### 3.4 Console 错误雷达
- 每 spec `test.beforeEach` 挂 `page.on('console')` + `page.on('pageerror')` 收集 error 级。
- `test.afterEach` 断言数组为空（白屏/运行时异常早期雷达）。
- 已知噪声第三方警告用白名单过滤（记录原因）。

### 3.5 数据清理
- 写操作：factory 创建 → `finally { deleteXxx() }`。
- 历史只读数据（产品 21/23/66 等）不写。
- 状态分支用例：seed 指定态订单 → 测完删除。

---

## 4. 阶段拆分与产出（元素级穷举）

| 阶段 | 范围 | 维度 | 产出 spec | 退出标准 |
|------|------|------|----------|---------|
| **0 冒烟雷达** | 45 路由：加载成功 + 0 console error + 关键元素可见（桌面视口） | I(加载)/V(无崩) | `public-smoke.spec.cjs`（含 admin/customer 路由对应登录） | 全路由绿，0 白屏 |
| **1 公开页交互穷举** | §2.2 公开页每个按钮/输入/选择/弹窗/下拉/Tab/分页/排序/Toast 触发断言 | I | `inventory-driven/public.spec.cjs` | 交互断言绿 |
| **2 认证流程穷举** | 登录/注册/设置/购物车/结算/下单/我的订单/Quote 全字段校验+跳转+toast | I | `inventory-driven/auth.spec.cjs` | 交易链路绿 |
| **3 Workspace 穷举** | ProductEditPage(37按钮/50输入/发布弹层/上传/校验) + Apps/Methods/Protocols/Goals/Refs/KnowledgeIntake 增删改弹层 | I | `inventory-driven/workspace.spec.cjs` | 研究员主流程绿 |
| **4 PO 门户穷举** | 客户侧 6 页 + 内部台 5 页（提交+附件/审核/分批改发/开票/AR/地址/下载） | I | `inventory-driven/po-portal.spec.cjs` | 提交→审核→发货→开票→下载 绿 |
| **5 Admin 穷举** | AdminOrders/Detail 审核/发货/开票 + AiToolsPanel | I | `inventory-driven/admin.spec.cjs` | legacy + 新流程绿 |
| **6 权限矩阵穷举** | §2.3 每受限页 × 4 角色 expected 行为 | P | `permission-matrix.spec.cjs` | 匿名→登录页(含 redirect)、customer→403/重定向、staff→OK 全绿 |
| **7 状态分支穷举** | §2.4 PO 8 态 UI + 产品 3 态 UI + 订单旧态展示 | S | `state-matrix.spec.cjs` | 每态标签/按钮集/时间线绿 |
| **8 响应式视口矩阵** | §10 四视口 × 关键页布局不崩+交互可用 | R | `responsive.spec.cjs` | 四视口关键页绿 |
| **9 跨浏览器 + 视觉** | chromium/firefox/webkit 冒烟 + 全站设计令牌 computed style 断言 | B/V | `browsers.spec.cjs` + `visual-tokens.spec.cjs` | 三浏览器一致 + token 一致 |
| **10 全站 a11y** | axe-core 扫每页 violations | A | `a11y.spec.cjs` | 0 critical/serious violation |

> 阶段 0~5 实现时，每页用例须对照 INTERACTION_INVENTORY.md 该行"按钮/弹窗/Toast/加载态"列，**逐元素写 test**，不得抽样。

---

## 5. 已知问题登记（E2E 中锁定为「预期」断言，避免误报）

| ID | 现象 | 处理 |
|----|------|------|
| K1 | L1 根分类产品编辑页 cascader 回填空（`checkStrictly:false` 限制） | 用空值锁定；待 cascader 改 `checkStrictly:true` 或 jena apply 走叶子后代后更新用例 |
| K2 | Jena apply 后 cascader 选中 L1 根失败（同 K1 根因） | 同上锁定 |
| K3 | 无 CAS 产品「生成 SDS」按钮禁用+tooltip（设计预期） | 断言 disabled + tooltip 文案 |
| K4 | 匿名写返回 403（DRF 标准） | 断言 403 而非 401 |
| **K5** | `products/ProductEditPage.vue` 为遗留版，与 `workspace/ProductEditPage.vue` 疑似重复 | 先确认前者是否被取代；若取代则 E2E 只覆盖 workspace 版并标记 K5；若并存则两版都测 |
| **K6** | `admin/AdminProductsPage`/`AdminProductEdit` 无独立路由，经 `/workspace/products` 内链访问 | E2E 从 workspace 入口覆盖，断言内链可达 |

---

## 6. 账号与数据基线

- **admin（is_staff）**：现有 spec 默认 `admin` / `AdminPass123!`（可用 `E2E_USER`/`E2E_PASS` 覆盖）。跑前须确认账号在测试库存在。
- **customer（is_staff=False，待建）**：阶段 0 基础设施创建，建议：
  - 用户名 `e2e_customer`，密码经 `E2E_CUSTOMER_PASS` 注入（不落库明文）。
  - 关联一个 `Organization`（供 PO 客户侧地址/订单使用）。
  - 创建方式：Django shell 一次性 seed，或 `management/seed_e2e.py` 命令（幂等）。
- **状态种子**：`seed_e2e` 须能造 PO 各态订单（PO_RECEIVED…COMPLETED/CANCELLED）+ 产品三态，供阶段 6/7。
- **已知只读数据**：产品 21（L1 根分类）、23（incomplete published）、66（SC8047 详情字段基准）等。

---

## 7. 运行命令与 playwright.config 升级

**配置升级（实现阶段 0 前改动 `playwright.config.cjs`）**：
```js
projects: [
  { name: 'chromium', use: { browserName: 'chromium' } },
  { name: 'firefox',  use: { browserName: 'firefox' } },
  { name: 'webkit',   use: { browserName: 'webkit' } },
],
// 视口矩阵在 responsive.spec.cjs 内用 test.use({ viewport }) 覆盖，不写死在全局
```
- 全局 `viewport` 保留 1280×720（默认桌面）；响应式专项用 `test.use` 覆盖。
- axe：`npm i -D @axe-core/playwright`，`a11y.cjs` 封装 `AxeBuilder`。

**运行**：
```bash
# 前置：起服务（沙箱内）
cd src_claude/backend && DB_ENGINE=sqlite venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 &
cd src_claude/frontend && npm run dev   # 标准 5173；被占则看实际端口

# 全量 E2E（主理人后台 Bash 跑，不派子代理）
cd src_claude/frontend && npx playwright test

# 按阶段 / 项目
npx playwright test e2e/inventory-driven/public.spec.cjs
npx playwright test --project=firefox          # 跨浏览器
npx playwright test e2e/responsive.spec.cjs     # 响应式

# 环境变量
E2E_USER=admin E2E_PASS=AdminPass123! E2E_CUSTOMER_USER=e2e_customer E2E_CUSTOMER_PASS=xxx npx playwright test
```

> 沙箱内 `npm run build` 可能因 safe-delete 护栏被拦，CI 须在普通 runner 执行；跨浏览器需 `npx playwright install firefox webkit`。

---

## 8. 风险与对策

| 风险 | 对策 |
|------|------|
| 子代理中断丢结果 | 主理人亲自 Bash 跑 E2E |
| AI 出网抖动致 flaky | mock 隔离（§3.3） |
| 端口跳变 / 代理 target 错 | 跑前校验 :8000 + :5173（§0#6） |
| 写操作污染库 | factory + cleanup（§3.5） |
| 已知 bug 误报失败 | 登记为预期断言（§5） |
| 弹层/下拉竞态 | 复用 helper + retries（§0#4） |
| **组件库误判（el-* 不存在）** | 所有选择器基于真实 DOM（§0#11 / §2.1） |
| 跨浏览器/视口差异 | 阶段 8/9 专项；webkit 对 `:has` 等支持差异先记录 |
| a11y 噪声 | axe 规则白名单（颜色对比度容忍度按设计系统校准） |

---

## 9. 下一步

1. 本计划 v2 经用户确认。
2. 升级 `playwright.config.cjs`（多浏览器 project）。
3. 实现**阶段 0**：`e2e/helpers/*` + 创建 customer 账号 seed + `public-smoke.spec.cjs`（全路由冒烟）。
4. 阶段 0 回归全绿后，逐阶段推进 1→10，每阶段退出标准满足再进下一阶段。
5. **彻底覆盖验收**：阶段 10 完成后，对照 §2.2 矩阵逐页打勾，确认 I/P/S/R/V/A/B 七维全覆盖、0 遗漏。
