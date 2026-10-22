# 角色 × 权限 × 流程 × 页面 —— 现状基线（V2，2026-10-22）

> 本文只陈述**代码与运行时实际是什么**，不做设计建议。每条结论带代码位置或脚本输出，可复核。
> 用途：为「按角色的拟人化测试方案」提供确定性的靶子。
>
> **V2 修订说明（诚实记录）**：V1 有三处把推断当结论，全部被实测推翻，已改：
> 1. "V1 说内部台 9 个页面" → 实际 **19 个**（`/workspace` 是父级壳，10 个子页继承守卫，V1 只数了路由块）
> 2. "V1 说 #6 admin(role) 什么都不能改" → 实际 **203 个写端点里能过 55 个（27%）**，能改的东西不少
> 3. "V1 说 procurement 能进 9 个内部台" → 实际只有 **16 个页面能正常用，3 个进去就是空白**（详见 §8）

---

## 0. 提取方法（可复现，两个脚本）

| 维度 | 来源 | 提取方式 |
|---|---|---|
| 角色字段 | `backend/apps/accounts/models.py:69-109` | 读 `Role` choices + 4 个布尔/枚举字段 |
| 权限类判据 | `backend/core/permissions.py:1-56` + `accounts/api/v1/views.py:315` | 逐类读 `has_permission` |
| 端点 × 权限（335 条） | `scripts/permission_audit.py` | 实例化真实视图读 `get_permissions()` |
| **身份 × 端点判定** | **`scripts/role_capability_probe.py`** | 用伪造 request 调**真实权限类实例**的 `has_permission` |
| 页面 → 调哪些 API | `docs/e2e/PAGE_API_MAP.json` | 静态解析 `@/api/*` 具名导入 + 直接 http 调用，带 `file:line` |
| **页面 × 角色判定** | **`scripts/page_role_matrix.py`** | 上面两张表叉乘 |
| 前端守卫 | `frontend/src/router/index.js:299-340` + `utils/internalAccess.js` | 读 `beforeEach` 与单一真相源 |

```bash
# 全部可重跑，无外部依赖
python scripts/permission_audit.py
cd backend && DB_ENGINE=sqlite venv/Scripts/python.exe ../scripts/role_capability_probe.py --json ../docs/e2e/ROLE_CAPABILITY_MATRIX.json
python scripts/page_role_matrix.py --json docs/e2e/PAGE_ROLE_MATRIX.json
```

### 探针证明了什么、没证明什么（必须先读，否则会误读 §8）

**证明**：视图级 `has_permission` 的准入 —— 也就是 **403 与"进得去"的分界**。
**没有证明**（所以 §8 的 `OK` 只是"不会被 403 挡"，不等于功能正常）：
- `has_object_permission`（对象级，如 `AddressPermission` 的机构隔离）
- `get_queryset` 收窄（权限过了但**看不到数据**，如客户只能看自己的订单）
- 前端守卫（另一层，见 §3）
- 业务前置条件（购物车为空时 checkout 仍 400）
- **反向**："被拒"是确定的 —— 权限类不通过，后面什么都发生不了。

---

## 1. 角色不是一个字段，是**四个维度的组合**

`apps/accounts/models.py`：

| 维度 | 取值 | 默认 | 谁能改 | 对权限有影响？ |
|---|---|---|---|---|
| `role` | researcher / procurement / editor / admin | researcher | **仅 Django admin**（`accounts/admin.py:42`） | ✅ 影响 **17** 个端点 |
| `is_staff` | bool | False | Django admin / `createsuperuser` | ✅ 影响 **231** 个端点 |
| `is_org_admin` | bool | False | 建房机构时自动 True；否则 Django admin | ❌ **零影响**（见 §5.4） |
| `email_verified` | bool | **False** | 点验证邮件 | ❌ **零影响**（见 §5.2） |

⚠️ **`role='admin'` ≠ 管理员权限**。`IsAdminOrReadOnly` / `IsStaffUser` / `IsAdminUser` **只看 `is_staff`**，完全不看 `role`。

### 真实的身份组合（8 种，全部实测）

