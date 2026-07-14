# SciReAgent 功能测试手册（测试人员版）· 修订版 v2

> 适用对象：**北京产品测试人员 `scire03`**（本手册按他唯一的测试范围——**仅线上站**——编写）。休斯顿实验室研究员 `scire02` 可参考同一流程在线上以各自账号测试。
> 目标：对照本文档，在浏览器中**逐页、逐元素、可遍历**地完成网站所有功能点的手动测试，并规范记录错误与复现步骤。
> 站点标题：`LabPro Global`（对外品牌名），项目代号 `SciReAgent`。
> 文档版本：**v2，2026-07-14 修订**，内容基于**线上服务器实际状态**编写（线上部署版本 `v2026.07.14`，站点 `https://scireagent.com`）。**测试范围：仅线上站，不测本地、不测 GitHub。**
> 配套文档：`docs/e2e/FULL_SITE_E2E_PLAN.md`（自动化 E2E 计划）、`docs/e2e/INTERACTION_INVENTORY.md`（前端交互元素逐页清单，本手册 §3 的元素级依据）。

---

## 0. 怎么用这份文档

1. 本手册**唯一测试目标 = 线上站 `https://scireagent.com`**（不测本地、不测 GitHub）。先按 **第 1 章** 备好线上站两层认证的账号。
2. 线上站有**两层认证**（nginx Basic Auth + 网站登录），第 1.2 节讲清楚，务必先读。
3. 按 **第 3 章** 的用例**逐条、逐元素**执行：每条用例写明「页面 / 角色 / 前置 / 步骤 / 预期」。步骤里的每个小点都对应页面上一个真实按钮或输入框，**不要抽样、不要合并**。
4. 每条用例在 **第 6 章** 的记录表填 `通过 / 失败 / 阻塞`；失败必须附**现象 + 复现步骤 + 截图**。
5. 全部用例跑完后，用 **附录 D 覆盖核对表** 勾选，确认**每个路由都走到了**（即「遍历」完成、0 遗漏）。
6. 跑完一轮，按 **第 4 章** 的端到端场景把关键链路串起来复测。

约定：本文所有路径以**线上站基址 `https://scireagent.com`** 为唯一基准。例如「打开 `/products`」即访问 `https://scireagent.com/products`。

---

## 1. 测试环境与访问方式

### 1.1 唯一测试目标：线上站

| 目标 | 基址 | 说明 |
|------|------|------|
| **线上站（唯一测试目标）** | `https://scireagent.com` | 部署版本 `v2026.07.14`，数据真实（8 款产品、4 笔订单），全站位于 nginx Basic Auth 之后 |

> **本手册只测线上站。** 本地开发环境、GitHub 仓库**均不在测试范围内**——你（scire03）无需搭建或访问它们。所有用例直接对 `https://scireagent.com` 执行即可。

### 1.2 线上站「两层认证」（关键，先读懂）

线上站整站位于 nginx **Basic Auth** 之后，且网站自身还有**登录态**。因此访问任意页面要过两关：

1. **第一层 · nginx Basic Auth（站点访问关）**
   - 浏览器首次打开 `https://scireagent.com` 会弹出**用户名/密码**框（非网站登录页，是浏览器原生的认证弹窗）。
   - 用 `scire01`~`scire06` 任一账号通过（见 1.4 表）。通过后本次会话即可浏览站点。
   - 这一层**只控制「能不能进站点」**，与网站业务权限无关。
2. **第二层 · 网站登录（业务权限关）**
   - 通过 Basic Auth 后看到的是公开页面。要做加购/下单/后台等操作，还需在网站内**登录**（点 Sign In）。
   - 网站登录账号是另一套（Django 应用账号：`admin` / `scire02` / `scire03` / `e2e_customer`，见 1.4）。

**三种测试身份的登录组合：**

| 你想模拟的角色 | Basic Auth（第一层） | 网站登录（第二层） |
|---------------|---------------------|-------------------|
| 游客（匿名浏览） | `scire01` 通过即可 | **不登录** |
| 客户（customer） | `scire01`（任一） | 登录 `e2e_customer` |
| 管理员/研究员（staff） | `scire03`（或 `scire02`） | 登录 `scire03`（同账号，staff） |

> 休斯顿研究员用 `scire02`、北京测试用 `scire03` 登录后台，其操作轨迹具分析价值，请如实记录。
> 浏览器建议用**无痕窗口**或每次清 localStorage，避免旧登录态干扰两层认证。

### 1.3 测试范围说明（重要）

- **你只测线上站 `https://scireagent.com`。**
- 本地开发环境（localhost）、GitHub 仓库**不在你的测试范围**——无需启动后端/前端，也无需访问 GitHub。
- 若你在线上发现 bug 且需要开发在本地复现，那是开发侧的事，你只需在缺陷记录（第 6 章）里写清「线上复现步骤 + 环境信息（浏览器/系统/Basic Auth 账号 scire03）」即可，开发会自行处理。

