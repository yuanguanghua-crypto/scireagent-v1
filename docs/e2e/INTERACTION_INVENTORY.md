# 全站前端交互元素清单
> 来源：`frontend/src/views/**/*.vue`（含 `po/`、`admin/`、`workspace/` 及复用子组件），扫描于 2026-07-10
> 配套路由来源：`frontend/src/router/index.js`
> 说明：**本项目几乎不使用 Element-UI 标准组件**。交互以「原生 `<button>` + 自定义组件 `AppButton`/`AppInput`/`AppSelect`/`AppDialog` + 自定义 `dialog-overlay` 弹层 + 原生 `<table>`/`<th @click>` 排序 + `DataPagination` 分页 + 自定义 `toast` 工具」实现。下文据此标注，而非按 el-* 套件假设。

## 技术栈交互特征速览
- **按钮**：原生 `<button>` 与 `<AppButton>`（约 52 个文件普遍使用）；无 `<el-button>`。
- **下拉/选择**：少量 `el-select`（仅 ResearchGoalIndex、AppsPage、MethodsPage、ProtocolsPage、workspace/ProductEditPage）；多选/分类多用原生 `<select>` 或 AppSelect。
- **弹窗**：无 `el-dialog`/`AppDialog` 实例；改用 `v-if="showXxx"` + `<div class="dialog-overlay">` 自定义弹层（ProductsPage、ProductEditPage、MethodsPage、ProtocolsPage、GoalsPage、AppsPage、ReferencesPage、PoAddressList）。
- **表格/分页**：无 `el-table`；列表页用原生 `<table>` + `<th class="sortable" @click>`，分页统一用 `<DataPagination>`（`:total`/`:page-size`/`@current-change`）。
- **Toast**：自定义 `toast` 工具（`import { toast } from '@/components/common'`，`toast.success/.error`）；部分页用页内 `<div class="toast/ki-toast/save-msg">` 显示状态；校验失败用原生 `alert()`/`confirm()`。无 `ElMessage`/`ElMessageBox`。
- **加载态**：`v-loading` 指令（MethodIndex、CheckoutPage、ProtocolDetail、CartPage、ProtocolIndex、ProductDetail、ResearchGoalDetail、workspace/ProductEditPage 等）+ `<LoadingSpinner>` 组件（CartPage、ProductDetail、AppsPage、MethodsPage、DashboardPage 等）。
- **表单校验**：多为 `v-model` + 手动 `if (!x) alert(...)` 校验；少数用 `required`/`:rules`（见 AdminProductEdit、products/ProductEditPage、PoSubmit）。

---

## 按页面

### 一、公共/营销/搜索页

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/HomePage.vue | 首页 | `/` (Home) | 少量（分类 pills、CTA） | — | — | 搜索框(HeroSearch) | — | — | — | 4 (router-link/分类/产品) | — | — | — | 静态展示为主 + 搜索与导航跳转 |
| views/SearchPage.vue | 搜索结果 | `/search` (Search) | 1 | — | — | 搜索输入(v-model) | — | — | — | 1 | — | — | 关键词搜索 + 结果列表跳转 |
| views/LoginPage.vue | 登录 | `/login` (Login) | 1 (提交) | — | — | 邮箱/密码等 4 输入(v-model) | — | — | — | 4 (注册/首页/redirect) | 错误提示(err.message) | — | 必填校验 | 表单提交 + 错误条幅 |
| views/RegisterPage.vue | 注册 | `/register` (Register) | 7 | — | — | 多字段 12 输入(v-model) | — | — | — | 2 | successMessage 横幅 / 错误条幅 | — | 多步(3步)校验 | 分步注册表单，含成功/失败横幅 |
| views/NotFound.vue | 404 | `/:pathMatch(.*)*` (NotFound) | 1 (返回首页) | — | — | — | — | — | — | 1 | — | — | — | 静态 + 返回首页跳转 |