| # | 身份 | 怎么产生 | 后端"内部人"? | 前端能进内部台? |
|---|---|---|---|---|
| 1 | 匿名 | — | ❌ | ❌ |
| 2 | 已注册未验证 | 注册后未点邮件 | **登录被拒**（`LoginView` 校验） | ❌ |
| 3 | researcher（solo） | 注册选 Independent | ❌ | ❌ |
| 4 | researcher + `is_org_admin` | 建房/被授 | ❌ | ❌ |
| 5 | procurement（`is_staff=False`） | Django admin 授予 | ⚠️ **部分** | ✅ |
| 6 | admin（`role='admin'`, `is_staff=False`） | Django admin 授予 | ⚠️ **部分** | ✅ |
| 7 | `is_staff=True`（role 任意） | Django admin 勾选 | ✅ **全部** | ✅ |
| 8 | superuser | `createsuperuser` | ✅ **全部** | ✅ |

**#5/#6 是断层**：前端按 `INTERNAL_ROLES = ['procurement','admin']` 放行 ⇒ 19 个内部页都能进；
后端 209 个 `IsAdminOrReadOnly` 的写 + 7 个 `IsStaffUser` + 15 个 `IsAdminUser` 全部 403。
**准确地说不是"什么都不能改"，而是"能改的只有采购/订单那一条链"**（§2 有精确数字）。

---

## 2. 八种权限类（判据 + 实测端点数）

| 权限类 | 判据（源码） | 端点数 | 谁能过 |
|---|---|---|---|
| `AllowAny` | — | **42** | 所有人（含匿名） |
| （未声明，落 DRF 默认 AllowAny） | — | **1** | `POST /quote-requests/`（匿名可提交询价，设计如此） |
| `IsAuthenticated` | 已登录 | **36** | 任何已验证用户 |
| **`IsAdminOrReadOnly`** | 读=任何人；**写=`is_staff`** | **209**（62%） | 写：**只看 `is_staff`** |
| `IsAdminUser`（DRF 内置） | `is_staff` | **15** | 只看 `is_staff` |
| `IsProcurementOrAdmin` | `is_staff` **OR** `role∈(procurement,admin)` | **16** | 内部人 |
| `IsStaffUser` | `is_staff` | **7** | 只看 `is_staff` |
| `AddressPermission` | 登录即可（机构隔离靠 queryset） | **6** | 登录即可 |
| `IsSuperUser` | `is_superuser` | **2** | 超管（产品 hard-delete） |
| `IsAdmin` | `is_staff` **OR** `role=='admin'` | **1** | `assign-rep` |

**合计 335 个 path×method。**

### 2.1 判据不一致（同一句话三种写法）

| 想表达"内部人" | 实际判据 | 出现在 | 端点数 |
|---|---|---|---|
| A | `is_staff` | `IsAdminOrReadOnly` / `IsAdminUser` / `IsStaffUser` | **231** |
| B | `is_staff` **or** `role∈(procurement,admin)` | `IsProcurementOrAdmin` / 前端 `internalAccess.js` | **16** |
| C | `is_staff` **or** `role=='admin'` | `IsAdmin` | **1** |

⇒ **同一个用户（#6）在 A 口径下是外部人，在 B/C 口径下是内部人。** 这不是笔误，是三种实现并存。

### 2.2 实测：每个身份能过多少端点（`role_capability_probe.py` 输出）

| 身份 | 读通过 | 写通过 | 被拒主因（权限类:端点数） |
|---|---|---|---|
| anon | 117/132 | **7/203** | `IsAdminOrReadOnly`:128, `IsAuthenticated`:36, `IsProcurementOrAdmin`:16, `IsAdminUser`:15, `IsStaffUser`:7 |
| unverified | 123/132 | 43/203 | `IsAdminOrReadOnly`:128, `IsProcurementOrAdmin`:16, `IsAdminUser`:15, `IsStaffUser`:7, `IsSuperUser`:2 |
| researcher | 123/132 | 43/203 | 同上（**与 unverified 完全相同**） |
| org_admin | 123/132 | 43/203 | 同上（**与 researcher 完全相同**） |
| **procurement** | 128/132 | **54/203** | `IsAdminOrReadOnly`:128, `IsAdminUser`:15, `IsStaffUser`:7, `IsSuperUser`:2, `IsAdmin`:1 |
| **admin_role** | 128/132 | **55/203** | 同上但**少了 `IsAdmin`:1**（它能调 assign-rep） |
| staff | **132/132** | **201/203** | `IsSuperUser`:2 |
| superuser | **132/132** | **203/203** | — |

