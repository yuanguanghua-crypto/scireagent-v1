# SciReAgent 全站角色与功能操作说明书

**版本** V1.0 · **生成日期** 2026-10-22 · **对应代码** `cc4e8f2`
**性质** 操作说明书（不是设计草案、不是改造建议）。每一条都对应现有代码。
**配套** `ROLE_CAPABILITY_MATRIX.md`（权限事实基线）、`ROLE_TEST_PLAN.md`（测试方案）、`PAGE_API_MAP.json`（页面↔API 机读表）

---

## 阅读说明

### 怎么保证"与代码相符"
本文不靠人工通读写成，而是三路取证后汇编：

| 取证手段 | 覆盖 | 落盘文件 |
|---|---|---|
| 权限类**实例化求值**（335 端点 × 8 身份） | 谁能调哪个端点 | `ROLE_CAPABILITY_MATRIX.json` |
| 前端**静态解析**（`@/api/*` 具名导入 + 直接 http） | 哪个页面调哪些端点 | `PAGE_API_MAP.json` |
| 前端**逐文件读模板**（元素文案、`@click` 处理函数、`v-if` 条件） | 页面上能看见什么、能点什么 | 本文各节 + `file:line` |
| 后端**状态机与模型字段**读取 | 状态怎么流转、字段含义 | 本文第 9 章与附录 A |

复核方法见附录 C，可一条条重跑。

### 图例

| 记号 | 含义 |
|---|---|
| ✅ | 该角色可正常使用 |
| ⚠️ | 可用但有已知缺陷/限制（第 11 章有明细） |
| ❌ | 不可用（403 / 路由拦截 / 无入口） |
| 🔒 | 存在端点但**前端无入口**（只能调 API） |
| 📄 文件:行 | 代码依据，可跳转核对 |

### 三个必须先懂的前提

**前提一：平台有三个互不相通的面**
```
销售前台（23 个公开页）   → 匿名即可浏览、加购、询价
客户门户（10 个需登录页） → researcher 下单、查单、提 PO、管地址
内部台  （19 个内部页）   → 采购运营 + 内容运营
```
它们不是"同一个后台的不同权限视图"，而是**三套独立路由树**，用 `meta.requiresAuth` / `meta.requiresAdmin` 二级守卫隔离。

**前提二：「角色」不是一个字段，是四个维度的组合**
`role`（researcher/procurement/editor/admin）、`is_org_admin`、`is_staff`、`email_verified`。
其中**只有 `role` 和 `is_staff` 影响权限**；`is_org_admin` 与 `email_verified` 实测对 API 权限**零影响**（第 13 节有证据）。

**前提三：前端只有 2 级守卫，后端有 8 类判据**
⇒ 会出现"页面能进、按钮点了 403"。这不是 bug 的偶发表现，而是两层粒度不匹配的**结构性后果**。

---

# 第 0 章 系统总览

## 0.1 页面总表（56 条路由声明 → 52 个实际页面 + 404）

| 分区 | 守卫 | 页面数 | 路径清单 |
|---|---|---|---|
| **公开** | 无 | **23** | `/`、`/products`、`/products/:id`、`/applications`、`/applications/:id`、`/applications/classes/:class_id`、`/methods`、`/methods/:id`、`/protocols`、`/protocols/:id`、`/research-goals`、`/research-goals/:id`、`/research-goals/classes/:class_id`、`/search`、`/login`、`/register`、`/verify-email`、`/cart`、`/wishlist`、`/quote-request`、`/about`、`/privacy`、`/terms` |
| **客户门户** | `requiresAuth` | **10** | `/settings`、`/checkout`、`/orders`、`/orders/:id`、`/po/submit`、`/po/orders`、`/po/orders/:id`、`/po/addresses`、`/po/reorder`、`/po/downloads` |
| **内部台** | `requiresAdmin` | **19** | 见 0.2 |
| 兜底 | — | 1 | `/:pathMatch(.*)*` → 404 |

📄 依据 `frontend/src/router/index.js`（`path:` 声明 56 处；`/workspace` 为父级壳，10 个子页继承守卫）
⚠️ **易错点**：只数带 `meta.requiresAdmin` 的路由块会得到 9，实际页面是 19（8 个 `/ops` + `/workspace` 壳 + 10 个子页）。

## 0.2 内部台 19 页

| # | 页面名 | 路径 | 组件 | 业务域 |
|---|---|---|---|---|
| 1 | Dashboard | `/workspace` | `workspace/DashboardPage.vue` | 内容运营 |
| 2 | Products | `/workspace/products` | `workspace/ProductsPage.vue` | 产品管理 |
| 3 | New Product | `/workspace/products/new` | `workspace/ProductEditPage.vue` | 产品新建 |
| 4 | Edit Product | `/workspace/products/:id/edit` | 同上 | 产品编辑 |
| 5 | Research Goals | `/workspace/goals` | `workspace/GoalsPage.vue` | 知识实体 |
| 6 | Applications | `/workspace/applications` | `workspace/AppsPage.vue` | 知识实体 |
| 7 | Methods | `/workspace/methods` | `workspace/MethodsPage.vue` | 知识实体 |
| 8 | Protocols | `/workspace/protocols` | `workspace/ProtocolsPage.vue` | 知识实体 |
| 9 | References | `/workspace/references` | `workspace/ReferencesPage.vue` | 知识实体 |
| 10 | Verified Applicability | `/workspace/verified` | `workspace/VerifiedPage.vue` | 关系审核 |
| 11 | Knowledge Intake | `/workspace/knowledge-intake` | `views/KnowledgeIntake.vue` | 知识录入 |
| 12 | Order Management | `/ops/orders` | `admin/AdminOrdersPage.vue` | 订单 |
| 13 | Order Detail | `/ops/orders/:id` | `admin/AdminOrderDetail.vue` | 订单 |
| 14 | Order Review Desk | `/ops/po/review` | `admin/PoReviewDesk.vue` | PO 审批 |
| 15 | Shipment Desk | `/ops/po/shipments` | `admin/PoShipmentDesk.vue` | 发货 |
| 16 | Invoicing Desk | `/ops/po/invoicing` | `admin/PoInvoicingDesk.vue` | 开票收款 |
| 17 | AR Aging | `/ops/po/ar` | `admin/PoArReport.vue` | 应收 |
| 18 | Organization Mgmt | `/ops/po/organizations` | `admin/PoOrgManagement.vue` | 机构 |
| 19 | Inventory Desk | `/ops/inventory` | `admin/InventoryDesk.vue` | 库存 |

**内部台分为两条业务线，容易被混为一谈：**

| 业务线 | 页面 | 数据来源 | 权限口径 |
|---|---|---|---|
| **内容运营线** | 1–11 | `/products`、`/methods`、`/post`… 的 `IsAdminOrReadOnly` 系列 | 写 = `is_staff` |
| **交易运营线** | 12–19 | 两套并存：`/admin/orders/`（`IsAdminUser`）与 `/orders/`（`IsProcurementOrAdmin`） | 部分只看 `is_staff`，部分收 `role` |

⚠️ **交易线两套 API 并存**是本书第 11 章列的第一个结构性问题：`AdminOrdersPage` 读 `/admin/orders/`（staff 专属），而四个 PO Desk 读 `/orders/`（采购也可）。**同一业务两种权限口径。**

## 0.3 身份模型：4 维 → 8 种真实组合

| 维度 | 取值 | 默认 | 谁改 | 对权限影响 |
|---|---|---|---|---|
| `role` | researcher / procurement / editor / admin | researcher | 仅 Django admin | ✅ 影响 **17** 个端点 |
| `is_staff` | true / false | **false** | Django admin / `createsuperuser` | ✅ 影响 **231** 个端点 |
| `is_org_admin` | true / false | false | 建机构时自动 true | ❌ **零影响** |
| `email_verified` | true / false | **false** | 点验证邮件 | ❌ **零影响**（仅登录时校验） |

| # | 身份 | 产生方式 | 内部人？ | 能进内部台？ | 本章 |
|---|---|---|---|---|---|
| 1 | 匿名访客 | — | ❌ | ❌ | 第 1 章 |
| 2 | 已注册未验证 | 注册后未点邮件 | 不能登录 | ❌ | 第 2 章 |
| 3 | researcher（独立） | 注册选 Independent | ❌ | ❌ | 第 3 章 |
| 4 | researcher + org_admin | 建/加入机构 | ❌ | ❌ | 第 4 章 |
| 5 | procurement（`is_staff=False`） | Django admin 授予 | ⚠️ 部分 | ✅ 能进，部分页面不可用 | 第 5 章 |
| 6 | admin（`role='admin'`，`is_staff=False`） | Django admin 授予 | ⚠️ 部分 | ✅ 能进，同上传 | 第 6 章 |
| 7 | `is_staff=True` | Django admin 勾选 | ✅ 全部 | ✅ 全功能 | 第 7 章 |
| 8 | superuser | `createsuperuser` | ✅ 全部 | ✅ 全功能 + Django admin | 第 8 章 |

## 0.4 权限判定机制

### 后端：8 类判据，335 个 path×method

| 权限类 | 判据 | 端点数 | 谁能过 |
|---|---|---|---|
| `AllowAny` | — | 42 | 所有人 |
| （未声明，落 DRF 默认） | — | 1 | `POST /quote-requests/` |
| `IsAuthenticated` | 已登录 | 36 | 任何登录用户 |
| **`IsAdminOrReadOnly`** | 读=任何人；**写=`is_staff`** | **209** | 写只看 `is_staff` |
| `IsAdminUser`（DRF 内置） | `is_staff` | 15 | 只看 `is_staff` |
| `IsProcurementOrAdmin` | `is_staff` **或** `role∈(procurement, admin)` | 16 | 内部人 |
| `IsStaffUser` | `is_staff` | 7 | 只看 `is_staff` |
| `AddressPermission` | 登录即可（机构隔离靠 queryset） | 6 | 登录即可 |
| `IsSuperUser` | `is_superuser` | 2 | 超管 |
| `IsAdmin` | `is_staff` **或** `role=='admin'` | 1 | `assign-rep` |

📄 依据 `backend/core/permissions.py`、`backend/apps/accounts/api/v1/views.py:315`（`AddressPermission`）

**这三种"内部人"写法并存** ⇒ 同一个用户在 A 口径下是外部人，在 B/C 口径下是内部人：

| 口径 | 表达式 | 端点数 |
|---|---|---|
| A | `is_staff` | 231 |
| B | `is_staff` or `role∈(procurement,admin)` | 16 |
| C | `is_staff` or `role=='admin'` | 1 |

### 前端：2 级 + 单一真相源

```
router.beforeEach（router/index.js:299）
├─ meta.requiresAuth  && !token  → /login?redirect=
└─ meta.requiresAdmin && !isInternal(auth) → /
```
`isInternal(auth) = Boolean(auth.isStaff) || ['procurement','admin'].includes(auth.role)`
📄 `frontend/src/utils/internalAccess.js:37-43`

**页面内还有第二道**：9 个 workspace 页面在 `setup` 里各自 `if (!isInternal(auth)) router.replace('/')`。
（2026-10-14 曾出现"路由放行但页面踢回"的分裂，现已统一调用同一函数。）

⚠️ **除守卫外，前端没有任何"按角色隐藏按钮"的机制**。19 个内部页逐文件检查，`isStaff` 只出现 **1 处**：`ProductsPage.vue:547` 的 `canBatchAi`，控制两个批量 AI 按钮。其余全部按钮对所有能进页面的人一视同仁。（`views/po/*` 6 个页面 grep `role|authStore|isStaff|isInternal` **零命中**。）

## 0.5 端到端数据链路

```
知识侧（内容运营维护）
  ResearchGoal ──1:N──▶ Application ──N:M──▶ Method ──1:N──▶ Protocol
                                                 │
                                                 └──N:M──▶ Product（derived / verified 两条边）
商品侧（内容运营维护）
  ProductClass（三级类目）◀── Product ──1:N──▶ SKU（价格/币种/现货状态）
                                          │
交易侧（客户下单 → 采购运营履约）              │
  Basket ──checkout──▶ Order ──1:N──▶ OrderItem（单价快照）
                          │
                          ├─▶ Shipment ──▶ ShippingRecordItem
                          ├─▶ Invoice ──▶ PaymentRecord
                          ├─▶ PoAttachment
                          └─▶ StatusLog（每次状态变更留痕）

合规侧（内容运营维护）
  SKU ──1:N──▶ Batch ──1:1──▶ Coa（draft → published）
  Product ──1:N──▶ SdsRevision（draft → published）
```

**六个业务状态机**（完整转换表见附录 A）：Order、Coa、SdsRevision、VerifiedRelation、Quote、Document(Batch)。

---

# 第 1 章 匿名访客

## 1.1 身份与边界

| 项 | 值 |
|---|---|
| 判定 | 无 token / 未登录 |
| 可进页面 | 第 0.1 节的 23 个公开页 |
| 可写端点 | **7 个**：`auth/login`、`auth/register`、`auth/resend-verification`、`basket/items`(POST/PATCH/DELETE)、`quote-requests/` |
| 读端点 | 132 个读端点中通过 **117** 个（`IsAdminOrReadOnly` 的 GET 全部对匿名开放） |
| 写端点 | 203 个写端点中通过 **7** 个 |

**匿名购物车靠什么识别**：`X-Session-Key` 请求头。后端不认 cookie，换浏览器/清缓存即丢失。

## 1.2 操作流程

### F1-1 浏览首页

**页面** `/`（`HomePage.vue`）+ 4 个子组件（`HeroSearch`、`CategoryPills`、`FeaturedProducts`、`KnowledgeSection`）

| 步 | 操作 | 页面元素（文案原文） | 请求 | 结果 |
|---|---|---|---|---|
| 1 | 进入首页 | — | `GET /site/home` | 渲染分类胶囊条、精选商品、统计条、知识图谱折叠区 |
| 2 | 点分类胶囊 | 分类名 + 数量 | 无 | 跳 `/products?category={slug}` |
| 3 | 点精选商品卡 | 商品名 / `CAS: xxx` / 价格 / `In Stock` | 无 | 跳 `/products/{id}` |
| 4 | 点 `View all {{n}}+ →` | — | 无 | 跳 `/products` |
| 5 | 展开知识区 | `Explore Knowledge Graph` + `4 domains` | 无 | 展开 4 张卡：`Research Goals`/`Applications`/`Methods`/`Protocols` |
| 6 | 点知识卡 | `Browse N →` | 无 | 跳对应列表页 |

**首页搜索**（`HeroSearch.vue`）：输入框 placeholder `Search products, CAS, methods…`；按回车或点 `Search` 跳 `/search?q=…`。**空输入不跳转**。
热门词按钮：`Popular:` + `ATP` / `PCR` / `Click Chemistry` / `Fluorescent Probes` / `Cell Assay`。

📄 `HomePage.vue:41-78`、`HeroSearch.vue:17-61`、`CategoryPills.vue:29`、`FeaturedProducts.vue:58-73`

### F1-2 浏览产品列表与筛选

**页面** `/products`（`ProductIndex.vue` + `ProductLayout.vue`）

| 步 | 操作 | 页面元素（文案原文） | 请求 | 结果 |
|---|---|---|---|---|
| 1 | 进入 | — | `GET /products`、`GET /categories` | 20 条/页卡片网格 |
| 2 | 切 L1 分类 | 分类胶囊（含数量） | `GET /products?category_l1=` | 重查 |
| 3 | 切 L2 分类 | L2 胶囊 | `GET /products?product_class_id=` | 重查 |
| 4 | 切 L3 子分类 | `Subcategory:` 标签 | 重查 | ⚠️ **L3 名称不进请求参数**（`ProductIndex.vue:43-47` 只传 `productClassId`/`l1`）⇒ 与 L2 结果实际相同 |
| 5 | 排序 | `默认` / `名称 A→Z` / `最新上架` / `知识关联最强` | `GET /products?ordering=` | 回第 1 页 |
| 6 | 搜索 | placeholder `Search products by name, CAS, catalog no...` | `GET /products?search=` | 重查 |
| 7 | 翻页 | `← Prev` / 页码 / `Next →` | `GET /products?page=` | 滚顶换页 |
| 8 | 清筛选 | `Clear filter` / 筛选标签的 `×` | 重查 | — |

