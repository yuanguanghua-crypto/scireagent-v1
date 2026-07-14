# 全站 E2E 测试计划 — SciReAgent 前端（彻底完全覆盖版 v2.1）

> 目的：对**全站每个页面、每个交互元素（按钮 / 跳转 / 输入 / 选择 / 弹窗 / 下拉 / Tab / 上传 / 分页 / 排序 / Toast / 加载态）、每个权限角色、每个业务状态、每种视口、每个浏览器、全站可访问性**建立可重复运行的端到端覆盖。
> 技术栈：Playwright（`@playwright/test`）+ 真实 Chromium/Firefox/WebKit，`baseURL=http://localhost:5173`，后端 `http://localhost:8000`。
> 状态：**计划文档 v2.1（彻底覆盖级）**。v2.1 相对 v2 增补：§10 响应式视口矩阵、§11 a11y 章节、Basic Auth 前置、两套账号体系区分、账号基线更正（admin/scire/e2e_customer）、状态逐态表、§5.1 三项修复回归专项、阶段退出量化门槛与验收报告机制。实现按阶段 0→10 推进，每阶段完成需回归全绿后再进下一阶段。
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

角色（⚠️ 见 §6「两套账号体系」区分 Basic Auth 与 Django 应用账号）：
- ① **匿名**（无 Django token）
- ② **customer**（`is_staff=False`，`requiresAuth`，普通登录用户）
- ③ **staff**（`is_staff=True` 的研究员账号，如 `scire02`/`scire03`/`admin`，可进 `/workspace`）
- ④ **admin**（`is_staff=True` **且** `is_superuser`，可进 `/admin` 及 `/workspace`）

> 读/写必须分开断言（同一受限页，匿名读与匿名写、customer 读与 customer 写响应不同）：

| 页面类型 | 匿名（读） | 匿名（写） | customer（读） | customer（写） | staff/admin |
|---------|-----------|-----------|---------------|---------------|------------|
| 公开页（无 meta） | ✓ 可访问 | ✓（公开资源） | ✓ | ✓ | ✓ |
| `guest:true`（`/login` `/register`） | ✓ | — | 已登录→重定向(测目标) | 已登录→重定向 | 已登录→重定向 |
| `requiresAuth`（`/settings` `/checkout` `/orders` `/po/*`） | → `/login?redirect=<原路径>` | → `/login?redirect=<原路径>`（或 403，视 endpoint） | ✓ | ✓ | ✓ |
| `requiresAdmin`（`/admin/*` `/workspace/*`） | → `/login?redirect=<原路径>` | **403**（K4，DRF 标准，非 401） | **AdminLayout 重定向 / 无权限提示**（非 403，UI 层拦截） | **403**（API 层） | ✓ |

**逐页穷举断言清单（阶段 6）**：
1. 匿名访问受限页 → 重定向 URL **含 `redirect=<原路径>`**（断言 `response.url()` 匹配，`not 401`）。
2. 匿名 POST/PUT/DELETE 受限写操作 → **断言 403**（K4），非 401、非 200。
3. customer（`is_staff=False`）访问 `/workspace/*` 或 `/admin/*`：
   - 页面导航 → 命中 AdminLayout 重定向 / 显示无权限提示（断言**不进入工作台内容**）。
   - 直接调受限写 API → 断言 403。
4. staff（`scire02`/`scire03`）访问 `/workspace/*` → 200 且可见工作台内容；访问 `/admin/*` → 若非 superuser 则按 AdminLayout 规则重定向（见 §6 账号分工）。
5. admin（`admin`）→ 全部 200。

### 2.4 状态分支矩阵

#### 2.4.1 PO / Order 8 态逐态表（驱动 PO 门户 + Admin 订单 UI 差异）

流转：`PO_RECEIVED → CONFIRMED → IN_PRODUCTION → SHIPPED → DELIVERED → INVOICED → PAID → COMPLETED`，外加 `CANCELLED`。