**三条从数字里直接读出来的事实**：
1. `unverified` 与 `researcher` **逐项相同** ⇒ `email_verified` 在 API 层**零影响**，只在 `LoginView` 拦一次；已发出去的 token 在邮箱被置否后**仍然全权可用**。
2. `org_admin` 与 `researcher` **逐项相同** ⇒ `is_org_admin` **零影响**（grep 双重确认，见 §5.4）。
3. `procurement` 与 `admin_role` 差 **1** 个端点 = `POST /orders/:id/assign-rep/`（`IsAdmin`）。
   ⇒ **role=admin 相对 procurement 的全部优势，只有这一个按钮**，而它在前端**没有任何入口**（孤儿）。

**匿名可写的 7 个端点**（逐个核对，全部为设计如此）：`auth/login`、`auth/register`、
`auth/resend-verification`、`basket/items`(POST/PATCH/DELETE，靠 `X-Session-Key`)、`quote-requests/`(未声明)。

---

## 3. 前后端权限粒度不匹配

```
前端：2 级                    后端：8 类判据
├─ requiresAuth  10 页面      ├─ AllowAny            42 + 1
└─ requiresAdmin 19 页面      ├─ IsAuthenticated     36
   （8 个 /ops                 ├─ is_staff 系        231
     + /workspace 壳           ├─ role∈(...)系        16
     + 10 个子页）              └─ superuser            2
```

前端**没有**"按 role 细分"的守卫 —— 不存在"只有 admin 能进、procurement 进不了"的页面。
所有更细的判定都发生在**调 API 时**（403）。

**后果**：#5/#6 能打开全部 19 个内部页，但其中 **3 个进去就是空白**、**9 个是只读**（§8 逐页列出）。
用户看到的是"页面能进、按钮点了没反应、表格还没数据"。

---

## 4. 页面清单（实测）

### 4.1 内部台 `requiresAdmin`（**19 个实际页面**）

`router/index.js:322` 判定，口径 = `utils/internalAccess.js` 的 `isInternal()`。
⚠️ `/workspace` 是**父级壳**（`meta.requiresAdmin`），10 个子页自身不带 meta、**继承**该守卫。

| # | 页面 | 路径 | 组件 | 主要能力 |
|---|---|---|---|---|
| 1 | 工作台首页 | `/workspace` | `DashboardPage.vue` | 统计卡 + 最近产品 |
| 2 | 产品管理 | `/workspace/products` | `ProductsPage.vue` | 归档/恢复/停用/删除/批量 AI |
| 3 | 产品新建 | `/workspace/products/new` | `ProductEditPage.vue` | 全字段 + AI AUTO MATCH + COA/SDS |
| 4 | 产品编辑 | `/workspace/products/:id/edit` | 同上 | 同上 |
| 5 | 研究目标 | `/workspace/goals` | `GoalsPage.vue` | CRUD |
| 6 | 应用 | `/workspace/applications` | `AppsPage.vue` | CRUD |
| 7 | 方法 | `/workspace/methods` | `MethodsPage.vue` | CRUD |
| 8 | 实验方案 | `/workspace/protocols` | `ProtocolsPage.vue` | CRUD |
| 9 | 文献 | `/workspace/references` | `ReferencesPage.vue` | CRUD |
| 10 | 已验证适用性 | `/workspace/verified` | `VerifiedPage.vue` | 审核/拒绝 |
| 11 | 知识录入 | `/workspace/knowledge-intake` | `KnowledgeIntake.vue` | 批量录入 |
| 12 | 订单管理 | `/ops/orders` | `AdminOrdersPage.vue` | 全库订单 |
| 13 | 订单详情 | `/ops/orders/:id` | `AdminOrderDetail.vue` | 报价/审批/发货/开票/收款 |
| 14 | PO 审核台 | `/ops/po/review` | `PoReviewDesk.vue` | 审批/拒绝/指派 |
| 15 | 发货台 | `/ops/po/shipments` | `PoShipmentDesk.vue` | 建发货/标记发出/送达 |
| 16 | 开票台 | `/ops/po/invoicing` | `PoInvoicingDesk.vue` | 开票/记录收款 |
| 17 | AR 账龄 | `/ops/po/ar` | `PoArReport.vue` | 应收聚合 |
| 18 | 机构管理 | `/ops/po/organizations` | `PoOrgManagement.vue` | 机构列表 + 按机构查单 |
| 19 | 库存台 | `/ops/inventory` | `InventoryDesk.vue` | 入库/盘点/备货/流水 |