### 1.4 测试账号（两套体系，真实可用）

**第一层 · nginx Basic Auth（站点访问，非网站账号）**

| 用户名 | 密码 | 用途 |
|--------|------|------|
| scire01 | `c5CCzN7LadMr` | 通用站点访问 |
| scire02 | `l618tWxn1CDi` | 休斯顿研究员站点访问（兼网站 staff 登录） |
| scire03 | `TpJOAXrameB3` | 北京测试站点访问（兼网站 staff 登录） |
| scire04 | `hrLeGxA4Zw52` | 通用站点访问 |
| scire05 | `Xm7eOaPw1JUJ` | 通用站点访问 |
| scire06 | `JP8Z3R6pNhnI` | 通用站点访问 |

**第二层 · 网站登录（Django 应用账号，控业务权限）**

| 角色 | 用户名 | 密码 | 权限说明 |
|------|--------|------|----------|
| 管理员 / 研究员（staff） | `admin` | `admin123` | `is_staff=True`，可进全部后台 |
| 研究员（staff） | `scire02` | `l618tWxn1CDi` | `is_staff=True`（休斯顿） |
| 研究员（staff） | `scire03` | `TpJOAXrameB3` | `is_staff=True`（北京） |
| 客户（customer） | `e2e_customer` | `E2ePass123!` | `is_staff=False`，可购物/下单/PO 客户侧，不能进后台 |

> `scire01/04/05/06` **只是 Basic Auth 账号，没有网站登录账号**——能进站点，但不能在网站里登录做任何业务操作。
> 不要自行改库或改密码；如密码与现状不符，以项目负责人提供为准。

### 1.5 全局交互识别指南（看不懂界面时看这里）

本项目**几乎不用第三方组件库（无 el-button / el-dialog / el-table）**，交互都是原生实现：
- **按钮**：原生 `<button>` 或 `<AppButton>`；主按钮 emerald（绿）实心、次按钮描边或 amber（琥珀）实心。
- **购物车角标**：右上角购物车图标叠加红底白字小数字 = 购物车总件数（同商品加多次累加）。
- **弹窗 / 对话框**：页面中间浮起卡片 + 半透明遮罩（类名 `dialog-overlay`），非浏览器原生弹窗。关闭：点「取消/关闭」或点遮罩空白处。
- **Toast 提示条**：页面角落短暂弹出的深色小条（成功/失败文案），几秒自动消失。
- **原生 alert / confirm**：浏览器自带弹窗（PO 提交、地址删除、订单操作处使用），点「确定/取消」。
- **分页**：列表底部页码/上下页按钮（`DataPagination` 组件）。
- **排序**：列表表格某些列标题可点击（鼠标移上去有手势），点一次升序、再点降序。
- **加载态**：数据加载时转圈或局部变灰，加载完恢复，属正常，等它结束再操作。

### 1.6 当前线上真实数据快照（2026-07-14）

> 以下为编写本手册时线上库真实状态，测试时以此作为「已知存在的真实数据」，避免用编造的 slug。

- **产品**：共 **8** 款。slug 与名称：
  - `sc8001` = 5-Propargylamino-CTP
  - `sc8002` = 5-Propargylamino-dCTP
  - `sc8003` = 5-Propargylamino-CTP-Cy3
  - `sc8004` = 5-Propargylamino-dCTP-Cy3
  - `sc8005` = 5-Propargylamino-CTP-Cy5
  - `sc8006` = 5-Propargylamino-dCTP-Cy5
  - `sc8009` = Fluorescein-12-UTP
  - `sc8011` = Pseudo-UTP
  - 状态：**7 款 `active` + 1 款 `draft`**（无 `discontinued`）。**8 款全部带有 `structure_image`（文档结构图）**——这正是「详情页结构图优先」修复的验证基础。
- **订单（PO）**：共 **4** 笔，状态分布 `confirmed` ×3、`quote_pending` ×1（数据仅含这两态；PO 生命周期还含审核/发货/开票等，需新提交才能走到）。
- **用户**：共 **15** 个；其中 `is_staff=True` = `admin` / `scire02` / `scire03`（共 3 个，可进后台）。
- **分类**：产品列表页有「分类 pills」筛选，按产品自身分类字段展示（线上 8 款属同一品类族，pills 可能只有 1~2 个）。

### 1.7 已知限制（遇到「失败」但属预期，记录即可，不当 bug）

- **地址簿保存**（`/po/addresses` 新增/保存地址）：后端接口尚未上线，保存会弹错误提示。属已知限制。
- **遗留编辑页** `products/ProductEditPage`、`admin/AdminProductsPage`、`admin/AdminProductEdit`：导航已不可直达，产品管理统一走 `/workspace/products`。不单独测。
- **AI 工具按钮**（enrich / validate / recommend / PubChem 自动匹配）：调用外部 AI/PubChem 服务，可能慢或需网络；点按时耐心等，超时/报错记为「环境依赖」，非功能缺陷。
- **PO 多状态数据**：线上仅 `confirmed`/`quote_pending` 两态有数据；审核→发货→开票→AR 等状态需由你新提交 PO 并推进才能得到，测试时主动构造。