### 二、索引/列表页（公共）

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/ApplicationIndex.vue | 应用列表 | `/applications` (Applications) | 2 | — | — | 搜索 1 (v-model) | — | — | DataPagination(:total/:page-size/@current-change) | 1 | — | — | — | 搜索 + 过滤 + 分页 |
| views/MethodIndex.vue | 方法列表 | `/methods` (Methods) | 4 | — | — | 搜索 1 (v-model) | — | — | DataPagination(:total/:page-size/@current-change) | 1 | — | v-loading | 过滤 chips | 分类过滤 + 分页 |
| views/ProtocolIndex.vue | 协议列表 | `/protocols` (Protocols) | 4 | — | — | 搜索 1 (v-model) | — | — | DataPagination(:total=store.total/:page-size=20/@current-change) | 1 | — | v-loading | 过滤 chips | 分类过滤 + 分页 |
| views/ProductIndex.vue | 产品列表 | `/products` (Products) | 5 | — | — | 搜索 1 (v-model) | — | — | 自定义分页(visiblePages) | 1 | — | — | — | 产品网格 + 分类 + 分页 |
| views/ResearchGoalIndex.vue | 研究目标列表 | `/research-goals` (ResearchGoals) | 1 | el-select 2 (状态/搜索) | — | 搜索 2 (v-model) | — | — | DataPagination(:total/:page-size/@current-change) | 1 | — | — | filters | 状态筛选 + 搜索 + 分页 |

### 三、详情页（公共）

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/ApplicationDetail.vue | 应用详情 | `/applications/:id` (ApplicationDetail) | 6 | — | — | — | — | — | — | 6 (关联方法/产品) | — | — | — | 详情 + 关联导航 |
| views/MethodDetail.vue | 方法详情 | `/methods/:id` (MethodDetail) | 4 | — | — | — | — | — | — | 4 | — | — | — | 详情 + 关联协议/产品 |
| views/ProtocolDetail.vue | 协议详情 | `/protocols/:id` (ProtocolDetail) | 1 | — | — | — | — | — | 原生表格 14 列(可排序 th) | 3 | — | v-loading | — | 步骤表 + 关联产品 |
| views/ProductDetail.vue | 产品详情 | `/products/:id` (ProductDetail) | 11 | — | — | 数量输入 | — | — | — | 13 (文档/应用/协议) | toast.success('Added to cart') / toast.error | LoadingSpinner + v-loading | — | 加入购物车 + 数量 + 文档链接 |
| views/ResearchGoalDetail.vue | 研究目标详情 | `/research-goals/:id` (ResearchGoalDetail) | 2 | — | — | — | — | — | — | 3 | — | v-loading | — | 详情 + 关联 |

### 四、表单/流程/账户页

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/QuoteRequestPage.vue | 询价申请 | `/quote-request` (QuoteRequest) | 5 | — | — | 多字段 11 输入(v-model) | — | — | — | 2 | — | — | 必填校验 | 询价多字段表单 |
| views/SettingsPage.vue | 账户设置 | `/settings` (Settings) | 5 | — | — | 多字段 20 输入(v-model) | — | — | — | 1 | saveMessage 横幅(success/error) | — | 必填校验 | 设置保存 + 状态横幅 |
| views/KnowledgeIntake.vue | 知识录入 | `/workspace/knowledge-intake` (WorkspaceKnowledgeIntake) | 6 | 选择产品下拉 | — | 多字段 12 输入(v-model) | — | — | — | — | ki-toast (ok/err) | — | — | 知识录入 + 复制相似产品 |

### 五、购物车/结算/订单

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/CartPage.vue | 购物车 | `/cart` (Cart) | 10 | — | showSubmitApproval 区块 | 数量输入 | — | — | — | 4 | toast.success('Item removed from cart') | LoadingSpinner + v-loading | — | 增减数量/删除/提交审批/结算跳转 |
| views/CheckoutPage.vue | 结算 | `/checkout` (Checkout) | 11 | — | — | 多字段 12 输入(v-model) | — | — | — | 1 (router) | serverError 横幅 | v-loading(11处) | 必填校验 | 多步结算表单 |
| views/OrderListPage.vue | 我的订单 | `/orders` (Orders) | 1 | — | — | — | — | — | DataPagination | 2 | — | — | — | 订单列表 + 详情跳转 |
| views/OrderDetailPage.vue | 订单详情 | `/orders/:id` (OrderDetail) | 2 | — | — | — | — | — | — | 2 | alert(err) | — | — | 详情 + 操作(alert 提示) |