**空态**：`No products found` / `Try adjusting your search or filter.`
**商品卡展示字段**：商品名、`CAS`、`Formula`、价格、库存徽章、`知识关联`
📄 `ProductIndex.vue:18-23,54-76,107-161`、`ProductLayout.vue:58-246`

### F1-3 查看产品详情

**页面** `/products/:id`（`ProductDetail.vue`）

**进入即发 5 个请求**：

| # | 请求 | 用途 |
|---|---|---|
| 1 | `GET /products/{id}/detail` | 主体数据 |
| 2 | `GET /sds-revisions/?product_id={id}` | SDS 区 |
| 3 | `GET /coas/?product_id={id}&status=published` | SKU 行 COA 图标 |
| 4 | `GET /products/{id}/methods/` | 已验证适用性 |
| 5 | `GET /wishlist/` | 仅登录时发 |

**页面分区**（自上而下）：停产提示条 → 面包屑 → 商品名 + 编号/CAS → 左列（结构图盒、分类标签、状态徽章 + `RUO`、overview、`Also known as:`、`Chemical Identity`（SMILES/InChI/CAS/Formula/MW）、`Modification Signature`（SMARTS）、`Specifications`）→ 右列（`Available SKUs` 表、`Related Products`）→ 知识 Tabs（`Applications`/`Methods`/`Protocols`/`References`/`FAQ`）→ `Handling Notes` → 收藏行 → CTA。

**可交互元素**：

| 元素 | 文案（原文） | 请求 | 结果 |
|---|---|---|---|
| InChI 展开 | `Show full` / `Collapse` | — | 文本展开 |
| SKU 行 COA 图标 | 悬浮提示 `COA: {lot_number}` | — | 前端弹层预览 |
| `−` / `+` | — | — | 行内数量增减（下限 1） |
| **加入购物车** | `Add to Cart` | `POST /basket/items` | toast `Added to cart` / 失败 `Failed to add` |
| SDS 预览 | `SDS`（+ 置信度徽章） | — | 前端弹层；无 SDS 时整块不渲染 |
| SDS 下载 | 图标 `title="Download SDS"` | `GET /sds-revisions/{id}/download/` | 新窗口下载 |
| 询价 | `Request Quote` | — | 跳 `/quote-request?product_id=` |
| 知识 Tab | 5 个 Tab | — | 切换面板 |
| 展开更多 | `Show all {N} →` / `Show less` | — | 展开全部 |
| FAQ 展开 | 问题文本 + `+`/`−` | — | 展开答案 |
| 收藏 | `收藏` / `已收藏` | `GET /wishlist/` → 必要时 `POST` / `PATCH /wishlist/{id}/` | toast `已收藏`/`已取消收藏`；**未登录 toast `请先登录`** |
| CTA | `Add to Cart` / `Request Quote` / `Browse Catalog` | 同对应动作 | — |

**SKU 表列**：`SKU` / `Pack Size` / `Price` / `Status` / `COA` / 操作列
**空态**：结构图 `Loading structure...`→`No structure`；已验证方法 `No verified method applicability has been confirmed for this product yet.`；页面 `Product not found or unavailable`
**停产横幅**：`This product has been discontinued and is no longer available for purchase. Specifications are retained for reference.`
📄 `ProductDetail.vue:327-424,487-966`

### F1-4 搜索（分组搜索）

**页面** `/search`（`SearchPage.vue`）

| 步 | 操作 | 元素（原文） | 请求 |
|---|---|---|---|
| 1 | 输入关键词回车 或 点 `Search` | placeholder `Search products, methods, protocols, applications...` | `GET /search/grouped?q=` |
| 2 | 切类型 Tab | `All` / `Products` / `Applications` / `Methods` / `Protocols` / `References` + 计数 | 无（客户端过滤） |
| 3 | 点结果 | 名称 / 副标题 / `Score: N%` | 跳 `/{type}/{id}` |

**空态**：`No results for "{q}"` / `Try different keywords or check spelling.`
⚠️ 请求失败**只在 console 报错，页面无提示**（`SearchPage.vue:68`）。
⚠️ `References` 类型结果**可点击但无跳转目标**（`typeMap.references = null`，`:81`）—— 无 Reference 详情页。
📄 `SearchPage.vue:14-21,34-58,112-203`

### F1-5 浏览知识实体（4 类 + 收敛类聚合）

| 页面 | 主体结构 | 特有交互 |
|---|---|---|
| `/applications`（`ApplicationIndex.vue`） | 两个 Tab：`All Applications`（搜索 + 状态 chips `All`/`Active`/`Draft`/`Deprecated` + 卡片网格 + 分页）、`Browse by Class`（收敛类表格：`Class Name`/`Class ID`/`Source`/`Members`/`Avg Cos`） | 收敛类来源筛选 `All Sources`/`Curated`/`High Frequency`/`KMeans` |
| `/applications/:id` | 面包屑 → 路径 chips → 上下文卡 → 标题 + 状态 → `Methods` 区 → `Protocols` 区 → `Products` 区 → 研究路径卡 → CTA | 卡片跳详情 |
| `/methods`（`MethodIndex.vue`） | 搜索 + chips `All Methods`/`Active`/`Draft` + 卡片 + 分页 | ⚠️ **chips 未生效**：`handleFilter` 不传 `status`（`:37`），只变高亮不筛数据 |
| `/methods/:id` | 上下文卡 → 标题 + `Purpose:` → 规格行（`Cost Band`/`Timeline`）→ `Advantages`/`Limitations` → `Protocols` 区 → `Products` 区 | 协议卡带 `v{version}` |
| `/protocols`（`ProtocolIndex.vue`） | 搜索 + chips `All Protocols`/`Published`/`Draft`/`Superseded` + 卡片 + 分页 | ⚠️ **chips 未生效**（同上，`:38`） |
| `/protocols/:id` | 面包屑 → 上下文卡（上游 Methods / `Required Products`）→ 标题 + `v{version}` → 研究分类 facet → `Objective`/`Principle` → 6 个 Tab（`Steps`/`Materials`/`Troubleshooting`/`Expected Results`/`References`/`Products`） | 无产品时出现 `Request protocol support →`（跳 `/quote-request?note=Protocol support requested`） |
| `/research-goals`（`ResearchGoalIndex.vue`） | Tab 1 `All Research Goals`（搜索 + 状态下拉 `All`/`Active`/`Draft`/`Completed` + 表格 + 分页）、Tab 2 `Browse by Class` | 表格列 `Goal Name`/`Summary`/`Status`/`Applications`/`Created` |
| `/research-goals/:id` | 面包屑 → 标题 + 状态 + `Priority:` → `Summary` → `Curated Protocols` 表 → `Created`/`Updated` | 表格列 `Protocol`/`Slug` |
| `/applications/classes/:class_id`、`/research-goals/classes/:class_id` | 返回行 → 类名 + 来源徽标 + `Members: N` + `Avg Cos` → `Members` 表格 → 分页 | 成员表列 `Name`/`Slug`/`Origin`/动态表头（`协议数` 或 `关联数`）；`混合方法` 徽标悬浮提示"该类聚合了多种不同方法，请以成员列表为准" |

**所有详情页的统一空态语气**（示例）：`Methods are being curated for this application.`、`Protocols are being documented for this method.`、`Product associations are being mapped…`
📄 各页面 `onMounted` 单请求；收敛类 `GET /convergence-classes/?group=ap|rg`

### F1-6 加入购物车（匿名）

**页面** `/cart`（`CartPage.vue`）

| 步 | 操作 | 元素（原文） | 请求 | 结果 |
|---|---|---|---|---|
| 1 | 进入 | — | `GET /basket` | 失败时回落 localStorage 本地购物车 |
| 2 | 加数量 | `+` | `PATCH /basket/items/{id}` | 重载 |
| 3 | 减数量 | `−` | `PATCH /basket/items/{id}`；减到 0 转为删除 | 重载 |
| 4 | 移除 | `Remove` | `DELETE /basket/items/{id}/delete` | toast `Item removed from cart` |
| 5 | 下单 | `Place Order` | 无 | 跳 `/checkout` ⇒ **被路由拦到 `/login?redirect=/checkout`** |
| 6 | 询价 | `Request Quote` | 无 | 跳 `/quote-request` |
| 7 | 提交审批 | `Submit for Approval` | 无 | ⚠️ 与 `Place Order` **同目标**（跳 `/checkout`），无审批接口；且该按钮仅 `role === 'researcher'` 且已登录且有机构时显示 ⇒ 匿名不可见 |

**空态**：`Your cart is empty` / `Start browsing our catalog to find the reagents you need.`
📄 `CartPage.vue:14-65,86-191`

⚠️ **匿名购物车转登录后的合并**：已知 `mergeLocalBasket` 零调用（历史缺陷），登录后本地购物车不会自动并入账户购物车。

### F1-7 提交询价单（RFQ）

**页面** `/quote-request`（`QuoteRequestPage.vue`），无守卫 ⇒ **匿名可用**（`POST /quote-requests/` 是唯一未声明权限的端点）

| 步 | 操作 | 元素（原文） | 校验 |
|---|---|---|---|
| 1 | 填联系信息 | `Name`* / `Email`* / `Phone` / `Company / Institution` / `Country` | Name、Email 必填；Email 走正则 |
| 2 | 填明细 | 每行 `Product` / `Qty`(min=1) / `Note` | 至少一行，且每行需 `product_id` 或非空名称 |
| 3 | 增删行 | `+ Add another product` / `×` | 删空自动补一行 |
| 4 | 补备注 | `Additional Notes` | — |
| 5 | 提交 | `Submit Quote Request`（提交中 `Submitting...`） | `POST /quote-requests/` |

**成功态**：`Quote Request Submitted` + `Thank you! Our team will review your request and respond within 1-2 business days.` + `Reference: RFQ #{id}`
⚠️ **失败只 `console.error`，页面无任何提示**（`:104-105`）—— 用户会以为提交成功了。

**从产品详情页带入**：URL 带 `product_id` 时，进入页面会 `GET /products/{id}` 预填一行；否则用购物车数据预填。
📄 `QuoteRequestPage.vue:29-64,78-106,115-206`

### F1-8 注册（三步向导）

**页面** `/register`（`RegisterPage.vue`），`meta.guest`

| 步 | 内容 | 字段与校验 | 提交 |
|---|---|---|---|
| **Step 1** 基本信息 | — | `Username`（≥3，`^[a-zA-Z0-9_-]+$`）、`Email`（正则）、`Password`（≥8，带 `Weak/Fair/Good/Strong` 强度条）、`Confirm Password`（一致） | 点 `Next`，仅前端校验 |
| **Step 2** 身份选择 | 3 张卡：`Independent Researcher` / `Researcher (Team)` / `Procurement Manager` | 必须选一张 | `solo` 时按钮变 `Complete Registration` 并直接提交；否则进 Step 3 |
| **Step 3** 机构 | Tab `Join Existing` / `Create New` | Join：机构搜索框（400ms 防抖，`GET /organizations/?q=`）必须选中一个；Create：`Organization Name`(≥2) + `Organization Type`（`Academic / University`/`Enterprise / Company`/`Government / Institute`/`Hospital / Medical`） | `Complete Registration` → `POST /auth/register` |

**关键事实（与运营强相关）**：
> **三张身份卡都发送 `role: 'researcher'`**（`RegisterPage.vue:65,74,91`）。
> 也就是说 **注册时无法自选 procurement / admin**，即使用户点的是 `Procurement Manager`。
> 采购身份只能由内部在 Django admin 里事后授予（第 12 章）。

**注册成功**：页面切换为 `Check your email` 面板，文案 `We've sent a verification link` / `Didn't receive it?` + `Resend verification email`。
**建机构的影响**：创建者自动 `is_org_admin = True` 且 `organization` 指向新机构（`accounts/api/v1/views.py:305-310`）。
**加入机构**：走 `_check_join_domain` 域名校验，不能自助加入任意机构。
📄 `RegisterPage.vue:58-94,96-115,130-186,265-296,369-442`

### F1-9 邮箱验证

**页面** `/verify-email?token=…`（`VerifyEmailPage.vue`）

| 状态 | 表现 |
|---|---|
| 验证中 | `Verifying your email address…`（进入即 `GET /auth/verify-email?token=`） |
| 成功 | `Email verified! Taking you to the site…` → **1.8 秒后自动登录并跳转**（`redirect` 或 `/`） |
| 失败 | `Verification failed. The link may be invalid or expired.` |
| 缺 token | `Missing verification token in the link.` |

⚠️ **失败态下 `Resend verification email` 按钮永不显示**（外层 `v-if="email"`，而 `email` 只在成功路径赋值，`:28` 与 `:117`）⇒ 验证链接过期后用户**没有任何自助重发入口**。
📄 `VerifyEmailPage.vue:17-41,62-127`

## 1.3 匿名做不到的事（明确边界）

| 想做的事 | 结果 | 原因 |
|---|---|---|
| 进入 `/checkout` 或任何 `/orders` | 跳 `/login?redirect=` | `requiresAuth` |
| 进入 `/workspace`、`/ops/*` | 跳 `/login?redirect=` | `requiresAdmin` |
| 改产品 / 知识实体 | 403 | `IsAdminOrReadOnly` 写要 `is_staff` |
| 看别人的购物车 | 看不到 | 购物车按 `X-Session-Key` 隔离 |
| 看未发布（draft）产品 | 看不到 | 公开 queryset 只含 `status=active` 且未归档 |

---

# 第 2 章 已注册未验证用户

## 2.1 身份与边界

| 项 | 值 |
|---|---|
| 产生方式 | 注册成功后、点验证邮件前的状态 |
| `email_verified` | `false` |
| 能否登录 | **不能**。`LoginView` 校验 `email_verified`，返回 403 |
| 能进页面 | 与匿名相同（无 token） |
| **API 权限** | 与 researcher **逐项完全相同**（实测：读 123/132、写 43/203） |

> 🔎 **这是一个必须说清的事实**：`email_verified` **不是权限维度**，它只是登录闸门。
> 一个已登录用户如果 `email_verified` 事后被置为 `false`，**其现有 token 依然全权可用**——
> 因为没有任何权限类检查这个字段。若业务上要求"未验证即不得操作"，当前实现并不满足。

## 2.2 操作流程

### F2-1 尝试登录 → 被拒 → 重发验证

| 步 | 操作 | 表现 |
|---|---|---|
| 1 | `/login` 输入 `Username` + `Password` 提交 | `POST /auth/login` |
| 2 | 后端返回 403 | 页面显示未验证提示，并**露出重发区** `Need a new verification link?` |
| 3 | 点 `Resend verification email` | ⚠️ **必然失败** |

> ⚠️ **已知死链（本章最重要的一条）**：`LoginPage.vue:112` 的 `handleResend` 读取 `form.email.trim()`，
> 而 `form` 只有 `username` 和 `password` 两个字段（`:22-25`）⇒ **`form.email` 是 `undefined`，点击必抛 `TypeError`，请求根本不会发出**。
> 用户在登录页上**没有任何办法自助重发验证邮件**。
> （注册页 `/register` 的重发按钮是好的，因为它单独 `ref` 了 `email`。）

📄 `LoginPage.vue:22-25,76-115,161-176`、`RegisterPage.vue:341-349`

### F2-2 重新走验证链接

| 步 | 操作 | 表现 |
|---|---|---|
| 1 | 从邮件点链接 | 打开 `/verify-email?token=…` |
| 2 | 自动验证 | `GET /auth/verify-email?token=` |
| 3 | 成功 | 自动登录 → 跳 `redirect` 或 `/`（成为第 3 章身份） |
| 4 | 失败（过期） | 见 F1-9 的死链问题 |

## 2.3 未验证用户做不到的事

| 想做的事 | 结果 |
|---|---|
| 登录 | 403，只能去验证邮箱 |
| 任何需要 token 的操作 | 无 token ⇒ 等同匿名 |
| 自助补发验证邮件（登录页路径） | ⚠️ 死链 |
| 自助补发验证邮件（注册成功后当页） | ✅ 可用 |

---

# 第 3 章 researcher（普通客户，绝大多数用户）