---

## 2. 角色与权限矩阵（逐路由 × 角色）

角色：①**游客**（过 Basic Auth 但不网站登录）②**客户**（`e2e_customer`，`is_staff=False`）③**staff**（`admin`/`scire02`/`scire03`，`is_staff=True`）。

| 路由（组） | 游客 | 客户 | staff | 拦截行为 |
|-----------|------|------|-------|---------|
| 公开页 `/` `/search` `/applications*` `/methods*` `/protocols*` `/products*` `/research-goals*` `/about` `/quote-request` `/cart` `/login` `/register` | ✅ | ✅ | ✅ | 均可访问 |
| 需登录 `/settings` `/checkout` `/orders*` `/po/submit` `/po/orders*` `/po/addresses` `/po/reorder` `/po/downloads` | → `/login?redirect=<原路径>` | ✅ | ✅ | 游客被拦并带 redirect |
| 需后台 `/workspace*` `/admin/orders*` `/admin/po/review` `/admin/po/shipments` `/admin/po/invoicing` `/admin/po/ar` `/admin/po/organizations` | → `/login?redirect=<原路径>` | → 首页 `/`（已登录但非 staff，静默跳） | ✅ | 游客跳登录；客户跳首页 |

> 测试方法：对每个「需登录/需后台」路由，分别用三种角色直接地址栏打开，核对上表行为。**重点验证**：游客访问受限页被拦并带 `redirect=`；客户访问后台被跳首页；staff 畅通。

---

## 3. 功能测试用例（逐路由遍历）

优先级：**[P0]** 核心必测　**[P1]** 重要　**[P2]** 增强
每条用例的「步骤」逐条对应页面上一个真实交互元素（依据 `INTERACTION_INVENTORY.md`），**请勿合并或跳过**。

### A. 公开浏览与导航

#### A-01 首页加载与导航　[P0]
- 页面：`/`（基址根）
- 角色：游客（Basic Auth 用 `scire01`，不网站登录）
- 步骤：
  1. 打开首页，确认无白屏、无报错（F12 Console 无红色 error）。
  2. 查看顶部导航栏：Logo、分类标签（Products/Applications/Methods/Protocols/Research Goals 等）、Sign In、购物车图标。
  3. 点击某个分类标签（如 `Products`）→ 预期跳 `/products`。
  4. 点击 Hero 区搜索框，输入 `CTP` 回车 → 预期跳 `/search?q=CTP` 并出结果。
  5. 点击导航 `About` → 预期跳 `/about` 展示项目说明。
- 预期：首页正常；导航/搜索/分类跳转均生效；购物车角标初始为 0 或无数字。

#### A-02 全局搜索　[P0]
- 页面：`/search`
- 角色：游客
- 步骤：
  1. 顶部搜索框输入 `5-Propargylamino` 回车 → 预期 `/search` 列出匹配产品（含 sc8001 等）。
  2. 点某条结果 → 预期跳对应详情页。
  3. 搜索框输入空串或乱码回车 → 预期显示空态或提示，**不崩溃**。
- 预期：搜索/结果/跳转正常；空查询结果态合理。

#### A-03 应用列表与详情　[P0]
- 页面：`/applications` 及 `/applications/:id`
- 步骤：
  1. 打开 `/applications`，在搜索框输入关键词过滤。
  2. 翻页（点 `DataPagination` 页码/上下页）。
  3. 点某条进 `/applications/:id` 详情。
  4. 详情页点关联的「方法 / 产品」链接各一次 → 预期跳对应详情。
- 预期：列表可搜索、可翻页；详情字段展示；关联链接可跳转。

#### A-04 方法列表与详情　[P0]
- 页面：`/methods` 及 `/methods/:id`
- 步骤：同 A-03，路径换 `methods`。额外：
  1. 列表页点分类过滤 chips（如某个 method type）→ 预期列表按 chip 过滤。
  2. 详情页点关联「协议 / 产品」链接。
- 预期：过滤 chips 生效；详情关联跳转正常。

#### A-05 协议列表与详情　[P0]
- 页面：`/protocols` 及 `/protocols/:id`
- 步骤：
  1. `/protocols`：分类 chips + 搜索 + 翻页。
  2. 进详情，查看步骤表（原生表格，多列）。
  3. **点步骤表某个列标题**（`<th class="sortable">`）→ 预期升序；再点一次 → 降序。
  4. 点关联产品链接。
- 预期：列表过滤/搜索/分页正常；步骤表列可排序，顺序随点击切换；关联跳转正常。