| 状态 | 状态点色（设计系统） | 客户侧（/po/*）可用按钮集 | 内部台（/admin/po/*）可用按钮集 | 禁用项 | 时间线 StatusLog 节点 | 备注 |
|------|-------------------|------------------------|------------------------------|--------|---------------------|------|
| `PO_RECEIVED` | 灰（中性） | 查看 / 编辑（未确认前） | 审核：approve / reject / assign-rep | 发货/开票 | 已收到 | 起点 |
| `CONFIRMED` | 蓝（info） | 查看 / 重订入口隐藏 | 标记生产 / 退回 | 发货/开票 | 已确认 | — |
| `IN_PRODUCTION` | 琥珀（amber） | 查看 | 标记发货（部分） | 开票 | 生产中 | — |
| `SHIPPED` | 蓝（info） | 查看 / 下载（若有） | 标记签收（全部）/ 记录分批 | 开票（未 DELIVERED） | 已发货（可能部分） | 多批发：部分发货语义 |
| `DELIVERED` | 绿（emerald） | 查看 / 下载 | 开票（对 DELIVERED） | — | 已签收 | 多批发：全部签收 |
| `INVOICED` | 琥珀（amber） | 查看发票 | 标记收款 | 重开发票 | 已开票 | 仅 DELIVERED 可开票 |
| `PAID` | 绿（emerald） | 查看 | 标记完成 | — | 已付款 | — |
| `COMPLETED` | 绿（emerald） | 查看 | — | 全部写操作 | 已完成 | 终态 |
| `CANCELLED` | 红（danger） | 查看 | 查看（不可再流转） | 全部写操作 | 已取消 | 终态，独立分支 |

- 每态须 seed 指定态订单（§3.1 factory `createPoOrderInState(state)`），断言：状态标签文案 + 点色（computed style 取色）、按钮集与禁用项、时间线节点存在。
- 多批发：SHIPPED（部分发货）/ DELIVERED（全部签收）语义（见 ARCHITECTURE.md），需构造「部分发货→再发货→全部签收」序列用例。
- 状态点色断言：取 `.status-dot` 背景色，对照设计系统 `emerald/amber/blue/danger` 令牌（§0#10）。

#### 2.4.2 产品 3 态逐态表

`active` / `draft` / `discontinued`：

| 状态 | 列表/详情展示 | 详情页结构图（§5.1 修复） | Add to Cart | ProductEditPage 发布按钮 | 备注 |
|------|-------------|------------------------|------------|------------------------|------|
| `active` | 正常展示 + 完整信息 | ✅ 优先显示文档图（structure_image），无则回退 SMILES 渲染 | ✅ 可加购 | 可用（可改回 draft？按业务） | 正式上线 |
| `draft` | 标记「草稿」徽标，部分字段可能空 | 同 active（若有图） | ⚠️ **非 active 不可加购**（断言购物车按钮禁用 / 点击报「未发布」） | 可用（发布→active） | 未发布 |
| `discontinued` | 标记「停产」徽标（红/灰） | 同 active（若有图） | ⚠️ **断言不可加购**（按钮禁用，文案「已停产」） | 可用（可作归档编辑） | 停产，仍可见详情 |

> 断言预期固化：**`draft` 与 `discontinued` 均不可加购**（按钮 `disabled` + 文案提示）；仅 `active` 可加购。此预期须写进 `product-detail` 用例，避免回归。

#### 2.4.3 订单旧态（legacy，deprecated）

`DRAFT` / `QUOTE_*` / `PROCESSING` 仅存量数据展示，不测新流程（旧 admin 视图已停用，见 PRD）。阶段 7 仅断言「旧态订单能在订单详情页正常渲染、不白屏」，不测状态流转。

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

### 3.1.1 数据 Factory 实体依赖图与最小字段集

Factory 函数（`api.cjs` 内）须按真实外键依赖构造，避免 seed 因 NOT NULL 约束失败：

```
Organization (必填: name)
   └─ Address (必填: org_id, line1, city, country)
Product (必填: name, slug, status[active/draft/discontinued])
   ├─ SKU (必填: product_id, sku_code)
   ├─ ProductMethod / MethodProtocol (可选，关联知识实体)
POOrder (必填: org_id, po_number[UNIQUE 注意空串冲突 K-UNIQUE], status)
   ├─ POOrderLine (必填: po_id, product_id, qty, unit_price)
   ├─ Shipment (SHIPPED/DELIVERED 态: po_id, carrier, tracking_no)
   ├─ Invoice (INVOICED 态: po_id, invoice_no, amount)
   └─ StatusLog (每态流转自动写入; 断言时间线节点用)
QuoteRequest (匿名可建: 必填 email + 产品描述)
```

- **最小字段集**：每个 factory 仅填 NOT NULL 字段 + 驱动本用例必需的字段，不填无关可选字段（保持测试数据精简、可重复）。
- **幂等策略**：`createXxx` 用固定 slug/code；`finally { cleanupXxx }` 按主键删除，保证重跑无 UNIQUE 冲突（尤其 `po_number`：用随机后缀或显式 cleanup，避免 K-UNIQUE 复现）。
- **状态构造**：`createPoOrderInState(state)` 内部按 §2.4.1 流转顺序依次建态并写 StatusLog，最终落到目标态；避免直接 INSERT 终态导致时间线缺失。
- **隔离**：所有 factory 数据前缀 `e2e_`（产品 slug `e2e-prod-*`、PO `e2e-po-*`），cleanup 按前缀批量删，防遗漏。

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

### 3.3 Mock 策略（出网 AI 端点隔离）

所有会触发**出站网络**的端点必须 mock，否则受沙箱/网络抖动影响致 flaky。完整出网端点清单：

| 端点（后端代理出网） | 触发场景 | mock 关键字段 | 关联修复/用例 |
|---------------------|---------|--------------|--------------|
| `POST /api/v1/products/enrich/` | 产品编辑页「AI 补全」 | `{smiles, formula, molecular_weight, name, cas, source}` | — |
| `POST /api/v1/products/recommend-protocols/` | 推荐协议 | `{protocols:[{id,name}]}` | — |
| `POST /api/v1/products/recommend-literature/` | 推荐文献 | `{references:[{id,title}]}` | — |
| `POST /api/v1/products/validate/` | SMILES/结构校验 | `{valid:true, message}` | §5.1 修复2 |
| `POST /api/v1/products/render-structure/` | SMILES→SVG 渲染 | `{svg:"<svg...>"}` | §5.1 修复1（详情页图） |
| **`POST /api/v1/products/apply-pubchem-candidate/`** | PubChem 候选写入（§5.1 修复2） | `{smiles, formula, molecular_weight, confidence, formula_mismatch, mw_mismatch, requires_review}` | **守卫：formula_mismatch/requires_review 时前端须拦截、不写 SMILES** |
| `POST /api/v1/knowledge/graph-match/` 或 `jena` 匹配 | jena 索引匹配分类 | `{matches:[{id,label,score}]}` | K1/K2 cascader |
| `POST /api/v1/products/parse-word/` | Word 文档解析提取结构图/SMILES | `{structure_image_base64, smiles, ...}` | §5.1 修复1（落库） |

- 用 `page.route('**/api/v1/products/enrich', r => r.fulfill({status:200, json: fixture}))` 等逐端点拦截（注意 path 匹配用 glob，避免漏 `/`）。
- fixture 放 `e2e/fixtures/ai-responses.json`，结构示例：
  ```json
  {
    "enrich": { "smiles": "C1=...", "formula": "C9H14N5O12P3", "molecular_weight": 483.1, "name": "Sample", "cas": null, "source": "pubchem" },
    "pubchem_candidate_ok": { "smiles":"C1=...", "formula":"C9H14N5O12P3", "molecular_weight":483.1, "confidence":"high", "formula_mismatch":false, "mw_mismatch":false, "requires_review":false },
    "pubchem_candidate_bad": { "smiles":"WRONG", "formula":"C20H30O2", "molecular_weight":302.0, "confidence":"low", "formula_mismatch":true, "mw_mismatch":true, "requires_review":true }
  }
  ```