## 3.1 身份与边界

| 项 | 值 |
|---|---|
| `role` | `researcher`（注册默认，不可自选其他） |
| `is_staff` | false |
| 可进页面 | 23 个公开页 + **10 个客户门户页** |
| 读端点 | 123/132 |
| 写端点 | **43/203** —— 全部集中在「购物车 / 下单 / 地址 / 个人资料 / 询价」 |
| 代表写操作 | `POST /checkout/`、`POST /orders/po/`、`POST /orders/{id}/confirm-quote/`、`/addresses/` 全套、`PUT /auth/profile`、`/basket/*` |
| 被拒的典型 | `POST /products/`、`POST /methods/`、`GET /verified/`、`GET /admin/orders/`、`GET /inventory/` |

**客户门户 10 页分工**：

| 页面 | 路径 | 干什么 |
|---|---|---|
| Settings | `/settings` | 改个人资料 / 联系 / 收货 / 密码（⚠️ 密码是假的） |
| Checkout | `/checkout` | 从购物车下单 |
| My Orders | `/orders` | 订单列表 |
| Order Detail | `/orders/:id` | 订单详情 + **报价应答** |
| PO Submit | `/po/submit` | 提交 PO（可带附件、可多行明细） |
| PO Orders | `/po/orders` | PO 单列表（按状态筛） |
| PO Order Detail | `/po/orders/:id` | PO 单详情 + 下载 |
| PO Addresses | `/po/addresses` | 地址簿 CRUD |
| PO Downloads | `/po/downloads` | 发票 PDF / PO 附件集中下载 |
| PO Reorder | `/po/reorder` | 已完成订单再次下单 |

## 3.2 操作流程

### F3-1 登录

**页面** `/login`（`LoginPage.vue`）

| 步 | 操作 | 元素（原文） | 请求 | 结果 |
|---|---|---|---|---|
| 1 | 输入 | `Username` / `Password` | — | 前端非空校验 |
| 2 | 提交 | `Sign In` | `POST /auth/login` | — |

**登录后的落点分三种**（`router/index.js:306-309` + `LoginPage.vue:76-83`）：

| 条件 | 落到 |
|---|---|
| URL 带 `?redirect=` | 该地址 |
| 内部人（`isInternal` 为真） | `/workspace` |
| 其他（researcher） | `/` |

**失败分支**：

| 状态 | 页面提示（原文） |
|---|---|
| 401 | `Incorrect username or password. Please check and try again.` |
| 403（未验证） | 未验证提示 + 露出重发区（⚠️ 重发按钮是死链，见 F2-1） |
| 其他 | 后端 `message` 或 `Login failed. Please try again.` |

📄 `LoginPage.vue:64-99,179-219`

### F3-2 管理个人资料（5 个 Tab）

**页面** `/settings`（`SettingsPage.vue`）—— **进入页面不发任何请求**，数据全来自已缓存的 `authStore.user`

| Tab | 字段 | 保存按钮（原文） | 请求 |
|---|---|---|---|
| `Profile` | `Avatar URL` / `Nickname` / `Phone` / `Department / Lab` / `Title` | `Save Changes` | `PUT /auth/profile` |
| `Contact` | `Alternate Email` / `Default Shipping Address` | `Save Changes` | `PUT /auth/profile` |
| `Shipping` | `Recipient Name` / `Phone` / `Email` / `Default Shipping Address` / `Default Payment Method`(`Purchase Order`/`Credit Card`/`Wire Transfer`) / `Default PO Number` | `Save Shipping Info` | `PUT /auth/profile` |
| `Security` | `Current Password` / `New Password`(≥8) / `Confirm New Password` | `Update Password` | ⚠️ **不发请求** |
| `Account` | 只读：Username / Email / Registered / Organization / Role / Organization Admin | — | — |

**成功/失败提示**（原文）：`Profile updated successfully.`、`Contact info updated successfully.`、`Shipping info updated successfully.`；失败 `Failed to update …`。

> ⚠️ **修改密码是假的**：`Security` 面板校验完三个字段后**直接弹** `Password update feature will be available soon.` 并清空输入（`SettingsPage.vue:191-221`）——
> **没有任何后端调用**。用户会以为改成功了，实际密码没变。这是全站最典型的"假成功"。

**Account 面板的两个只读事实**：`Role cannot be changed`（角色不可自助修改）；`Organization Admin` 行只在 `is_org_admin` 为真时显示 `Admin` 徽章，否则显示 `No`。
📄 `SettingsPage.vue:13-19,124-238,246-574`

### F3-3 购物车（登录态）

**页面** `/cart`（`CartPage.vue`）—— 与匿名的 F1-6 相同，但后端按 `user` 而非 `X-Session-Key` 归属。

登录后 `Place Order` 可正常进入 `/checkout`（不再被拦截）。

### F3-4 结账下单（核心流程）

**页面** `/checkout`（`CheckoutPage.vue`）

**前置**：购物车非空。购物车为空 ⇒ 显示 `Your cart is empty` / `Browse our catalog to find the reagents you need.`

| 步 | 操作 | 元素（原文） | 说明 |
|---|---|---|---|
| 1 | 进入 | — | `GET /basket` |
| 2 | 填收货 | `Recipient Name *`、`Phone`、`Email`、`Shipping Address *` | 见下校验表 |
| 3 | 选支付方式 | `Purchase Order` / `Credit Card / Online Payment` / `Wire Transfer` / `Request Quote` | 默认 `purchase_order` |
| 4 | 选 PO 时补字段 | `PO Number *`、`PO Contact` | 条件必填 |
| 5 | 备注 | `Order Notes` | — |
| 6 | 提交 | `Place Order`；`paymentMethod==='quote'` 时文案变 `Request Quote` | `POST /checkout/` |
| 7 | 成功 | 清空购物车 → 跳 `/orders/{id}` | 后端返回订单详情 |
| 8 | 失败 | 顶部错误横幅，文案取后端 `message` 或 `Checkout failed. Please try again.` | 停留原页 |

**表单校验（前端）**：

| 字段 | 必填 | 校验与提示（原文） |
|---|---|---|
| `Recipient Name` | ✅ | 空 ⇒ `Recipient name is required` |
| `Shipping Address` | ✅ | 空 ⇒ `Shipping address is required` |
| 支付方式 | ✅（默认已选） | — |
| `PO Number` | 条件（选 `purchase_order` 时） | 空 ⇒ `PO number is required for Purchase Order payment` |
| `Phone` / `Email` / `PO Contact` / `Order Notes` | ❌ | 无校验 |

**服务端行为（下单时发生什么）**：
1. 校验购物车非空 ⇒ 空则 400 `EMPTY_BASKET`
2. 逐条校验 SKU 库存状态 ⇒ 有 `out_of_stock` 则 400 `OUT_OF_STOCK`，文案 `SKU {code} is out of stock`
3. **总价由服务端按 SKU 现价重算**（客户端提交的价格不作数）
4. 初始状态：`payment_method == 'quote'` ⇒ `quote_pending`；否则 `confirmed`
5. 订单号 `ORD-YYYYMMDD-NNN`，由 `OrderNoService` 独立计数器生成（业务日分桶）
6. 逐行建 `OrderItem`，`unit_price` 取当时 SKU 价（**快照**），`subtotal = unit_price × quantity`
7. 清空购物车
8. 提交成功后额外发一次 `PUT /auth/profile` 回写收货信息（**失败只 `console.warn`，不影响下单**）

**默认值**：收货信息取自缓存的用户资料（`default_shipping_address`、`shipping_name`、`shipping_phone`、`default_payment_method`、`default_po_number`）。
📄 `CheckoutPage.vue:19-113,122-230`、`backend/apps/transactions/api/v1/checkout_views.py:24-120`

> ⚠️ **币种硬编码**：下单时订单 `currency` 固定写 `'USD'`（`checkout_views.py:93`），
> 而 `SKU.currency` 支持 USD/CNY/EUR。当前库内 596 个 SKU 全为 USD、992 张订单全为 USD ⇒ 尚无错误数据，
> 但**只要上架一个非 USD 的 SKU，订单金额币种就会错**。详见第 11 章 #5。

### F3-5 查看订单列表

**页面** `/orders`（`OrderListPage.vue`）

| 元素 | 说明 |
|---|---|
| 表格列 | `Order #` / `Date` / `Status` / `Payment` / `Total` / 操作列 |
| 行点击 | 跳 `/orders/{id}` |
| 分页 | `total, prev, pager, next`；仅 `total > pageSize(20)` 时显示 |
| 空态 | `No orders yet` / `You have no orders yet.` |
| 加载失败 | 顶部 `ErrorBanner`：`Couldn't load orders.` |

**数据范围**：只能看到自己的订单（`get_queryset` 按 `user` 收窄）。
📄 `OrderListPage.vue:11,16,39-108`

### F3-6 订单详情 + 报价应答

**页面** `/orders/:id`（`OrderDetailPage.vue`）

**页面分区**：头部（订单号 + 下单日期 + 状态徽章）→ **报价操作条（仅 `status === 'quoted'`）** → `Items` 表 + 合计 → `Payment` → `Shipping Address` → `Invoice`（有则）→ `Shipping`（有则）→ `Notes`（有则）

| 元素 | 文案（原文） | 请求 | 结果 |
|---|---|---|---|
| 接受报价 | `Accept Quote` | `POST /orders/{id}/confirm-quote/` body `{action:'accept'}` | 重拉详情 |
| 拒绝报价 | `Reject Quote` | 同上 `{action:'reject'}` | 重拉详情 |
| 失败 | — | — | ⚠️ **用原生 `alert()`** 弹后端 message 或 `Action failed` |

**报价操作条提示原文**：`A quote has been provided for this order. Please review and respond.`

**明细表列**：`Product` / `SKU` / `Qty` / `Unit Price` / `Subtotal`
**Payment 区字段**：`Method` / `PO Number` / `Terms` / `Due Date`
**Invoice 区字段**：`Invoice #` / `Status` / `Due Date` / `Amount`
**Shipping 区字段**：`Carrier` / `Tracking #` / `Shipped`

**权限**：`confirm-quote` 是 `IsAuthenticated` ⇒ 任何登录用户都能调；隔离靠 queryset（只能操作自己的订单）。
📄 `OrderDetailPage.vue:13,28-34,41-180`

### F3-7 提交 PO（客户门户的核心动作）

**页面** `/po/submit`（`views/po/PoSubmit.vue`）

**页面分区**：页头（含 `Order ID` 输入 + `Load from Order`）→ 顶部成功条 → `PO Information` → `Ship-to` → `Bill-to` → `PO Attachments` → `Line Items` 表格 → `Estimated Total` → `Submit PO`

| 步 | 操作 | 元素（原文） | 请求 |
|---|---|---|---|
| 0（可选） | 从历史订单载入 | 输入 `Order ID` → 点 `Load from Order` | `GET /orders/{id}/` ⇒ 预填表单与明细 |
| 1 | 填 PO 信息 | `PO Number（可选）` / `Quote / Reference #（可选）`（下拉选项来自 `GET /quotes/`）/ `Grant / Sponsor Code` / `Shipping Method`（`Ambient`/`Cold Pack`/`Dry Ice`/`Blue Ice`）/ `Requested Delivery Date`（原生 `min=今天`，过去日期被浏览器拦） | — |
| 2 | 填收货 | `Recipient Name` / `Phone` / `Address` / `Email` | — |
| 3 | 填账单 | `Billing Name` / `Billing Address` | — |
| 4 | 传附件 | `Drag & drop or click to upload (PDF / PNG / JPEG, ≤10MB)` | ⚠️ **仅 `accept` 属性过滤，无大小/类型 JS 校验**；服务端会校验（10MB + MIME 白名单） |
| 5 | 加明细 | `+ Add Line Item`；每行：`Product`（搜索框，≥2 字符触发 `GET /products/?search=&page_size=8`）→ 选产品（`GET /products/{id}/detail` 载入 SKU 下拉）→ 选 `SKU`（自动填单价）→ `Qty` → `Unit Price` | — |
| 6 | 提交 | `Submit PO`（提交中 `Submitting…`） | `POST /orders/po/`（无附件走 JSON，有附件走 multipart） |

**前端校验（点击提交时 `alert`）**：
- 明细为空 ⇒ `Add at least one line item.`
- 任一行缺 SKU / 数量 / 单价 ⇒ `Each line item requires a SKU, quantity and unit price.`

**成功**：顶部条 `PO submitted successfully. Order No: {order_no}` + `View My Orders` 链接
**明细表列**：`Product` / `SKU` / `Qty` / `Unit Price` / `Subtotal` / 删除列
**空态**：`No line items yet.`

**服务端行为（`PoSubmissionService.submit`）**：
1. PO 号去空白；**空 ⇒ 存 `NULL`**（允许"无 PO 号"的多张订单共存，靠 `uniq_order_po_number_nonempty` 条件唯一约束）
2. 建 `Order`，初始状态 **`po_received`**
3. 逐行按 **SKU 现价**覆盖客户端单价（`services.py:141`，注释明确"客户端提交不可信"）
4. 汇总写 `subtotal` / `grand_total`；`tax_total` 恒 0
5. 存附件（PDF/PNG/JPEG，≤10MB，双校验）
6. 写 `StatusLog` + 入队通知邮件

📄 `PoSubmit.vue:16-177,187-340`、`backend/apps/transactions/services.py:105-175`

### F3-8 查看 PO 单

**页面** `/po/orders`（`PoOrderList.vue`）

| 元素 | 说明 |
|---|---|
| 状态下拉 | 10 个主状态 + `optgroup Historical / Quote states` 6 个历史状态 |
| 表格列 | `Order No` / `PO Number` / `Status` / `Items` / `Total` / `Created` / 操作列 |
| `View` | 跳 `/po/orders/{id}` |
| `Re-order` | 跳 `/po/submit?reorder={id}` |
| `+ New PO` | 跳 `/po/submit` |
| 空态 | `No purchase orders found.` |

**数据范围**：只能看自己的（`GET /orders/` 按用户收窄）。
📄 `PoOrderList.vue:16-33,40-98`

### F3-9 PO 单详情与下载

**页面** `/po/orders/:id`（`PoOrderDetail.vue`）

**区块**：页头（订单号 + `PO {po_number} · Placed {date}` + 状态徽章）→ `Order Information` → `Addresses`（Ship-to / Bill-to）→ `Line Items` + **RUO 声明** + 合计 → `Invoice`（有则）→ `Shipments`（有则，含每批明细表与 `Track Package` 外链）→ `PO Attachments`（有则）→ `Status Timeline`

| 元素 | 文案（原文） | 请求 |
|---|---|---|
| 下载发票 | `Download PDF` | `GET /invoices/{id}/pdf/`（blob） |
| 物流跟踪 | `Track Package` | 外链 `tracking_url`，无则不渲染 |
| 下载附件 | `↓` | `GET /orders/attachments/{id}/download/` |

**RUO 声明原文**：`For Research Use Only. Not for use in diagnostic or therapeutic procedures.`
**空态**：`No timeline events yet.`；缺值统一显示 `—`
📄 `PoOrderDetail.vue:23,41-186`

### F3-10 地址簿 CRUD

**页面** `/po/addresses`（`PoAddressList.vue`）

| 操作 | 按钮（原文） | 请求 |
|---|---|---|
| 新建 | `+ New Address` → 填表 → `Save` | `POST /addresses/` |
| 编辑 | `Edit` → 改 → `Save` | `PUT /addresses/{id}/` |
| 删除 | `Delete` → 原生 `confirm('Delete this address?')` | `DELETE /addresses/{id}/` |
| 取消 | `Cancel` | — |

**表单字段**：`Type`(`Bill-to`/`Ship-to`/`Other`，默认 shipping) / `Country`(默认 US) / `Attention` / `Phone` / `Address Line 1` / `Address Line 2` / `City` / `State` / `Postal Code` / `Default for type`(checkbox)。
**字段全部非必填**（前端无校验）。
**表格列**：`Type` / `Attention` / `Address` / `Country` / 操作列
**空态**：`No addresses yet.`