### 六、PO 采购门户（客户侧）

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/po/PoSubmit.vue | 提交采购单 | `/po/submit` (PoSubmit) | 5 (添加行/提交/重置) | — | — | 多字段 20 输入(v-model, 含行项目) | — | — | — | 2 | 拦截器 toast(静默) | — | alert 校验(PO号/行项目必填) | 行项目动态表单 + 提交 |
| views/po/PoOrderList.vue | 我的采购单 | `/po/orders` (PoOrders) | 2 | — | — | — | — | — | DataPagination(2处) | 3 | — | — | — | 列表 + 详情跳转 |
| views/po/PoOrderDetail.vue | 采购单详情 | `/po/orders/:id` (PoOrderDetail) | 2 | — | — | — | — | — | — | 2 | — | — | — | 详情 |
| views/po/PoAddressList.vue | 地址簿 | `/po/addresses` (PoAddresses) | 5 (新增/保存/删除/编辑) | — | showForm 区块(v-if) | 多字段 11 输入(v-model) | — | — | — | — | 后端未实现(错误 toast 提示) | — | confirm('Delete this address?') | CRUD 草稿(后端 endpoint 待上线) |
| views/po/PoReorder.vue | 重新下单 | `/po/reorder` (PoReorder) | 1 | — | — | — | — | — | — | 1 | — | — | — | 重订操作 |
| views/po/PoDownloadCenter.vue | 下载中心 | `/po/downloads` (PoDownloads) | 2 | — | — | — | — | 下载链接 | — | 2 | — | — | — | 文档下载列表 |

### 七、Admin 内部台

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/admin/AdminOrdersPage.vue | 订单管理 | `/admin/orders` (AdminOrders) | 2 | — | — | 过滤输入 | — | — | filters + 列表 | 1 | — | — | — | 管理列表 + 过滤 |
| views/admin/AdminOrderDetail.vue | 订单处理 | `/admin/orders/:id` (AdminOrderDetail) | 5 | — | — | 处理字段 5 输入(v-model) | — | — | — | 2 | alert(actionError) | — | — | 状态流转处理 |
| views/admin/AdminProductsPage.vue | 产品管理 | 无独立路由(AdminLayout nav 内链) | 5 | — | — | 搜索 4 输入 | — | — | 列表 | 4 | — | — | — | 管理列表 |
| views/admin/AdminProductEdit.vue | 产品编辑 | 无独立路由(AdminLayout nav 内链) | 11 | — | — | 大表单 33 输入(v-model) | — | 图片上传(el-upload 区域) | — | 2 | saveMessage toast(success/error) | — | required/:rules | 最密集后台表单之一 |
| views/admin/PoReviewDesk.vue | 订单审核台 | `/admin/po/review` (PoReviewDesk) | 4 | — | — | — | — | — | DataPagination(2处) | — | — | — | 审核动作 | 审核流转 |
| views/admin/PoShipmentDesk.vue | 发货台 | `/admin/po/shipments` (PoShipmentDesk) | 5 | — | — | 发货字段 6 输入(v-model) | — | — | 多选列表 | — | — | — | 发货操作 | 发货处理 |
| views/admin/PoInvoicingDesk.vue | 开票台 | `/admin/po/invoicing` (PoInvoicingDesk) | 4 | — | — | 开票字段 6 输入(v-model) | — | — | 列表 | — | — | — | 开票操作 | 开票处理 |
| views/admin/PoArReport.vue | AR 账龄报表 | `/admin/po/ar` (PoArReport) | 1 | — | — | — | — | — | 报表表格 | — | — | — | — | 报表展示 |
| views/admin/PoOrgManagement.vue | 组织管理 | `/admin/po/organizations` (PoOrgManagement) | 2 | — | — | — | — | — | 列表 | — | — | — | — | 组织 CRUD |