- **真实联调用例**（不打 mock）：仅「AI 联调专项」关闭 mock、用 `test.slow()` + 长超时（≥60s）真实等待 PubChem/jena；其余用例一律 mock。
- apply-pubchem-candidate 守卫用例：mock `pubchem_candidate_bad`（formula_mismatch=true），断言前端 `applyCandidate` 被拦截、SMILES 输入框不变、显示错误 feedback（见 §5.1 修复2）。

### 3.4 Console 错误雷达

- 每 spec `test.beforeEach` 挂 `page.on('console')` + `page.on('pageerror')` 收集 error 级。
- `test.afterEach` 断言数组为空（白屏/运行时异常早期雷达）。
- **白名单（已知噪声，按原因过滤，不计入失败）**：

| 噪声特征（substring 匹配） | 来源 | 过滤原因 |
|--------------------------|------|---------|
| `favicon.ico` 404 | 浏览器自动请求 | 测试环境无 favicon，无害 |
| `[vite]` / `HMR` / `hmr` | Vite dev server | 开发热更新日志，非应用错误 |
| `Download the Vue Devtools` | Vue 生产/开发提示 | 框架提示，非错误 |
| `Source map` / `sourcemap` | 构建产物 | 仅在 dev 偶发，无害 |
| `Cross-Origin` / `CORS` 来自 `pubchem.ncbi` / `jena` | 出网端点（已 mock 时仍可能预检） | 联调专项外不阻断；真实联调用例单独处理 |
| `net::ERR_` 在 `route.fulfill` 已 mock 的端点 | 路由拦截日志 | 断言由用例负责，非 console 错误 |