### 4.2 需登录 `requiresAuth` 且非内部（10 个）

`/settings`、`/checkout`、`/orders`、`/orders/:id`、`/po/submit`、`/po/orders`、
`/po/orders/:id`、`/po/addresses`、`/po/reorder`、`/po/downloads`

### 4.3 公开（23 个，另加 404）

`/`、`/products`、`/products/:id`、`/applications`、`/applications/:id`、`/applications/classes/:class_id`、
`/methods`、`/methods/:id`、`/protocols`、`/protocols/:id`、`/research-goals`、`/research-goals/:id`、
`/research-goals/classes/:class_id`、`/search`、`/login`、`/register`、`/verify-email`、`/cart`、
`/wishlist`、`/quote-request`、`/about`、`/privacy`、`/terms`

---

## 5. 逐角色：能进什么、能做什么、流程对应哪些页面

### 5.1 匿名
- **页面**：仅 4.3 的 23 个
- **API**：`AllowAny` 43 + `IsAdminOrReadOnly` 的**读**（209 个端点的 GET）⇒ 读 117/132 通过
- **写**：只有 7 个（见 §2.2），全是登录/注册/询价/匿名购物车
- **流程**：浏览目录 → 搜索 → 加购物车（`X-Session-Key` 匿名会话）→ 注册/登录
- **边界**：`/checkout` 需登录；`/cart` 匿名可用但 `/checkout` 不能

### 5.2 已注册未验证（`email_verified=False`）
- **页面**：与匿名相同（**登录被硬拦截**，`LoginView` 校验 `email_verified`）
- **流程**：只能"查收验证邮件 → 点链接"
- **实测事实**：**权限层与 researcher 逐项相同**（123/43）。`email_verified` **不是权限维度**，
  只是登录闸门 ⇒ 若某用户已登录后邮箱被置否，**其 token 仍全权可用**
- **风险点**：这条路径现有用例仅 1 个（`verify-improvements`）

### 5.3 researcher（solo，绝大多数客户）
- **页面**：23 公开 + 10 客户侧
- **API**：`IsAuthenticated` 36（只能碰自己的资源，靠 `get_queryset` 收窄）+ 公开读
- **典型流程**：搜索 → 加购 → `/checkout` 下单 → `/orders` 看单 → `/po/submit` 提 PO → `/po/addresses` 管地址
- **实测可用写操作**：43/203 —— 全部集中在"购物车 / 下单 / 地址 / 个人资料 / 询价"

### 5.4 researcher + `is_org_admin`
- **与 5.3 完全相同**（实测逐项相同：读 123/132、写 43/203）
- **为什么**：`is_org_admin` 全仓只出现在 4 处，**没有一处是权限判据**：
  - `accounts/models.py:87` 字段定义
  - `accounts/admin.py:37,38,43` Django admin 展示/筛选
  - `accounts/api/v1/serializers.py:217,237,247,269` 注册/加入机构时写入 + 序列化输出
  - `accounts/api/v1/views.py:308` 建房时置 True
  - 前端：`stores/auth.js:26` 取字段 → `SettingsPage.vue:564` **只显示一个 "Admin" 徽章**
- ⇒ **该字段目前是纯展示字段，对权限零影响。机构管理员没有任何特权。**

### 5.5 procurement（`is_staff=False`）
- **页面**：19 个内部台**全部能进**（`internalAccess` 认 `role∈(procurement,admin)`）
- **API**：16 个 `IsProcurementOrAdmin` 全通；231 个 `is_staff` 系全拒
- **实测**：读 128/132、写 **54/203**
- **能用的页面（16 个）**：库存台、PO 审核台、发货台、开票台、AR 账龄、机构管理（全部 `IsProcurementOrAdmin`）
- **坏掉的页面（3 个）**见 §8.1：订单管理、订单详情、已验证适用性 —— **进去即空白**
- **只能看不能改的页面（9 个）**：产品/知识实体全部 CRUD、工作台统计卡