#### A-06 产品列表与详情　[P0]
- 页面：`/products` 及 `/products/:id`
- 步骤：
  1. `/products`：点分类 pills、用搜索框、翻页（自定义分页 `visiblePages`）。
  2. 进 `/products/sc8001` 详情。
  3. 详情页：**结构图区域**应显示文档结构图（`<img class="pd-structure-img">`），**不是** SMILES 渲染的 SVG（验证「结构图优先」修复，见 R-01）。
  4. 展开「相关应用 / 协议 / 文档 / FAQ / 参考文献」各 Tab（点 `activeTab`）→ 预期内容切换。
  5. 点 FAQ 某条展开箭头（`+`/`-`）→ 预期展开/收起。
  6. 点参考文献某条 DOI 链接 → 预期新开 `doi.org` 页。
  7. 某个 SKU 行的数量 `-`/`+` 按钮 → 预期数量增减。
  8. 点某 SKU 的 **Add to Cart** → 预期：右上角角标 +数量；Toast `Added to cart`；点购物车图标跳 `/cart`。
  9. 点 SDS 文档链接（`previewSds` / `downloadSds`）→ 预期预览或下载。
  10. 点 **Request Quote** → 预期跳 `/quote-request`（或预填该产品）。
- 预期：列表/详情/结构图/加购/文档/引用全部正常；同一产品多次加购角标累加。

#### A-07 研究目标列表与详情　[P0]
- 页面：`/research-goals` 及 `/research-goals/:id`
- 步骤：
  1. `/research-goals`：用**状态下拉（el-select）** + 搜索过滤 + 翻页。
  2. 进详情，点关联链接。
- 预期：状态下拉/搜索/分页正常；详情关联跳转正常。

#### A-08 关于页　[P1]
- 页面：`/about`
- 步骤：打开 `/about`，确认内容展示、无报错。

#### A-09 404 页面　[P0]
- 页面：`/<任意不存在路径>`（如 `/zzz`）
- 步骤：地址栏输入不存在路径回车。
- 预期：显示 404 提示页 + 「返回首页」按钮；点击回 `/`。

### B. 账户与认证

#### B-01 注册（多步表单）　[P0]
- 页面：`/register`
- 角色：游客
- 步骤：
  1. 打开 `/register`，按 3 步填必填字段（邮箱、密码、组织等约 12 项）。
  2. 每步点「下一步」；必填留空时点「提交」→ 预期校验提示、不能前进。
  3. 最后一步提交 → 预期成功横幅；账户可登录。
- 预期：分步校验生效；提交成功有横幅。测试新账号建议起易识别用户名，避免污染。

#### B-02 登录　[P0]
- 页面：`/login`
- 角色：游客
- 步骤：
  1. 用 `e2e_customer / E2ePass123!` 登录 → 预期进首页或 `redirect` 回跳页；右上角显用户名+购物车。
  2. 用错误密码登录 → 预期错误条幅，停留登录页。
  3. 用 `scire03 / TpJOAXrameB3` 登录（staff）→ 预期登录成功，后续可进 `/workspace`。
- 预期：正确凭据登录成功；错误密码被拦；错误提示清晰。

#### B-03 登出　[P0]
- 页面：任意已登录页
- 步骤：点右上角用户菜单「登出 / Sign out」。
- 预期：回游客态（导航变 Sign In）；再访需登录页被拦回 `/login`。

#### B-04 已登录访问 guest 页重定向　[P1]
- 步骤：客户登录后直接开 `/login`、`/register`。
- 预期：自动跳回首页 `/`（或 `/workspace`，视角色），不显示登录表单。

#### B-05 账户设置　[P1]
- 页面：`/settings`
- 角色：已登录（任意）
- 步骤：
  1. 修改部分字段（昵称/联系方式等，约 20 输入项），点「保存」。
  2. 必填留空点保存 → 预期校验提示。
- 预期：保存成功横幅；刷新后修改仍生效（只读字段依界面）。

### C. 购物车 / 结算 / 我的订单

#### C-01 购物车查看与改数量　[P1]
- 页面：`/cart`
- 前置：已加购 ≥1 件（先按 A-06 加购；游客加购会被拦登录，故用客户或 staff 登录后加购）
- 步骤：
  1. 打开 `/cart`，确认列出加购商品。
  2. 改某商品数量输入框，确认/失焦 → 预期小计更新。
  3. 点「删除」某商品 → 预期该商品消失、角标减少、Toast `Item removed from cart`。
  4. 点「提交审批」区块（如有）→ 预期展开确认区或提示。
- 预期：增删改数量生效；角标同步；提示正确。

#### C-02 去结算　[P1]
- 页面：`/cart`
- 步骤：点「去结算 / Checkout」→ 预期跳 `/checkout`（未登录先被拦到 `/login`）。

#### C-03 结算下单　[P1]
- 页面：`/checkout`
- 角色：已登录客户 + 购物车有商品
- 步骤：
  1. 填收货/账单等约 12 字段；必填留空提交 → 预期校验提示（`serverError` 横幅）。
  2. 提交 → 预期生成订单，跳订单详情或列表；`/orders` 出现新订单。