**权限与隔离（重要）**：
- 权限类 `AddressPermission`：**登录即可写**（2026-10-21 从"采购或管理员"放开，因为 `/po/addresses` 是客户页）
- 行级隔离在**三处**：`get_queryset` 按 `organization_id` 收窄（无机构返回 `.none()`）→ `create()` 强制写入本人机构 → `update/destroy` 走 `get_object()` 必然经过第一处
- ⇒ 实际语义是「**只能改自己机构那一小撮行**」，同机构成员可互改
- ⚠️ 无机构用户：`create` 返回结构化 400 `NO_ORGANIZATION`；`update/destroy` 自然 404

📄 `PoAddressList.vue:13-62,67-146`、`backend/apps/accounts/api/v1/views.py:315-345`

### F3-11 下载中心

**页面** `/po/downloads`（`PoDownloadCenter.vue`）

进入即 `GET /orders/?page_size=100`，**只渲染有发票或有附件的行**（`:14-22` 过滤）。

| 表格列 | 内容 |
|---|---|
| `Order` | 订单号 |
| `Status` | 状态 |
| `Invoice` | `Invoice PDF` 下载按钮 |
| `PO Attachments` | `PO {id}` 逐个下载 |
| `Actions` | — |

**空态**：`No downloadable documents yet.`
📄 `PoDownloadCenter.vue:12-67`

### F3-12 再次订购

**页面** `/po/reorder`（`PoReorder.vue`）—— 固定 `status=completed`（`:14`），只列已完成订单，点 `Re-order` 跳 `/po/submit?reorder={id}`。

**空态**：`No completed orders available to re-order.`
⚠️ 行选中样式存在但**无任何赋值逻辑**（`selectedId` 从未被写入）⇒ 选中高亮永不出现（不影响功能）。
📄 `PoReorder.vue:12-47`

### F3-13 收藏夹

**页面** `/wishlist`（`WishlistPage.vue`），**无守卫**（匿名可进，页内提示登录）

| 状态 | 表现 |
|---|---|
| 未登录 | `请先登录后使用收藏夹` + `Sign In`(跳 `/login?redirect=/wishlist`) / `Register` |
| 已登录空 | `还没有收藏任何产品` / `在产品详情页点击「收藏」，就能把产品存到这里。` |
| 已登录有数据 | 产品网格 + 每卡 `移除`；顶部件数 + `清空收藏` |
| 加载失败 | `收藏夹加载失败` + `重试` |

**请求**：`GET /wishlist/`（空则自动 `POST /wishlist/` 建空夹）；移除/清空走 `PATCH /wishlist/{id}/`（读-改-写 `product_ids`）。
**收藏入口**：只在产品详情页（F1-3 的 `收藏` 按钮）。
📄 `WishlistPage.vue:43-103,107-166`

## 3.3 researcher 做不到的事

| 想做的事 | 结果 | 原因 |
|---|---|---|
| 进 `/workspace`、`/ops/*` | 跳 `/` | `isInternal` 为假 |
| 新建/编辑产品、知识实体 | 403 | `IsAdminOrReadOnly` 写要 `is_staff` |
| 看 COA/SDS 审核台 | 403 | `IsStaffUser` |
| 看全库订单 | 看不到（403 或仅自己的） | `/admin/orders/` 是 `IsAdminUser`；`/orders/` 按用户收窄 |
| 改自己的角色 | 不能 | `ProfileUpdateSerializer` 白名单不含 `role`（已核，无自助提权） |
| 改密码 | ⚠️ 假成功 | 前端无后端调用 |

---

# 第 4 章 researcher + `is_org_admin`（机构管理员）

## 4.1 核心结论（先说最重要的一句）

> **`is_org_admin` 对权限零影响。** 该身份的**页面可达性、API 权限、可用写操作**与第 3 章的普通 researcher **逐项完全相同**（实测：读 123/132、写 43/203，一模一样）。

**唯一可见的差别**：`/settings` → `Account` 面板多显示一个 `Admin` 徽章（`SettingsPage.vue:564` 的 `v-if="authStore.isOrgAdmin"`）。

## 4.2 证据（三重）

| 证据 | 内容 |
|---|---|
| 1. 探针实测 | 8 身份求值中，`org_admin` 与 `researcher` 的 335 个端点判定**逐格相同** |
| 2. 后端 grep | `is_org_admin` 全仓仅 4 处，**无一是权限判据**：`models.py:87`（字段定义）、`admin.py:37,38,43`（Django admin 展示/筛选）、`serializers.py:217,237,247,269`（注册/加入机构时写入 + 序列化输出）、`views.py:308`（建机构时置 True） |
| 3. 前端 grep | 仅 `stores/auth.js:26` 取字段 + `SettingsPage.vue:564` 显示徽章，无任何条件渲染用于控制功能 |

## 4.3 该身份怎么产生

| 路径 | 行为 | 代码 |
|---|---|---|
| 注册时选 `Create New` 建机构 | 创建者 `organization` = 新机构，`is_org_admin = True` | `accounts/api/v1/views.py:305-310` |
| 注册时 `Join Existing` | 加入者 `is_org_admin = False`（有测试守护：`test_membership_guard.py:120` 断言"join 进来的人不该自动成为机构管理员"） | `serializers.py:237` |
| Django admin 手改 | 可直接置 true/false | `admin.py:43` |

## 4.4 机构字段实际影响什么

| 字段 | 影响 |
|---|---|
| `user.organization` | ✅ **影响很大**：地址簿按机构隔离；订单归属机构；`/organizations/manage/` 的按机构查单 |
| `organization.tax_exempt_id` | ✅ 影响开票免税判定（当前税恒 0，故无实际金额影响） |
| `user.is_org_admin` | ❌ **无影响** |

## 4.5 所以本章的操作流程

**与第 3 章完全相同，不重复。** 只追加一条：

### F4-1 确认自己是机构管理员（唯一的实际用法）

| 步 | 操作 | 表现 |
|---|---|---|
| 1 | 进 `/settings` | — |
| 2 | 切到 `Account` Tab | 若 `is_org_admin=true`，`Organization Admin` 行显示 `Admin` 徽章 |
| 3 | — | **到此为止**：没有任何后续管理动作可用（不能改机构信息、不能管成员、不能审地址） |

> 若业务上期望"机构管理员可管理本机构成员/地址/订单"，**当前实现不提供**。这是第 11 章列的功能缺口 #3。

---

# 第 5 章 procurement（采购经理，`is_staff = false`）

## 5.1 身份与边界（这一章是全站最容易踩坑的地方）

| 项 | 值 |
|---|---|
| `role` | `procurement` |
| `is_staff` | **false** ⇒ 231 个 `is_staff` 系端点**全拒** |
| 产生方式 | **注册时拿不到**（三张身份卡都发 `researcher`）；只能由内部在 Django admin 授予 |
| 能进页面 | 19 个内部台**全部能进**（`isInternal` 认 `role∈(procurement,admin)`） |
| 读端点 | 128/132 |
| 写端点 | **54/203** |
| 登录后落点 | `/workspace` |

### 19 个内部页对采购的真实可用性（实测）

| 判定 | 页数 | 含义 |
|---|---|---|
| ✅ **正常** | **7** | 全部请求不会被 403 挡 |
| ⚠️ **只读**（能看不能改） | **9** | 页面能打开、数据能加载，但写操作 403 |
| ❌ **空白**（进去就没数据） | **3** | 首屏读请求即 403 |

| 页面 | 判定 | 具体表现 |
|---|---|---|
| `/ops/orders`（订单管理） | ❌ **空白** | `GET /admin/orders/` ← `IsAdminUser` ⇒ 403。列表 0 行 |
| `/ops/orders/:id`（订单详情） | ❌ **空白** | `GET /admin/orders/:id/` ⇒ 403 |
| `/workspace/verified`（审核台） | ❌ **空白** | `GET /verified/` ← `IsStaffUser` ⇒ 403 |
| `/workspace`（首页统计） | ⚠️ 只读 | `GET /admin/dashboard-stats/` ⇒ 403，统计卡无数据；「最近更新」表正常 |
| `/workspace/products` | ⚠️ 只读 | 读 5/5 正常；**写 0/7**（归档/恢复/停用/删除/批量全 403） |
| `/workspace/products/*/edit` | ⚠️ 只读 | 读 10/10 正常；**写 0/21**（保存/新建/Word 解析/SEO/AI/COA/SDS 全 403） |
| `/workspace/goals` | ⚠️ 只读 | 写 0/2 |
| `/workspace/applications` | ⚠️ 只读 | 写 0/2 |
| `/workspace/methods` | ⚠️ 只读 | 写 0/2 |
| `/workspace/protocols` | ⚠️ 只读 | 写 0/2 |
| `/workspace/references` | ⚠️ 只读 | 写 0/2 |
| `/workspace/knowledge-intake` | ⚠️ 只读 | `POST /knowledge-intake/` ← `IsAdminUser` ⇒ 403 |
| `/ops/po/review` | ⚠️ 只读（1 个死按钮） | 审批/拒绝可通；`Assign Rep` ← `IsAdmin` ⇒ 403 |
| `/ops/po/shipments` | ✅ | 建发货、标记发出、标记送达全通 |
| `/ops/po/invoicing` | ✅ | 开票、记录收款全通 |
| `/ops/po/ar` | ✅ | AR 账龄可看 |
| `/ops/po/organizations` | ✅ | 机构列表 + 按机构查单可看 |
| `/ops/inventory` | ✅ | 入库、盘点调整、流水全通 |

> ⚠️ **没有一处 UI 会告诉他"你没权限"**：前端 19 个内部页里只有 1 处角色条件渲染（`ProductsPage.vue:547` 的批量 AI 按钮），
> 其余按钮对所有能进页面的人都显示。采购点了就静默失败或弹一个通用错误。

## 5.2 操作流程（能用的那条线）

采购的实际工作流是**履约**：审批 PO → 发货 → 开票 → 收款 → 看应收。这条线全部走 `IsProcurementOrAdmin`，**采购完全够用**。

### F5-1 审批 PO（`/ops/po/review`）

**进入即** `GET /orders/?status=po_received`（服务端固定筛选，页面无筛选器）

| 步 | 操作 | 元素（原文） | 请求 | 结果 |
|---|---|---|---|---|
| 1 | 看队列 | 头部 `Order Review Desk` + `{n} PO(s) awaiting review` | — | 每单一张卡：单号、状态徽章、PO 号、金额、`Grant Code`、`Shipping Method`、`Ship-to` |
| 2 | 看明细 | `View Items` / `Hide Items` | 首次展开 `GET /orders/{id}/` | 明细表：`SKU` / `Pack` / `Qty` / `Available` / `Status`；缺货行高亮 + 徽章 `缺货 {n}` 或 `可满足` |
| 3a | 通过 | `Approve` | `POST /orders/{id}/approve/` | 刷新列表，状态 → `confirmed` |
| 3b | 拒绝 | 填 `Reject reason`（placeholder `Reject reason`）→ `Reject` | `POST /orders/{id}/reject/` body `{reason}` | 刷新 |
| 3c | 指派销售 | 填 `Rep ID`（placeholder `Rep ID`）→ `Assign Rep` | `POST /orders/{id}/assign-rep/` | ❌ **403**（`IsAdmin`） |
| 4 | 刷新 | `Refresh` | `GET /orders/?status=po_received` | — |

⚠️ **本页 4 个按钮全部无 try/catch**（`PoReviewDesk.vue:34-58`）⇒ 失败时**没有任何 UI 反馈**：
- `Assign Rep` 的 rep 为空 ⇒ **静默 return**，看起来像点了没反应
- 审批失败 ⇒ Promise rejection 未捕获，页面无提示

**空态**：`No orders pending review.`

### F5-2 发货（`/ops/po/shipments`）

**进入即** `GET /orders/?page_size=200`，客户端过滤 `confirmed` / `in_production` / `shipped`

| 步 | 操作 | 元素（原文） | 请求 |
|---|---|---|---|
| 1 | 选订单 | 左表点单号（列 `Order` / `Status` / `Items`） | `GET /orders/{id}/`，右侧渲染并预填明细（数量默认 = 订单数量） |
| 2 | 填发货单 | `Carrier` / `Tracking #` / `Tracking URL` / `Est. Delivery`（空串自动转 null）/ 每行 `Qty to Ship` | — |
| 3 | 建单 | `Create Shipment` | `POST /orders/{id}/shipments/` |
| 4 | 标记发出 | `Mark Shipped`（仅 `status !== shipped && !== delivered` 时显示） | `POST /shipments/{id}/mark-shipped/` ⇒ 订单 → `shipped` |
| 5 | 标记送达 | 填 `Received by`（placeholder `Received by`）→ `Mark Delivered`（仅 `status === shipped` 时显示） | `POST /shipments/{id}/mark-delivered/` body `{received_by}` ⇒ 订单 → `delivered` |

**支持多批发货**：同一订单可建多个发货单（`Shipments` 列表逐个操作）。
⚠️ 右侧 `New Shipment` 表单**不区分订单状态**（`confirmed`/`in_production`/`shipped` 都显示同一套表单），无"仅特定状态可建单"判断。
⚠️ 全部操作无 try/catch，失败静默。

**空态**：`No orders to ship.` / `No shipments yet.`

### F5-3 开票与收款（`/ops/po/invoicing`）

**进入即** `GET /orders/?page_size=200`，客户端过滤 `delivered` / `invoiced`

| 步 | 操作 | 元素（原文） | 请求 |
|---|---|---|---|
| 1 | 选订单 | 左表点单号（列 `Order` / `Status` / `Total`） | `GET /orders/{id}/` |
| 2 | 开票（未开票时） | 选付款条件（`Net 30`/`Net 45`/`Net 60`，默认 NET30）→ `Issue Invoice` | `POST /orders/{id}/invoice/` body `{payment_terms}` ⇒ 订单 → `invoiced` |
| 3 | 记录收款（已开票时） | `Amount`（placeholder `0.00`）/ `Method`（`Online`/`Wire Transfer`/`Check`）/ `Reference` → `Record Payment` | `POST /invoices/{id}/pay/` body `{amount, method, reference}` |

⚠️ **`Amount` 必须有值**，否则**静默 return**（`PoInvoicingDesk.vue:53`），无任何提示。
⚠️ **全站没有"标记已付/核销"按钮**：只有"记录收款"，订单状态不会因为收款自动变 `paid`。
- `POST /admin/invoices/{id}/verify-payment/` 端点存在（`IsAdminUser`），但**前端 0 引用**
- `api/orders.js:108` 的 `verifyPayment` **全站无调用点**

⇒ **订单从 `invoiced` 到 `paid` 没有产品路径**（只能靠 Django admin 或直接调 API）。

### F5-4 看应收账龄（`/ops/po/ar`）

**进入即** `GET /ar/aging/`。四个账龄卡：`Current` / `1–30 Days` / `31–60 Days` / `90+ Days`，每卡显示 `{count} invoices` + 金额；底部 `Total Outstanding`。
⚠️ 无 try/catch、**无空态**：接口失败时页面只剩头部，无任何文案。

### F5-5 机构管理（`/ops/po/organizations`）

**进入即** `GET /organizations/manage/?page_size=100`。左表 `Name`/`Type`/`Country`；点机构 ⇒ `GET /orders/?organization_id={id}&page_size=100` 在右表显示该机构订单（`Order`/`Status`/`Total`/`Created`）。
⚠️ 副标题写 "View organizations, their addresses and order history."，但**模板里没有任何地址字段** —— 与描述不符。

### F5-6 库存管理（`/ops/inventory`）

**进入即** `GET /inventory/`

**三种操作**：

| 操作 | 入口 | 字段 | 请求 |
|---|---|---|---|
| **入库** | 行内 `Receipt` 或头部 `+ New Stock Row` → 弹窗 `Confirm Receipt` | `SKU`* / `Location`(`Main Warehouse`/`EU Warehouse`/`US Warehouse`) / `Quantity`*(min=1) / `Reason`*(placeholder `e.g. PO-1234 到货 / 盘盈`) | `POST /inventory/receipt/` body `{sku_id, location, quantity, batch_id:null, reason}` |
| **盘点调整** | 行内 `Adjust` → 弹窗 `Confirm Adjust` | `Delta`(±) / `Reason`*(placeholder `e.g. 盘点差异 -2`) | `POST /inventory/{id}/adjust/` body `{delta, reason}` |
| **看流水** | 行内 `History` → 弹窗 → `Close` | 只读 | `GET /inventory/{id}/` |