### 5.6 admin（`role='admin'`，`is_staff=False`）—— 断层组合
- 与 5.5 几乎相同；**唯一差别 = `assign-rep` 这 1 个端点**（`IsAdmin`）
- 写 **55/203**
- **"指派销售"按钮实测存在**（`PoReviewDesk.vue:94` `<button>Assign Rep</button>`，`api/adminPo.js:26-27`），
  且**没有任何角色条件渲染** ⇒ 对 admin(role) 可用、对 procurement **必 403 的死按钮**
- 坏掉/只读页面与 5.5 基本相同（少 1 个只读：PO 审核台对它全通）

### 5.7 `is_staff=True`（真正的内部员工）
- **读 132/132、写 201/203** —— 只有 2 个 `IsSuperUser`（产品 hard-delete）过不去
- **流程**：`/workspace` 全功能（产品/知识实体 CRUD、AI、verified 审核）→ `/ops/*` 全流程
- 这是**设计意图中的"内部员工"**

### 5.8 superuser
- 5.7 全部 + 产品 hard-delete（`IsSuperUser` 2 个端点）+ Django admin
- 注意：`hard-delete` **有端点、无前端入口**（孤儿），见 §6 #6

---

## 6. 已知不一致与风险（都要在测试方案里覆盖）

| # | 事实 | 代码依据 | 后果 |
|---|---|---|---|
| 1 | **`role` 只影响 17 个端点**，其余 231 个写操作只看 `is_staff` | §2 实测 | `role=admin` 能改 **55/203**，剩下 148 个点不动 |
| 2 | **前端守卫比后端粗**（2 级 vs 8 类） | `router/index.js:322` | 19 个内部页里 3 个空白、9 个只读，用户无解释 |
| 3 | **`is_org_admin` 对权限零影响** | 全仓无权限类引用 + 探针数字与 researcher 相同 | 机构管理员**没有任何特权**，纯展示字段 |
| 4 | **`email_verified` 只在登录处校验** | 探针 unverified == researcher | 邮箱被置否的已登录用户仍全权可用 |
| 5 | 同一概念三种判据（A/B/C） | `core/permissions.py` | 改一处口径不会同步另两处 |
| 6 | **`hard-delete` 是**真孤儿**（前端 0 引用）；`assign-rep` 有按钮但无角色条件渲染** | `IsSuperUser` 2 / `IsAdmin` 1；`grep hard-delete frontend/src` = 0 命中 | 超管独有能力完全打不到；procurement 看到一个**必 403 的死按钮** |
| 7 | **同一业务两套订单 API**：`/admin/orders/`（`IsAdminUser`）vs `/orders/`（`IsProcurementOrAdmin`） | `api/orders.js:58` vs `api/adminPo.js:33` | 采购在"订单管理"页 403，在"PO 审核台"却正常（§8.1） |
| 8 | `KnowledgeIntake` 页面守卫是内部台，但 `POST /knowledge-intake/` 是 `IsAdminUser` | `router:279` vs 探针 | 非 staff 内部人**录入必 403** |

---

## 7. 对测试方案的直接推论

**现有 E2E 覆盖到的身份**：匿名（`permission-matrix`）、researcher、staff（`loginAsStaff`）。
⇒ **procurement / admin(role) / org_admin / 未验证 这 4 个身份，页面级 E2E 覆盖为零。**

**必须补的按角色用例（按缺陷严重度排序）**：

| 优先 | 身份 × 场景 | 要断言什么 | 为什么 |
|---|---|---|---|
| P0 | procurement 打开 `/ops/orders` | **不能**出现空白表 + 无提示；要么 403 提示、要么能看 | 实测 DEAD |
| P0 | procurement 打开 `/workspace/verified` | 同上 | 实测 DEAD |
| P0 | procurement 进 `/workspace/products/:id/edit` 点保存 | 要么按钮禁用 + 说明，要么成功 | 实测 21 个写全 403 |
| P0 | procurement 点 "Assign Rep"（PO 审核台） | 要么按钮不渲染，要么点击有明确 403 提示 | 实测死按钮 |
| P0 | admin(role) 点 "Assign Rep" | **成功**（唯一独有能力） | 实测端点过、按钮在 |
| P1 | org_admin 与 researcher 逐页对比 | **行为完全一致**（当前就该一致；若将来不为此则本用例会红，是好事） | 锁定"零影响"这一事实 |
| P1 | 邮箱被置否的已登录用户 | 明确期望：能继续用 / 或立即失效 | 当前是"能继续用"，可能非预期 |
| P1 | superuser 调 hard-delete | 端点可用；但**前端 0 引用** ⇒ 决定是否补入口 | 真孤儿能力 |
| P2 | 未验证用户全路径 | 登录被拒 + 提示文案 | 仅 1 个用例 |