- 预期：校验生效；下单成功；订单可见。

#### C-04 我的订单列表与详情　[P1]
- 页面：`/orders` 及 `/orders/:id`
- 角色：已登录客户
- 步骤：
  1. `/orders` 翻页（`DataPagination`）。
  2. 点某订单进 `/orders/:id`，看状态时间线。
  3. 触发订单操作按钮（如有，会弹 `alert`）→ 预期 alert 提示。
- 预期：仅显示本人订单；详情/时间线正确；非本人订单不出现。

### D. 询价申请

#### D-01 提交询价（匿名也可）　[P1]
- 页面：`/quote-request`
- 角色：游客即可
- 步骤：
  1. 填多字段表单（产品、数量、联系方式等约 11 项）。
  2. 必填留空提交 → 预期校验提示。
  3. 正确填写提交 → 预期成功提示/横幅。
- 预期：校验生效；提交成功。

### E. PO 采购门户（客户侧，需登录客户）

#### E-01 提交采购单（PO）　[P1]
- 页面：`/po/submit`
- 角色：已登录客户（`e2e_customer`）
- 步骤：
  1. 点「添加行项目」→ 预期新增一行（产品/数量/单价等动态字段）。
  2. PO 号或行项目留空点提交 → 预期浏览器 `alert` 校验。
  3. 填全（PO 号 + 至少 1 行项目，产品可选 `sc8001`）提交 → 预期成功提示，PO 进入「已提交」态。
- 预期：行动态增删；校验 alert 生效；提交成功。

#### E-02 我的采购单列表与详情　[P1]
- 页面：`/po/orders` 及 `/po/orders/:id`
- 角色：已登录客户
- 步骤：
  1. `/po/orders` 翻页（两处 `DataPagination`）。
  2. 点某 PO 进详情，看状态标签、时间线、发票、发货、附件。
- 预期：仅列本人 PO；详情完整流转信息。

#### E-03 地址簿　[P1]
- 页面：`/po/addresses`
- 角色：已登录客户
- 步骤：
  1. 点「新增地址」→ 预期弹 `showForm` 表单层。
  2. 填字段保存 → **预期弹错误提示（已知限制：后端未上线）**，记「已知限制」不当 bug。
  3. 点编辑、删除（删除弹 `confirm`）→ 确认弹层开关正常。
- 预期：表单层可开关；保存报错属预期；删除有确认框。

#### E-04 重新下单　[P2]
- 页面：`/po/reorder`
- 角色：已登录客户 + 有历史 PO
- 步骤：打开页面，选历史 PO 执行重订 → 预期基于历史复制行项目生成新草稿/提交。

#### E-05 下载中心　[P2]
- 页面：`/po/downloads`
- 角色：已登录客户
- 步骤：打开页面，点某文档下载链接 → 预期触发下载或打开文件。

### F. PO 采购门户（内部台，需 staff）

> 用 `scire03`（北京）或 `scire02`（休斯顿）登录后台测试。客户账号访问会被跳首页（F-06）。

#### F-01 订单审核台　[P1]
- 页面：`/admin/po/review`
- 步骤：
  1. 打开审核台，翻页（两处 `DataPagination`）。
  2. 对某 PO 执行审核动作（通过/驳回/指派）→ 预期状态推进、列表更新。
- 预期：列表展示待审 PO；审核后状态变化。

#### F-02 发货台　[P1]
- 页面：`/admin/po/shipments`
- 步骤：
  1. 选待发货 PO，创建发货记录（可多批发，填运单号等 6 字段）。
  2. 标记「已发货 / 已签收」。
- 预期：发货记录可建；状态随「已发货→已签收」推进；时间线更新。

#### F-03 开票台　[P1]
- 页面：`/admin/po/invoicing`
- 步骤：选已达可开票态的 PO，填开票字段（6 项）开票 → 预期开票成功，客户侧详情可见发票。
- 预期：仅对可达开票态 PO 可开；开票后状态推进。

#### F-04 AR 账龄报表　[P2]
- 页面：`/admin/po/ar`
- 步骤：打开报表，看 30/60/90 天账龄分组 → 预期表格展示各区间应收。

#### F-05 组织管理　[P2]
- 页面：`/admin/po/organizations`
- 步骤：打开看组织/地址/订单列表 → 预期列表展示，可查看（CRUD 依界面按钮）。

#### F-06 权限拦截验证　[P1]
- 步骤：用**客户** `e2e_customer` 登录，直接开 `/admin/po/review`、`/workspace` → 预期跳首页 `/`。游客开则跳 `/login?redirect=...`。

### G. 管理员订单管理

#### G-01 订单管理列表　[P1]
- 页面：`/admin/orders`
- 步骤：打开，用过滤输入筛选，看列表（含各客户订单）→ 预期过滤生效。