- 过滤实现：`console.cjs` 维护 `CONSOLE_IGNORE = [/favicon/, /\[vite\]/, /Devtools/, ...]`，`afterEach` 对未过滤项断言为空。
- 真 `pageerror`（未捕获异常）**绝不白名单**，一律失败——它是白屏/崩溃的直接信号。

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

### 4.1 阶段退出标准量化（覆盖率门槛）

每阶段进入下一阶段前，须满足以下量化门槛（避免「跑过即算绿」的虚假覆盖）：

| 门槛项 | 阈值 | 度量方式 |
|--------|------|---------|
| 本阶段 spec 通过率 | **100%**（0 failed） | `npx playwright test --reporter=line` |
| 交互元素覆盖率（I 维） | 每页用例数 **≥** 该页 INTERACTION_INVENTORY 「按钮/弹窗/Toast/加载态」条目数 | 逐页比对 inventory 行 vs spec `test` 数 |
| Flake 率 | 连续 2 次全量跑 **≤ 1%** 用例不稳定（重试后通过） | CI 跑 2 遍，统计 `retries` 命中数 |
| 控制台错误 | 0 未过滤 error（§3.4 白名单外） | `afterEach` 断言 |
| 权限/状态维（阶段 6/7） | 矩阵**每行每列**均有断言，0 遗漏 | §2.3 / §2.4 表 vs 用例 |
| 视口/浏览器维（阶段 8/9） | 4 视口 × 关键页 + 3 浏览器冒烟全绿 | §10 / §7 project |
| a11y 维（阶段 10） | 0 critical/serious violation | axe-core 报告 |

> 覆盖率口径：以 `INTERACTION_INVENTORY.md` 为权威清单。阶段 0~5 每页 `test` 数不得低于 inventory 该页交互条目数；若 inventory 有漏扫交互，先补 inventory 再补用例（双向同步）。

### 4.2 验收与报告机制

- **本地报告**：`npx playwright test --reporter=html` 生成 `playwright-report/index.html`（含每用例步骤 / 失败快照 / trace）。
- **CI 报告**：`--reporter=github` 或 `list` + JUnit `results.xml`（`@playwright/test` 内置），供流水线汇总。
- **失败分类流程**：
  1. 失败先判 **flaky**（重跑通过）→ 归为稳定性问题，查 §0#4（出网/竞态/动画），加 `waitForSelector` 或 `retries`。
  2. 稳定失败 → 判 **真 bug** → 提 issue + 在 §5 登记（或更新既有 K 条目），E2E 先以「预期」锁定避免阻塞（仅限已确认的非阻断缺陷）。
  3. 真 bug 修复后，解除锁定、验证绿。