---

## 8. 页面 × 角色实测矩阵（`page_role_matrix.py` 输出）

**判定口径**：
- `DEAD` = 进入页面时的**首屏读请求全部 403** ⇒ 用户看到空白/骨架屏
- `READONLY` = 能看数据，但有写操作 403 ⇒ "按钮点了没反应"
- `OK` = 所有请求都不会被 403 挡（**不等于业务成功**，见 §0 的边界说明）

### 8.1 procurement / admin(role)（`is_staff=False` 的内部人）

| 页面 | 判定 | 首屏读 | 写 | 403 的端点 |
|---|---|---|---|---|
| `/ops/orders` | **DEAD** | 0/1 | — | `GET /admin/orders/` ← `IsAdminUser` |
| `/ops/orders/:id` | **DEAD** | 0/1 | 7/9 | `GET /admin/orders/:id/`、`complete`、`quote` ← `IsAdminUser` |
| `/workspace/verified` | **DEAD** | 0/1 | 0/2 | `GET /verified/`、`approve`、`reject` ← `IsStaffUser` |
| `/workspace`（首页统计） | READONLY | 1/2 | — | `GET /admin/dashboard-stats/` ← `IsStaffUser` |
| `/workspace/products` | READONLY | 5/5 | **0/7** | 归档/恢复/停用/删除/批量 ← `IsAdminOrReadOnly` |
| `/workspace/products/*/edit` | READONLY | 10/10 | **0/21** | 保存/新建/parse-word/SEO/AI/COA/SDS/verified 全拒 |
| `/workspace/goals` | READONLY | 1/1 | 0/2 | 新建/编辑 ← `IsAdminOrReadOnly` |
| `/workspace/applications` | READONLY | 2/2 | 0/2 | 同上 |
| `/workspace/methods` | READONLY | 2/2 | 0/2 | 同上 |
| `/workspace/protocols` | READONLY | 2/2 | 0/2 | 同上 |
| `/workspace/references` | READONLY | 1/1 | 0/2 | 同上 |
| `/workspace/knowledge-intake` | READONLY | 1/1 | 0/1 | `POST /knowledge-intake/` ← `IsAdminUser` |
| `/ops/po/review` | READONLY（仅 procurement） | 1/1 | 2/3 | `assign-rep` ← `IsAdmin`（admin_role 下为 **OK**） |
| 其余 6 个 `/ops/*` | **OK** | ✓ | ✓ | — |

**⇒ 19 个内部页里：3 个空白、9 个只读、7 个正常。** 这就是"按角色拟人化测试"要抓住的准确位置。

### 8.2 researcher / org_admin / 未验证 / 匿名

| 页面 | 判定 | 说明 |
|---|---|---|
| 全部 10 个客户侧页 | **OK** | 下单/地址/PO 提交/下载都通（researcher 与 org_admin 逐项相同） |
| `/cart` | OK | 匿名也能用（`X-Session-Key`） |
| 全部 19 个内部页 | 打不开 | 路由层 `isInternal()` 就踢回首页 —— **这一层是正确的** |

### 8.3 staff / superuser

**29 个页面全部 OK**（本批 21 个组件 + 其余客户侧页），无一个 403。

### 8.4 这一节没覆盖到的（诚实声明）

- `AddressPermission` 的**机构隔离**（能改自己机构的地址，改不了别人的）—— 需真实对象，探针测不到
- 客户只能看**自己的**订单（`get_queryset` 收窄）—— 探针测不到
- 页面内**组件级条件渲染**（如"指派销售"按钮是否真的渲染出来）—— 静态提取只能到调用点
- 数据为空时的空态、加载失败的重试 —— 属交互层，不在权限矩阵范围