#### G-02 订单处理详情　[P1]
- 页面：`/admin/orders/:id`
- 步骤：
  1. 进某订单详情，看字段与状态流转按钮（5 个）。
  2. 填处理字段（5 项），执行状态流转（确认/发货/完成）→ 预期状态更新；失败有 `alert`。
  3. 留意页内 **AI 工具面板**（8 个按钮：enrich/validate/recommend 等）→ 点按观察（慢/超时记环境依赖）。
- 预期：状态流转生效；AI 按钮调用外部服务，非功能缺陷。

### H. Workspace 研究后台（staff）

> 入口 `/workspace`，左侧栏 ~20 个导航 `@click`。所有子页仅 staff 可进。

#### H-01 仪表盘　[P1]
- 页面：`/workspace`（默认 Dashboard）
- 步骤：看概览卡片、快捷入口；点快捷入口跳转；看两处 `DataPagination` → 预期卡片/入口/加载（`LoadingSpinner`）正常。

#### H-02 产品管理列表　[P1]
- 页面：`/workspace/products`
- 步骤：
  1. 过滤栏输入 + 翻页 + 点 6 个可排序列标题排序（升/降）。
  2. 选中若干产品，点「批量关联」→ 开 `showBatchLinkPanel` 弹层，操作后关闭。
  3. 点某产品「归档」→ 开 `showArchiveDialog` 确认层；「删除」→ 开 `showDeleteDialog` 确认层。
- 预期：列表可过滤/分页/排序；三弹层均可开/关；确认操作有提示。

#### H-03 新建 / 编辑产品（最密集，含三项修复验证）　[P0]
- 页面：`/workspace/products/new` 与 `/workspace/products/sc8001/edit`
- 步骤（按区块遍历，字段详见附录 D）：
  1. 点「新建产品」或进 `sc8001/edit`。
  2. **基础信息**：填名称/分类/描述等必填；必填留空保存 → 预期校验提示。
  3. **结构图**：点「从 Word 导入」选 `SC8001` docx → 预期 `structure_image` 被填充（见 R-01 背景）；或手动上传图片。
  4. **SKU 管理**：点「添加 SKU」填 sku_code/规格；**编辑已有 SKU 后保存，确认 SKU id 稳定、不重建**（验证 SKU 增量同步，见 R-03）。
  5. **PubChem 自动匹配（守卫验证）**：点「AI Auto Match / runPubchemEnrich」→ 等待结果；对模糊/低置信候选，其「Use this」按钮应**禁用**，且无法写入错误 SMILES（验证 PubChem 守卫，见 R-02）。
  6. **COA / Batch（验证 R-03）**：对某个 SKU 点「新建批次」填 lot/生产日期 → 预期 `Batch + COA draft created`；点「生成 COA」→ 预期 COA 生成；**保存产品后再进编辑页，确认 COA/Batch 仍在、不报「SKU matching query does not exist」**。
  7. **Save Draft**：点「Save Draft」（描边按钮）→ 预期存为草稿，提示 `Draft saved`。
  8. **Publish**：点「Publish」（绿实心）→ 预期弹 `showPublishDialog` 确认层；确认 → 预期状态变更、提示 `Product published`。
  9. 点「内联编辑」`showInlineEditor` 弹层 → 预期可开关。
- 预期：表单可填、上传可用、校验生效；三项修复均符合 R-01/02/03；保存/发布提示正确。

#### H-04 研究目标管理　[P1]
- 页面：`/workspace/goals`
- 步骤：点「新建」→ `showEditor` 弹层填名称等 2 字段保存；编辑/删除某条 → 预期增改删可用、列表更新。

#### H-05 应用管理　[P1]
- 页面：`/workspace/applications`
- 步骤：同 H-04，含**分类下拉（el-select）**；保存失败有 `toast.error('Save failed')`。

#### H-06 方法管理　[P1]
- 页面：`/workspace/methods`
- 步骤：同 H-05（含分类下拉、toast.error）。

#### H-07 协议管理　[P1]
- 页面：`/workspace/protocols`
- 步骤：同 H-05（含分类下拉）。

#### H-08 参考文献管理　[P1]
- 页面：`/workspace/references`
- 步骤：同 H-04（含 5 字段、Bioz 证据卡片 `BiozEvidenceSection` 展示）。

#### H-09 知识录入　[P1]
- 页面：`/workspace/knowledge-intake`
- 步骤：填表单（约 12 字段 + 选择产品下拉，可选 `sc8001`），提交；试「复制相似产品」→ 预期 `ki-toast` 成功/错误提示。

### R. 三项修复回归专项（每次发布必跑）

#### R-01 详情页结构图优先于 SMILES 渲染　[P0]
- 页面：`/products/sc8001`（该产品的 `structure_image` 与 `smiles` 均存在）
- 角色：游客
- 步骤：
  1. 打开 `/products/sc8001`，滚动到结构图区域。
  2. 确认显示的是**文档结构图 `<img class="pd-structure-img">`**（来自 Word 导入的真实结构图）。
  3. 确认**未**把 SMILES 渲染的 SVG 当作主图显示（SVG 仅在不含 `structure_image` 时回退显示）。