- **覆盖率看板**：阶段 10 完成后，对照 §2.2 矩阵逐页打勾（I/P/S/R/V/A/B 七维），输出 `COVERAGE.md` 勾选表，0 遗漏为彻底覆盖达成标志。
- **轨迹留痕**（见 §6）：scire02/scire03 执行的 E2E 轨迹（账号 + 用例 + 时间）建议并入报告元信息，便于测试人员问题回溯。

---

## 5. 已知问题登记（E2E 中锁定为「预期」断言，避免误报）

| ID | 现象 | 处理 |
|----|------|------|
| K1 | L1 根分类产品编辑页 cascader 回填空（`checkStrictly:false` 限制） | **状态待回填**：阶段 3（Workspace 穷举）实跑 `ProductEditPage` 确认是否仍存在；若 jena apply 走叶子后代后已修复 → 移除 K1 锁定、改断言正确回填；若仍在 → 维持空值锁定并提 issue |
| K2 | Jena apply 后 cascader 选中 L1 根失败（同 K1 根因） | 同 K1：阶段 3 实跑回填结论 |
| K3 | 无 CAS 产品「生成 SDS」按钮禁用+tooltip（设计预期） | 断言 disabled + tooltip 文案 |
| K4 | 匿名写返回 403（DRF 标准） | 断言 403 而非 401 |
| **K5** | `products/ProductEditPage.vue` 遗留版与 `workspace/ProductEditPage.vue` 关系 | **2026-07-14 已确认**：`workspace/ProductEditPage.vue` 为权威完整版（产品编辑页是完整单元，勿拆碎）；`products/ProductEditPage.vue` 为遗留版，**E2E 只覆盖 workspace 版**，标记 K5 为「已取代/仅覆盖 workspace 版」 |
| **K6** | `admin/AdminProductsPage`/`AdminProductEdit` 无独立路由，经 `/workspace/products` 内链访问 | E2E 从 workspace 入口覆盖，断言内链可达 |
| **K-UNIQUE** | `po_number` 空串 UNIQUE 冲突致 500（阶段 7 状态 seed 易触发） | factory 用随机后缀 / 显式 cleanup（见 §3.1.1），断言不 500 |

### 5.1 功能修复回归专项（v2026.07.14 三项修复）

> 对应后端 `3da02a3` / `14e2fe3` 发布。以下用例须纳入 `regression-fixes.spec.cjs`，**每次全量 E2E 必跑**，防止回退。

**修复 1：详情页结构图优先于 SMILES 渲染（`frontend/src/views/ProductDetail.vue`）**
- 前提：产品同时含 `structure_image`（文档提取图，base64）与 `rendered_svg`（SMILES 渲染）。
- 用例：`product-detail-structure-image.spec.cjs`
  - 打开含 structure_image 的产品详情页 → 断言 `<img class="pd-structure-img">` **存在且可见**、`src` 非占位。
  - 断言该 img 在 `renderedSvg` 容器**之前**（DOM 顺序 / 视觉优先）。
  - 反转数据（仅 rendered_svg、无 structure_image）→ 断言回退显示 rendered_svg。
- 防回退：若有人删 `<template v-if="product.structure_image">`，用例失败。

**修复 2：PubChem 模糊匹配守卫拦截（后端 `pubchem_enhancer` + 前端 `applyCandidate`）**
- 用例：mock `apply-pubchem-candidate` 返回 `pubchem_candidate_bad`（`formula_mismatch:true` / `requires_review:true` / `confidence:low`）。
- 断言（前端 `ProductEditPage.applyCandidate`）：
  - 点击候选「Use this」按钮 → **被 `:disabled` 拦截 / 点击后 `setFeedback('error', ...)` 提示 Formula 不符**。
  - **SMILES 输入框值不变**（不写入错误分子）。
  - 候选卡显示文档 Formula 与匹配 Formula 对比（`formula_mismatch` 标记）。
- 正向用例：mock `pubchem_candidate_ok`（`formula_mismatch:false`）→ 点击写入成功。