### 八、Workspace 后台（admin/requiresAdmin）

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/workspace/AdminLayout.vue | 后台布局 | `/workspace` (Workspace,父布局) | 侧栏导航(~20 @click) | — | — | — | — | — | — | 20 (侧栏路由) | — | — | — | 仅布局+导航，无业务交互 |
| views/workspace/DashboardPage.vue | 仪表盘 | `/workspace` (Dashboard) | 2 | — | — | — | — | — | DataPagination(2处) | 2 | — | LoadingSpinner | — | 概览卡片 + 快捷入口 |
| views/workspace/ProductsPage.vue | 产品管理 | `/workspace/products` (WorkspaceProducts) | 15 | — | 3 弹层(batchLink/archive/delete, dialog-overlay) | 11 输入(v-model) | — | — | 原生表格 + sortable th(6列可排序) + 过滤栏 | 2 | — | — | — | 交互最密集列表页之一 |
| views/workspace/ProductEditPage.vue | 产品编辑(后台) | `/workspace/products/new` & `/:id/edit` | **37** | el-select 1 | 2 弹层(publish/inline editor) | **50** 输入(v-model) | — | 图片/文件上传 | — | — | — | v-loading | required/:rules | **全站交互最密集文件** |
| views/workspace/AppsPage.vue | 应用管理 | `/workspace/applications` (WorkspaceApps) | 4 | el-select 2 | showEditor 弹层 | — | — | — | — | — | toast.error('Save failed') | LoadingSpinner | — | 增改弹层 |
| views/workspace/MethodsPage.vue | 方法管理 | `/workspace/methods` (WorkspaceMethods) | 4 | el-select 2 | showEditor 弹层 | — | — | — | — | — | toast.error('Save failed') | LoadingSpinner | — | 增改弹层 |
| views/workspace/ProtocolsPage.vue | 协议管理 | `/workspace/protocols` (WorkspaceProtocols) | 4 | el-select 2 | showEditor 弹层 | — | — | — | — | — | — | — | — | 增改弹层 |
| views/workspace/GoalsPage.vue | 目标管理 | `/workspace/goals` (WorkspaceGoals) | 4 | — | showEditor 弹层 | 2 输入(v-model) | — | — | — | — | — | — | — | 增改弹层 |
| views/workspace/ReferencesPage.vue | 参考文献 | `/workspace/references` (WorkspaceRefs) | 4 | — | showEditor 弹层 | 5 输入(v-model) | — | — | — | — | — | — | — | 增改弹层 |

### 九、复用交互子组件（views 内嵌）

| 文件路径 | 页面/组件 | 路由(对照 router) | 按钮 | 选择/下拉 | 弹窗 | 输入 | Tab | 上传 | 表格/分页 | 跳转 | Toast | 加载态 | 表单校验 | 备注 |
|---------|----------|-----------------|------|----------|------|------|-----|------|----------|------|-------|--------|---------|------|
| views/admin/components/AiToolsPanel.vue | AI 工具面板 | 内嵌(AdminOrderDetail/AdminProductEdit) | 8 | — | — | 1 输入(v-model) | — | — | — | — | errorMsg 提示 | — | — | AI 调用按钮组 |
| views/admin/components/ExpandableSection.vue | 可展开区 | 内嵌 | 1 (展开/收起) | — | — | — | — | — | 可见项 v-for | — | — | — | — | 折叠/展开交互 |
| views/products/ProductEditPage.vue | 产品编辑(市场版,疑似遗留) | 无独立路由(或已被 workspace 版取代) | 9 | — | — | 大表单 35 输入(v-model) | — | — | — | 1 | saveMessage 横幅 | — | required/:rules | 与 AdminProductEdit 同源遗留 |
| views/workspace/components/BiozEvidenceSection.vue | Bioz 证据段 | 内嵌(ReferencesPage) | 3 | — | — | — | — | — | visibleRefs 列表 | — | — | — | — | 证据卡片展示 |
| views/workspace/components/JenaMatchSection.vue | Jena 匹配段 | 内嵌 | 1 | — | — | — | — | — | — | — | — | — | — | 匹配操作 |
| views/workspace/components/StructureViewer.vue | 结构查看器 | 内嵌(ProductDetail/编辑) | — | — | — | — | — | — | — | — | — | — | — | 3D/结构图展示，无标准交互按钮 |