- 预期：优先显示文档图；SMILES 错图不覆盖。→ 若看到 SMILES 渲染的错图，提 bug。

#### R-02 PubChem 模糊匹配守卫拦截　[P0]
- 页面：`/workspace/products/sc8001/edit`
- 角色：staff（`scire03`）
- 步骤：
  1. 点「AI Auto Match / runPubchemEnrich」等待结果。
  2. 在候选列表中找一个**模糊/低置信/公式不符**的候选。
  3. 确认其「Use this」按钮**禁用**（`disabled`），且页面提示文档 Formula 对比。
  4. 尝试点禁用按钮 → 预期无任何 SMILES 被写入产品。
- 预期：守卫生效，错误分子不会被采纳；若错误 SMILES 被写入，提 bug。

#### R-03 重存产品 SKU 不丢 COA/Batch　[P0]
- 页面：`/workspace/products/sc8001/edit`
- 角色：staff
- 步骤：
  1. 进 `sc8001/edit`，确认已有 SKU 与 COA/Batch 存在。
  2. 改一个非关键字段（如概述），点「Save Draft」或「Publish」。
  3. 保存后**重新打开** `sc8001/edit`。
  4. 确认：SKU 的 id 未变（不是新建）、COA/Batch 仍在、编辑页 COA 区域**不报** `SKU matching query does not exist`。
- 预期：增量同步生效，SKU/COA 持久；若报匹配错误或 COA 丢失，提 bug。

---

## 4. 端到端业务链路场景（串测）

### 场景 1：游客加购 → 结算下单 → 查看订单　[P0]
1. 游客开 `/products/sc8001`，加购 2 件 → 角标显 2（若被拦登录，用 `e2e_customer` 登录后继续）。
2. 点购物车 → `/cart` → 去结算 → 被拦到登录。
3. 用 `e2e_customer` 登录后回结算。
4. 填收货信息提交 → 跳订单详情。
5. 开 `/orders` 确认出现该订单，详情状态时间线正确。

### 场景 2：PO 全流程（提交 → 审核 → 发货 → 开票 → AR）　[P1]
1. 客户 `e2e_customer` → `/po/submit` 提交一张 PO（PO 号 + 行项目选 `sc8001`）→ 出现在 `/po/orders`（状态：已提交）。
2. staff `scire03` → `/admin/po/review` 审核通过（状态推进）。
3. → `/admin/po/shipments` 创建发货、标已签收。
4. → `/admin/po/invoicing` 对该 PO 开票。
5. → `/admin/po/ar` 报表应体现该 PO 应收。
6. 客户 → `/po/orders/:id` 详情可见发票与发货信息。

### 场景 3：研究员维护知识图谱　[P1]
1. staff → `/workspace/goals` 新建研究目标。
2. `/workspace/applications` 新建应用并关联该目标。
3. `/workspace/methods` 新建方法关联应用。
4. `/workspace/protocols` 新建协议关联方法。
5. `/workspace/products` 新建/编辑产品（如 `sc8001`）关联方法/协议。
6. 回公开页 `/research-goals`、`/applications` 等，确认新建实体可见、关联跳转正确。

---

## 5. 已知限制 / 暂不可测项（汇总）

| 项 | 现象 | 处理 |
|----|------|------|
| 地址簿保存 | `/po/addresses` 保存返回错误提示 | 后端接口未上线，记已知限制 |
| 遗留编辑页 | `products/ProductEditPage`、`admin/AdminProductsPage`、`admin/AdminProductEdit` 导航不可直达 | 产品管理统一测 `/workspace/products` |
| AI 工具按钮 | enrich/validate/recommend/PubChem 匹配调用外部服务，可能慢/超时 | 环境依赖，非功能缺陷 |
| PO 多状态数据 | 线上仅 `confirmed`/`quote_pending` 两态有数据 | 审核/发货/开票/AR 态需新提交 PO 构造 |

---

## 6. 测试结果记录与缺陷提交

### 6.1 用例执行记录表（每轮一份）
| 用例ID | 功能 | 角色 | 结果(通过/失败/阻塞) | 现象简述 | 截图/录屏 |
|--------|------|------|----------------------|----------|-----------|
| A-01 | 首页 | 游客 | 通过 | — | — |
| … | … | … | … | … | … |

> 建议配合 **`SciReAgent_测试用例跟踪表.xlsx`**（可由本手册生成）填写：含「测试用例清单」与「缺陷记录」两表，缺陷表含编号/发现人/日期/页面/关联用例ID/现象/复现步骤/严重度/状态/截图链接/处理人，专为「记录错误与复现」设计。