**修复 3：重存产品 SKU 不丢 CoA / Batch（后端 `ProductCreateUpdateSerializer` 增量同步）**
- 用例：用 API 建一产品（含 1 SKU + 该 SKU 的 CoA/Batch 记录）→ 再 PATCH 更新同一产品（传同一 sku_code、不传 id）→ 断言：
  - SKU **id 稳定**（未重建）→ CoA/Batch 级联记录仍在（不被 CASCADE 删）。
  - 移除某 SKU 行 → 该 SKU 及关联 CoA/Batch 被删，其余存活。
  - 新增无 id 的 SKU 行 → 新建不冲突。
- 后端单测已覆盖（`test_serializers.py::ProductCreateUpdateSerializerSKUSyncTest`），E2E 侧用 UI 重存路径补端到端验证。

---

---

## 6. 账号与数据基线

### 6.1 两套账号体系（务必区分）

| 体系 | 控制什么 | 存储 | E2E 如何使用 |
|------|---------|------|-------------|
| **① nginx Basic Auth** | 谁能**进站点**（整站 `auth_basic "SciReAgent Internal Test"`，401 拦截） | 服务器 `/etc/nginx/.htpasswd`（非 Django） | Playwright context 须带 basic auth，否则所有请求 401 |
| **② Django 应用账号** | 业务权限（匿名/customer/staff/admin） | `auth_user` 表 | 前端登录（`/login`）拿 token，驱动业务断言 |

> ⚠️ **两套账号相互独立**：`scire01`~`scire06` 仅存在于 Basic Auth，**不是 Django 用户**（Django `auth_user` 查不到）；Django 的 `admin`/`scire02`/`scire03`/`e2e_customer` 也需在 Basic Auth 通过后才能访问站点。E2E 必须**同时**满足两层。

### 6.2 Basic Auth 前置（E2E 必做，原文档遗漏）

站点经 nginx `auth_basic` 保护。Playwright 在 `baseURL=https://scireagent.com`（或本地 nginx）下**必须注入 basic auth**，否则全部 401：

```js
// playwright.config.cjs 或 spec 内
use: {
  httpCredentials: { username: process.env.E2E_BASIC_USER, password: process.env.E2E_BASIC_PASS },
  // 或 baseURL 内联： https://scire01:c5CCzN7LadMr@localhost
}
```
- Basic Auth 账号（来自服务器 `deploy/CREDENTIALS.txt`，明文，**已 gitignore**）：

| 账号 | 密码 | 用途 |
|------|------|------|
| `scire01` | `c5CCzN7LadMr` | 站点访问（休斯顿/北京测试人员共用入口之一） |
| `scire02` | `l618tWxn1CDi` | 站点访问 **+ Django staff**（见 6.3） |
| `scire03` | `TpJOAXrameB3` | 站点访问 **+ Django staff**（见 6.3） |
| `scire04`~`scire06` | 见 `CREDENTIALS.txt` | 站点访问（普通） |

- 本地 dev（`localhost:5173` + `localhost:8000`）若未套 nginx basic auth，则无需此步；**仅真环境/预发需带**。

### 6.3 Django 应用账号基线（2026-07-14 核实）

| 账号 | 密码 | 角色 | 状态 | E2E 用途 |
|------|------|------|------|---------|
| `admin` | **`admin123`** | superuser（兼管订单/发票） | 存在 | Workspace + Admin 全部；spec 默认 staff/admin 身份 |
| `scire02` | `l618tWxn1CDi` | **Django staff（is_staff）** | 2026-07-14 建库并授权 | **休斯顿实验室研究员**测试账号；执行 Workspace E2E，其轨迹留痕有价值（§4.2） |
| `scire03` | `TpJOAXrameB3` | **Django staff（is_staff）** | 2026-07-14 建库并授权 | **北京产品测试人员**测试账号；执行前端/Workspace E2E，轨迹留痕有价值 |
| `e2e_customer` | `E2ePass123!` | customer（is_staff=False） | **已存在**（非「待建」） | 认证用户/PO 客户侧用例 |
| `e2e_user_demo` | （测试库既有） | customer | 存在 | 补充认证用例 |
| `solo_researcher` | — | — | **2026-07-14 已删除**（不明来历） | 不再使用 |