**筛选**：`Search`（placeholder `SKU code or product name`）/ `Location` / `Low stock ≤`（默认阈值 10）→ `Apply`
**表格列**：`SKU` / `Product` / `Lot` / `Location` / `Available` / `Allocated` / `On hand` / `Actions`
**低库存高亮**：`available <= 10` 行加 `po-row-low`
**流水弹窗两张表**：`Current reserved allocations`（`Order item` / `Qty` / `Status`）、`Movements（最近 50）`（`Kind` / `ΔAvail` / `ΔAlloc` / `Reason` / `At`）

⚠️ **两个必须知道的设计事实**：

1. **库存台的数量与商品页的"现货"徽章完全无关。**
   - 商品页显示的 `in_stock`/`limited`/`preorder`/`out_of_stock` 来自 `SKU.inventory_status`（一个手工字段，默认 `in_stock`）
   - 库存台改的是 `Inventory.available/allocated`（另一个表）
   - `apps/inventory/*` **从不写** `SKU.inventory_status`（grep 已核，0 命中）
   - ⇒ **入库 100 支不会让商品从"缺货"变"现货"**；反之改徽章也不会改数量

2. **`SKU.inventory_status` 在前端没有任何输入控件。**
   `ProductEditPage` 的 SKU 表只有 `Code`/`Pack Size`/`Pack Unit`/`Concn`/`Conc Unit`/`Price`/`Curr`/`Default`（`ProductEditPage.vue:2261`），
   保存时原样回传（`inventory_status: s.inventory_status || 'in_stock'`，`:408`）⇒ **新 SKU 恒为 `in_stock`，老 SKU 无法通过产品界改**。

⚠️ 入库/调整的前端必填校验全部是静默 `return`（`:260,282`），无错误文案。
⚠️ `batch_id` 恒为 `null`（`:265`），界面无批次入口。

## 5.3 procurement 做不到的事

| 想做的事 | 结果 | 原因 |
|---|---|---|
| 打开订单管理页看全库订单 | ❌ 空白（403） | `/admin/orders/` 是 `IsAdminUser` |
| 审核 COA/SDS / verified | ❌ 空白（403） | `IsStaffUser` |
| 新建/编辑产品、知识实体 | ❌ 403 | `IsAdminOrReadOnly` 写要 `is_staff` |
| 指派销售 | ❌ 403（按钮却在） | `IsAdmin` |
| 用 AI 批量校验/批量文献 | ❌ 按钮根本不渲染 | `canBatchAi = Boolean(auth.isStaff)` |
| 把订单从 `invoiced` 推到 `paid` | ❌ 全站无入口 | 无"标记已付"按钮 |

---

# 第 6 章 admin（`role='admin'`，`is_staff=false`）

## 6.1 与第 5 章的差异只有一处

| 项 | procurement | **admin(role)** |
|---|---|---|
| 读端点 | 128/132 | **128/132**（同） |
| 写端点 | 54/203 | **55/203**（多 1 个） |
| 差的这 1 个 | — | `POST /orders/{id}/assign-rep/`（`IsAdmin`） |
| 19 页可用性 | 3 空白 / 9 只读 / 7 正常 | **3 空白 / 9 只读 / 7 正常**（`/ops/po/review` 从"只读"变"正常"） |

> **结论：`role='admin'` 相对 `procurement` 的全部额外能力，就是"指派销售"这一个按钮。**
> 它并不能改产品、不能审 COA、不能看 `/admin/orders/` —— 因为那些只认 `is_staff`。
> 这就是第 11 章 #1 说的"断层"：**一个叫 admin 的角色，实际权限比名字暗示的少得多。**

## 6.2 F6-1 指派销售（本角色唯一专属流程）

**页面** `/ops/po/review`（`PoReviewDesk.vue`）

| 步 | 操作 | 元素（原文） | 请求 |
|---|---|---|---|
| 1 | 进入 | — | `GET /orders/?status=po_received` |
| 2 | 找目标单 | 每卡的操作行 | — |
| 3 | 填销售 ID | 输入框 placeholder `Rep ID`（宽度 100px） | — |
| 4 | 提交 | `Assign Rep` | `POST /orders/{id}/assign-rep/` body `{rep_id}` ⇒ 写入订单 `assigned_rep` |

⚠️ 三点注意：
- **按钮对所有内部人渲染**，没有角色条件 ⇒ 采购点它必然 403（死按钮）
- rep 为空时**静默 return**，无提示
- 失败无 try/catch，无 UI 反馈

## 6.3 admin(role) 做不到的事

**与 5.3 完全相同**，唯一例外是 assign-rep 可用。

---

# 第 7 章 staff（内部员工，`is_staff = true`）

## 7.1 身份与边界

| 项 | 值 |
|---|---|
| `is_staff` | true |
| 产生方式 | 仅 Django admin 勾选 / `createsuperuser` |
| 能进页面 | 23 公开 + 10 客户 + **19 内部 = 全部 52 页** |
| 读端点 | **132/132（全通）** |
| 写端点 | **201/203**（只有 2 个 `IsSuperUser` 过不去：产品 hard-delete） |
| 登录后落点 | `/workspace` |

**这是设计意图中的"内部员工"**：内容运营（产品/知识实体/合规文档）+ 交易运营（订单/发货/开票/收款）全部可做。

## 7.2 工作台导航

**外壳** `/workspace`（`AdminLayout.vue`）—— 左侧栏分三组：

| 组 | 菜单项（原文文案） | 跳转 |
|---|---|---|
| （品牌） | `SciReAgent` | `/workspace` |
| `Overview` | `Dashboard` | `/workspace` |
| `Products` | `Products` | `/workspace/products` |
| `Knowledge` | `Research Goals` / `Applications` / `Methods` / `Protocols` / `References` / `Verified Applicability` / `Knowledge Intake` | 对应 7 个页面 |
| 底部 | `Back to Site` | `/` |

⚠️ 侧栏**不按角色渲染**（无 `v-if`）⇒ 采购/admin(role) 登录后看到同样 7 个 Knowledge 菜单，
点 `Verified Applicability` 会得到一个空表格（403）；点 `Knowledge Intake` 能看能填但保存必 403。

## 7.3 产品新建（全站最复杂的页面）

**页面** `/workspace/products/new`（`ProductEditPage.vue`，约 1600 行）
**进入即发 5 个请求**：`GET /product-classes/?page_size=500`、`GET /research-goals/?page_size=200`、`GET /applications/?page_size=200`、`GET /methods/?page_size=200&origin=imported`、`GET /protocols/?page_size=500`
（新建态 `loadCategoryOptions` **被调用了两次**，`:1179` 与 `:1636`）

### 页面结构（11 个区块，自上而下）

| # | 区块 | 内容 |
|---|---|---|
| — | 已发布但不完整横幅 | 仅编辑态且 `status==='active'` 且缺推荐字段时出现 |
| — | **Completeness bar** | `✓ Complete` 或 `✗ Incomplete — missing: {项}` |
| — | 生命周期步进器 | `Product` / `SDS` / `COA` 三条轨（仅编辑态显示） |
| — | 页面身份行 | `Editing {catalog_no}` 或 `New Product` + 状态徽标 |
| 0 | `📄 Word Import (optional)` | 上传 .docx 自动填表 |
| 0 | `🤖 AI AUTO MATCH` | 一站式补全（化学/文献/协议/供应商/Bioz） |
| 1 | `1. Basic Information` | Name* / Catalog No* / CAS / Synonyms / Slug / Status |
| 2 | `2. Chemical Structure` | SMILES / InChI / Formula / Molecular Weight + 结构预览 |
| 3 | `3. Scientific Parameters` | Purity / Concentration / Storage / Shipping / Lead Time / Shelf Life / Handling Notes |
| 4 | `4. Category` | 三级类目 cascader* |
| 5 | `5. Knowledge Links` | Methods / Protocols / Research Goals / Applications chips |
| 6 | `6. Description` | Overview（≤5000）/ Usage (vendor-claimed)（≤5000） |
| 7 | `7. SKUs` | SKU 表 + `+ Add SKU` |
| 8 | `8. SEO` | SEO Title / SEO Description / `Auto-generate SEO` |
| 9 | `9. Compliance — COA & SDS` | SDS 版本列表、批次、COA |
| — | Actions | `Save Draft` / `Publish` |

### 7.3.1 完整性检查（Completeness bar）—— 产品能否上架的判定

**判定式**（`ProductEditPage.vue:297-300`）：
```
name && catalog_no && cas && smiles && product_class_id && skus.some(is_default)
```

| 显示项 | 缺失条件 | 行号 |
|---|---|---|
| `Name/Catalog No` | 任一为空 | `:303` |
| `CAS` | 为空 | `:304` |
| `SMILES` | 为空 | `:305` |
| `Category` | 未选到三级 | `:306` |
| `Default SKU` | 无 `is_default` 的 SKU | `:307` |

**保存时的红框提示**：另一套 `REQUIRED_FIELDS`（`:41-47`）+ `collectMissing`（`:48-57`）把上面 5 项拆开，
缺哪个就给哪个字段加红框（Name `:2020`、Catalog No `:2024`、SMILES `:2047`、Category `:2105-2109`、Default SKU `:2287`），
并提示 `{n} required fields unfilled (marked red); save/publish kept available`。

> ⚠️ **完整性条上的缺失项不可点击**（纯 `<span>`，无 `@click`、无 `scrollIntoView`）。
> `id="smiles-missing"`（`:2047`）定义了但全文件无引用 —— 想做"点击跳转到缺失字段"的功能没做完。

**推荐项（不阻断，但发布时会提醒）**：`CAS`、`SMILES`、`Formula`、`Molecular Weight`、`Knowledge Links`、`SEO metadata`。

### 7.3.2 Word 文档导入

| 元素 | 文案（原文） | 请求 | 行为 |
|---|---|---|---|
| 上传 | `Choose .docx File` | `POST /products/parse-word/`（multipart） | 解析成功 ⇒ **直接写入表单**（无"采纳"按钮），含 SKU 重建与结构图 |
| 结果提示 | `✓ {n} fields extracted — review before publishing` | — | — |

**返回可填字段**：`product_name`、`catalog_number`、`cas`、`formula`、`molecular_weight`、`purity`、`concentration`、`storage`、`shipping`、`synonyms`、`description`、`smiles`、`structure_image_base64`、`skus[]`、`fields_found`
⚠️ 导入**不覆盖已有值以外的判断**，是"整套重建"式写入 ⇒ 建议在空白新建页用，不要在已有数据的编辑页用。

### 7.3.3 AI AUTO MATCH（一站式 enrich）

| 元素 | 文案（原文） | 请求 |
|---|---|---|
| 主按钮 | `AI AUTO MATCH "{name\|\|cas\|\|smiles\|\|inchi}"`（运行中 `Searching & matching…`） | `POST /products/enrich/`，body 含 `product_name/cas/smiles/inchi/formula/molecular_weight/product_id/protocol_top_k`（新产品页传 50） |
| 采纳全部 | `Apply All to Form` | 无（纯前端写表单） |
| 候选化合物 | `⚠ 自动匹配未经验证（{confidence}）— 必须手动选择正确的化合物，请勿直接 Apply All。` + 每行 `Use this` | 无 |

**返回五块**：`chemical`（化学属性）、`literature`（文献）、`protocols`（协议候选）、`jena`（供应商规格）、`bioz`（Bioz 文献证据）

**采纳规则（这是最容易出错的地方）**：

| 来源 | 何时自动写入 | 何时必须手动 |
|---|---|---|
| 化学属性 | **仅当 `chemAutoVerified` 为真**才自动写入 | 否则提示 `化学属性未经验证，未自动套用 — 请从候选中选择或手动填写`，需点某候选的 `Use this` |
| 供应商规格（Jena 等） | 点 `Apply from {vendor}` 只填**空字段**（`purity`/`storage`/`shipping`/`shelf_life`/`CAS`/`category_l1`） | 模糊匹配标 `参考`，提示 `参考匹配：仅手动采纳，勿盲选` |
| 文献（Bioz） | 点 `Adopt`/`Adopt all ({n})` ⇒ `POST /products/{id}/adopt-bioz-refs/` **落库** | **必须先保存产品**，否则提示 `请先保存产品，再采纳文献` |
| 协议候选 | 点 `🔽 Import to Knowledge Base` ⇒ `POST /products/import-protocol/` 落库 | 点 `＋ 关联` 只改本地，保存时随 `PUT` 落库 |

**候选化合物拒写条件**：`formula_mismatch` / `mw_mismatch` / `confidence === 'rejected'` ⇒ 点了 `Use this` 也不写，并提示原因。
**结构式渲染**：无按钮，随 `form.smiles` 自动触发 `POST /products/render-structure/`，失败回退 PubChem CID → PubChem SMILES → Cactus。

⚠️ **已知解析偏差**：父级传给 `StructureViewer` 的 `:pubchem-cid` 取 `pubchemEnrichResult?.found ? .cid : null`（`:2061`），但新返回结构里 `found`/`cid` 在 `.chemical` 下 ⇒ **该 prop 恒为 null**（不影响主渲染链，因为优先用 SMILES）。

### 7.3.4 保存 vs 发布（两个动作的区别）

| 动作 | 按钮（原文） | 请求 | 状态字段 | 成功提示（原文） |
|---|---|---|---|---|
| **保存** | `Save Draft` | 编辑态 `PUT /products/{id}/`；新建态 `POST /products/` | **不改 status**，提交表单里 `Status` 下拉的当前值（`Draft`/`Active`/`Deprecated`/`Archived`） | `Draft saved`；新建 `Product saved. You can now generate SDS, COA, and SEO in section 9.` |
| **发布** | `Publish` → 确认框 `Confirm Publish` | 先置 `form.status='active'`，再走同一条 PUT/POST | `draft → active` | `Product published` / `Product created and published` |
| 回车提交 | — | 等同 `Save Draft` | 同保存 | 同保存 |

**保存时自动做的事**：
1. `applyVerifiedChemicalToForm()` —— 仅 `chemAutoVerified` 时填空字段
2. 若存在 enrich 结果 ⇒ `applyEnrichKnowledgeLinks()` —— 自动关联前 5 条协议
3. `sanitizeChoiceFields` —— 把不在枚举内的 `purity/concentration/storage/shipping/lead_time` 置空
4. `ensureSlug` —— 空则按 `catalog_no → name → product-{ts}` 生成
5. SKU 的 `pack_size`+`pack_unit`、`concentration`+`conc_unit` 合并成单字段
6. SKU code 为空则按 `{catalog_no}-{i+1}` 派生

**保存失败提示格式**：`Save failed: ` + 逐级降级（优先 `meta.error.message`，其次 `detail`，再次逐字段拼接，前缀 `HTTP {status} — `）

⚠️ **缺失必填不阻断保存**（只标红）—— 这是刻意的，但意味着**可以保存出"不完整"的产品**。
⚠️ **发布也不阻断**：只弹确认框列出缺失项。

### 7.3.5 知识与关联（Section 5）

| 区域 | 可做的操作 |
|---|---|
| Methods chips | 每个 chip：方法名链接（跳 `/methods/{id}`）+ `旧种子` 徽标（若有）+ `✕` 取消关联 |
| Protocols chips | 每个 chip：名称链接 + `row.tier_label` + `axisBadges` + `来源：{link_source_label}`；`✕` **仅对非服务端派生行可点**（派生行 disabled）；另有 `None（另有 N 条弱相关候选 — 点击右侧「弱相关」查看）` 提示 |
| Research Goals / Applications chips | chip 链接 + `✕` + 追加下拉 `Add Research Goal…` / `Add Application…` |
| 展开/收起 | `显示全部 (N)` / `收起` / `弱相关 (N) ▲` |
| 追加已有实体 | `— Link existing Method —` 下拉（远程搜索 `GET /methods/?search=`）+ `Link`；Protocol 同 |
| 快速新建 | `+ New Method` / `+ New Protocol` → 弹窗 → `Save & Link` ⇒ `POST /methods/` 或 `POST /protocols/`，新 id 自动关联 |