### 6.2 失败 / 缺陷提交必须包含的信息
1. **用例ID + 功能名称**（如 `R-02 PubChem 守卫`）。
2. **角色 / 账号**（游客 / `e2e_customer` / `scire03`）+ 用的 Basic Auth 账号。
3. **操作步骤**（截图或录屏最佳）。
4. **预期结果 vs 实际结果**。
5. **复现步骤**（关键！逐条写清：打开哪个 URL → 点什么 → 填什么 → 观察到什么；注明是否「清缓存再跑一次仍出现」）。
6. **环境信息**：基址（固定为线上站 `https://scireagent.com`）、浏览器与版本、Basic Auth 账号（scire03）。
7. **控制台报错**：F12 → Console，粘贴红色 error（排除已知 wasm/网络噪声）。
8. **严重度**：P0（核心功能不可用）/ P1（重要功能缺陷）/ P2（体验/边缘）。

### 6.3 判断「真 bug」还是「已知限制」
- 先对照 **第 5 章** 与 **第 1.7 节**：命中则记已知限制，不提 bug。
- 对照预期明显不符、且非环境依赖（后端在跑、网络正常）→ 提 bug。
- 不确定时先记录现象并标「待确认」，由项目负责人判断。

---

## 附录 A：快速命令速查
```bash
# 后端（必须 8000）
cd <项目根>/src_claude/backend
DB_ENGINE=sqlite venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
# 前端
cd <项目根>/src_claude/frontend
npm install && npm run dev
```

## 附录 B：测试账号速查
- Basic Auth（站点访问）：scire01 `c5CCzN7LadMr` / scire02 `l618tWxn1CDi` / scire03 `TpJOAXrameB3` / scire04 `hrLeGxA4Zw52` / scire05 `Xm7eOaPw1JUJ` / scire06 `JP8Z3R6pNhnI`
- 网站登录：admin `admin123`（staff）/ scire02 `l618tWxn1CDi`（staff）/ scire03 `TpJOAXrameB3`（staff）/ e2e_customer `E2ePass123!`（customer）

## 附录 C：术语表
- **PO**：采购订单（本项目用 `transactions.Order` 模型，含 `po_number`）。客户 `/po/submit` 提交，经审核/发货/开票流转。
- **SKU**：产品的具体规格条目，详情页多行。
- **Toast**：角落短暂提示条。
- **dialog-overlay**：带遮罩的自定义弹窗（非浏览器 alert）。
- **Workspace**：staff 研究后台（`/workspace`），维护知识图谱实体与产品。
- **staff / 管理员**：`is_staff=True`（`admin`/`scire02`/`scire03`），可进所有后台。
- **customer / 客户**：`is_staff=False`（`e2e_customer`），可购物与 PO 客户侧，不能进后台。
- **两层认证**：nginx Basic Auth（站点访问）+ 网站登录（业务权限）。

## 附录 D：覆盖核对表（确保遍历，0 遗漏）
> 每跑完一条在 □ 打勾。全部勾选 = 本手册测试用例遍历完成。

- [ ] A-01 首页　[ ] A-02 搜索　[ ] A-03 应用　[ ] A-04 方法　[ ] A-05 协议　[ ] A-06 产品　[ ] A-07 研究目标　[ ] A-08 关于　[ ] A-09 404
- [ ] B-01 注册　[ ] B-02 登录　[ ] B-03 登出　[ ] B-04 guest 重定向　[ ] B-05 设置
- [ ] C-01 购物车　[ ] C-02 去结算　[ ] C-03 结算　[ ] C-04 我的订单
- [ ] D-01 询价
- [ ] E-01 提交 PO　[ ] E-02 PO 列表/详情　[ ] E-03 地址簿　[ ] E-04 重订　[ ] E-05 下载中心
- [ ] F-01 审核台　[ ] F-02 发货台　[ ] F-03 开票台　[ ] F-04 AR　[ ] F-05 组织　[ ] F-06 权限拦截
- [ ] G-01 订单列表　[ ] G-02 订单处理
- [ ] H-01 仪表盘　[ ] H-02 产品列表　[ ] H-03 产品编辑　[ ] H-04 目标　[ ] H-05 应用　[ ] H-06 方法　[ ] H-07 协议　[ ] H-08 文献　[ ] H-09 知识录入
- [ ] R-01 结构图优先　[ ] R-02 PubChem 守卫　[ ] R-03 SKU/COA 同步

**路由级遍历核对（每个 router 路由至少被上述一条用例覆盖）**：
`/` `/login` `/register` `/search` `/applications` `/applications/:id` `/methods` `/methods/:id` `/protocols` `/protocols/:id` `/products` `/products/:id` `/about` `/research-goals` `/research-goals/:id` `/quote-request` `/cart` `/settings` `/checkout` `/orders` `/orders/:id` `/admin/orders` `/admin/orders/:id` `/po/submit` `/po/orders` `/po/orders/:id` `/po/addresses` `/po/reorder` `/po/downloads` `/admin/po/review` `/admin/po/shipments` `/admin/po/invoicing` `/admin/po/ar` `/admin/po/organizations` `/workspace`(+9 子路由) `/:pathMatch(404)` —— **共 40+ 路由，全部覆盖**。