> 纠正旧文档：admin 密码为 **`admin123`**（非 `AdminPass123!`）；`e2e_customer` 已存在（非待建）；`scire02`/`scire03` 为 2026-07-14 新增的 staff 测试账号（休斯顿/北京），其访问/操作轨迹具分析价值，E2E 报告应带账号元信息（§4.2）。

### 6.4 环境变量（运行命令配套）

```bash
E2E_BASIC_USER=scire01 E2E_BASIC_PASS=c5CCzN7LadMr \
E2E_USER=admin E2E_PASS=admin123 \
E2E_CUSTOMER_USER=e2e_customer E2E_CUSTOMER_PASS=E2ePass123! \
E2E_STAFF_USER=scire02 E2E_STAFF_PASS=l618tWxn1CDi \
npx playwright test
```

### 6.5 状态种子与已知只读数据

- **状态种子**：`seed_e2e` 须能造 PO 各态订单（PO_RECEIVED…COMPLETED/CANCELLED）+ 产品三态，供阶段 6/7（构造见 §3.1.1）。
- **已知只读数据**：产品 21（L1 根分类）、23（incomplete published）、66（SC8047 详情字段基准）等（仅读，不写）。
- **轨迹留痕**：`scire02`/`scire03` 执行的 E2E 在报告中标明账号+时间（§4.2），便于测试人员反馈问题回溯。

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