⚠️ **级联影响提示**（页面原文）：`⚠ Goals / Applications 是级联入口…` —— 选 Goal/Application 会连带引入其方法。
> **历史坑（操作时务必知道）**：`_sync_method_bridges` 是**先删后加**语义。改 Goal/Application 时若不显式带上 `method_ids`，
> 原有方法关联会被**真删**。保存前请确认 chip 区显示的关系与你预期一致。

### 7.3.6 SKU 表（Section 7）

| 列 | 控件 | 说明 |
|---|---|---|
| `Code` | 输入 | 空则保存时派生 `{catalog_no}-{i+1}` |
| `Pack Size` | 数字 | 与 `Pack Unit` 合并为 `"值 单位"` |
| `Pack Unit` | 下拉 `µg`/`mg`/`g`/`µL`/`mL`/`L` | — |
| `Concn` | 输入 | 与 `Conc Unit` 合并 |
| `Conc Unit` | 下拉 `mM`/`µM`/`M`/`mg/mL`/`µg/mL`/`%` | — |
| `Price` | 数字（step 0.01, min 0） | 默认 `0.00` |
| `Curr` | 下拉 `USD`/`CNY`/`EUR` | 默认 USD |
| `Default` | radio | 单选；第一行自动勾选 |
| 删除 | `✕` | — |
| 新增 | `+ Add SKU` | — |

**两条实时告警**：`⚠ Duplicate pack size + concentration combination detected`（按 `pack_size::concentration` 判重）、`⚠ Add at least one SKU and tick Default`。
⚠️ **SKU 表没有 `inventory_status`（现货/少量/预订/缺货）输入** ⇒ 见第 5 章 F5-6 的说明，新 SKU 恒为 `in_stock`。

### 7.3.7 合规文档（Section 9，COA & SDS）

**前置**：**必须先保存产品**。未保存时整段显示 `💡 Save the product first to enable SDS / COA generation. After saving, return here to generate compliance documents.`

**进入编辑态时发 3 个请求**：`GET /sds-revisions/?product_id=`、`GET /batches/?product_id=`、`GET /coas/?product_id=`

| 操作 | 按钮（原文） | 请求 | 前置/条件 | 成功提示 |
|---|---|---|---|---|
| 生成 SDS | `Generate SDS` | `POST /sds-revisions/generate/` body `{product_id}` | 需有 `CAS`/`SMILES`/`InChI` 之一；缺失时点击提示 `SDS needs a chemical identifier (CAS, SMILES, or InChI). Add one in section 2 “Chemical Structure” first.` | `SDS draft generated. Click “Approve & Publish SDS” to make it public.` |
| 审批发布 SDS | `Approve & Publish SDS` | `POST /sds-revisions/{id}/approve/` | 仅非 `is_current` 版本显示 | `SDS approved and published` |
| 撤回 SDS | `Withdraw` | `POST /sds-revisions/{id}/withdraw/` | 仅 `is_current` 版本显示 | `SDS withdrawn` |
| 预览 SDS | `Preview` | 无（前端弹层） | — | — |
| 下载 SDS | `Download` | `GET /sds-revisions/{id}/download/` | 仅 `pdf_path` 存在时显示 | 新窗口 |
| 建批次并生成 COA | `Generate COA` | `POST /coas/create-coa/` body `{sku_id, lot_number, produced_at, retest_at?}` | 仅该 SKU **无批次**时显示表单；`lot_number` 必填（缺 ⇒ `Enter a lot number`）、`produced_at` 必填（缺 ⇒ `Select a production date`） | `Batch + COA draft created. Click “Approve & Publish COA” to make it public.` |
| 录入 QC（展开） | `Enter measurements` | 无 | 仅 `coa.status === 'draft'` | 展开 9 项表单 |
| 保存 QC | `Save measurements` | `PUT /coas/{id}/qc-results/` | — | `COA measurements saved` |
| 审批发布 COA | `Approve & Publish COA` | `POST /coas/{id}/approve/` | 仅 `draft` | `COA approved and published` |
| 撤回 COA | `Withdraw` | `POST /coas/{id}/withdraw/` | 仅 `published` | `COA withdrawn (back to draft)` |
| 预览 / 下载 COA | `Preview` / `Download` | 下载走 `GET /coas/{id}/download/` | 下载需 `pdf_path` | — |

**QC 表 9 个字段**：`Appearance`、`Purity`、`Water content`、`Melting point`、`Specific rotation`、`Residual solvents`、`Heavy metals`、`NMR`、`LC-MS`（对应 payload 键 `appearance_result`/`purity_result`/`water_content_result`/`melting_point`/`specific_rotation`/`residual_solvents`/`heavy_metals`/`nmr_result`/`lcms_result`）
**新建批次字段**：`Lot number`（默认带入 SKU code）、`Production date`、`Retest date`
**SDS 卡展示**：`v{revision_no}`、`Currently published`/`Draft`、`Confidence: {High/Medium/Low/Very low}`、`Signal word:`、`GHS: {pictograms}`、`data_source_detail`
**COA 卡展示**：`Batch {lot_number}`、`Published`/`Draft`/`No COA`、`Doc: {doc_id}`、`Produced: {produced_at}`
**空态**：`No SDS versions yet.`、`This product has no batches yet.`、`No COA yet — COA is generated together when you create the batch above.`

**两条必须记住的语义**（页面自身说明句原文）：
> `“Publish” makes the product visible to the public. “Approve & Publish SDS / COA” makes the compliance document public.`

⇒ **产品上架 ≠ 合规文档公开**，这是两个独立动作。客户能在产品页看到 COA 图标，前提是该 COA `status=published`。

## 7.4 产品管理（列表页）

**页面** `/workspace/products`（`ProductsPage.vue`）
**进入即** `GET /products/?archived=1&page_size=500`（注意：请求名是"archived"，实际取回受控列表）

### 视图与筛选

| 控件 | 可选值（原文） |
|---|---|
| 视图 | `Products` / `Recycle Bin ({n})` |
| 状态筛选 | `All Status` / `Active` / `Draft` / `Deprecated` / `Unpublished` |
| 完整性筛选 | `All` / `Complete` / `Incomplete` / `No CAS` / `No SMILES` / `No Knowledge Link` / `No Category` |
| 排序 | 点表头：`Catalog No` / `Name` / `CAS` / `Status` / `Category` / `Knowledge Link`（纯前端排序，`Knowledge Link` 数值比较空值沉底） |
| 分页 | **无分页**；一次取 500 条，超出显示 `Showing the first {500} of {total} products — the list is truncated.` |

### 表格列

复选框 / `Catalog No` / `Name` / `CAS` / `Complete`（`✓` 或 `✗ {缺失项}`）/ `Status` / `Category` / `Knowledge Link`（`aggregate_relevance_score` 两位小数或 `—`）/ `Compliance`（`SDS✓`|`SDS—` + `COA {n}`）/ `Actions ▾`

### 单条操作（`Actions ▾` 菜单，按状态条件出现）

| 菜单项 | 可见条件 | 请求 | 结果 |
|---|---|---|---|
| `Edit` | 总是 | — | 跳编辑页 |
| `Unpublish` | `status` ∈ `active`/`draft` | `POST /products/{id}/archive/` | toast `Unpublished N products` |
| `Republish` | `status === 'archived'` | `PATCH /products/{id}/` `{status:'active'}` | toast `{name} republished` |
| `Discontinue` | `status !== 'deprecated'` | `PATCH /products/{id}/` `{status:'deprecated'}` | toast `{name} discontinued` |
| `Reopen` | `status === 'deprecated'` | `PATCH {status:'active'}` | 同上 |
| `Move to Recycle Bin` | 总是（在售视图） | `DELETE /products/{id}/`（软删，置 `archived=True`） | toast `Moved … to the recycle bin` |
| `Restore` | 回收站视图 | `POST /products/batch-restore/` | toast `Restored N products` |

> **"删除"实际是软删（回收站）**：`DELETE /products/{id}/` 置 `archived=True`，不物理删。可恢复。
> **物理删**只有 `POST /products/{id}/hard-delete/`（`IsSuperUser`），**前端无入口** ⇒ 见第 8 章。

### 批量操作

| 按钮（原文） | 条件 | 请求 | 说明 |
|---|---|---|---|
| `Batch Link` | 选中 ≥1 | 打开时拉 4 个下拉数据（goals/apps/methods/protocols）；确认后逐条 `PATCH /products/{pid}/` body `{method_ids, protocol_ids}` | 弹窗内 `Preview` 显示 `Will link N products, skip M (already linked).`（`Method *` 必选） |
| `🔬 Batch validate` | **`is_staff` 才渲染** | `POST /products/batch-validate/`，按 10 条分批 | 结果对话框逐条列出 |
| `📚 Batch literature` | **`is_staff` 才渲染** | `POST /products/batch-recommend-literature/` | 结果对话序列 `reference(s)` |
| `Batch archive` | 选中 ≥1 | 逐条 `POST /products/{id}/archive/` | toast `Unpublished N products` |
| `Batch delete` | 选中 ≥1 + 勾选确认框 | 逐条 `DELETE /products/{id}/` | 需勾 `I understand these products will be moved to the recycle bin` 才能提交 |
| `Restore selected` | 回收站视图 + 选中 | `POST /products/batch-restore/` | toast 带 `already active` / `not found` 附加 |

### 空态（4 种，按情境自动切换）

| 情境 | 标题 / 描述（原文） | 按钮 |
|---|---|---|
| 一个产品都没有 | `No products yet` / `Create your first product to get started.` | `+ New Product` |
| 回收站为空 | `Recycle bin is empty` / `Products you move to the recycle bin will appear here and can be restored at any time.` | — |
| 有产品但全在回收站 | `No products in the catalog` / `All {n} products are currently in the recycle bin. Storefront shows nothing until they are restored.` | `Go to Recycle Bin ({n})` |
| 筛选无结果 | `No products match the current filters` / `Try clearing the status / completeness filters.` | `Clear filters` |

> 📌 **当前生产状态对应第 3 种**：125 个产品全在回收站，前台可见 0 —— 空态文案已经把这个情形写清楚了。

## 7.5 知识实体 CRUD（5 个页面）

**五个页面结构高度一致**，差异只在字段：

| 页面 | 路径 | 列表列 | 对话框字段 | 分页大小 |
|---|---|---|---|---|
| Research Goals | `/workspace/goals` | `ID` / `Name` / `Summary` / `Status` / Edit | `Name` / `Summary` / `Curated Protocols`（多选远程搜索 `GET /protocols/?search=&page_size=50`） | 200 |
| Applications | `/workspace/applications` | 同上 | `Name` / `Summary` / `Research Goal`（下拉） | 200 |
| Methods | `/workspace/methods` | `ID` / `Name` / `Purpose` / `Status` / Edit | `Name` / `Purpose` / `Application`（下拉） | 200 |
| Protocols | `/workspace/protocols` | `ID` / `Name` / `Status` / Edit | `Name` / `Method`（单选，提交为 `methods:[id]`） | 500 |
| References | `/workspace/references` | `ID` / `Title` / `DOI/URL` / `Type` / Edit | `Title` / `URL` / `DOI` / `Citation` / `Source Type` | 200 |

**统一操作**：
| 操作 | 按钮 | 请求 |
|---|---|---|
| 新建 | `+ New Goal` / `+ New Application` / `+ New Method` / `+ New Protocol` / `+ New Reference` | `POST /{实体}/` |
| 编辑 | 行内 `Edit` | Goals/Methods/Protocols 会先拉详情（`GET /{实体}/{id}/`）预填；Apps/Refs 直接用行数据 | 
| 保存 | `Save`（保存中 `Saving...`） | `PUT /{实体}/{id}/` 或 `POST /{实体}/` |
| 取消 | `Cancel` | — |
| 失败 | — | toast `Save failed: {msg}` |

**`Source Type` 可选值**（References）：`Journal`/`Book`/`Patent`/`Thesis`/`Website`/`PubMed`/`Other`
**截断提示**（通用组件）：`Showing first {shown} of {count} records`
**空态**：`No goals yet` / `No applications yet` / `No methods yet` / `No protocols yet` / `No references yet`
⚠️ **所有字段都无必填校验**（连 `Name` 都没有）⇒ 可以保存空实体。

## 7.6 Verified 适用性审核

**页面** `/workspace/verified`（`VerifiedPage.vue`）
**进入即** `GET /verified/?status=review`

| 元素 | 说明 |
|---|---|
| Tab | `Review` / `Active` / `Rejected` / `All` ⇒ 切 `GET /verified/?status=`（`All` 不带参） |
| 表格列 | `Product`（附 `product_catalog_no` 小字）/ `Method` / `Status` / `Evidence`（`type: value` 芯片 + note 首行）/ `Strength` / `Curator` / `Created`（前 10 位）/ 操作列 |
| 通过 | `Approve` → 原生 `confirm('Approve "{method}" as verified applicable for "{product}"?\nThis publishes it to the public product page.')` → `POST /verified/{id}/approve/` |
| 驳回 | `Reject` → 原生 `prompt('Reject "{method}" for "{product}" — reason (optional):')` → `POST /verified/{id}/reject/` body `{note}` |

**状态流**：`review` --Approve--> `active`（**立即出现在公开产品页**）--Reject--> `rejected`
**空态**：`No verified relations in this state.`

**审核内容从哪来**：产品编辑页的 `Verified Applicability` 区块（`isEdit && productLoaded` 才渲染）可以建 `review` 草稿 ——
表单：`Method *`（远程搜索选）/ `Evidence type`（`pubmed`/`doi`/`msds`/`literature`/`other`）/ `Strength`（`high`/`medium`/`low`）/ `Evidence reference`（行内 `type` ∈ `PMID`/`DOI`/`PROTOCOL`/`MANUFACTURER`/`DOC` + 值）/ `Note`
⇒ `POST /verified/`，提示 `已创建 verified 草稿（待 workspace 审核发布）`。

> ⚠️ **`Approve` 的后果要知道**：`confirmed` 后这条关系**立刻公开**到产品详情页的 `Verified Methods` 区。
> 有二次确认框，但没有撤销后的预览。

## 7.7 知识录入（Knowledge Intake）

**页面** `/workspace/knowledge-intake`（`views/KnowledgeIntake.vue`）
**进入即** `GET /products/?page_size=200`

左右两栏：左=产品列表（`Filter products...` 本地过滤 `category_l1`/`name`/`catalog_no`）；右=选中产品的知识表单。

| 字段组 | 控件 | 说明 |
|---|---|---|
| Research Goals | 芯片多选（8 个固定选项：`RNA Analysis`/`DNA Sequencing`/`Click Chemistry`/`Protein Engineering`/`RNA Modification`/`RNA Therapeutics`/`Epigenetics`/`Cell Biology`） | — |
| Applications | 芯片多选（12 个固定选项） | — |
| Methods | 芯片多选（11 个固定选项） | — |
| Protocol | `Protocol Name` / `Steps (brief)`（placeholder `1. Prepare RNA 2. Add reagents 3. Incubate 4. Purify`）/ `Materials` / `Time` / `Difficulty`(`Beginner`/`Intermediate`/`Advanced`) | — |
| 文献 | `PMID (comma separated)` / `DOI` | 无格式校验 |
| 评价 | `Key Advantages` / `Key Limitations` | — |
| 置信度 | 芯片单选 `high` / `medium` / `low`（默认 high） | — |

| 操作 | 按钮 | 请求 | 结果 |
|---|---|---|---|
| 保存 | `Save`（`Saving...`） | `POST /knowledge-intake/` body `{product_id, ...form}` | 提示条 `Saved as draft for {catalog_no}` |
| 复制到同类 | `Copy to Similar Products` | 逐条 `POST /knowledge-intake/` | 先 `confirm('Copy knowledge to {n} similar product(s)?')`；结果 `Copied to {c} of {t} ({f} failed)` |
| 候选服务端选品 | 点左栏产品卡 | 无 | 右栏重置为空表单 |

