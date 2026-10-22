# SciReAgent 全站角色与功能操作说明书

**版本** V2.0 · **生成日期** 2026-10-22 · **对应代码** `cc4e8f2`
**性质** 操作说明书（不是设计草案、不是改造建议）。每一条都对应现有代码。
**配套** `ROLE_CAPABILITY_MATRIX.md`（权限事实基线）、`PAGE_API_MAP.json`（页面↔API 机读表）
**测试方案（本文的下游）** [`GLOBAL_TEST_PLAN_V3.md`](./GLOBAL_TEST_PLAN_V3.md)（以本文为索引的全局覆盖 + 缺口）、[`PERSONA_TEST_PLAN.md`](./PERSONA_TEST_PLAN.md)（8 个角色的拟人化脚本）

> **V2.0 修订（2026-10-22，手册化）——为什么升大版本**
> V1.x 是"事实与证据文档"：结论可靠，但**当手册用不合格**——没有目录、没有反查入口、
> 每段都插实测编号。V2.0 在不改动任何已实测事实的前提下，补了四样手册必备的东西：
> 1. **[目录](#目录按章节号-ctrlf-跳转)**（22 条，全部指向真实存在的标题，脚本校验 58/58 有效）
> 2. **[任务索引](#任务索引我想做什么去哪)**：28 个"我想做 X → 谁有权限 → 去哪个页面 → 详见哪节"
> 3. **[第 12 章 页面索引](#第-12-章-页面索引按页面反查)**：**52 个页面逐页**反查（谁能进 / 能干什么 / 调什么接口）
> 4. **[附录 F 错误提示对照表](#附录-f-错误提示对照表)**：看到什么提示 → 什么原因 → 怎么办
> 5. 每角色的"**一天/一周工作流**"（§1.0 / §3.0 / §5.0 / §7.0），把零散流程按真实时序串起来
> 另新增 [附录 G 术语表](#附录-g-术语表)、[附录 H 本地环境与实验栈](#附录-h-本地环境与实验栈)，
> 并把附录顺序调整为 A→B→C→D→E→F→G→H。
>
> **V1.4 修订（2026-10-22，凭据到位后补完最后两项 + 修正一处错结论）**
> 1. **生产登录态只读**已实测（`Authorization: Basic` + `X-Auth-Token` 两层头）：
>    生产**公开产品 0 条 / 回收站 125 / 库存 0 / 订单 16 / COA 33 / SDS 12**；
>    `site/navigation` **18.6 KB**、`sitemap.xml` **511 字节** ⇒ 之前两处性能修复在生产确已生效 `[M-71~M-75]`
> 2. ★ **`admin / admin123` 在生产可登录**（`is_staff=true`+`is_superuser=true`）—— 默认口令未改，安全缺陷 `[M-72]`
> 3. ★ **修正 V1.3 的错结论**：V1.3 写"并发写会 500"，那是**只测了 SQLite**。
>    换到项目已有的 PG（`pgdata-l4:5433`）重测：**库存 10 并发全部成功、总量 +10；PO 10/10 建成**，
>    `run_pg_tests.py` **6/6 通过零 skip** ⇒ **500 是本地 SQLite 特性，不是应用缺陷** `[M-50 修正]`
> 4. 现只剩 **1 项**未测：生产环境的**写**操作（主动不做，会污染真实数据）
>
> **V1.3 修订（2026-10-22，第二轮实测：把 V1.2 §D.5 列的"未覆盖 7 项"补掉 5 项）**
> 本轮新做的实测与结论：
> 1. **对象级权限 / queryset 收窄**（上轮最大的空白）：造真实跨机构对象后打，隔离全部生效；
>    跨机构 404、同机构第二人可改、甚至 staff 也读不到客户地址 `[M-30~M-35]`
> 2. **邮件链路**：`EmailTemplate` 表 **0 条**、`EmailOutbox` **2984 封全 pending 且历史零发送**；
>    跑一次发送命令 → 发出的是**空主题空正文** `[M-40~M-42]`
> 3. **跨浏览器**：chromium / firefox / webkit 三家 **12/12 全通过、事实一致** `[M-60]`
> 4. **视觉/响应式**：72/72 通过（边界：只验"加载不崩 + 令牌一致"，非像素级回归）`[M-61]`
> 5. **并发**：SQLite 下 10 并发写入 → 8~9 个 **500 `database is locked`** `[M-50]`
> 6. **生产**：10 条路径**全部 401 `Basic realm="SciReAgent Internal Test"`** ⇒ 站点仍是内部测试态 `[M-70]`
>
> 仍剩 2 项未覆盖，且都有明确阻塞：**生产登录态/写操作**（无凭据，不猜口令）、
> **PG 并发互斥**（`initdb` 被本机安全策略拦截）。见实测清单 §10。
>
> **V1.2 修订（2026-10-22，实测层接入）**
> 在这一版之前，本文所有结论都是**读代码 + 权限类求值**得来，没有一条在真实浏览器/真实 HTTP 里验过。
> V1.2 补上了实测：起独立 DB 副本 + 独立后端(8011) + 独立前端(5174)，用 7 个构造账号做
> **8 身份 × 199 端点的真实 HTTP 探测** 与 **Playwright 真实点击**，证据全部落在
> `MANUAL_FACTS_MEASURED.md`（下称「实测清单」），正文以 `[M-nn]` 引用。
>
> 实测**推翻/修正了 8 处**表述，最要紧的三条：
> 1. procurement 打开订单管理页**不是白屏**，而是"0 行 + 错误横幅 + `No orders found` 空态"并列 —— 后者会让人误以为全库真没订单 `[M-10]`
> 2. `POST /api/v1/verified/` **不是 staff 专属**，任何登录用户都能建 review 草稿（201 实测建成功） `[M-15]`
> 3. 未验证用户**根本拿不到 token**，"API 权限与 researcher 相同"只在权限类层面成立，HTTP 层不可达 `[M-04]`
>
> 另新发现一条缺陷：`Assign Rep` 填用户名（非数字 ID）⇒ **500 + HTML 错误页** `[M-21]`
>
> **V1.1 修订（2026-10-22，同日二次审计）**
> V1.0 有 **8 处**事实错误 / 表述不精确 / 遗漏，已全部修正，明细见**附录 D**。其中影响最大的一条：
> V1.0 把"页面没写 try/catch"写成"用户看不到任何反馈"——**错**。
> 前端有全局错误拦截器，403/404/5xx 都会弹 toast，401 还会强制整页跳转。
> 真正静默的只有"请求根本没发出"的前端早退。修正涉及 §0.6（新增）、§5.2、§7.8.3、§11.2 共 19 处。

---

---

## 目录（按章节号 Ctrl+F 跳转）

| 章 | 标题 | 一句话说明 |
|---|---|---|
| **[第 0 章](#第-0-章-系统总览)** | 系统总览 | 有多少页面、多少种身份、权限怎么判、数据怎么流 |
| **[第 1 章](#第-1-章-匿名访客)** | 匿名访客 | 不登录能干什么：浏览 / 搜索 / 加购 / 询价 / 注册 |
| **[第 2 章](#第-2-章-已注册未验证用户)** | 已注册未验证 | 为什么登不进去、怎么让用户通过验证 |
| **[第 3 章](#第-3-章-researcher普通客户绝大多数用户)** | researcher（客户） | 下单 / 看单 / 提 PO / 地址 / 下载 / 收藏 |
| **[第 4 章](#第-4-章-researcher-is_org_admin机构管理员)** | 机构管理员 | **结论：这个身份没有任何额外权限** |
| **[第 5 章](#第-5-章-procurement采购经理is_staff-false)** | procurement（采购） | 履约主线：审批 / 发货 / 开票 / 收款 / 库存 |
| **[第 6 章](#第-6-章-adminroleadminis_stafffalse)** | admin（`role=admin`） | 只比采购多一个"指派销售"按钮 |
| **[第 7 章](#第-7-章-staff内部员工is_staff-true)** | staff（内部员工） | 全功能：产品 / 知识实体 / 合规文档 / 全部订单 |
| **[第 8 章](#第-8-章-superuser)** | superuser | 多一个无入口的物理删除 + Django admin |
| **[第 9 章](#第-9-章-跨角色闭环同一业务在多个角色间的传递)** | 跨角色闭环 | 一件事在角色之间怎么流动（接缝在哪） |
| **[第 10 章](#第-10-章-权限速查总表)** | 权限速查总表 | 8 身份 × 30 个关键动作，一页看完 |
| **[第 11 章](#第-11-章-已知限制与常见故障参考章非操作步骤)** | 已知限制与常见故障 | 死按钮 / 假成功 / 能力缺口 / 生产状态（参考章） |
| **[第 12 章](#第-12-章-页面索引按页面反查)** | **页面索引（按页面反查）** | **52 个页面逐页：谁能进、能做什么、调什么接口** |
| [附录 A](#附录-a-状态机全表) | 状态机全表 | Order / CoA / SDS / verified 的合法流转 |
| [附录 B](#附录-b-端点索引按业务域) | 端点索引 | 按业务域查 336 个端点的权限 |
| [附录 C](#附录-c-如何复核本文) | 如何复核 | 每类结论怎么自己重跑一遍 |
| [附录 D](#附录-d-本轮审计记录v10-v11) | 审计记录 | 我们自己写错过什么、怎么改的 |
| [附录 E](#附录-e-实测证据索引) | 实测证据索引 | `[M-nn]` 编号去哪查 |
| [附录 F](#附录-f-错误提示对照表) | **错误提示对照表** | **看到什么提示 = 什么原因 = 怎么办** |
| [附录 G](#附录-g-术语表) | 术语表 | RG / AP / PMR / COA / RUO 等 |
| [附录 H](#附录-h-本地环境与实验栈) | 本地环境与实验栈 | 想自己复跑实测要准备什么 |

---

## 怎么用这份文档

**你是运营 / 客服** → 先看 [任务索引](#任务索引我想做什么去哪)，再翻对应角色的章节；遇到报错查 [附录 F](#附录-f-错误提示对照表)。
**你是开发** → 看 [第 12 章页面索引](#第-12-章-页面索引按页面反查) + [附录 B 端点索引](#附录-b-端点索引按业务域)；改权限前必读 [第 0.4 节](#04-权限判定机制)。
**你要写汇报 / 对外说明** → 只能说"**开发测试态 + 种子数据**"。理由见 [第 11.6 节](#116-生产环境当前状态全站-401仍是内部测试态)：生产全站挂着 Basic 认证，匿名用户连首页都打不开。
**你要判断"这个功能能不能用"** → 认证据等级：`[M-nn]` 是实测可查，`[E]` 是权限类求值，`[S]` 是读码推断。没标记的按 `[S]` 对待。

> 一条硬规矩：**本文任何"能不能"的结论，都以"当前代码 + 当前配置"为准**。
> 权限改了口径，先跑 `scripts/role_capability_probe.py` 与 `scripts/http_role_probe.py` 复验，再改文档。

---

## 任务索引（我想做什么，去哪）

> 按"你要完成的事"反查：先看左边，再跳到对应章节；"能不能做"那一列是**由你的身份决定的**。

| 我想做… | 谁能做 | 去哪个页面 | 详细步骤 |
|---|---|---|---|
| 看有哪些试剂、查 CAS | 任何人 | `/products` `/search` | [F1-2](#f1-2-浏览产品列表与筛选) [F1-4](#f1-4-搜索分组搜索) |
| 加购物车 | 任何人（含匿名） | 产品详情 `Add to Cart` | [F1-6](#f1-6-加入购物车匿名) |
| 直接下单（不用 PO） | 已登录客户 | `/checkout` | [F3-4](#f3-4-结账下单核心流程) |
| 用采购单（PO）下单 | 已登录客户 | `/po/submit` | [F3-7](#f3-7-提交-po客户门户的核心动作) |
| 看自己的订单进度 | 已登录客户 | `/orders` `/po/orders` | [F3-5](#f3-5-查看订单列表) [F3-8](#f3-8-查看-po-单) |
| 下载发票 / PO 附件 | 已登录客户 | `/po/downloads` | [F3-11](#f3-11-下载中心) |
| 改收货地址 | 已登录客户 | `/po/addresses` | [F3-10](#f3-10-地址簿-crud) |
| 接受 / 拒绝报价 | 已登录客户 | `/orders/:id` | [F3-6](#f3-6-订单详情-报价应答) |
| 改个人资料 | 已登录客户 | `/settings` | [F3-2](#f3-2-管理个人资料5-个-tab) |
| **改密码 / 找回密码** | ⚠️ **没人能自助** | — | 见 [11.3.0](#1130-最严重账号自救能力为零)：只能运维上 Django admin |
| 审批客户的 PO | staff / procurement | `/ops/po/review` | [F5-1](#f5-1-审批-poopsporeview) [F7-8](#78-交易运营订单与-po8-个页面) |
| 发货 / 标记送达 | staff / procurement | `/ops/po/shipments` | [F5-2](#f5-2-发货opsposhipments) |
| 开票 / 记收款 | staff / procurement | `/ops/po/invoicing` | [F5-3](#f5-3-开票与收款opspoinvoicing) |
| 查应收账款账龄 | staff / procurement | `/ops/po/ar` | [F5-4](#f5-4-看应收账龄opspoar) |
| 按机构查订单 | staff / procurement | `/ops/po/organizations` | [F5-5](#f5-5-机构管理opspoorganizations) |
| 入库 / 盘点调整 | staff / procurement | `/ops/inventory` | [F5-6](#f5-6-库存管理opsinventory) |
| 看客户询价单（RFQ） | staff / procurement / admin(role) | `/ops/rfq` | [F5-7](#f5-7-询价单收件箱opsrfq) |
| 指派销售 | **staff / admin(role)** | `/ops/po/review` | [F6-1](#62-f6-1-指派销售本角色唯一专属流程) |
| 新建产品 | **仅 staff** | `/workspace/products/new` | [7.3](#73-产品新建全站最复杂的页面) |
| 从 Word 导入产品 | 仅 staff | 同上 `Word Import` | [7.3.2](#732-word-文档导入) |
| 用 AI 补全产品资料 | 仅 staff | 同上 `AI AUTO MATCH` | [7.3.3](#733-ai-auto-match一站式-enrich) |
| 改产品价格 / 加 SKU | 仅 staff | `/workspace/products/:id/edit` | [7.3.6](#736-sku-表section-7) |
| 上架 / 下架 / 删除产品 | 仅 staff | `/workspace/products` | [7.4](#74-产品管理列表页) |
| 生成 / 审批 COA 与 SDS | 仅 staff | 产品编辑页 Section 9 | [7.3.7](#737-合规文档section-9coa-sds) |
| 新建知识实体（RG/AP/Method/Protocol/Ref） | 仅 staff | `/workspace/{goals,applications,methods,protocols,references}` | [7.5](#75-知识实体-crud5-个页面) |
| 审核 verified 适用性 | 仅 staff | `/workspace/verified` | [7.6](#76-verified-适用性审核) |
| 批量录入知识 | 仅 staff | `/workspace/knowledge-intake` | [7.7](#77-知识录入knowledge-intake) |
| 分配角色 / 给某人 is_staff | **仅 superuser** | Django admin → Users | [8.3.1](#831-怎么给一个人授予采购管理员权限分步)（**改完要让对方重登**） |
| 物理删除产品 | superuser（**但无 UI**） | — | [8.2](#82-f8-1-物理删除产品-有端点无-ui) |
| 退出登录 | 所有已登录 | 右上角头像下拉 `Sign Out` | [0.7](#07-全角色通用动作登出与会话失效) |

---

## 角色速查（30 秒判断"这个人能干什么"）

| 身份 | 一句话 | 能进内部台吗 | 能改产品吗 | 能履约订单吗 |
|---|---|---|---|---|
| 匿名 | 只能逛 | ❌ | ❌ | ❌ |
| 已注册未验证 | **登不进去** | ❌ | ❌ | ❌ |
| researcher | 正常客户 | ❌ | ❌ | ❌（只能下自己的单） |
| researcher + 机构管理员 | **与普通客户完全一样** | ❌ | ❌ | ❌ |
| procurement | 采购：只管履约 | ✅ 19 页里能用 7 页 | ❌ | ✅ |
| admin（`role=admin`） | 采购 + 指派销售 | ✅ 同上 | ❌ | ✅ |
| staff | 内部员工 | ✅ 全 19 页 | ✅ | ✅ |
| superuser | staff + Django admin | ✅ | ✅（含物理删） | ✅ |

**记住三个反直觉的点**（都是实测确认的）：
1. **`role='admin'` 不是管理员**：231 个写操作只看 `is_staff`，`role` 只影响 17 个端点
2. **`is_org_admin` 没有任何权限效果**，只是 `/settings` 上一个展示徽章
3. **`email_verified` 不是权限维度**，它只是登录闸门（未验证=拿不到 token）


---

## 阅读说明

### 怎么保证"与代码相符"
本文不靠人工通读写成，而是三路取证后汇编：

| 取证手段 | 覆盖 | 落盘文件 |
|---|---|---|
| 权限类**实例化求值**（336 端点 × 8 身份） | 谁能调哪个端点 | `ROLE_CAPABILITY_MATRIX.json` |
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

### 证据等级（每条结论都标了，请按等级采信）

| 标记 | 含义 | 可信度 | 本章分布 |
|---|---|---|---|
| **`[M-nn]`** | **实测**：真实 HTTP 请求 / 真实浏览器点击观测到，出处在 `MANUAL_FACTS_MEASURED.md` | 高 | 权限矩阵、页面可用性、关键缺陷 |
| **`[E]`** | **求值**：实例化真实权限类调 `has_permission`，未发请求 | 中高（已用 HTTP 校核，一致度 99.7%） | 端点级权限归属 |
| **`[S]`** | **静态读码**：读源码/模板得出，未运行 | 中（可能漏掉运行时条件） | 字段、文案、状态机、条件渲染 |

> **一句话**：`[M]` 可以直接拿去决策；`[E]` 可以当事实用（已交叉验证）；`[S]` 请当成"待验证的线索"。
> 尚未实测的清单见实测清单 §4（共 7 项，含"生产环境完全未测"）。

**前提三：前端只有 2 级守卫，后端有 8 类判据**
⇒ 会出现"页面能进、按钮点了 403"。这不是 bug 的偶发表现，而是两层粒度不匹配的**结构性后果**。

---

# 第 0 章 系统总览

## 0.1 页面总表（52 个不同 URL 的页面 + 404；路由 name 声明 54 条）

| 分区 | 守卫 | 页面数 | 路径清单 |
|---|---|---|---|
| **公开** | 无 | **23** | `/`、`/products`、`/products/:id`、`/applications`、`/applications/:id`、`/applications/classes/:class_id`、`/methods`、`/methods/:id`、`/protocols`、`/protocols/:id`、`/research-goals`、`/research-goals/:id`、`/research-goals/classes/:class_id`、`/search`、`/login`、`/register`、`/verify-email`、`/cart`、`/wishlist`、`/quote-request`、`/about`、`/privacy`、`/terms` |
| **客户门户** | `requiresAuth` | **10** | `/settings`、`/checkout`、`/orders`、`/orders/:id`、`/po/submit`、`/po/orders`、`/po/orders/:id`、`/po/addresses`、`/po/reorder`、`/po/downloads` |
| **内部台** | `requiresAdmin` | **19** | 见 0.2 |
| 兜底 | — | 1 | `/:pathMatch(.*)*` → 404 |

📄 依据 `frontend/src/router/index.js`。**三组数字必须分清**（口径不同，别互相加减）：

| 计数口径 | 值 | 为什么是这个数 |
|---|---|---|
| `path:` 声明 | **56** | 含 `/login` 等重定向声明 |
| 路由 `name` 声明 | **54** | `/workspace` 同时挂了父级 `Workspace` 与子级 `Dashboard` 两个 name（同一 URL） |
| **不同 URL 的页面** | **53** | 23 公开 + 10 客户 + 20 内部；另加 1 个 404 兜底 |

> 逐页的"谁能进 / 能干什么 / 调什么接口"见 **[第 12 章 页面索引](#第-12-章-页面索引按页面反查)**。

⚠️ **易错点**：只数带 `meta.requiresAdmin` 的路由块会得到 **9**（8 个 `/ops` + `/workspace` 父级），实际是 **19** 个页面 —— 因为 `/workspace` 下有 **11 个页面**（`Dashboard` 本身 + 10 个子页），子页自身没有 meta、继承父级守卫。

## 0.2 内部台 19 页（8 个 `/ops` + 11 个 `/workspace` 页面）

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
| 20 | RFQ Inbox | `/ops/rfq` | `admin/RfqDesk.vue` | 询价线索 |

**内部台分为两条业务线，容易被混为一谈：**

| 业务线 | 页面 | 数据来源 | 权限口径 |
|---|---|---|---|
| **内容运营线** | 1–11 | `/products`、`/methods`、`/post`… 的 `IsAdminOrReadOnly` 系列 | 写 = `is_staff` |
| **交易运营线** | 12–20 | 两套并存：`/admin/orders/`（`IsAdminUser`）与 `/orders/`、`/quote-requests/manage/`（`IsProcurementOrAdmin`） | 部分只看 `is_staff`，部分收 `role` |

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

### 后端：8 类判据，336 个 path×method

| 权限类 | 判据 | 端点数 | 谁能过 |
|---|---|---|---|
| `AllowAny` | — | 42 | 所有人 |
| （未声明，落 DRF 默认） | — | 1 | `POST /quote-requests/` |
| `IsAuthenticated` | 已登录 | 36 | 任何登录用户 |
| **`IsAdminOrReadOnly`** | 读=任何人；**写=`is_staff`** | **209** | 写只看 `is_staff` |
| `IsAdminUser`（DRF 内置） | `is_staff` | 15 | 只看 `is_staff` |
| `IsProcurementOrAdmin` | `is_staff` **或** `role∈(procurement, admin)` | **17** | 内部人（2026-10-22 +1：`GET /quote-requests/manage/`） |
| `IsStaffUser` | `is_staff` | **6**（原记 7）| 只看 `is_staff`。★ 实测修正：`GET /verified/` 是它，但 **`POST /verified/` 只要登录**（`get_permissions()` 按方法分权）`[M-15]` |
| `AddressPermission` | 登录即可（机构隔离靠 queryset） | 6 | 登录即可 |
| `IsSuperUser` | `is_superuser` | 2 | 超管 |
| `IsAdmin` | `is_staff` **或** `role=='admin'` | 1 | `assign-rep` |

📄 依据 `backend/core/permissions.py`、`backend/apps/accounts/api/v1/views.py:315`（`AddressPermission`）

**这三种"内部人"写法并存** ⇒ 同一个用户在 A 口径下是外部人，在 B/C 口径下是内部人：

| 口径 | 表达式 | 端点数 |
|---|---|---|
| A | `is_staff` | 231 |
| B | `is_staff` or `role∈(procurement,admin)` | 17 |
| C | `is_staff` or `role=='admin'` | 1 |

### 前端：2 级 + 单一真相源

```
router.beforeEach（router/index.js:299）
├─ meta.requiresAuth  && !token  → /login?redirect=
└─ meta.requiresAdmin && !isInternal(auth) → /
```
`isInternal(auth) = Boolean(auth.isStaff) || ['procurement','admin'].includes(auth.role)`
📄 `frontend/src/utils/internalAccess.js:32-36`（`isInternal` 函数体；文件共 37 行）

**页面内还有第二道**：9 个 workspace 页面在 `setup` 里各自 `if (!isInternal(auth)) router.replace('/')`。
（2026-10-14 曾出现"路由放行但页面踢回"的分裂，现已统一调用同一函数。）

⚠️ **必须区分"能不能进页面"和"能点什么"——前端只有前者有机制，后者几乎没有。**

| 层次 | 机制 | 实测规模 |
|---|---|---|
| ① 能不能进页面 | `isInternal(auth)` 二次守卫写在每个页面 `setup` 里 | 9 个 workspace 页 + `AdminLayout` 各一份（共 10 处） |
| ② 页面内按角色显示/隐藏元素 | 只有 `ProductsPage.vue:666` 的 `v-if="canBatchAi"`（定义 `:547`） | **全站仅 1 处**，控制 2 个批量 AI 按钮 |
| ③ 其余所有按钮 | 无任何角色判断 | **全部按钮对所有能进页面的人一视同仁** |

补充：`views/po/*` 6 个客户侧页面 grep `role\|authStore\|isStaff\|isInternal` **零命中**。

> 所以采购进 `/workspace/products` 会看到「批量校验」「批量文献」两个按钮**根本不渲染**（②生效），但同页的归档/恢复/删除按钮**照常显示**、点了才 403（③的后果）。

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

## 0.6 全局请求与错误机制（所有角色共用，判断"为什么没反应"的前提）

前端**只有一个** axios 实例（`frontend/src/utils/http.js:9-10`，`baseURL = '/api/v1'`），
所有 `@/api/*` 都复用它（`api/http.js` 仅再导出）。⇒ **错误处理是全局的**：
**页面写不写 try/catch 并不决定"用户能不能看到提示"**，只决定"页面自己要不要额外处理"。

### 成功响应信封
```
{ success: true, data: {...}, meta: {...} }      // 常规
{ success: true }                                // 204 No Content（DELETE 等）
<裸 DRF 2xx>                                     // 无信封但 2xx，原样透传
```

### 错误响应信封（后端 `backend/core/exceptions.py:6-23` 统一包装）
```json
{"success": false, "data": null,
 "meta": {"error": {"code": "forbidden", "message": "...", "details": {...}}}}
```

| `code` | HTTP | 含义 |
|---|---|---|
| `validation_error` | 400 | 字段校验失败（`details` 里逐字段列出） |
| `unauthorized` | 401 | 未登录 / token 失效 |
| `forbidden` | 403 | 已登录但无权限 |
| `not_found` | 404 | 对象不存在（**也用于"无权限查看该对象"**，见下） |
| `conflict` | 409 | 冲突（如 PO 号唯一） |
| `rate_limited` | 429 | 触发限流（登录 5 次/分） |
| `server_error` | 500 | 服务端异常 |
| `error` | 其他 | 兜底 |

### 前端三段式处理（`frontend/src/utils/http.js:74-102`）

| 情形 | 前端行为 | 用户看到 |
|---|---|---|
| 2xx 但 `success:false` | 取 `meta.error.message` | 红色 toast |
| **401** | **清 `localStorage.token` + `window.location.href = '/login'`** | toast `Session expired, please sign in again`，随即**整页跳转** |
| 403 / 404 / 5xx / 网络错误 | `ElMessage.error(message \|\| 'Action failed')` | 红色 toast |

### 四条运营必须知道的推论

| # | 推论 | 依据 |
|---|---|---|
| 1 | **401 是整页跳转，未保存的表单会全部丢失**。产品编辑页这类长表单，token 一过期就等于白填 | `utils/http.js:88-95` |
| 2 | **401 跳转不带 `redirect` 参数** ⇒ 重新登录后回首页，不是回原页 | 同上（硬编码 `/login`） |
| 3 | **403 的文案是后端英文技术话术**（`You do not have permission to perform this action.`），不说明缺哪个权限、也不提示该找谁 | `core/exceptions.py` + DRF 默认文案 |
| 4 | **404 有时其实是"无权查看"**：对象级隔离靠 `get_queryset` 收窄，查不到就 404 ⇒ 客户看到"订单不存在"，真实原因可能是"不是你的订单" | `AddressPermission` 等类的设计 |

### 错误文案的提取与展开

- 消息提取降级顺序（`utils/http.js:40-63`）：`meta.error.message` → `meta.error` 里任一字符串 → `data.detail` → `data.message` → `Action failed`
- **字段级校验错误会被展开成人话**（后端 `core/exceptions.py:39-60`）：
  `{'catalog_no': ['该字段已存在']}` → `catalog_no: 该字段已存在`，不会把 Python repr 泄漏到弹窗

### 三种"没反应"必须分清（第 11.2 节据此分类）

| 类型 | 现象 | 有无 toast | 典型 |
|---|---|---|---|
| ① **前端早退** | 请求根本没发出 | **无** | Rep ID 为空、收款金额为空、库存数量为空 |
| ② **请求被拒** | 后端返回 4xx/5xx | **有**（401 还会跳页） | 采购点产品保存、`Assign Rep` 被 `IsAdmin` 挡 |
| ③ **成功但没体现** | 后端 200，界面没变 | 无（明明是成功） | 改密码假成功、`Internal Notes` 不落库 |

## 0.7 全角色通用动作：登出与会话失效

### 登出

| 步 | 操作 | 入口在哪（原文文案） | 请求 |
|---|---|---|---|
| 1 | 展开用户下拉 | 前台页：`PublicNav` 右上角；客户门户与 `/ops/*`：`AppHeader` 右上角头像（`.user-avatar`） | — |
| 2 | 点 `Sign Out` | `AppHeader.vue:174-180`、`PublicNav.vue:148` | `POST /auth/logout` |
| 3 | 完成 | — | 清 token + 用户态，跳 `/login` |

**⚠️ 内部台 `/workspace` 没有登出入口**：`AdminLayout.vue` 侧栏底部只有 `Back to Site`（`:101`），没有 `Sign Out`。
⇒ 在内容运营台里要登出，必须先点 `Back to Site` 回到前台，再从右上角下拉登出。

**接口失败不影响登出**：`stores/auth.js:158-166` 用 `try/catch` 包住，注释 `ignore logout API errors`，本地状态照样清空。

### 会话失效（非用户主动）

| 触发 | 后果 |
|---|---|
| 任何请求返回 401（token 过期/被吊销/服务端重启后失效） | 立刻清 token → 弹 `Session expired, please sign in again` → **整页跳 `/login`** |
| 此时页面有未保存内容 | **全部丢失**（整页跳转，不走路由） |
| 登录后落点 | 首页（`/login` 硬编码，不带 `redirect`） |

---

# 第 1 章 匿名访客

### 1.0 匿名访客能走多远（一条线看完）

```
首页 → 分类/搜索 → 产品详情（看 CAS/结构式/COA/SDS/知识关联）
     → 加购物车（X-Session-Key 识别，换浏览器即丢）
     → 想下单 ⇒ 被拦到 /login
     → 也可以直接提交询价 /quote-request（无需登录）
     → 或注册 → 验证邮箱 → 成为客户
```

| 能做 | 不能做 |
|---|---|
| 浏览 23 个公开页、搜索、看产品详情与文档 | 下单、看订单、进内部台 |
| 加购物车（匿名会话） | 收藏（点了提示"请先登录"） |
| 提交询价 RFQ | 看到别人的购物车 |
| 注册 / 登录 | 看 draft 状态的产品 |

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
⚠️ 请求失败时**页面无内联错误区**（`SearchPage.vue:68` 只写 console）；用户能看到的只有全局 toast（见 §0.6）。**结果区会停留在上一轮的旧结果**，容易被误读为"这次搜到的"。
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
⚠️ 失败时页面**不会切换成功态**（这一点是对的），但也没有内联错误区（`:104-105` 只 `console.error`）；用户看到的仅是全局 toast（§0.6），**填过的内容仍留在表单里**——是否重试全靠用户自己判断。

**从产品详情页带入**：URL 带 `product_id` 时，进入页面会 `GET /products/{id}` 预填一行；否则用购物车数据预填。
📄 `QuoteRequestPage.vue:29-64,78-106,115-206`

> **提交之后运营在哪看？** 见 **§F5-7 询价单收件箱（`/ops/rfq`）**（2026-10-22 新增）。
> 在此之前这条链路是**断的**：客户提交得到 `RFQ #id`，但内部侧没有任何页面能查，
> 详情接口也只对提交人可见（连 staff 都 404）—— 详见 §11.2 与 `UNIFIED_TEST_ENTRY.md` §1.4。

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

### F1-10 静态信息页与 404

这四个页面**没有任何业务动作**（不发请求、不写数据），但它们是公开路由的一部分，运营改文案时会碰：

| 页面 | 路径 | 组件 | 内容来源 | 请求 |
|---|---|---|---|---|
| About | `/about` | `AboutPage.vue` | 硬编码在模板里（公司定位、平台说明） | 无 |
| Privacy Policy | `/privacy` | `PrivacyPolicyPage.vue` | 硬编码 | 无 |
| Terms of Service | `/terms` | `TermsPage.vue` | 硬编码 | 无 |
| 404 | 任意未匹配路径 | `NotFound.vue` | 硬编码 | 无 |

**要点**：
- 三份法务/介绍文案**存在 Vue 组件里，不在数据库、不在 CMS** ⇒ 改一个字就要改代码、重新构建前端、重新部署
- 三个页面都走 `meta.nav:'public'`，即用前台导航（`PublicNav`），登录状态下也显示
- 404 兜底路由是 `path: '/:pathMatch(.*)*'`，**排在路由表最后**，所以任何未定义路径都会落到它，而不是白屏

📄 `router/index.js`（`/about`、`/privacy`、`/terms`、`/:pathMatch(.*)*`）

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
| **认证层** | **登录直接 403，拿不到 token** ⇒ API 实际不可达 `[M-04]` |
| **权限层** | 权限类不看 `email_verified` ⇒ 若已持有 token（如登录后邮箱被置否），不受限 `[E]` |

> 🔎 **必须分两层说**（旧版把两层混成一句"与 researcher 相同"，实测已拆开）：
> - **认证层**：未验证用户 `POST /auth/login` 返回 **403**，`meta.error.detail` =
>   `Email address is not verified. ...`，**根本拿不到 token** ⇒ API 不可达 `[M-04 实测]`
> - **权限层**：没有任何权限类检查 `email_verified` ⇒ 若 token 已存在，权限不受影响 `[E 求值]`
>
> 换句话说：**"未验证"不是权限收紧，是登录被拒**。它只是登录闸门。
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

### 3.0 researcher 的一天（把 3.2 的流程按真实时序串起来）

| 时间点 | 他要做什么 | 页面 | 对应流程 |
|---|---|---|---|
| 上午 | 搜试剂、比价、看 COA/SDS | `/search` → `/products/:id` | F1-4 / F1-3 |
| 上午 | 加购物车（可能先不登录） | 产品详情 `Add to Cart` | F1-6 |
| 中午 | 登录后结账 | `/checkout` | F3-4 |
| 或中午 | 走内部采购流程：提 PO + 传采购单附件 | `/po/submit` | F3-7 |
| 下午 | 查进度、下载发票 | `/orders` `/po/downloads` | F3-5 / F3-11 |
| 随时 | 机构地址变更 | `/po/addresses` | F3-10 |
| 需要时 | 内部给了报价 → 接受/拒绝 | `/orders/:id` | F3-6 |
| ⚠️ 卡住时 | 忘了密码 | **无处可去** | 见 11.3.0 |

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
3. 逐行按 **SKU 现价**覆盖客户端单价（`transactions/services.py:141`，注释明确"客户端提交不可信"）
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

## 3.3 数据隔离实测：客户能看到谁的数据（[M-30~M-35] 实测）

用两个机构（org10 / org11）、各一个客户、各一条地址和一张订单，做交叉访问：

| 做什么 | 结果 | 说明 |
|---|---|---|
| 读自己的订单 / 地址 | **200** | 正常 |
| 读**别的机构**的地址 | **404** + `No Address matches the given query.` | 靠 queryset 收窄，**不是 403** |
| 改 / 删别人的地址 | **404** | 写同样被挡；事后对方仍能读到自己的地址（没被删） |
| 读**别的机构**的订单 | **404** | 同上 |
| 对**别人的订单**接受报价 | **403** | ★ 这里不同：是"查得到但不许"，该端点有显式归属校验 |
| 下载**别人的发票** PDF | **403**（匿名 401） | — |
| 改**别人的购物车行** | **404** | — |
| 改**别人的愿望清单** | **404**，对方数据未被改动 | — |
| 下载 **draft 状态**的 SDS | **404** | 门控生效；published 的可以 200 下载 |

**同机构内是可以互改的**（实测 200 且已持久化）：
> 同机构第二人 `PUT /addresses/{第一人的地址}` → **200**，地址 attention 真的被改掉了。
> 这与 `AddressPermission` 的设计意图一致（"同机构成员可改彼此的地址——本来就是机构内协作"）。

**一条容易误解的限制**（实测）：
> **连 staff / procurement 也读不到客户地址**（同样 404）。因为地址 ViewSet 按"**请求者自己所属机构**"
> 过滤，内部员工的机构与客户不同 ⇒ 查不到。所以**内部台无法代客查看/修改收货地址**，
> 需要让客户自己改，或把员工加入该机构。

## 3.4 researcher 做不到的事

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

## 4.0 身份与边界

| 项 | 值 |
|---|---|
| `role` | researcher |
| **`is_org_admin`** | **true**（本章唯一特殊之处） |
| `is_staff` | false |
| 能进页面 | 与第 3 章**完全相同**的 33 页（23 公开 + 10 客户）；内部台一律被踢回首页 |
| 读写端点 | 与 researcher **逐格相同**（实测 读 75/84、写 31/115） |
| 唯一可见差别 | `/settings` → `Account` 面板多一个 `Admin` 徽章 |
| 能不能管机构成员/地址/订单 | **都不能**（没有任何对应端点） |

## 4.1 核心结论（先说最重要的一句）

> **`is_org_admin` 对权限零影响。** 该身份与普通 researcher 在**真实 HTTP 探测**里逐项相同：
> 读 **75/84**、写 **31/115**、被拒 **93**，三个数字完全一致 `[M-01 实测]`。

**唯一可见的差别**：`/settings` → `Account` 面板多显示一个 `Admin` 徽章（`SettingsPage.vue:564` 的 `v-if="authStore.isOrgAdmin"`）。

## 4.2 证据（三重）

| 证据 | 内容 |
|---|---|
| 1. 探针实测 | 8 身份求值中，`org_admin` 与 `researcher` 的 336 个端点判定**逐格相同** |
| 2. 后端 grep | `is_org_admin` 全仓仅 4 处，**无一是权限判据**：`accounts/models.py:87`（字段定义）、`accounts/admin.py:37,38,43`（Django admin 展示/筛选）、`accounts/api/v1/serializers.py:217,237,247,269`（注册/加入机构时写入 + 序列化输出）、`accounts/api/v1/views.py:308`（建机构时置 True） |
| 3. 前端 grep | 仅 `stores/auth.js:26` 取字段 + `SettingsPage.vue:564` 显示徽章，无任何条件渲染用于控制功能 |

## 4.3 该身份怎么产生

| 路径 | 行为 | 代码 |
|---|---|---|
| 注册时选 `Create New` 建机构 | 创建者 `organization` = 新机构，`is_org_admin = True` | `accounts/api/v1/views.py:305-310` |
| 注册时 `Join Existing` | 加入者 `is_org_admin = False`（有测试守护：`test_membership_guard.py:120` 断言"join 进来的人不该自动成为机构管理员"） | `accounts/api/v1/serializers.py:237` |
| Django admin 手改 | 可直接置 true/false | `accounts/admin.py:43` |

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

### 5.0 procurement 的一天（履约主线）

| 时间点 | 他要做什么 | 页面 | 对应流程 |
|---|---|---|---|
| 早 | 看有没有新 PO 待审 | `/ops/po/review` | F5-1 |
| 早 | 审批 / 拒绝（填拒绝原因） | 同上 | F5-1 |
| 上午 | 建发货单、标记发出 | `/ops/po/shipments` | F5-2 |
| 下午 | 在途订单标记送达 | 同上 | F5-2 |
| 下午 | 已送达订单开票 | `/ops/po/invoicing` | F5-3 |
| 下午 | 记录客户回款 | 同上 | F5-3 |
| 每周 | 看应收账龄、催款 | `/ops/po/ar` | F5-4 |
| 按需 | 到货入库、盘点调整 | `/ops/inventory` | F5-6 |
| 按需 | 看客户提交的询价单（只读） | `/ops/rfq` | F5-7 |
| 按需 | 查某机构的订货历史 | `/ops/po/organizations` | F5-5 |
| ⚠️ 别去 | 订单管理页 `/ops/orders`（403 + 误导性空态） | — | 见 5.1 |
| ⚠️ 别点 | PO 台的 `Assign Rep`（必 403） | — | 见 5.3 |

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
| ❌ **不可用**（首屏读即 403） | **3** | 首屏读请求 403；**注意不是白屏**——见下表实测形态 |

| 页面 | 判定 | 具体表现 |
|---|---|---|
| `/ops/orders`（订单管理） | ❌ **不可用** | `GET /admin/orders/` ← `IsAdminUser` ⇒ 403。实测：**0 行 + 错误横幅 `Couldn't load orders.` + 空态 `No orders found` 并列**（后者会让人误判"全库没订单"）`[M-10]` |
| `/ops/orders/:id`（订单详情） | ❌ **不可用** | `GET /admin/orders/:id/` ⇒ 403。实测文案 `Couldn't load this order.` `[M-11]` |
| `/workspace/verified`（审核台） | ❌ **不可用** | `GET /verified/` ← `IsStaffUser` ⇒ 403。实测文案 `Failed to load review queue.`（**无**误导性空态）`[M-12]` |
| `/workspace`（首页统计） | ⚠️ 只读 | `GET /admin/dashboard-stats/` ⇒ 403。实测页面显示 `Failed to load dashboard data`；「最近更新」表正常 `[M-13]` |
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

> ⚠️ **几乎没有任何 UI 会提前告诉他"你没权限"**：19 个内部页里元素级角色条件渲染只有 1 处（`ProductsPage.vue:666` 的两个批量 AI 按钮），
> 其余按钮对所有能进页面的人都显示。采购点了会弹一个**英文技术话术**的全局 toast（403 时是 DRF 原文 `You do not have permission to perform this action.`）——既不说明缺哪个权限，也不告诉他该找谁。详见 §0.6。

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
- 审批失败 ⇒ 无 try/catch，但**全局 toast 会弹**（403 为 DRF 英文原文）；页面自身既不回滚状态、也无内联错误区

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
⚠️ 全部操作无 try/catch。失败由全局 toast 兜底（§0.6），但页面**不会回滚已变化的本地状态**，也不告诉操作员下一步该做什么。

**空态**：`No orders to ship.` / `No shipments yet.`

### F5-3 开票与收款（`/ops/po/invoicing`）

**进入即** `GET /orders/?page_size=200`，客户端过滤 `delivered` / `invoiced`

| 步 | 操作 | 元素（原文） | 请求 |
|---|---|---|---|
| 1 | 选订单 | 左表点单号（列 `Order` / `Status` / `Total`） | `GET /orders/{id}/` |
| 2 | 开票（未开票时） | 选付款条件（`Net 30`/`Net 45`/`Net 60`，默认 NET30）→ `Issue Invoice` | `POST /orders/{id}/invoice/` body `{payment_terms}` ⇒ 订单 → `invoiced` |
| 3 | 记录收款（已开票时） | `Amount`（placeholder `0.00`）/ `Method`（`Online`/`Wire Transfer`/`Check`）/ `Reference` → `Record Payment` | `POST /invoices/{id}/pay/` body `{amount, method, reference}` |

⚠️ **`Amount` 必须有值**，否则**静默 return**（`PoInvoicingDesk.vue:53`）——请求**根本没发出**，所以连全局 toast 都不会有。这与"接口返回失败"是两种不同的沉默，别混。
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

⚠️ 入库/调整的前端必填校验全部是静默 `return`（`:260,282`）——**请求不发出 ⇒ 无 toast、无红框**。
⚠️ `batch_id` 恒为 `null`（`:265`），界面无批次入口。

### F5-7 询价单收件箱（`/ops/rfq`）

> **2026-10-22 新增。** 在此之前客户提交的 RFQ **只有创建入口、没有任何查询入口** ——
> 详情 queryset 按 `contact_email == 当前用户邮箱` 过滤，**连 staff 也是 404**，运营只能进 Django admin。
> 本节记录补上之后的真实能力边界，包括它**做不到**的部分。

**入口**：页头用户下拉 → `RFQ Inbox`（仅 `isInternal` 可见：`is_staff` 或 `role∈(procurement, admin)`）
**进入即** `GET /quote-requests/manage/`（`IsProcurementOrAdmin`）

| 操作 | 入口 | 参数 | 请求 |
|---|---|---|---|
| 看列表 | 进入即 / `Refresh` / `Apply` | `page_size`(默认 100，夹紧 1–500) / `search` / `status` | `GET /quote-requests/manage/` |
| 搜索 | 输入框（placeholder `Search name, email, company…`，回车或 `Apply`） | 模糊匹配 **`contact_name` / `contact_email` / `company_name` / `notes`** | 同上带 `search` |
| 按状态筛 | 下拉 `All statuses / Pending / Reviewing / Quoted / Closed`（`change` 即发） | `status`；**非法值被忽略**（不报错，退回全量） | 同上带 `status` |
| 看明细 | 行内 `View` | — | `GET /quote-requests/{id}/`（内部人员可读**任意** RFQ） |

**列表列**：`ID` / `Received` / `Contact`（姓名 + 邮箱两行）/ `Company`（公司，下面一行灰字显示国家 —— 国家不单独占一列：8 列在 1.6fr 里放不下，实测会把 `Country` 压成 `Chi`）/ `Items`（`items_count`）/ `Status` / `View`
**详情区**：联系人 / 邮箱 / 电话 / 公司 / 国家 / 状态 / 收到时间 / 备注 + `Items (N)` 表（`Product` / `SKU` / `Qty` / `Note`）

⚠️ **五条必须知道的事实**：

1. **本页是只读的，且这是刻意的。**
   `pending → reviewing → quoted → closed` 这条状态机**后端没有更新端点**，前端也不提供任何按钮
   （已由 `p3-rfq-inbox` 反向断言锁死：页面上出现 `Update Status`/`Save`/`Delete` 类按钮即判红）。
   要改状态目前只能走 Django admin。**别在 UI 上"假装能改"**。
2. **列表用 `items_count`，不带明细。** 列表一次最多 100 行 × N 条明细会把响应放大；
   要明细必须点 `View`（`QuoteRequestListSerializer` 与 Detail 的刻意差别）。
3. **`search` 搜不到产品名和明细备注。** 只覆盖 RFQ 表头四个字段；
   想"按询价的产品找单子"目前做不到（`items` 未参与过滤）。
4. **明细的 `Product` 列可能显示 `—`。** RFQ 明细允许**只填产品名、不挂产品**
   （`product_id` 可为 `null`，客户走自由文本提交时就是这种），此时 `product_name` 也是空
   ⇒ 前端必须显示占位符。⚠️ 早期实现写成 `#${item.product_id}`，空值会渲染成 **`#null`**
   （截图确认过），运营会误以为数据坏了 —— 已改为 `itemProductLabel()` 判空。
5. **⚠️ 没有分页组件。** 首次只取 100 条（副标题显示的是**总数** `N quote request(s)`），
   超过 100 条时**看不到后面的记录，也没有翻页入口**。本地当前 RFQ 数未到 100，故尚未暴露；
   若运营真要靠它管线索，这是下一个必须补的点（与 F5-4/F5-5 的"行数与 API 一致"断言同性质）。

**为什么不复用 `GET /quote-requests/`**：那个路径只有 `POST`（匿名获客入口），`GET` 返回 **405**（已锁）。
查询面刻意拆成 `/quote-requests/manage/`，与 `organizations/manage/`、`ar/aging/` 同风格。

## 5.3 procurement 做不到的事

| 想做的事 | 结果 | 原因 |
|---|---|---|
| 打开订单管理页看全库订单 | ❌ 不可用（403 + 空态误导）`[M-10]` | `/admin/orders/` 是 `IsAdminUser` |
| 审核 verified（**看**队列） | ❌ 403（`GET /verified/`）`[M-12]` | `IsStaffUser` |
| **提交** verified 草稿 | ✅ **可以**（任何登录用户）`[M-15]` | `POST /verified/` 只要 `IsAuthenticated` |
| 新建/编辑产品、知识实体 | ❌ 403 | `IsAdminOrReadOnly` 写要 `is_staff` |
| 指派销售 | ❌ 403（按钮却在） | `IsAdmin` |
| 用 AI 批量校验/批量文献 | ❌ 按钮根本不渲染 | `canBatchAi = Boolean(auth.isStaff)` |
| 把订单从 `invoiced` 推到 `paid` | ❌ 全站无入口 | 无"标记已付"按钮 |

---

# 第 6 章 admin（`role='admin'`，`is_staff=false`）

## 6.0 身份与边界

| 项 | 值 |
|---|---|
| `role` | **admin** |
| `is_staff` | **false** ← 关键：名字叫 admin，但不是 Django staff |
| 能进页面 | 19 个内部台**全部能进**（`isInternal()` 认 `role`） |
| 读端点 | 80/84（与采购相同） |
| 写端点 | **43/115**（比采购多 **1** 个） |
| 比采购多的唯一能力 | `POST /orders/:id/assign-rep/`（`IsAdmin` = `is_staff` **或** `role=='admin'`） |
| 与 staff 的差距 | 产品/知识实体/COA·SDS/verified/`/admin/orders/` **全部 403** |

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

### 7.0 staff 的一周（内容 + 交易两条线）

**内容线（产品从无到上架）**：
```
新建产品 → 补全字段 → Word 导入 / AI AUTO MATCH → 建 SKU 定价
        → 关联知识实体 → 生成并联审 COA·SDS → Publish → （可选）建并审 verified 关系
```
对应：`/workspace/products/new` → 编辑页各 Section → `/workspace/verified`

**交易线（订单从收到完结）**：
```
PO 审核 → 发货 → 送达 → 开票 → 记录收款 → 完成（Mark as Completed）
```
对应：`/ops/po/review` → `/ops/po/shipments` → `/ops/po/invoicing` → `/ops/orders/:id`

| 场景 | 页面 | 详细 |
|---|---|---|
| 产品全生命周期 | `/workspace/products/*` | §7.3 §7.4 |
| 知识实体维护 | `/workspace/{goals,applications,methods,protocols,references}` | §7.5 |
| 合规文档（SDS/COA） | 产品编辑页 Section 9 | §7.3.7 |
| verified 审核 | `/workspace/verified` | §7.6 |
| 订单详情推进 | `/ops/orders/:id`（**状态按钮矩阵**） | §7.8.2 |
| 四个 PO Desk | `/ops/po/*` | §7.8.3 |
| 库存 | `/ops/inventory` | §F5-6 |
| 询价单收件箱 | `/ops/rfq` | §F5-7 |

> ⚠️ **staff 也读不到客户地址**（实测）：地址簿按"你所属机构"过滤，内部员工机构与客户不同 ⇒ 404。
> 要让客户改地址，或把该员工加入该机构。详见 §3.3。

## 7.1 身份与边界

| 项 | 值 |
|---|---|
| `is_staff` | true |
| 产生方式 | 仅 Django admin 勾选 / `createsuperuser` |
| 能进页面 | 23 公开 + 10 客户 + **20 内部 = 全部 53 页** |
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
| 页面 | 与 staff 完全相同的 53 页 + **Django admin** |
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

### 8.3.1 怎么给一个人授予采购/管理员权限（分步）

| 步 | 操作 | 注意 |
|---|---|---|
| 1 | 用 **superuser** 打开 `<站点>/admin/` | 生产还要先过 nginx Basic 认证（两层） |
| 2 | `Users` → 右上角搜索框输入用户名 | 注意别改错同名账号 |
| 3 | 进入该用户，找到 `Role` 下拉与 `is_staff` / `is_superuser` 勾选 | `role` 决定前端的"内部人"判定 |
| 4 | 改完点 `Save`（右下角） | — |
| 5 | **让他退出再登录** | ★ 必做，理由见下 |

> ★ **生效边界（运营最容易踩）**：
> - **后端权限实时生效** —— 权限类是每个请求重新判断，不用等、不用重启
> - **前端菜单与守卫要重新登录才变** —— 前端只在**登录那一刻**把 `is_staff` / `role`
>   写进 localStorage（`stores/auth.js:34-36`、`:65-66`），之后一直读缓存
> ⇒ 用户报"我改了权限但看不到工作台"，先让他 `Sign Out` 再登录，不要以为是没生效
>
> **该给谁什么**（对照第 0.3 节）：
> - 只想让他处理订单/库存 → 给 `role=procurement`（**不要**勾 `is_staff`）
> - 要他能编产品/知识实体 → **必须勾 `is_staff`**（`role` 再高也没用）
> - 要他能进 Django admin 改别人权限 → 必须 `is_superuser`

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

**两套口径，别混用**：`[E]` 是权限类求值（全量 336 端点，含格式变体）；
`[M]` 是真实 HTTP 探测（剔除外呼/格式变体后 199 端点，写方法用空 body）。

| 身份 | 读通过 `[E 求值]` | 写通过 `[E 求值]` | 读通过 **`[M 实测]`** | 写通过 **`[M 实测]`** |
|---|---|---|---|---|
| 匿名 | 117/132 | 7/203 | **69/84** | **7/115** |
| 未验证 | 123/132 | 43/203 | **登录 403，无 token** | **—** |
| researcher | 123/132 | 43/203 | **75/84** | **31/115** |
| org_admin | 123/132 | 43/203 | **75/84** | **31/115** |
| procurement | 128/132 | 54/203 | **80/84** | **42/115** |
| admin(role) | 128/132 | 55/203 | **80/84** | **43/115** |
| staff | **132/132** | 201/203 | **84/84** | **114/115** |
| superuser | **132/132** | **203/203** | **84/84** | **115/115** |

**实测数字的三条自检**（说明它不是噪声）：
1. **单调**：读通过的端点集合逐级包含，身份越高压过的越多 —— 反向出现就说明实验有 bug（第一版就踩过，见实测清单 §5）
2. **差值可解释**：`admin_role` 比 `procurement` 写多 **1**（assign-rep）；`staff` 被拒 **1**（hard-delete）
3. **与求值同向**：每一行的相对大小与 `[E]` 列一致 ⇒ 两套方法互证

出处与复跑命令：`MANUAL_FACTS_MEASURED.md` §1（M-01）

---

# 第 11 章 已知限制与常见故障（参考章，非操作步骤）

> 本章是"操作时一定会撞上的坑"。按影响面排序，每条都带代码依据。

## 11.1 结构性不一致（5 条）

| # | 现象 | 依据 | 后果 |
|---|---|---|---|
| 1 | **`role` 只影响 17 个端点**，其余 231 个写操作只看 `is_staff` | 权限类统计 | `role=admin` 能改 55/203，名为 admin 实权有限 |
| 2 | **前端只有 2 级守卫，后端 8 类判据** | `router/index.js:322` | 19 个内部页里 3 个空白、9 个只读，用户无解释 |
| 3 | **`is_org_admin` 零影响** | 全仓无权限引用 + 探针数字相同 | 机构管理员没有任何管理能力 |
| 4 | **`email_verified` 只在登录处校验** | 探针 unverified == researcher | 已登录用户邮箱被置否后 token 仍全权可用 |
| 5a | **`get_permissions()` 按方法分权，静态读类属性会读错** | `bridges/api/v1/views.py:79-82` | 探针把 `POST /verified/` 判成 `IsStaffUser`，实测是 `IsAuthenticated`（一致度 99.7% 里唯一的一类偏差）`[M-02][M-15]` |
| 5 | **同一动作两套端点、两套权限** | `/admin/orders/{id}/invoice/`(`IsAdminUser`) vs `/orders/{id}/invoice/`(`IsProcurementOrAdmin`) | 采购在订单详情页开不了票，在开票台却能 |

## 11.2 死按钮 / 假成功 / 功能失效（运营最常撞的，21 条）

> **先分清三种"没反应"**（判断责任方时最关键）：
> 1. **请求根本没发出**（前端校验早退）⇒ 无 toast、无任何提示，纯靠代码里的 `return`
> 2. **请求发出但被拒**（401/403/404/5xx）⇒ 有全局 toast；401 还会**清 token + 强制整页跳 `/login`**
> 3. **请求成功但结果没体现**⇒ 页面状态没刷新（假成功）
> 下表逐条标注属于哪一种。

| # | 位置 | 现象 | 依据 |
|---|---|---|---|
| 1 | `/settings` → Security → `Update Password` | **假成功**：校验后直接提示 `Password update feature will be available soon.`，无任何后端调用 | `SettingsPage.vue:191-221` |
| 2 | `/login` → `Resend verification email` | **必崩**：读 `form.email`（字段不存在）⇒ `TypeError`，请求不发 | `LoginPage.vue:22-25,112` |
| 3 | `/verify-email` 失败态 | **重发按钮永不显示**（`v-if="email"` 只在成功路径为真） | `VerifyEmailPage.vue:28,117` |
| 4 | `/ops/orders/:id` → `Internal Notes` | 有输入框，**无保存按钮无 API** ⇒ 输入不落库 | `AdminOrderDetail.vue:267` |
| 5 | `/ops/orders/:id` → 报价备注 | `quoteForm.notes` 有字段、模板无输入框 ⇒ 永远传空 | `AdminOrderDetail.vue:26,104` |
| 6 | `/ops/po/review` → `Assign Rep` | 采购点击必 403（**有 toast**，DRF 英文原文）；rep 为空时**静默 return**（请求不发）；失败无状态回滚 | `PoReviewDesk.vue:53-58` |
| 7 | `/ops/po/invoicing` → `Record Payment` | Amount 为空时**静默 return**（请求不发，无 toast）| `PoInvoicingDesk.vue:53` |
| 8 | `/ops/inventory` 入库/调整 | 必填校验全部静默 `return`（请求不发，无 toast、无红框）| `InventoryDesk.vue:260,282` |
| 9 | `/quote-request` 提交失败 | 页面无内联错误区（只 console），**全局 toast 会弹**；表单内容保留 | `QuoteRequestPage.vue:104` |
| 10 | `/search` 失败 | 无内联错误区（只 console），**全局 toast 会弹**；结果区停留在旧结果 | `SearchPage.vue:68` |
| 11 | `/cart` → `Submit for Approval` | 与 `Place Order` 同目标，**无审批接口**；且仅 researcher 可见 | `CartPage.vue:14-19,59` |
| 12 | `/methods`、`/protocols` 状态 chips | 点击只变高亮，**不筛数据**（未传 `status`） | `MethodIndex.vue:37`、`ProtocolIndex.vue:38` |
| 13 | 产品列表 `Knowledge Link` 列 | 可排序，但 L3 子分类筛选未进请求参数 | `ProductIndex.vue:43-47` |
| 14 | `PoReorder` 行选中 | `selectedId` 从未赋值 ⇒ 高亮永不出现 | `PoReorder.vue:12,53` |
| 15 | `AdminOrdersPage` 加载失败 | 错误横幅与"无订单"空态同时出现 | `AdminOrdersPage.vue:93,130` |
| 16 | `PoArReport` 加载失败 | 无 catch、无空态，页面只剩头部（**有 toast 但无重试入口**）| `PoArReport.vue:16-24` |
| 17 | `PoOrgManagement` 副标题 | 声称 "their addresses"，模板无地址字段 | `PoOrgManagement.vue:44` |
| 18 | 完整性条缺失项 | 纯文本，不可点击跳转到缺失字段 | `ProductEditPage.vue:1666-1667` |
| 20 | 并发写（库存入库 / PO 提交） | **仅 SQLite 下出现**：10 并发 → 8~9 个 500，异常 `database is locked`。**PostgreSQL 下同样 10 并发全部成功**（库存 +10、PO 10×201），`run_pg_tests.py` 6/6 通过 ⇒ **这是本地 dev 环境特性，不是应用缺陷** `[M-50 修正]` | — |
| ~~22~~ | ~~`/verify-email?token=<非UUID>` 返回 500 + HTML 错误页~~ | **✅ 2026-10-22 已修**：现在返回 **400 + `Invalid or expired verification token.`**（JSON 信封），与"合法 UUID 但不存在"同一条文案，不再泄露内部异常。根因：`EmailVerification.token` 是 `UUIDField`，畸形串抛的是 `django.core.exceptions.ValidationError`（不是 `ValueError`），原 `except` 漏捕。回归用例 `apps/accounts/tests/test_verify_email_token_tolerance.py`（5 条）+ `p2-auth-verify` | `accounts/api/v1/views.py` |
| 19 | `/ops/po/review` → `Assign Rep` 填**用户名** | **500 + HTML 错误页**（不是 JSON 信封）。`except` 只捕获 `User.DoesNotExist`，非数字 `rep_id` 抛 `ValueError`。实测：填 `probe_staff`→500，填数字 `26`→200 成功 `[M-21]` | `transactions/api/v1/po_views.py:130` |

## 11.3 能力缺口（有需求、无实现）

### 11.3.0 ⚠️ 最严重：**账号自救能力为零**

这是本轮审计新发现的一条，按影响面应该排在所有问题之前：

| 想做的事 | 现状 | 后果 |
|---|---|---|
| **改密码** | `/settings` → Security → `Update Password` 校验完直接弹 `Password update feature will be available soon.`，**无任何后端调用** | 用户以为改了，实际没改 |
| **忘记密码后重置** | **全站不存在**。无端点、无路由、无 api 封装（`grep password-reset\|forgot\|reset-password` 于 urls/views/router/api 全部 0 命中；`accounts` app 里除测试外无 `set_password` 调用） | **永久锁死**，只能内部去 Django admin 重置 |
| 邮箱验证链接过期后重发 | 登录页的重发按钮**必崩**（读不存在的 `form.email`） | 只能靠注册成功当页那个按钮（已离开就没了） |

**结论**：一个已注册用户，**只要忘了密码或验证链接过期，就无法靠自己恢复账号**。
唯一出路是运维人员登录 Django admin 手工处理（`/admin/` → Users → 改密码 / 改 `email_verified`）。

**这三条必须在产品层面给结论**：
1. 补 `POST /auth/password/change`（已登录改密）+ `POST /auth/password/reset-request` / `reset-confirm`（忘记密码）
2. 修登录页重发按钮（`form` 加 `email` 字段，或在未验证分支复用注册页的输入框）
3. 在补上之前，**运营手册必须写明"忘记密码请走工单，内部用 Django admin 重置"** —— 否则一线会答"点那个按钮"，而那个按钮是假的

---

### 其余能力缺口

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
| 11 | **通知邮件全是空壳** | `EmailTemplate` 表 **0 条**；`EmailOutbox` **2984 封全 pending、历史零发送**；手动跑命令发出的是**空主题空正文** `[M-41][M-42]` |
| 12 | **验证邮件"已发送"是话术** | 无 Mailgun key 时走 console backend ⇒ 邮件只打印到服务器日志，用户收不到，但接口照回 `We have sent a verification link` `[M-40]` |

## 11.4 潜在风险（当前无实际数据触发，但一旦触发就是事故）

| # | 风险 | 触发条件 | 依据 |
|---|---|---|---|
| 1 | **非 USD 币种订单金额错** | 上架任一 CNY/EUR 的 SKU | `checkout_views.py:93` 硬编码 `currency='USD'`；当前 596 SKU 全 USD |
| 2 | **`create_order` 信任客户端单价** | 有人把它接上生产调用链 | `transactions/services.py:40-52`；当前只有测试调用 |
| 3 | **`_sync_method_bridges` 先删后加** | 保存时只传 goal/app 不传 `method_ids` | 原有方法关联被真删 |

---

## 11.5 界面文案语种混杂（直接影响客户）

界面主体是英文，但存在**用户可见的中文**，且集中在最需要引导的地方：

| 位置 | 中文文案（原文） | 谁看得到 |
|---|---|---|
| `ProductDetail.vue:266` | `toast.warning('请先登录')` | **客户**（未登录点收藏） |
| `ProductDetail.vue:286` | `toast.success('已收藏' / '已取消收藏')` | **客户** |
| `WishlistPage.vue` 整页 | `请先登录后使用收藏夹`、`还没有收藏任何产品`、`清空收藏`、`收藏夹加载失败`、`重试` | **客户** |
| `InventoryDesk.vue:113-115,135-137` | `Reason *` 标签 + placeholder `e.g. PO-1234 到货 / 盘盈`、`e.g. 盘点差异 -2` | 内部运营（英文按钮 + 中文提示） |
| `ProductEditPage.vue` | 约 1200 处中文（提示、确认框、错误说明） | 内部运营 |

**中文出现量实测**（`grep -oP '[\x{4e00}-\x{9fa5}]+' | wc -l`）：
ProductEditPage **1211**、ProductsPage **287**、ProductDetail **145**、WishlistPage **77**、RegisterPage 53。

**判断**：
- **内部台以中文为主是可接受的**（操作员是中文母语），不算缺陷
- **客户侧（ProductDetail / WishlistPage）中英混杂是真问题**：英文客户点收藏会看到中文提示，且 `WishlistPage` 整页中文
- 这与既定目标「官网纯英文本地化（DB 实体 + 前端 UI 文案）」**方向相反**，属于该事项的遗留未清部分

---

## 11.6 生产环境当前状态：**全站 401，仍是内部测试态**

2026-10-22 只读匿名探测（10 条路径，只 GET、不带凭证、不写）：

| 路径 | 状态 | 响应头 |
|---|---|---|
| `/`、`/robots.txt`、`/sitemap.xml` | **401** | `WWW-Authenticate: Basic realm="SciReAgent Internal Test"` |
| `/api/v1/health/`、`/site/home`、`/products/`、`/search/suggest` | **401** | 同上 |
| `/api/v1/orders/`、`/admin/orders/`、`/verified/` | **401** | 同上 |

**三条结论**：
1. **站点对整个互联网不可访问** —— 连首页与 `robots.txt` 都要 Basic 认证
2. realm 名 `SciReAgent Internal Test` ⇒ 明确是**内部测试态**，不能称"已上线"
3. **sitemap 与 SEO 优化当前对搜索引擎无效**（爬虫同样吃 401）

⇒ 任何对外汇报必须用"**开发测试态 + 种子数据**"，不得写"能用了/已上线/已交付"。

### 11.6.1 登录态实测（2026-10-22，凭据由用户提供）

**两层认证的正确组合**（实测）：
```
Authorization: Basic <nginx 账号>    ← 过 nginx
X-Auth-Token: <应用层 token>          ← 过 Django（前端就是这么发的）
```
只用 `Authorization: Token xxx` 会被 nginx 拦（401）。

| 资源 | 生产实际数量 |
|---|---|
| 公开产品 | **0** |
| 产品（回收站） | **125** |
| 库存行 | **0** |
| 内部订单 | **16** |
| COA | **33** |
| SDS 版本 | **12** |
| verified 待审 | **0** |

**体积验证（证明之前的修复在生产生效）**：
- `site/navigation` = **18.6 KB**（曾 2.78 MB）✅
- `sitemap.xml` = **511 字节**（分片 index 生效）✅

⚠️ **安全缺陷**：生产 `admin / admin123` **能登录**（`is_staff=true`、`is_superuser=true`）。
对外前必须改口令，或把 Basic 层撤掉时同步收紧账号。

> 生产**只做了 GET**；唯一写动作是回收自己刚拿到的 token（logout）。凭据未落盘、未入仓库。

---

# 第 12 章 页面索引（按页面反查）

> 前面各章是"按角色讲流程"，本章反过来：**给你一个页面，告诉你是谁的地盘、能干什么、调什么接口**。
> "客户能进 / 采购能进"这三列来自**实测**（`PAGE_ROLE_MATRIX.json`），不是推断。

## 12.1 公开页（23 个 + 404）

> 守卫：**无**。未登录可访问；已登录也可访问。

| 页面 | 路由 | 主要动作（界面文案） | 关键接口 | 详见 |
|---|---|---|---|---|
| 首页 | `/` | 搜索框、热门词、分类胶囊、精选商品、折叠知识图谱 | `GET /site/home` | §F1-1 |
| 产品列表 | `/products` | 按三级分类筛、排序（默认/名称/最新/关联最强）、搜索、翻页 | `GET /products` `GET /categories` | §F1-2 |
| 产品详情 | `/products/:id` | 看规格/SKU/COA·SDS/知识 Tabs；`Add to Cart` `Request Quote` `收藏` | `GET /products/{id}/detail` | §F1-3 |
| 搜索 | `/search` | 关键词搜全站；按 Products/Applications/Methods/Protocols 过滤 | `GET /search/grouped` `GET /search/suggest` | §F1-4 |
| 应用列表 | `/applications` | `All Applications` / `Browse by Class` 两个 Tab、状态 chips | `GET /applications/` `GET /convergence-classes/` | §F1-5 |
| 应用详情 | `/applications/:id` | 看该应用下的方法 / 方案 / 产品 | `GET /applications/{id}/` | §F1-5 |
| 收敛类详情（应用侧） | `/applications/classes/:class_id` | 看该类成员与来源徽标 | `GET /convergence-classes/{class_id}` | §F1-5 |
| 方法列表 | `/methods` | 浏览、搜索（⚠️ 状态 chips 点击不筛数据） | `GET /methods/` | §F1-5 |
| 方法详情 | `/methods/:id` | 看 Purpose / 成本带宽 / 优劣 / 方案 / 关联产品 | `GET /methods/{id}/` | §F1-5 |
| 方案列表 | `/protocols` | 浏览、搜索（⚠️ 状态 chips 同上） | `GET /protocols/` | §F1-5 |
| 方案详情 | `/protocols/:id` | 6 Tab：`Steps` `Materials` `Troubleshooting` `Expected Results` `References` `Products` | `GET /protocols/{id}/` | §F1-5 |
| 研究目标列表 | `/research-goals` | 搜索、状态下拉、`Browse by Class` | `GET /research-goals/` | §F1-5 |
| 研究目标详情 | `/research-goals/:id` | 看摘要 + 策展方案表 | `GET /research-goals/{id}/` | §F1-5 |
| 收敛类详情（目标侧） | `/research-goals/classes/:class_id` | 同上 | 同上 | §F1-5 |
| 提交询价 | `/quote-request` | 填联系人、加多行需求、`Submit Quote Request` | `POST /quote-requests/` | §F1-7 |
| 购物车 | `/cart` | 改数量、`Remove`、`Place Order`、`Request Quote` | `GET /basket`、`PATCH/DELETE /basket/items/*` | §F1-6 |
| 收藏夹 | `/wishlist` | 看收藏、`移除`、`清空收藏`（未登录提示登录） | `GET/POST /wishlist/`、`PATCH /wishlist/{id}/` | §F1-8 |
| 登录 | `/login` | `Sign In`；未验证时显示重发（⚠️ 按钮死链） | `POST /auth/login` | §F3-1 |
| 注册 | `/register` | 三步向导：基本信息 → 身份（3 张卡）→ 机构（加入/新建） | `POST /auth/register` | §F1-8 |
| 邮箱验证 | `/verify-email` | 点邮件链接后自动验证并登录（1.8s 跳转） | `GET /auth/verify-email` | §F1-9 |
| 关于 | `/about` | 纯静态 | — | §F1-10 |
| 隐私政策 | `/privacy` | 纯静态 | — | §F1-10 |
| 服务条款 | `/terms` | 纯静态 | — | §F1-10 |
| 404 | 任意未匹配路径 | 兜底页 | — | §F1-10 |

> **表格里 ✅/⚠️/❌ 的口径**（与 `PAGE_ROLE_MATRIX.json` 一致）：
> ✅ = 页面所有请求都不会被 403 挡；⚠️ = 能进、绝大多数动作可用，但**至少有一个**动作会 403；
> ❌ = 进入页面时的首屏读请求就 403（页面不可用）。
> 所以 ⚠️ 不等于"整页不可用"，只表示"有坑，看详见列"。

> ⚠️ `/login`、`/register`、`/verify-email` 虽无守卫，但带 `meta.guest`：
> **已登录用户访问会被自动跳走**（内部人 → `/workspace`，其他人 → `/`）。

## 12.2 客户门户（10 个）

> 守卫：`meta.requiresAuth`。未登录 → `/login?redirect=`。

| 页面 | 路由 | 主要动作 | 关键接口 | 详见 |
|---|---|---|---|---|
| 设置 | `/settings` | 5 Tab：Profile / Shipping / Contact / Security / Account。⚠️ `Update Password` **假成功** | `PUT /auth/profile` | §F3-2 |
| 结账 | `/checkout` | 填收货、选支付方式（PO / 卡 / 电汇 / 报价）、`Place Order` | `POST /checkout/` | §F3-4 |
| 我的订单 | `/orders` | 看自己的订单列表、翻页 | `GET /orders/` | §F3-5 |
| 订单详情 | `/orders/:id` | 看明细/支付/收货/发票/物流；`status=quoted` 时出现 `Accept Quote` `Reject Quote` | `GET /orders/{id}/`、`POST /orders/{id}/confirm-quote/` | §F3-6 |
| 提交 PO | `/po/submit` | PO 信息 + 收货 + 账单 + 附件 + 多行明细；`Submit PO` | `POST /orders/po/` | §F3-7 |
| PO 单列表 | `/po/orders` | 状态筛选、`View`、`Re-order`、`+ New PO` | `GET /orders/` | §F3-8 |
| PO 单详情 | `/po/orders/:id` | 看明细/RUO 声明/发票/物流/附件/状态时间线；`Download PDF` `Track Package` | `GET /orders/{id}/`、`GET /invoices/{id}/pdf/` | §F3-9 |
| 地址簿 | `/po/addresses` | `+ New Address` / `Edit` / `Delete`（同机构成员共享可见可改） | `/addresses/` CRUD | §F3-10 |
| 下载中心 | `/po/downloads` | 集中下载发票 PDF 与 PO 附件 | `GET /orders/?page_size=100` | §F3-11 |
| 再次订购 | `/po/reorder` | 从已完成订单 `Re-order` | `GET /orders/?status=completed` | §F3-12 |

## 12.3 内部台（19 个）

> 守卫：`meta.requiresAdmin` ⇒ 前端 `isInternal()` = `is_staff` **或** `role ∈ (procurement, admin)`。
> "采购能否用得起来"这一列是**实测**结果（`procurement`，`is_staff=false`）。

| 页面 | 路由 | 采购（非 staff） | 主要动作 | 关键接口 | 详见 |
|---|---|---|---|---|---|
| 工作台首页 | `/workspace` | ⚠️ 统计卡 403，其余正常 | 看统计卡与「最近更新」 | `GET /admin/dashboard-stats/` | §7.2 |
| 产品管理 | `/workspace/products` | ⚠️ **只读**（写 0/7） | 筛选/排序、批量关联、批量 AI、`Unpublish`/`Discontinue`/回收站 | `GET /products/`、`POST /products/{id}/archive/` | §7.4 |
| 产品新建 | `/workspace/products/new` | ⚠️ **只读**（写 0/21） | 11 区块：Word 导入 / AI AUTO MATCH / SKU / 知识关联 / SEO / 合规 | `POST /products/` | §7.3 |
| 产品编辑 | `/workspace/products/:id/edit` | ⚠️ **只读** | 同上 + 生成/审批 COA·SDS + 建 verified 草稿 | `PUT /products/{id}/` | §7.3 |
| 研究目标 | `/workspace/goals` | ⚠️ 只读 | 增改研究目标、绑策展方案 | `/research-goals/` | §7.5 |
| 应用 | `/workspace/applications` | ⚠️ 只读 | 增改应用、挂到研究目标 | `/applications/` | §7.5 |
| 方法 | `/workspace/methods` | ⚠️ 只读 | 增改方法、挂到应用 | `/methods/` | §7.5 |
| 方案 | `/workspace/protocols` | ⚠️ 只读 | 增改方案、挂到方法 | `/protocols/` | §7.5 |
| 文献 | `/workspace/references` | ⚠️ 只读 | 增改文献 | `/references/` | §7.5 |
| Verified 审核 | `/workspace/verified` | ❌ **不可用**（403） | 审核通过 / 驳回（通过即公开到产品页） | `GET /verified/`、`POST /verified/{id}/approve/` | §7.6 |
| 知识录入 | `/workspace/knowledge-intake` | ⚠️ **保存必 403** | 按产品填知识、`Copy to Similar Products` | `POST /knowledge-intake/` | §7.7 |
| 订单管理 | `/ops/orders` | ❌ **不可用**（403 + 误导性空态） | 全库订单、状态筛、搜索、进详情 | `GET /admin/orders/` | §7.8.1 |
| 订单详情（内部） | `/ops/orders/:id` | ❌ **不可用**（403） | 8 个状态推进按钮，矩阵见 §7.8.2 | `/admin/orders/*`、`/orders/{id}/approve/` 等 | §7.8.2 |
| PO 审核台 | `/ops/po/review` | ⚠️ 基本可用（`Assign Rep` 会 403） | 审批 / 拒绝 / 看明细与缺货 | `GET /orders/?status=po_received` | §F5-1 |
| 发货台 | `/ops/po/shipments` | ✅ 可用 | 建发货单、`Mark Shipped`、`Mark Delivered` | `POST /orders/{id}/shipments/` | §F5-2 |
| 开票台 | `/ops/po/invoicing` | ✅ 可用 | `Issue Invoice`、`Record Payment` | `POST /orders/{id}/invoice/`、`POST /invoices/{id}/pay/` | §F5-3 |
| AR 账龄 | `/ops/po/ar` | ✅ 可用 | 看 4 个账龄桶与应收总额 | `GET /ar/aging/` | §F5-4 |
| 机构管理 | `/ops/po/organizations` | ✅ 可用 | 机构列表、按机构查订单 | `GET /organizations/manage/` | §F5-5 |
| 库存台 | `/ops/inventory` | ✅ 可用 | `Receipt` 入库、`Adjust` 盘点、`History` 流水 | `POST /inventory/receipt/`、`POST /inventory/{id}/adjust/` | §F5-6 |

## 12.4 两套"同名页面"别混（最容易走错的地方）

| 看起来一样 | 实际是两套 | 谁能进 | 数据源 |
|---|---|---|---|
| 「订单管理」 | `/ops/orders`（内部全库） vs `/orders`（客户自己的） | 前者 staff；后者任何客户 | `/admin/orders/` vs `/orders/`（按 user 收窄） |
| 「订单详情」 | `/ops/orders/:id`（内部） vs `/orders/:id`（客户） | 前者 staff；后者仅本人 | 同上 |
| 「PO 单」 | `/po/orders`（客户提交的 PO 后自己看） vs `/ops/po/*`（内部处理 PO 的四个台） | 前者客户；后者内部 | `/orders/`（收窄） vs `/orders/`（跨机构） |
| 「产品」 | `/products`（公开目录，只出 active 且未归档） vs `/workspace/products`（管理台，含回收站） | 前者任何人；后者 staff | 两者 queryset 不同 |

> 本章的 52 行是测试方案的**页面维度索引**：
> 覆盖核算见 `GLOBAL_TEST_PLAN_V3.md` §4（每条流程标了 🟩FULL/🟨PART/🟦LOAD/🟥NONE），
> 逐角色真人脚本见 `PERSONA_TEST_PLAN.md`。

**同一个动作在两个页面权限不同**（实测，最容易踩）：
- 开票：`/ops/po/invoicing` 用 `/orders/{id}/invoice/`（采购**可以**）；
  `/ops/orders/:id` 用 `/admin/orders/{id}/invoice/`（采购**403**）
- 完成订单 / 提交报价：只有 `/ops/orders/:id` 有，且是 `IsAdminUser`（采购 403）

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
产品级状态是**派生**的（`commerce/models.py:218-228`）：有任一 SKU `in_stock` ⇒ `in_stock`；否则 `limited`；否则 `preorder`；否则 `out_of_stock`。

## A.9 库存数量（`inventory`，与上者无关）

`available` / `allocated` / `on_hand` 三个整数；`on_hand = available + allocated`。
所有变更经 `InventoryService`（`select_for_update` 原子操作 + 写 `InventoryMovement` 流水），**禁止直改 `available`**。

---

# 附录 B 端点索引（按业务域）

> ⚠️ **这是"代表端点"，不是全量索引。**
> 实测（`scripts/audit_manual_coverage.py`）：去掉 `.json` 等格式后缀变体后，
> 全站 **140 条路径 / 211 个 method**；本附录覆盖 **133 条路径 / 200 个 method（95%）**。
> 但"路径出现"≠"讲清了"：其中约 9 类 ViewSet 详情路由只在本节末尾"未收录清单"里点了名，正文按 CRUD 概括。
> 未提及的 7 条全是 `{id}` 详情路由或 `sitemap-{kind}-{page}.xml`。

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
| **verified 关系** | `GET /verified/`（审核队列）、`PATCH /verified/{id}/`、`POST /verified/{id}/approve\|reject/` | `IsStaffUser` |
| **verified 草稿** | `POST /verified/` ← **注意：只要登录**，实测客户可建 review 草稿 `[M-15]` | `IsAuthenticated` |
| **订单** | `GET /orders/`（按用户收窄）、`GET /orders/{id}/`、`POST /checkout/`、`POST /orders/po/`、`POST /orders/{id}/approve\|reject\|assign-rep\|cancel\|shipments\|invoice/`、`POST /orders/{id}/confirm-quote/` | 混合：`IsAuthenticated` / `IsProcurementOrAdmin` / `IsAdmin` |
| **订单（admin 套）** | `GET /admin/orders/`、`GET /admin/orders/{id}/`、`POST /admin/orders/{id}/complete\|quote\|confirm\|invoice/` | `IsAdminUser` |
| **发货** | `POST /shipments/{id}/mark-shipped\|mark-delivered/` | `IsProcurementOrAdmin` |
| **发票收款** | `POST /invoices/{id}/pay/`、`GET /invoices/{id}/pdf/`、🔒 `POST /admin/invoices/{id}/verify-payment/` | `IsProcurementOrAdmin` / `IsAuthenticated` / `IsAdminUser` |
| **应收** | `GET /ar/aging/` | `IsProcurementOrAdmin` |
| **库存** | `GET /inventory/`、`GET /inventory/{id}/`、`POST /inventory/receipt/`、`POST /inventory/{id}/adjust/` | `IsProcurementOrAdmin` |
| **合规文档** | `/sds-revisions/`（list/generate/approve/withdraw/download）、`/coas/`（list/create-coa/approve/withdraw/download/qc-results）、`/batches/` | 读 `AllowAny`；写 `IsAdminOrReadOnly` |
| **询价** | `POST /quote-requests/`（匿名获客）、`GET /quote-requests/{id}/`（内部人可读任意 / 客户只读自己的）、**`GET /quote-requests/manage/`**（运营台收件箱，分页 + `search` + `status`）；`/quotes/` CRUD | 未声明 / `IsAuthenticated` / **`IsProcurementOrAdmin`** |
| **愿望清单** | `GET/POST /wishlist/`、`PATCH /wishlist/{id}/` | `IsAuthenticated` |
| **站点** | `GET /site/home`、`GET /site/navigation`、`/sitemap*.xml`、`/health/` | `AllowAny` |
| **知识图谱** | `GET /graph`（实体周边子图；`api/graph.js:11`） | `AllowAny` |
| **结构化数据** | `GET /products/{id}/json-ld/`、`GET /methods/{id}/json-ld/`、`GET /protocols/{id}/json-ld/`（`api/agent.js:10,20,30`） | 读 `AllowAny` |
| **搜索建议** | `GET /search/suggest?q=`（`api/search.js:8`） | `AllowAny` |
| **机构创建** | `POST /organizations/create`（注册 Step 3 选 `Create New` 时；`api/organizations.js:18`） | `IsAuthenticated` |
| **PubChem 补全** | `POST /products/enrich-from-pubchem/`（单条 + 批量；`api/aiTools.js:30,40`） | `IsAdminUser` |
| **产品附加数据** | `GET /products/{id}/related/`、`GET /products/{id}/faq/`（详情聚合接口已一并返回，前端不单独调） | `AllowAny` |
| **单条产品恢复** | `POST /products/{id}/restore/`（前端只用批量版 `batch-restore`） | `IsAdminOrReadOnly` 写 |
| **库存分货** | `POST /orders/{id}/allocate/`（🔒 前端 0 引用） | `IsProcurementOrAdmin` |
| **兼容性表** | `/compatibility/` CRUD（前端 0 调用；仅出现在 `/products/{id}/detail` 的返回字段注释里） | 读 `AllowAny`；写 `is_staff` |

**合计 336 个 path×method** —— 注意这是**去重后的 path×method 计数，不是"业务动作"数**：
每个 ViewSet 在 URL resolver 里还会多一份 `.json` 后缀变体（`\.(?P<None>[a-z0-9]+)`），
同一业务动作因此常被计 2 次。去格式变体后实际是 **140 条路径 / 211 个 method**。

🔒 = 有端点、前端无入口。

### 仍未收录的（诚实声明，不假装是全量）

| 类别 | 内容 | 为什么不写进正文 |
|---|---|---|
| 系统/元信息 | `GET /api/schema`、`GET /api/docs`、`GET /robots.txt`、`GET /sitemap.xml`、`GET /sitemap-static.xml`、`GET /sitemap-{kind}-{page}.xml` | 面向爬虫与开发者，不是业务操作 |
| ViewSet 详情路由 | `/applications/{id}`、`/protocols/{id}`、`/references/{id}`、`/research-goals/{id}`、`/quotes/{id}`、`/skus/{id}`、`/batches/{id}`、`/documents/{id}`、`/pdf-files/{id}` 的 `GET/PUT/PATCH/DELETE` | 正文各章已按"CRUD"概括；权限与列表路由相同 |
| 前端 0 引用的内部/工具端点 | `/catalog-groups`、`/pubchem-cache`、`/documents`、`/pdf-files`、`/admin/orders/{id}/confirm`、`/inventory/movements`（`api/inventory.js:28` 有封装，但页面走 `getInventoryDetail`） | 无操作入口，写进说明书会误导操作员 |

**覆盖率实测**：`python scripts/audit_manual_coverage.py` ⇒ 路径 **134/141**、method **201/212（94.8%）**。明细与剩余局限见 §D.4 / §D.5。

---

# 附录 C 如何复核本文

```bash
cd src_claude

# 1) 权限矩阵（336 端点 × 8 身份，0 次 HTTP）
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

**文档版本** V2.0 · 2026-10-22 · 对应代码 `cc4e8f2` · 覆盖 8 身份 / 336 端点 / 53 页面 / 20 内部台

---

# 附录 D 本轮审计记录（V1.0 → V1.1）

> 📋 **交付前审计另见 [`MANUAL_DELIVERY_AUDIT.md`](./MANUAL_DELIVERY_AUDIT.md)**：
> 2026-10-22 按 14 项交付标准做了 6 类机械检查（引用 106/106、页面 52/52、交叉引用 58/58、
> 锚点 66/66、表格 141/141、接口抽查 14/14），发现并修复 11 处问题，
> 结论为"可交付"，并列出 3 条必须随文告知的边界。

> 这一节记录的是**我自己上一版写错/漏掉的东西**。写出来是为了让后来者知道哪些结论曾经不可靠、
> 以及用什么方法才把它变成可靠的 —— 不留审计痕迹的文档，下一轮还会犯同样的错。

## D.1 审计方法（三个脚本，可复跑）

| 脚本 | 解决什么 | 能自动发现的问题 |
|---|---|---|
| `scripts/audit_manual_refs.py` | 文档里 83 条 `file:line` 的**文件是否存在、行号是否越界、路径是否有歧义** | 行号溢出、指向不存在的文件、裸文件名无法定位 |
| `scripts/dump_manual_refs.py` | 把每条引用的**目标行原文**连同文档主张一起打出来 | 引用存在但**内容答非所问**（语义错配） |
| `scripts/audit_manual_coverage.py` | 路由 name 与 140 条端点路径的**覆盖率** | 漏页、漏端点 |
| `scripts/audit_manual_numbers.py` | 按守卫规则**重新归类每个路由**，核对 53 = 23 公开 + 10 客户 + 20 内部 | 数字自相矛盾、把壳路由重复计数 |

```bash
cd src_claude
python scripts/audit_manual_refs.py
python scripts/dump_manual_refs.py --grep COA     # 抽样人读
python scripts/audit_manual_coverage.py
python scripts/audit_manual_numbers.py
```

## D.2 已修正的错误（8 处）

| # | V1.0 写的 | 实际是什么 | 影响章节 |
|---|---|---|---|
| 1 | "页面无 try/catch ⇒ **失败静默 / 用户以为成功**" | **错**。全局拦截器 `utils/http.js:74-102` 对所有非 401 错误弹 `ElMessage.error(后端 message)`；401 还会**清 token + 整页跳 `/login`**。真正静默的只有**前端早退（请求没发出）** | §5.2、§7.8.3、§11.2 共 14 行 + 新增 §0.6 讲机制 |
| 2 | 把 `isInternal` 标成 **37–43 行** | **行号越界**（文件仅 37 行）；实际是 **32–36 行** | §0.4 |
| 3 | 9 处**裸文件名**引用（`models.py` / `services.py` / `admin.py` / `serializers.py` / `views.py` 后直接跟行号） | 仓库里同名文件有 3 个以上，**读者无法定位** | §4.2、§5.2、§7.3.4、§11.4 |
| 4 | 4 个公开页完全没写（About / Privacy / Terms / 404） | 它们是 23 个公开页的一部分，且文案硬编码在前端 | 新增 §F1-10 |
| 5 | **登出流程完全缺失** | `POST /auth/logout` 存在（`api/auth.js:19`、`stores/auth.js:158`），且在 2 个布局里有入口 | 新增 §0.7 |
| 6 | 附录 B 漏了 7 组**有前端封装**的端点 | `/graph`（8 处调用）、`json-ld`×3、`/search/suggest`、`/organizations/create`、`/products/enrich-from-pubchem/`、`related`/`faq`、`restore`、`allocate`、`compatibility` | 附录 B 补 10 行 |
| 7 | 「哪条路由算一个页面」表述错：写成「8 个 `/ops` + `/workspace` 壳 + 10 个子页」 | 数字 19 是对的，但算式漏了 `Dashboard` 本身（`/workspace` 的子路由 `path:''` 才是真页面，父级只是壳）。已改为「8 个 `/ops` + 11 个 `/workspace` 页面」，并补三套计数口径：`path:` 56 / 路由 `name` 54 / 不同 URL 52 | §0.1、§0.2、§D.4 |
| 8 | 「`isStaff` 在内部页只出现 **1 处**」 | 不精确。`isInternal` 守卫在 **10 处**（9 个 workspace 页 + AdminLayout，管"能不能进"）；**元素级**角色条件渲染确实只有 1 处（`ProductsPage.vue:666`）。两者性质不同，混为一谈会误导读者 | §0.4、§5.1 |

## D.3 V1.0 完全没写的重大缺口（本轮新发现）

| # | 缺口 | 为什么重要 |
|---|---|---|
| 1 | **全站没有"忘记密码/重置密码"**，且改密码是假成功 | 用户忘记密码 = **永久锁死**，只能运维上 Django admin 手工重置。见 §11.3.0 |
| 2 | **全局错误信封与 401 行为** | 决定"用户看到的错误提示从哪来、为什么会被整页踢出、为什么未保存表单会丢"。见 §0.6 |
| 3 | **客户侧中英混杂** | `ProductDetail` 点收藏弹中文 `请先登录`、`WishlistPage` 整页中文。见 §11.5 |
| 4 | **内部台侧栏没有登出入口** | `/workspace` 只有 `Back to Site`，必须先回前台才能登出。见 §0.7 |

## D.4 覆盖率实测（改稿后重算）

| 维度 | 覆盖率 | 说明 |
|---|---|---|
| 页面（不同 URL 52 个） | **52/52** | V2.0 起第 12 章逐页覆盖，含 `NotFound`（见 §12.1）；脚本 `audit_manual_delivery.py` 实测 52/52、0 漏 0 编造 |
| 端点路径（去 `.json` 变体） | **133/140 = 95%** | 未提及的 7 条全是 `{id}` 详情路由或 `sitemap-{kind}-{page}.xml` |
| 端点"详细描述" | 约 **124/140** | ⚠️ "路径出现"≠"讲清了"：约 9 类 ViewSet 详情路由只在"未收录清单"里点了名，正文按 CRUD 概括 |

## D.5 本说明书仍然存在的局限（不掩盖）

| # | 局限 | 影响 | 怎么才能补上 |
|---|---|---|---|
| 1 | **全部是静态推断 + 权限求值，没有一条在真实浏览器里验过** | 文档说的是"代码会怎样"，不是"实测怎样"。**这是最大局限** | 按 `ROLE_TEST_PLAN.md` 的 L3 层跑 Playwright，逐条把断言变成实测 |
| 2 | `has_object_permission` 未覆盖 | 地址簿的机构隔离、对象级不可见，只写了设计意图未验证 | 需真实对象 + 两机构账号 |
| 3 | `get_queryset` 收窄未覆盖 | "客户只能看自己的订单"是按代码读出来的，未实证 | 同上 |
| 4 | 组件**运行时**条件渲染只读到表达式 | 例如某按钮 `v-if` 依赖异步结果，静态只能确认条件存在，不能确认何时为真 | 浏览器实测 |
| 5 | 未验证服务端错误文案的**实际渲染** | 403 弹的是 DRF 英文原文，这是读 `core/exceptions.py` 推出来的 | 打一次 403 看 toast 文案 |

## D.5.1 已经修掉的缺陷（不在 §11 里重复列）

| 日期 | 缺陷 | 修法 | 回归 |
|---|---|---|---|
| 2026-10-22 | **`/po/downloads` 永远空态**：页面按 `o.invoice \|\| o.attachments.length` 过滤，但 `/orders/` 列表序列化器不返回这两个字段 | `OrderListSerializer` 增加最小子集 `invoice{id,invoice_no}` / `attachments[{id,original_filename}]`；`OrderViewSet` 与 `/admin/orders/` 的 queryset 加 `select_related('invoice')` + `prefetch_related('attachments','items')` 防 N+1；`items_count` 改用 `len(obj.items.all())` 以吃 prefetch 缓存 | 后端 `apps/transactions` + `apps/commerce` 全绿；`p1-customer-pages` 7/7（含"无数据客户仍空态"反例） |

## D.6 下一轮建议（按投入产出排序）

> **2026-10-22 更新**：本节原有 5 条 P0/P1 已全部完成，留档如下；当前建议见文末「下一步」。

| 原优先 | 原建议 | 状态 |
|---|---|---|
| ~~P0~~ | ~~给 §11.3.0 三条账号自救问题定方案~~ | ⏳ **仍未做**（唯一的 P0 遗留） |
| ~~P0~~ | ~~用 Playwright 实测 3 个 DEAD 页面~~ | ✅ 已完成（`M-10~M-12`） |
| ~~P1~~ | ~~把 §0.6 错误机制做成真实抓包验证~~ | ✅ 已完成（`M-20`、`M-21`） |
| ~~P1~~ | ~~补 ViewSet 详情路由的字段级说明~~ | ✅ 已完成（第 12 章 + 附录 B） |
| ~~P2~~ | ~~把附录 A 状态机做成按钮矩阵~~ | ✅ 已完成（§7.8.2 状态推进按钮矩阵） |

**当前唯一遗留**：账号自救能力为零（改密码假成功 + 无忘记密码 + 登录页重发死链）。
处置方案见 §11.3.0。

---

# 附录 E 实测证据索引

本文所有 `[M-nn]` 标记的出处，以及完整实验环境、复跑命令、以及**尚未实测的 7 项**，都在：

**`docs/e2e/MANUAL_FACTS_MEASURED.md`**

该文件同时记录了「实测推翻了旧版哪 8 句话」的逐条对照表 —— 读它可以知道本文哪些结论曾经不可靠。

> ⚠️ **一处已知且有意为之的口径差**：`ROLE_CAPABILITY_MATRIX.json`（权限类求值产物）里
> `IsStaffUser` 仍记 **7**，而正文 §0.4 按 **6** 记。原因：HTTP 实测发现 `POST /verified/`
> 实际只要登录（`get_permissions()` 按方法分权），求值按类属性读错了。
> ⇒ **正文以实测为准，JSON 保留原始求值结果**为的是可追溯；这不是笔误。

V1.3 又补齐 5 项（对象级权限、邮件、跨浏览器、视觉响应式、并发），证据编号 `M-30 ~ M-61`；
生产匿名边界为 `M-70`。**只剩 2 项未覆盖**（生产登录态、PG 并发），阻塞原因写在实测清单 §10。

---

---

# 附录 F 错误提示对照表

> 用途：运营/客服看到用户报错时，按"屏幕上那句话"查原因与处置。
> 文案来自实测（`MANUAL_FACTS_MEASURED.md`）与代码里的字符串常量。

## F.1 登录与账号

| 屏幕上的提示 | 真实原因 | 怎么办 |
|---|---|---|
| `Incorrect username or password. Please check and try again.` | 账号或密码错（HTTP 401） | 核对账号；⚠️ **产品没有"忘记密码"功能**，只能运维上 Django admin 重置 |
| `Your email address is not verified. Please check your inbox for the verification link.` | `email_verified=false`，登录被拒（403） | 让用户点注册时的验证邮件；⚠️ **登录页的"重发"按钮是死链**，只能重新走注册页或由运维改 `email_verified` |
| `Session expired, please sign in again` | 任意请求返回 401（token 失效/被吊销） | 重新登录；⚠️ 会**整页跳转**，未保存的表单会丢 |
| `Please enter your username` / `Please enter your password` | 前端必填校验 | 补填 |
| `Email already registered` / `Username already exists` | 注册重复 | 换用户名或找回原账号（需运维） |

## F.2 权限（403）

| 屏幕上的提示 | 真实原因 | 怎么办 |
|---|---|---|
| `You do not have permission to perform this action.` | 403：你的身份不在该端点的允许集合里 | 看 §10.1 确认该动作是否属于你的角色；采购改产品、非 staff 开票等都属此类 |
| 页面显示 `Failed to load dashboard data` | `GET /admin/dashboard-stats/` 403（`IsStaffUser`） | 采购/`role=admin` 无此权限，正常现象 |
| 页面显示 `Failed to load review queue.` + 列表 0 行 | `GET /verified/` 403（`IsStaffUser`） | 该页只给 staff |
| 页面显示 `Couldn't load orders.` **并且** `No orders found` | `GET /admin/orders/` 403（`IsAdminUser`） | ⚠️ **不是"没有订单"**，是没权限。采购请用 `/ops/po/review` |
| `Couldn't load this order.` | `GET /admin/orders/{id}/` 403 | 同上 |

## F.3 业务校验（400）

| 屏幕上的提示 | 原因 | 怎么办 |
|---|---|---|
| `Basket is empty`（`EMPTY_BASKET`） | 购物车为空就点结账 | 先加购 |
| `SKU {code} is out of stock`（`OUT_OF_STOCK`） | 该 SKU `inventory_status = out_of_stock` | 换 SKU 或改库存状态（注意：库存台数量与这个徽章**不联动**，见 §F5-6） |
| `catalog_no: 该字段已存在`（字段校验被展开成人话） | 唯一冲突 | 换编号 |
| `该 产品-方法 已存在 verified 关系`（`unique_conflict`） | 重复建 verified | 去审核台处理已有的那条 |
| `rep_id is required` / `Invalid rep_id` | 指派销售没填 / 填了非采购非 admin 的用户 | 填**数字用户 ID**（不是用户名） |
| `PO number is required for Purchase Order payment` | 选 PO 支付但没填 PO 号 | 补填 |

## F.4 服务端异常（500）

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `Assign Rep` 填**用户名**后弹 `Action failed` | `ValueError`（`pk` 期望整数）→ 500 + HTML 错误页 | 改填**数字 ID**；实测填数字 26 成功 |
| 本地/开发环境并发操作弹 `Action failed` | SQLite `database is locked` | 本地特有；**生产 PG 无此问题**（实测 10/10 成功） |

## F.5 点了没反应（三种沉默，判断责任方用）

| 现象 | 类型 | 判断方法 |
|---|---|---|
| 点了，无 toast、无变化 | **① 前端早退**（请求没发出） | 看该动作是否必填未填（Rep ID / 收款金额 / 库存数量与原因） |
| 点了，弹红 toast | **② 请求被拒**（4xx/5xx） | 读 toast 文案，按 F.2/F.3 处理 |
| 提示成功，但数据没变 | **③ 假成功** | 目前已知两处：`/settings` 改密码、`Internal Notes` 输入框 |

---

# 附录 G 术语表

| 术语 | 全称 / 含义 | 在本系统中的位置 |
|---|---|---|
| **RG** | Research Goal 研究目标 | 知识链顶层；`/research-goals` |
| **AP** | Application 应用场景 | 挂在 RG 下；`/applications` |
| **Method** | 实验方法 | 挂在 AP 下；`/methods` |
| **Protocol** | 实验方案（带版本 `v{n}`） | 挂在 Method 下；`/protocols` |
| **PMR** | Product-Method Relation 产品-方法关系 | 两条边：`derived_relevance`（算法派生）/ `verified_applicability`（人工策展） |
| **verified** | 已验证适用性 | 需 staff 审核；通过后公开到产品页 |
| **SKU** | 最小可售单元（包装规格 + 价格 + 币种 + 现货状态） | 产品详情右栏、产品编辑页 Section 7 |
| **COA** | Certificate of Analysis 质检报告 | 挂批次；`draft → published` 才能被客户下载 |
| **SDS** | Safety Data Sheet 安全数据表 | 挂产品；同上门控 |
| **RUO** | Research Use Only 仅供科研 | 商品页/订单页/发票上的法定标注 |
| **PO** | Purchase Order 采购订单 | 客户在 `/po/submit` 提交；内部在 PO 审核台处理 |
| **RFQ** | Request for Quotation 询价单 | `/quote-request`，**匿名也能提交** |
| **Quote** | ⚠️ 三个不同的东西：① RFQ 询价线索 ② `Quote` 实体（有 `quote_no`）③ 订单的 `quote_pending` 状态 | 详见 §9.5，沟通时必须说清是哪个 |
| **AR** | Accounts Receivable 应收账款 | `/ops/po/ar` 账龄 |
| **is_staff** | Django 的"员工"标记 | **实际权限的主开关**（231 个端点看它） |
| **role** | 业务角色（researcher/procurement/editor/admin） | 只影响 17 个端点 |
| **is_org_admin** | 机构管理员标记 | ⚠️ **对权限零影响**，仅展示徽章 |
| **is_superuser** | 超管 | 多物理删除 + Django admin |
| **Basic Auth** | nginx 第一层认证 | 生产全站挂着；`realm="SciReAgent Internal Test"` |
| **X-Auth-Token** | 应用层 token 头 | 与 Basic 并存（不用 `Authorization` 以免冲突） |
| **收件箱（Outbox）** | `EmailOutbox` 待发邮件表 | ⚠️ 当前 **2984 封全 pending、模板表 0 条**，见 §11.3 |

---

# 附录 H 本地环境与实验栈

想自己复跑本文的实测，需要两套环境。**两套都与你的日常开发栈隔离**。

## H.1 独立探测栈（用来跑权限/页面实测，不碰开发库）

```bash
cd src_claude
cp backend/db.sqlite3 backend/db_probe.sqlite3          # 99MB 副本
cd backend && DB_ENGINE=sqlite SCIREAGENT_DB_NAME="$(pwd)/db_probe.sqlite3" \
  venv/Scripts/python.exe ../scripts/probe_seed_accounts.py    # 建 7 个身份账号
DB_ENGINE=sqlite SCIREAGENT_DB_NAME="$(pwd)/db_probe.sqlite3" \
  venv/Scripts/python.exe manage.py runserver 127.0.0.1:8011 --noreload
# 另开终端（必须 E: 物理路径，C: 是联接会让 vite 解析失败）
cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
VITE_API_PROXY=http://127.0.0.1:8011 ./node_modules/.bin/vite --port 5174 --strictPort
```
7 个探测账号：`probe_researcher` / `probe_orgadmin` / `probe_procure` / `probe_adminrole` /
`probe_staff` / `probe_super` / `probe_unverified`，密码统一 `Probe#2026!`。
**用完删掉副本**：`rm backend/db_probe.sqlite3`。

## H.2 PostgreSQL（并发结论只认它）

见 **[`PG_QUICKSTART.md`](./PG_QUICKSTART.md)**：集群 `pgdata-l4` 在 5433，角色 `scireagent`，
库 `scireagent_l4`，**不需要 initdb**。

## H.3 复跑命令一览

| 想复核什么 | 命令 |
|---|---|
| 权限矩阵（0 次 HTTP） | `python scripts/role_capability_probe.py` |
| 真实 HTTP 权限（8 身份） | `python scripts/http_role_probe.py` |
| 对象级权限 / 数据隔离 | `python scripts/http_object_probe.py`、`http_object_probe2.py` |
| 求值 vs 实测比对 | `python scripts/compare_probe_vs_http.py` |
| 页面 × 角色判定 | `python scripts/page_role_matrix.py` |
| PG 并发用例 | `cd backend && venv/Scripts/python.exe ../scripts/run_pg_tests.py` |
| 浏览器实测（关键事实） | `npx playwright test manual-facts-probe --project=chromium\|firefox\|webkit` |
| 浏览器实测（**53 页加载级**） | `npx playwright test manual-pages-smoke --project=chromium` |
| 页面覆盖率核算 | `python scripts/check_browser_coverage.py` |
| 交付审计（6 项机械检查） | `python scripts/audit_manual_delivery.py` |
| 生产匿名边界 | `python scripts/prod_anon_probe.py` |
| 生产登录态只读 | `SC_BASIC_USER=… SC_APP_PASS=… python scripts/prod_readonly_probe.py` |

> ⚠️ 所有命令都要**剥代理**：`env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy`；
> 本机 `http_proxy` 会把回环请求转出去，实测得到 502。

---