---

## 交互密度排名（Top，供 E2E 优先级）
1. **workspace/ProductEditPage.vue** — 37 按钮 / 50 v-model / 2 弹层 / 表单校验（最密集）
2. **products/ProductEditPage.vue** — 9 按钮 / 35 v-model / 表单校验（遗留版）
3. **admin/AdminProductEdit.vue** — 11 按钮 / 33 v-model / 上传 / 表单校验
4. **workspace/ProductsPage.vue** — 15 按钮 / 26 @click / 3 弹层 / 可排序表格
5. **SettingsPage.vue** — 5 按钮 / 20 v-model
6. **po/PoSubmit.vue** — 5 按钮 / 20 v-model / alert 校验
7. **CheckoutPage.vue** — 11 按钮 / 12 v-model / v-loading
8. **CartPage.vue** — 10 按钮 / 7 @click / toast
9. **QuoteRequestPage.vue / RegisterPage.vue / PoAddressList.vue** — 多字段表单 + 校验

## 几乎静态 / 低交互页（E2E 可轻量覆盖）
- NotFound.vue、HomePage.vue（仅导航/搜索）、ApplicationDetail / MethodDetail / ResearchGoalDetail（详情+关联跳转）、PoReorder.vue、PoOrderDetail.vue、PoArReport.vue、PoOrgManagement.vue、StructureViewer.vue（纯展示）、AdminLayout.vue（仅导航）。

## 全局跳转与守卫（E2E 必测）
- `router.beforeEach`：`requiresAuth` 无 token → 跳转 `/login?redirect=...`；`requiresAdmin` 无 token 同样拦截，非 staff 由 AdminLayout 重定向。
- 高频跳转目标：产品/方法/协议/应用/目标 详情与列表、购物车→结算、PO 各节点、Workspace 各子路由、登录回调 redirect。

## 弹窗/弹层清单（自定义 dialog-overlay）
- workspace/ProductsPage.vue：`showBatchLinkPanel`(批量关联)、`showArchiveDialog`(归档)、`showDeleteDialog`(删除)
- workspace/ProductEditPage.vue：`showPublishDialog`(发布)、`showInlineEditor`(内联编辑)
- workspace/MethodsPage / ProtocolsPage / GoalsPage / AppsPage / ReferencesPage：`showEditor`(增改编辑器)
- po/PoAddressList.vue：`showForm`(地址表单)
- CartPage.vue：`showSubmitApproval`(提交审批确认区)

## 自定义 Toast 调用点（供断言文案）
- CartPage：`toast.success('Item removed from cart')`
- ProductDetail：`toast.success('Added to cart')` / `toast.error('Failed to add')`
- workspace/AppsPage、MethodsPage：`toast.error('Save failed: ...')`
- AdminProductEdit / products/ProductEditPage / KnowledgeIntake / SettingsPage：页内 `saveMessage`/`ki-toast`/`successMessage` 状态横幅（success/error）
- PoSubmit / PoAddressList / OrderDetailPage / AdminOrderDetail：原生 `alert()` / `confirm()` 校验与提示

## 加载态清单
- `v-loading` 指令：MethodIndex、CheckoutPage、ProtocolDetail、CartPage、ProtocolIndex、ProductDetail、ResearchGoalDetail、workspace/ProductEditPage
- `<LoadingSpinner>` 组件：CartPage、ProductDetail、AppsPage、MethodsPage、DashboardPage（及若干 workspace 列表页）