**两条限制**：无同类 ⇒ `No similar products found`；超过 50 个 ⇒ `Too many similar products ({n}); limit is {50}. Nothing was copied.`（**一个都不复制**，不是部分复制）
**空态**：`Select a product from the list to fill in knowledge content`
⚠️ 芯片选项是**前端写死的固定词表**（`:47-62`），不是从后端拉取的实体列表 ⇒ 录入的 Goal/Application/Method 名称可能与知识库现有实体**对不上**。

## 7.8 交易运营：订单与 PO（8 个页面）

### 7.8.1 订单管理（`/ops/orders`）

**进入即** `GET /admin/orders/?page=1&page_size=20`（**注意：这条是 `IsAdminUser`，只有 staff 能看**）

| 控件 | 可选值（原文） |
|---|---|
| 状态下拉 | `All` + 10 个主状态；`optgroup Historical / Quote states` 6 个历史状态 |
| 搜索 | placeholder `Search order #, PO #...` |
| 分页 | 固定 20/页，`total, prev, pager, next` |

**表格列**：`Order #` / `Customer` / `PO #` / `Status` / `Payment` / `Total` / `Date` / 箭头列
⚠️ `Customer` 列实际渲染的是 `order.user_id`（**数字 ID，不是姓名**）
⚠️ 加载失败时错误横幅与 `No orders found` 空态**同时出现**，容易被误读为"没有订单"

### 7.8.2 订单详情与状态推进（`/ops/orders/:id`）—— 交易运营的核心

**进入即** `GET /admin/orders/{id}`

**页面区块**：头部（`Order {order_no}` + 创建时间 + 状态徽章）→ 动作区 → `Items` 表 + `Total` → `Customer` / `Payment` 双列 → `Shipping Address` → `Invoice`（有则）→ `Internal Notes`

**⚠️ 状态推进按钮矩阵（最关键的一张表）**：

| 当前状态 | 出现的按钮（原文） | 请求 | 目标状态 |
|---|---|---|---|
| `po_received` | `Approve` | `POST /orders/{id}/approve/` | `confirmed` |
| `confirmed` 或 `in_production` | `Carrier` + `Tracking Number` 表单 + `Create & Mark Shipped` | `POST /orders/{id}/shipments/` → 取 id → `POST /shipments/{id}/mark-shipped/`（**两步串联**） | `shipped` |
| `shipped` | `Mark as Delivered`（无未完成发货单时禁用） | `POST /shipments/{id}/mark-delivered/` | `delivered` |
| `delivered` | `Generate Invoice`（**无字段**，付款条件硬编码 `NET30`） | `POST /orders/{id}/invoice/` | `invoiced` |
| `invoiced` | `Amount` + `Method` 表单 + `Record Payment` | `POST /invoices/{id}/pay/` | 后端决定（部分付款仍停 `invoiced`） |
| `paid` | `Mark as Completed` | `POST /admin/orders/{id}/complete/` | `completed` |
| `quote_pending` | `Total Price` + `Valid Until` 表单 + `Submit Quote` | `POST /admin/orders/{id}/quote/` | 未在前端声明；客户侧变 `quoted` 后出现接受/拒绝 |
| `po_received`/`confirmed`/`in_production`/`shipped`/`delivered`/`invoiced`/`quote_pending` | `Cancel Order`（红底，**无二次确认，点击即提交**） | `POST /orders/{id}/cancel/` | `cancelled` |
| `completed` / `cancelled` / `quoted` / `quote_accepted` / `quote_rejected` / `draft` / `processing` | **无任何动作按钮** | — | — |

**这张表必须与权限一起看**（同一动作在两个页面权限不同）：

| 动作 | 本页端点 | 权限 | 采购能做？ | PO Desk 的对等端点 | 权限 | 采购能做？ |
|---|---|---|---|---|---|---|
| 审批 | `/orders/{id}/approve/` | `IsProcurementOrAdmin` | ✅ | `PoReviewDesk` 同端点 | 同 | ✅ |
| 拒绝 | ❌ **本页无此按钮** | — | — | `/orders/{id}/reject/` | `IsProcurementOrAdmin` | ✅ |
| 发货 | `/orders/{id}/shipments/` | `IsProcurementOrAdmin` | ✅ | 同 | 同 | ✅ |
| 开票 | `/admin/orders/{id}/invoice/` | **`IsAdminUser`** | ❌ | `/orders/{id}/invoice/` | `IsProcurementOrAdmin` | ✅ |
| 收款 | `/invoices/{id}/pay/` | `IsProcurementOrAdmin` | ✅ | 同 | 同 | ✅ |
| 完成 | `/admin/orders/{id}/complete/` | **`IsAdminUser`** | ❌ | 无对等入口 | — | — |
| 报价 | `/admin/orders/{id}/quote/` | **`IsAdminUser`** | ❌ | 无对等入口 | — | — |
| 取消 | `/orders/{id}/cancel/` | `IsProcurementOrAdmin` | ✅ | 无 | — | — |

⇒ **采购只能在 4 个 PO Desk 里干活，在订单详情页会看到一半按钮是 403**。

**本页缺失的东西**（运营会问到的）：
- ❌ 无 `Reject` 按钮（拒绝只能在 PO 审核台）
- ❌ 无"开始生产"按钮（`in_production` 只能靠 API 或 admin）
- ❌ 无附件区块、**无状态日志区块**（`StatusLog` 有数据但页面不展示）
- ❌ 无发货记录列表（`order.shipments` 只用于判断"是否有未完成发货单"）
- ❌ `Internal Notes` 输入框**没有保存按钮也没有 API** ⇒ 输入不落库（死输入框）
- ⚠️ `quoteForm.notes` 有状态字段但模板无输入框 ⇒ 报价备注永远传空串

### 7.8.3 四个 PO Desk

| 页面 | 队列来源 | 能做的操作 |
|---|---|---|
| `/ops/po/review` | `GET /orders/?status=po_received` | `Approve` / `Reject`（带原因）/ `Assign Rep`（带 Rep ID）/ `View Items` |
| `/ops/po/shipments` | `GET /orders/?page_size=200` 客户端过滤 3 态 | `Create Shipment`（Carrier/Tracking #/Tracking URL/Est. Delivery/每行 Qty to Ship）/ `Mark Shipped` / `Mark Delivered`（带 Received by） |
| `/ops/po/invoicing` | 客户端过滤 `delivered`/`invoiced` | `Issue Invoice`（付款条件）/ `Record Payment`（Amount/Method/Reference） |
| `/ops/po/ar` | `GET /ar/aging/` | 只读：4 个账龄卡 + `Total Outstanding` |
| `/ops/po/organizations` | `GET /organizations/manage/?page_size=100` | 只读：机构列表 + 按机构查订单 |

## 7.9 staff 做不到的事

| 想做的事 | 结果 | 原因 |
|---|---|---|
| 物理删除产品 | ❌ 前端无入口 | `hard-delete` 是 `IsSuperUser`（第 8 章） |
| 改自己的权限/角色 | ❌ 无 API | 只能 Django admin |
| 把订单 `invoiced → paid` | ❌ **全站无按钮** | 只有"记录收款"，无"标记已付" |
| 在订单详情页拒绝/报价（若非 staff 代理） | — | 见 7.8.2 权限对照表 |

---

# 第 8 章 superuser

## 8.1 身份与边界

| 项 | 值 |
|---|---|
| `is_superuser` | true（且必然 `is_staff=true`） |
| 端点 | **203/203 写 + 132/132 读 = 全通** |
| 页面 | 与 staff 完全相同的 52 页 + **Django admin** |
| 唯一增量能力 | 产品物理删除（`IsSuperUser` 2 个端点） + Django admin 全量 |

## 8.2 F8-1 物理删除产品（🔒 有端点，无 UI）

| 项 | 事实 |
|---|---|
| 端点 | `POST /products/{id}/hard-delete/`（`IsSuperUser`） |
| 前端入口 | ❌ **全仓 `grep hard-delete frontend/src` 0 命中** |
| 调用方式 | 只能 curl / Django shell / admin |

> 这是全站**唯一的真孤儿能力**：只有超管能用，而超管在界面上根本看不到它。
> 若要保留该能力，需要补入口（或至少写进运维手册）；若不需要，应删除端点。
> **当前状态下这个能力等于不存在**，而 `DELETE /products/{id}/` 是软删（回收站）——两者语义完全不同，别混。

## 8.3 F8-2 Django admin（角色与权限分配的唯一场所）

> ⚠️ **产品内没有"角色权限分配"功能**。这是全站最重要的一条运营事实：
> 授予 `procurement` / `admin` / `is_staff` / `is_superuser` **只能登录 Django admin 手工改**。

| 想改的东西 | 在 Django admin 哪里 | 备注 |
|---|---|---|
| `role` | Users → 选用户 → fieldsets 里的 `role` | `accounts/admin.py:42` |
| `is_staff` | Users → `is_staff` 勾选框 | — |
| `is_superuser` | Users → `is_superuser` 勾选框 | — |
| `is_org_admin` | Users → `is_org_admin` | 改了也不影响权限（第 4 章） |
| `organization` | Users → `organization` | ✅ 这个真的影响地址隔离与订单归属 |
| 产品状态 | Products → `status` | 与工作台 `Status` 下拉等价 |
| `SKU.inventory_status` | SKUs → `inventory_status` | **前端唯一没有入口的字段** |
| 订单状态 | Orders → `status` | 绕过状态机，慎用 |
| 发票状态 | Invoices → `status` | 同上 |

**admin 列表页提供的筛选**：`role` / `is_org_admin` / `is_staff` / `is_active`（`accounts/admin.py:37-38`）

---

# 第 9 章 跨角色闭环（同一业务在多个角色间的传递）

> 前 8 章是"某个角色能做什么"，本章是"**一件事在角色之间怎么流动**"。
> 运营出问题时，答案通常在这些链条的接缝处。

## 9.1 订单全生命周期（客户发起 → 采购履约 → 客户确认）

```
【客户 researcher】                 【内部 staff / procurement】              【客户 researcher】
购物车 → /checkout 或 /po/submit
        ↓
   Order(po_received)  ────────▶  PO 审核台 Approve ──▶ Order(confirmed)
                                        │
                                        ├──▶ 发货台 Create Shipment → Mark Shipped ──▶ Order(shipped)
                                        │                                              ↓
                                        │                                    Mark Delivered → Order(delivered)
                                        │                                              ↓
                                        │                                    开票台 Issue Invoice → Order(invoiced)
                                        │                                              ↓
                                        │                                    Record Payment → (Invoice.status)
                                        │                                              ↓
                                        └──▶ 订单详情 Mark as Completed ──▶ Order(completed)
                                                                   
【客户可能在任意环】OrderDetailPage 看进度、下载发票 PDF、Track Package
【取消】7 个状态内可 Cancel（客户侧无取消入口，只能内部取消）
```

**六个接缝（出问题的高发点）**：

| # | 接缝 | 事实 |
|---|---|---|
| 1 | 客户下单 → 采购看到 | 客户走 `/checkout`（`IsAuthenticated`）或 `/po/submit`（同）都能成单；但采购在 `/ops/orders` 看不到（403），**必须在 PO 审核台看 `po_received` 队列** |
| 2 | 收款 → 订单状态 | **不联动**。`Record Payment` 只写 `PaymentRecord` + `Invoice.status`，`Order.status` 停在 `invoiced` |
| 3 | `invoiced → paid` | **无入口**。全站没有"标记已付"，`verify-payment` 端点前端 0 引用 |
| 4 | 发票唯一性 | `Invoice` 是 `Order` 的 `OneToOne`（`models.py:...`）⇒ **一单只能开一张发票**，不支持拆票/多期开票 |
| 5 | 金额快照 | `OrderItem.unit_price` 在下单时快照 ⇒ 后续改 SKU 价不影响历史订单（正确行为，但必须知道） |
| 6 | 报价 | 订单的 `quote_pending` 状态与 `Quote` 实体是**两个东西**：前者是订单状态，后者是独立询价单（有 `quote_no` 和 6 个自己的状态）。名字相同，别混 |

## 9.2 产品上架生命周期（内容运营）

```
1. 新建产品        /workspace/products/new          → POST /products/  (status=draft)
2. 补全字段        Completeness bar 变 ✓
3. 关联知识实体    Section 5 chips                  → PUT 时带 method_ids / protocol_ids
4. 建 SKU + 定价   Section 7                        → 随产品保存
5. 生成合规文档    Section 9 Generate SDS / COA     → draft
6. 审批发布合规    Approve & Publish SDS / COA      → published
7. 发布产品        Publish                          → status=active
8. 建 verified 关系 (可选) Section 5 verified 区块   → POST /verified/ (review)
9. 审核 verified   /workspace/verified Approve      → active（立即公开）
10. 下架/删除      Unpublish / Move to Recycle Bin  → status=archived / archived=True
```

**四个"看起来一步、实际两步"的地方**：

| 动作 | 第一步 | 第二步 | 忘了第二步的后果 |
|---|---|---|---|
| 产品可见 | `Publish`（status=active） | — | 但若 `archived=True`，前台**仍然看不到**（回收站优先级更高） |
| 合规文档可见 | `Generate` | `Approve & Publish` | 客户看不到 COA/SDS 图标 |
| verified 关系可见 | 建草稿（review） | `Approve` | 产品页的 `Verified Methods` 区为空 |
| 知识关联生效 | 选 chip（改本地） | 保存产品（PUT） | 刷新即丢失 |

## 9.3 COA / SDS 状态机（合规侧）

```
SDS：draft ──Approve&Publish──▶ published ──Withdraw──▶ draft
COA：draft ──Approve&Publish──▶ published ──Withdraw──▶ draft
       └─（approved 为历史兼容值，新流程不写）
```
**下载门控**：只有 `status=published` 的文档允许匿名下载（`SdsRevision` 的 `status` 字段就是为此在 2026-10-17 补上的）。
**可见入口**：产品详情页的 SKU 行 `COA` 图标、`SDS` 徽章。

## 9.4 verified 关系状态机

```
（产品编辑页建草稿）──▶ review ──Approve──▶ active ──（产品页立即可见）
                        └──Reject──▶ rejected
另有 derived（自动派生，status=active）+ deprecated（弃用）
```
**两条边的区别（必须分清）**：

| 边 | 来源 | 谁维护 | 是否公开 |
|---|---|---|---|
| `derived_relevance` | 算法派生（`source_reagent_class` 必填） | 离线重建 | 以"关联方法"弱展示 |
| `verified_applicability` | 人工策展（`source_reagent_class` 必须 NULL） | staff 建草稿 + 审核 | ✅ 独立 `Verified Methods` 区 |

## 9.5 询价（RFQ）与报价（Quote）—— 三个"quote"别混

| 名字 | 是什么 | 谁发起 | 状态机 |
|---|---|---|---|
| **RFQ / 询价单** | `/quote-request` 提交的线索，落 `quote_requests` | 任何人（含匿名） | 无状态机 |
| **Quote 实体** | `Quote` 模型，有 `quote_no` | `POST /quotes/`（`IsAuthenticated`） | draft / submitted / responded / negotiating / closed / cancelled |
| **订单报价** | `Order.status = 'quote_pending'` → 内部 `Submit Quote` → `quoted` → 客户 Accept/Reject | 内部发起 | 走 Order 状态机 |

⚠️ 三个都叫 quote，运营沟通时必须说清是哪一个。

---

# 第 10 章 权限速查总表

## 10.1 八身份 × 关键动作

| 关键动作 | 匿名 | 未验证 | researcher | org_admin | procurement | admin(role) | staff | superuser |
|---|---|---|---|---|---|---|---|---|
| 浏览商品/搜索 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 加入购物车 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 提交询价 RFQ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 注册 | ✅ | — | — | — | — | — | — | — |
| 登录 | — | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 下单 `/checkout` | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 提 PO `/orders/po/` | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 看自己的订单 | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 管地址簿 | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 改个人资料 | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 改密码 | — | — | ⚠️ 假成功 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| 进内部台 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 新建/编辑产品 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 删产品（软删） | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 删产品（物理） | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🔒 |
| 新建/编辑知识实体 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 知识录入 intake | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 生成/审批 COA·SDS | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 审核 verified | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 看 `/admin/orders/` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 审批/拒绝 PO | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 发货/标记送达 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 开票（PO Desk） | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 开票（订单详情页） | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 记录收款 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 指派销售 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| 完成订单 / 提交报价 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 库存入库/调整 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| 批量 AI（校验/文献） | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 改任意人的角色 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Django admin |