# 环境变量（含 Basic Auth 前置，见 §6.2；密码以 2026-07-14 核实为准）
E2E_BASIC_USER=scire01 E2E_BASIC_PASS=c5CCzN7LadMr \
E2E_USER=admin E2E_PASS=admin123 \
E2E_CUSTOMER_USER=e2e_customer E2E_CUSTOMER_PASS=E2ePass123! \
E2E_STAFF_USER=scire02 E2E_STAFF_PASS=l618tWxn1CDi \
npx playwright test
```

> ⚠️ 真环境（`scireagent.com` / 本地 nginx）必须带 `httpCredentials`（§6.2），否则全量 401。本地纯 dev（`5173+8000` 无 nginx）可省 Basic Auth 步。

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
| a11y 噪声 | axe 规则白名单（颜色对比度容忍度按设计系统校准，见 §11） |

---

## 10. 响应式视口矩阵（R 维度，阶段 8）

> §2.0 / §4 阶段 8 引用本章。四视口须保证「布局不崩 + 关键交互可用」。

### 10.1 四视口定义

| 视口 | 尺寸（宽×高） | 代表设备 | 全局默认 |
|------|-------------|---------|---------|
| 移动 Mobile | **375 × 667** | iPhone SE / 安卓 | — |
| 平板 Tablet | **768 × 1024** | iPad 竖 | — |
| 笔记本 Laptop | **1280 × 720** | 常用开发/办公 | ✅ `playwright.config` 默认 |
| 桌面 Desktop | **1920 × 1080** | 外接显示器 | — |

- 视口在 `responsive.spec.cjs` 内用 `test.use({ viewport: { width, height } })` 逐视口覆盖（不写死全局，§7）。
- 额外边界：超窄 **320×568**（防止极端溢出）、宽屏 **2560×1440**（大屏不空旷异常）。

### 10.2 每视口断言清单

**通用不崩断言（每个视口必做）**：
1. `document.documentElement.scrollWidth <= viewport.width + 2`（无横向滚动 / 无溢出）。
2. 无元素 `position:fixed` 遮挡致关键 CTA 不可点（如移动端底部 bar 不挡 Add to Cart）。
3. 关键文本不被截断（对比 desktop 与 mobile 的标题/价格可见）。

**关键页 × 视口交互可用矩阵**：

| 关键页 | 移动(375) | 平板(768) | 笔记本(1280) | 桌面(1920) |
|--------|----------|----------|------------|-----------|
| HomePage | 汉堡菜单展开导航 ✓ | 导航可见 ✓ | 全导航 ✓ | 全导航 ✓ |
| ProductDetail | Tab 可切、Add to Cart 触底可见 ✓ | 同 ✓ | ✓ | ✓ |
| ProductEditPage（37 按钮） | 表单可滚动填、发布弹层全屏 ✓ | 同 ✓ | ✓ | ✓ |
| Workspace 列表 | 表格横向可滚 / 列折行不崩 ✓ | ✓ | ✓ | ✓ |
| CartPage | 提交审批按钮可见 ✓ | ✓ | ✓ | ✓ |
| Admin 各台 | 表格/弹层可用 ✓ | ✓ | ✓ | ✓ |

- 移动端特有：导航收为汉堡（`click` 展开断言链接出现）；表格允许横向滚动而非压扁。
- 断言手段：`test.use({ viewport })` + `expect(page).toHaveScreenshot()` 可选（视觉回归，P2）；主用 DOM 断言（无溢出 + 关键元素 `toBeVisible` + `toBeEnabled`）。

### 10.3 阶段 8 退出标准
四视口 × 上表关键页全绿；通用不崩断言 0 失败；无横向溢出。

---

## 11. 全站可访问性（A 维度，阶段 10）

> §2.0 / §4 阶段 10 引用本章。用 `@axe-core/playwright` 扫描。

### 11.1 等级与规则集
- **目标等级：WCAG 2.1 AA**（critical/serious 零容忍；moderate/minor 记录但不阻断）。
- 启用的 axe 规则标签：`wcag2a`、`wcag2aa`、`wcag21a`、`wcag21aa`（可选 `+ best-practice` 仅记录）。
- 封装：`e2e/helpers/a11y.cjs` 的 `runAxe(page, { tags })` 返回 violations。

### 11.2 对比度容忍度（按设计系统校准）
- 主色 `emerald` 文字 on 白底、中性灰文字 on 白底均须 ≥ 4.5:1（AA 正文）。
- `amber` 仅用于强调/状态点（非正文），豁免「小字/非文本」对比度规则（按 §0#10 设计令牌）。
- 若某配色经设计系统确认为「状态语义点」（非文字），在白名单标 `color-contrast` 豁免并注明理由。

### 11.3 已知误报白名单（axe 规则 → 原因）
| axe 规则 | 误报场景 | 处理 |
|---------|---------|------|
| `color-contrast`（状态点） | emerald/amber 语义点非正文 | 白名单豁免（设计系统确认） |
| `aria-hidden-focus` | 装饰性 SVG / 图标按钮带 `aria-hidden` | 改用 `role="img"`+`aria-label` 或确认无焦点 |
| `image-alt`（装饰图） | 纯装饰背景图 `alt=""` | 标 `presentation` 白名单 |
| `region` | 单 main 外的 section 未命名 | 补 `aria-label` 或标 landmark 白名单（仅记录） |
| 第三方 widget（地图/图表 canvas） | 外部库无 aria | 标 `best-practice` 仅记录，不阻断 |

- 白名单实现：`runAxe(page, { disabledRules: [...] })` 或在报告中过滤指定 ruleId+selector。
- 阶段 10 退出：**0 critical / 0 serious violation**；moderate/minor 进报告但不阻断（除非设计确认需修）。

---

## 9. 下一步

1. 本计划 v2.1 经用户确认（§10/§11/§5.1/Basic Auth/账号体系已补全）。
2. 升级 `playwright.config.cjs`（多浏览器 project + httpCredentials 注入 Basic Auth）。
3. 实现**阶段 0**：`e2e/helpers/*`（auth.cjs 区分 Basic Auth + Django 两层登录）+ 确认 `e2e_customer` 已存在（必要时 seed）+ `public-smoke.spec.cjs`（全路由冒烟）。
4. 阶段 0 回归全绿后，逐阶段推进 1→10，每阶段退出标准（§4.1 量化门槛）满足再进下一阶段。
5. **功能修复回归**：每次全量 E2E 必跑 `regression-fixes.spec.cjs`（§5.1 三项修复：详情页结构图优先 / PubChem 守卫 / SKU 增量同步），防回退。
6. **彻底覆盖验收**：阶段 10 完成后，对照 §2.2 矩阵逐页打勾 + §10 四视口 + §11 a11y 报告，确认 I/P/S/R/V/A/B 七维全覆盖、0 遗漏，输出 `COVERAGE.md`（§4.2）。