## 10.2 端点级计数

| 身份 | 读通过 | 写通过 |
|---|---|---|
| 匿名 | 117/132 | 7/203 |
| 未验证 | 123/132 | 43/203 |
| researcher | 123/132 | 43/203 |
| org_admin | 123/132 | 43/203 |
| procurement | 128/132 | 54/203 |
| admin(role) | 128/132 | 55/203 |
| staff | **132/132** | 201/203 |
| superuser | **132/132** | **203/203** |

---

# 第 11 章 已知不一致、限制与死按钮

> 本章是"操作时一定会撞上的坑"。按影响面排序，每条都带代码依据。

## 11.1 结构性不一致（5 条）

| # | 现象 | 依据 | 后果 |
|---|---|---|---|
| 1 | **`role` 只影响 17 个端点**，其余 231 个写操作只看 `is_staff` | 权限类统计 | `role=admin` 能改 55/203，名为 admin 实权有限 |
| 2 | **前端只有 2 级守卫，后端 8 类判据** | `router/index.js:322` | 19 个内部页里 3 个空白、9 个只读，用户无解释 |
| 3 | **`is_org_admin` 零影响** | 全仓无权限引用 + 探针数字相同 | 机构管理员没有任何管理能力 |
| 4 | **`email_verified` 只在登录处校验** | 探针 unverified == researcher | 已登录用户邮箱被置否后 token 仍全权可用 |
| 5 | **同一动作两套端点、两套权限** | `/admin/orders/{id}/invoice/`(`IsAdminUser`) vs `/orders/{id}/invoice/`(`IsProcurementOrAdmin`) | 采购在订单详情页开不了票，在开票台却能 |

## 11.2 死按钮 / 假成功 / 无反馈（运营最常撞的）

| # | 位置 | 现象 | 依据 |
|---|---|---|---|
| 1 | `/settings` → Security → `Update Password` | **假成功**：校验后直接提示 `Password update feature will be available soon.`，无任何后端调用 | `SettingsPage.vue:191-221` |
| 2 | `/login` → `Resend verification email` | **必崩**：读 `form.email`（字段不存在）⇒ `TypeError`，请求不发 | `LoginPage.vue:22-25,112` |
| 3 | `/verify-email` 失败态 | **重发按钮永不显示**（`v-if="email"` 只在成功路径为真） | `VerifyEmailPage.vue:28,117` |
| 4 | `/ops/orders/:id` → `Internal Notes` | 有输入框，**无保存按钮无 API** ⇒ 输入不落库 | `AdminOrderDetail.vue:267` |
| 5 | `/ops/orders/:id` → 报价备注 | `quoteForm.notes` 有字段、模板无输入框 ⇒ 永远传空 | `AdminOrderDetail.vue:26,104` |
| 6 | `/ops/po/review` → `Assign Rep` | 采购点击必 403；rep 为空时静默 return；失败无提示 | `PoReviewDesk.vue:53-58` |
| 7 | `/ops/po/invoicing` → `Record Payment` | Amount 为空时**静默 return**，无提示 | `PoInvoicingDesk.vue:53` |
| 8 | `/ops/inventory` 入库/调整 | 必填校验全部静默 `return`，无文案 | `InventoryDesk.vue:260,282` |
| 9 | `/quote-request` 提交失败 | 只 `console.error`，页面无提示 ⇒ 用户以为成功 | `QuoteRequestPage.vue:104` |
| 10 | `/search` 失败 | 只 console，页面无提示 | `SearchPage.vue:68` |
| 11 | `/cart` → `Submit for Approval` | 与 `Place Order` 同目标，**无审批接口**；且仅 researcher 可见 | `CartPage.vue:14-19,59` |
| 12 | `/methods`、`/protocols` 状态 chips | 点击只变高亮，**不筛数据**（未传 `status`） | `MethodIndex.vue:37`、`ProtocolIndex.vue:38` |
| 13 | 产品列表 `Knowledge Link` 列 | 可排序，但 L3 子分类筛选未进请求参数 | `ProductIndex.vue:43-47` |
| 14 | `PoReorder` 行选中 | `selectedId` 从未赋值 ⇒ 高亮永不出现 | `PoReorder.vue:12,53` |
| 15 | `AdminOrdersPage` 加载失败 | 错误横幅与"无订单"空态同时出现 | `AdminOrdersPage.vue:93,130` |
| 16 | `PoArReport` 加载失败 | 无 catch、无空态，页面只剩头部 | `PoArReport.vue:16-24` |
| 17 | `PoOrgManagement` 副标题 | 声称 "their addresses"，模板无地址字段 | `PoOrgManagement.vue:44` |
| 18 | 完整性条缺失项 | 纯文本，不可点击跳转到缺失字段 | `ProductEditPage.vue:1666-1667` |

## 11.3 能力缺口（有需求、无实现）

| # | 缺口 | 现状 |
|---|---|---|
| 1 | **`invoiced → paid`** | 全站无"标记已付"按钮；`verify-payment` 端点前端 0 引用 |
| 2 | **库存数量与商品"现货"徽章不联动** | `apps/inventory` 从不写 `SKU.inventory_status` |
| 3 | **机构管理员无任何管理功能** | 只有 `/settings` 一个徽章 |
| 4 | **产品物理删除无入口** | `hard-delete` 前端 0 引用（超管专属） |
| 5 | **角色分配无产品界面** | 只能 Django admin |
| 6 | **知识录入芯片是写死词表** | 与知识库现有实体可能对不上 |
| 7 | **一单只能一张发票** | `Invoice` 是 `Order` 的 `OneToOne` |
| 8 | **匿名购物车不合并** | `mergeLocalBasket` 零调用 |
| 9 | **Reference 无详情页** | 搜索结果可点但无跳转 |
| 10 | **`in_production` 无独立入口** | 订单详情页无"开始生产"按钮 |

## 11.4 潜在风险（当前无实际数据触发，但一旦触发就是事故）

| # | 风险 | 触发条件 | 依据 |
|---|---|---|---|
| 1 | **非 USD 币种订单金额错** | 上架任一 CNY/EUR 的 SKU | `checkout_views.py:93` 硬编码 `currency='USD'`；当前 596 SKU 全 USD |
| 2 | **`create_order` 信任客户端单价** | 有人把它接上生产调用链 | `services.py:40-52`；当前只有测试调用 |
| 3 | **`_sync_method_bridges` 先删后加** | 保存时只传 goal/app 不传 `method_ids` | 原有方法关联被真删 |

---

# 附录 A 状态机全表

## A.1 Order（`transactions/models.py:57-74`）

| 当前状态 | 允许流转到 |
|---|---|
| `po_received` | `confirmed` / `cancelled` |
| `confirmed` | `in_production` / `shipped` / `cancelled` |
| `in_production` | `shipped` / `cancelled` |
| `shipped` | `delivered` / `cancelled` |
| `delivered` | `invoiced` / `cancelled` |
| `invoiced` | `paid` / `cancelled` |
| `paid` | `completed` |
| `completed` | —— |
| `cancelled` | —— |
| *（历史兼容）* `draft` | `confirmed` / `quote_pending` / `cancelled` |
| *（历史）* `quote_pending` | `quoted` / `cancelled` |
| *（历史）* `quoted` | `quote_accepted` / `quote_rejected` |
| *（历史）* `quote_accepted` | `confirmed` |
| *（历史）* `quote_rejected` | —— |
| *（历史）* `processing` | `shipped` |

**注意**：`paid` 只能来自 `invoiced`，而 `invoiced` 只能来自 `delivered`。**跳步不可能**。
每次流转写 `StatusLog`（`actor` / `from` / `to` / `note`）。

## A.2 Coa（`documents/models.py:78-92`）

| 当前 | 允许 | 触发动作 |
|---|---|---|
| `draft` | `published` | `POST /coas/{id}/approve/` |
| `published` | `draft` | `POST /coas/{id}/withdraw/` |
| `approved` | —（历史兼容值，新流程不写） | — |

## A.3 SdsRevision（`documents/models.py:156-176`）

与 Coa 同构：`draft ⇄ published`（approve / withdraw）。`approved` 为历史兼容。

## A.4 VerifiedRelation（`bridges/models.py:495-524`）

| 当前 | 允许 | 触发 |
|---|---|---|
| `review` | `active` | `POST /verified/{id}/approve/` |
| `review` | `rejected` | `POST /verified/{id}/reject/` |
| `active` | —（页面无"弃用"按钮） | — |
| `rejected` | — | — |
| `deprecated` | —（存在但无 UI） | — |

## A.5 Quote（`transactions/models.py:501-524`）

`draft` / `submitted` / `responded` / `negotiating` / `closed` / `cancelled` —— **无前端状态推进界面**（只有 `GET /quotes/` 被 PO 提交页用作下拉选项）。

## A.6 Invoice（`transactions/models.py`）

`draft` / `issued` / `paid` / `overdue` / `void` —— 前端只做 `Record Payment`，`overdue`/`void` 无入口。

## A.7 Product（`core/models.py:36-48` StatusMixin）

`draft` / `active` / `deprecated` / `archived`
**另有独立布尔** `archived`（回收站），与 `status='archived'` **不是同一回事**：
- `status='archived'` = 通过状态下拉设的历史状态
- `archived=True` = `DELETE /products/{id}/` 软删标记
前台可见条件：`status='active'` **且** `archived=False`

## A.8 SKU.inventory_status（`commerce/models.py:233-237`）

`in_stock` / `limited` / `preorder` / `out_of_stock` —— 手工字段，**前端无输入控件**，默认 `in_stock`。
产品级状态是**派生**的（`models.py:218-228`）：有任一 SKU `in_stock` ⇒ `in_stock`；否则 `limited`；否则 `preorder`；否则 `out_of_stock`。

## A.9 库存数量（`inventory`，与上者无关）

`available` / `allocated` / `on_hand` 三个整数；`on_hand = available + allocated`。
所有变更经 `InventoryService`（`select_for_update` 原子操作 + 写 `InventoryMovement` 流水），**禁止直改 `available`**。

---

# 附录 B 端点索引（按业务域）

| 业务域 | 代表端点 | 权限 |
|---|---|---|
| **认证** | `POST /auth/login`、`POST /auth/register`、`GET /auth/verify-email`、`POST /auth/resend-verification`、`GET /auth/me`、`PUT /auth/profile` | `AllowAny` / `IsAuthenticated` |
| **机构** | `GET /organizations`（匿名搜索）、`GET /organizations/manage/`、`POST /organizations` | `AllowAny` / `IsProcurementOrAdmin` |
| **地址** | `GET/POST /addresses/`、`PUT/DELETE /addresses/{id}/` | `AddressPermission`（登录即可） |
| **购物车** | `GET /basket`、`POST /basket/items`、`PATCH /basket/items/{id}`、`DELETE /basket/items/{id}/delete`、`POST /basket/merge` | `AllowAny`（`X-Session-Key`） |
| **商品** | `GET /products/`、`GET /products/{id}/detail`、`GET /products/{id}/methods/`、`POST /products/`、`PUT/DELETE /products/{id}/`、`POST /products/{id}/archive/`、`POST /products/batch-restore/`、🔒 `POST /products/{id}/hard-delete/` | 读 `AllowAny`；写 `IsAdminOrReadOnly`；hard-delete `IsSuperUser` |
| **SKU** | `/skus/` 系列 | `IsAdminOrReadOnly`（前端无直接入口，随产品保存） |
| **AI 工具** | `POST /products/enrich/`、`/products/parse-word/`、`/products/render-structure/`、`/products/{id}/generate-seo/`、`/products/import-protocol/`、`/products/{id}/adopt-bioz-refs/`、`/products/batch-validate/`、`/products/batch-recommend-literature/` | `IsStaffUser` / `IsAdminOrReadOnly` |
| **知识实体** | `/research-goals/`、`/applications/`、`/methods/`、`/protocols/`、`/references/` 各自 CRUD | 读 `AllowAny`；写 `IsAdminOrReadOnly` |
| **收敛类** | `GET /convergence-classes/?group=ap\|rg`、`GET /convergence-classes/{id}/` | `AllowAny` |
| **知识录入** | `POST /knowledge-intake/` | `IsAdminUser` |
| **verified 关系** | `GET/POST /verified/`、`PATCH /verified/{id}/`、`POST /verified/{id}/approve\|reject/` | `IsStaffUser` |
| **订单** | `GET /orders/`（按用户收窄）、`GET /orders/{id}/`、`POST /checkout/`、`POST /orders/po/`、`POST /orders/{id}/approve\|reject\|assign-rep\|cancel\|shipments\|invoice/`、`POST /orders/{id}/confirm-quote/` | 混合：`IsAuthenticated` / `IsProcurementOrAdmin` / `IsAdmin` |
| **订单（admin 套）** | `GET /admin/orders/`、`GET /admin/orders/{id}/`、`POST /admin/orders/{id}/complete\|quote\|confirm\|invoice/` | `IsAdminUser` |
| **发货** | `POST /shipments/{id}/mark-shipped\|mark-delivered/` | `IsProcurementOrAdmin` |
| **发票收款** | `POST /invoices/{id}/pay/`、`GET /invoices/{id}/pdf/`、🔒 `POST /admin/invoices/{id}/verify-payment/` | `IsProcurementOrAdmin` / `IsAuthenticated` / `IsAdminUser` |
| **应收** | `GET /ar/aging/` | `IsProcurementOrAdmin` |
| **库存** | `GET /inventory/`、`GET /inventory/{id}/`、`POST /inventory/receipt/`、`POST /inventory/{id}/adjust/` | `IsProcurementOrAdmin` |
| **合规文档** | `/sds-revisions/`（list/generate/approve/withdraw/download）、`/coas/`（list/create-coa/approve/withdraw/download/qc-results）、`/batches/` | 读 `AllowAny`；写 `IsAdminOrReadOnly` |
| **询价** | `POST /quote-requests/`、`GET /quote-requests/{id}/`；`/quotes/` CRUD | 未声明 / `IsAuthenticated` |
| **愿望清单** | `GET/POST /wishlist/`、`PATCH /wishlist/{id}/` | `IsAuthenticated` |
| **站点** | `GET /site/home`、`GET /site/navigation`、`/sitemap*.xml`、`/health/` | `AllowAny` |

**合计 335 个 path×method**（含 ViewSet 的 `.json` 等格式后缀变体）。
🔒 = 有端点、前端无入口。

---

# 附录 C 如何复核本文

```bash
cd src_claude

# 1) 权限矩阵（335 端点 × 8 身份，0 次 HTTP）
cd backend && DB_ENGINE=sqlite venv/Scripts/python.exe ../scripts/role_capability_probe.py \
  --json ../docs/e2e/ROLE_CAPABILITY_MATRIX.json && cd ..
# 输出应复现第 10.2 节的 8 行数字

# 2) 页面 × 角色判定（DEAD / READONLY / OK）
python scripts/page_role_matrix.py --json docs/e2e/PAGE_ROLE_MATRIX.json
# 输出应复现第 5.1 节的 3/9/7

# 3) 端点权限类清单（核对附录 B 的权限列）
python scripts/permission_audit.py

# 4) 单页复核（例：查某页调了哪些接口）
grep -nE "http\.(get|post|put|patch|delete)|from '@/api" frontend/src/views/<Page>.vue

# 5) 查某角色能否过某端点
cd backend && DB_ENGINE=sqlite venv/Scripts/python.exe ../scripts/role_capability_probe.py \
  --identity procurement --denied && cd ..
```

**本文三个已知的"看不到"**（如实声明，避免过度信任）：
1. `has_object_permission`（对象级隔离，如地址簿的机构边界）—— 探针只能测 `has_permission`
2. `get_queryset` 收窄（客户只能看自己的订单）—— 需要真实对象才能验
3. 组件内**运行时**条件渲染（例如某按钮的 `v-if` 依赖异步数据）—— 静态读只能读到条件表达式

---

**文档版本** V1.0 · 2026-10-22 · 对应代码 `cc4e8f2` · 覆盖 8 身份 / 335 端点 / 52 页面


