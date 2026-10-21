# 全站测试发现的真实缺陷（2026-10-21 汇总）

> 这份文件是**测试的产出物**，不是猜测清单。每条都带：复现路径、代码证据（`文件:行号`）、
> 实测证据（E2E 用例 / API 响应）、严重度。
> ⚠️ 本轮只**发现并固化断言**，**未修代码**。修复应单独排期，修完把对应用例从
> "记录现状"改成"断言正确行为"（这一步必须做，否则修了也没人拦）。

## 严重度定义

- **P0** 数据隔离/资金安全/主体功能不可用
- **P1** 核心流程关键环节缺失或出错，有 user-facing 影响
- **P2** 体验/合规瑕疵，有绕过办法
- **P3** 文案/死代码

---

## 状态总览

| # | 级别 | 一句话 | 状态 |
|---|---|---|---|
| D1 | P0 | `/ops/po/organizations` 订单查看~~忽略机构筛选~~ | ✅ **已修 2026-10-21** |
| D2 | P0 | `/orders` ~~无分页 ⇒ 第 21 单起看不到、total 错~~ | ✅ **已修 2026-10-21** |
| D3 | P1 | `/ops/po/invoicing` 一开票订单就消失 | ⬜ 待修 |
| D4 | P1 | `/ops/orders` 状态筛选缺 PO 流程态（且无分页） | ⬜ 待修 |
| D5 | P1 | `/po/orders` 筛选缺 `quote_pending` / `quoted` | ⬜ 待修 |
| D6 | P1 | `/po/orders/:id` RUO 声明恒显示 | ⬜ 待修 |
| D7 | P2 | a11y：25 页 50 处 color-contrast + 1 critical | ⬜ 待修 |
| D8 | P3 | `PoSubmit.vue:156-159` 死代码 alert | ⬜ 待修 |
| D9 | P3 | `/po/addresses` 过期 callout 文案 | ⬜ 待修 |
| D10 | P2 | `/orders` `/ops/orders` 错误只有 4 秒 toast（静默失败） | ⬜ 待修 |

---

## D1 · P0 · ✅ **已修（2026-10-21）** · `/ops/po/organizations` 的「订单查看」忽略机构筛选，显示全库订单

| 项 | 内容 |
|---|---|
| 现象 | 在机构管理页选中任一机构，右侧「\<机构名\> — Orders」表格显示的是**全库 937 单**，与所选机构无关 |
| 复现 | staff 登录 → `/ops/po/organizations` → 点任一机构行 → 对比不同机构右侧表格 |
| 实测（修前） | admin token 下 `organization_id=6` 与 `organization_id=4` 返回**完全同一批**订单 |
| 根因 | 前端 `adminPo.js:94` 传 `organization_id=`，但后端 `OrderViewSet.filterset_fields = ['status']`（`transactions/api/v1/views.py:14`）**只认 status**，其余查询参数被 DjangoFilterBackend **静默丢弃** |
| 影响 | **跨机构订单可见**（内部台租户隔离形同虚设）；运营按机构查单一律拿到错的 |
| **修法** | `filterset_fields = ['status', 'organization', 'organization_id']` —— 两种写法都收（`_id` 是本仓库既有惯例，见 `commerce/api/v1/views.py:59` 的 `product_class_id`；`organization` 是 FK 规范名）。**前端零改动** |
| **为什么不会提权** | `get_queryset()` **先**按用户收窄（客户只看自己的），过滤只在其**之上**再收窄 ⇒ 客户传别人的机构 id 依然什么都看不到（已写反向断言钉住） |
| **验证** | 后端 `test_cross_org_visibility.py::OrderOrganizationFilterTest` **5 例**（无过滤对照 / 按 id 收窄 / 别名生效 / 非法 id 被 400 拒绝而非静默回落 / 客户不得提权）；E2E `ops-po-desk-gaps.spec.cjs` 两条（有单机构渲染表格、0 单机构空态）**2 passed** |
| **线上确认** | 重启后端后实测：`organization_id=4 → 983`、`organization_id=6 → 0`（修前两者都是 984） |
| ⚠️ 附带发现 | 修复后原「点机构行 → 有订单行」用例**变红**：它点的是 0 单机构，却断言有行 —— 因为修前它借缺陷（显示全库）才绿。已改为点有订单的机构，属"测试在钉住缺陷"的典型，已一并纠正 |

## D2 · P0 · ✅ **已修（2026-10-21）** · `/orders` 客户订单历史永久不可达（第 21 单起看不到），且 total 显示成 20

| 项 | 内容 |
|---|---|
| 现象 | 客户订单历史页只显示 20 条，**没有分页也没有筛选**；页面上的总数显示 20，而真值是 976+ |
| 复现 | customer/staff 登录 → `/orders` |
| 实测响应 | 信封 `{success, data: [20 条], meta: {pagination: {count: 984, next, previous}}}` |
| 根因（三层） | ① `OrderListPage.vue` 全文无分页控件；② `stores/orders.js` 的 `fetchOrders` 从不传 `page` ⇒ 恒第 1 页；③ 同文件 `total.value = data.count \|\| data.meta?.pagination?.count \|\| orders.value.length` —— 此处 `data` 已是 `res.data`，而 `core/renderers.py:31-37` 把分页信息放在**信封的 `meta.pagination`**、并把 `data` 直接替换成结果数组 ⇒ 前两个分支永远 undefined ⇒ `total` 恒为当前页条数 20 |
| 影响 | **客户永远查不到自己 21 单以前的订单**（售后、对账、复购全靠它） |
| **修法** | ① `stores/orders.js` 改为读**信封的** `meta.pagination.count`，并显式带 `page` / `page_size`；② `OrderListPage.vue` 引入通用组件 `DataPagination`（`total > pageSize` 才显示），翻页**重新向后端取数**（不在前端切片，否则仍拿不到第 21 单） |
| **验证** | E2E `orders-pagination.spec.cjs` **2 例**：①总数必须 > 20（缺陷时恒 20）；②翻第 2 页内容不同、能回第 1 页。实测 **2 passed / 10.0s** |
| ⚠️ 同类未修 | `/ops/orders`（`AdminOrdersPage.vue`）**同样没有分页**，且状态筛选缺 PO 流程态（见 D4）。不在本次 D1/D2 范围内，单独排期 |

## D3 · P1 · `/ops/po/invoicing` 一开票，订单就从列表消失，再也进不去「记录收款」

| 项 | 内容 |
|---|---|
| 现象 | 对 DELIVERED 订单开票后，刷新列表该订单**消失**，无法再进入「Record Payment」 |
| 根因 | 列表过滤 `status === 'delivered' \|\| o.invoice`（`PoInvoicingDesk.vue:21`），但列表用的 `OrderListSerializer.fields`（`serializers.py:56-61`）**不含 `invoice` 字段** ⇒ `\|\| o.invoice` 恒假；开票又把订单推进成 `invoiced` ⇒ 两个条件同时不成立 |
| 实测 | 50 行列表数据里含 `invoice` 键的 = **0 行** |
| 影响 | 开票后**收不回款也记不上收款**（资金链闭环断了） |
| 用例 | `ops-po-desk-gaps.spec.cjs` 的开票用例改为"切走再切回验服务端真值"，避开该缺陷；缺陷本身在注释里写明 |

## D4 · P1 · `/ops/orders` 状态筛选缺 PO 流程态

| 项 | 内容 |
|---|---|
| 现象 | 状态下拉只有 legacy 9 态，**没有** `po_received` / `delivered` / `cancelled` / `in_production` |
| 根因 | `AdminOrdersPage.vue:54-64` 的下拉选项写死了一套旧状态 |
| 实测 | `selectOption('po_received')` 45s 内报 `did not find some options` |
| 影响 | 运营在订单管理里**筛不出待审单**，而详情页与三个内部台全用 PO 状态机 ⇒ 列表与详情状态词汇不一致 |
| 用例 | `state-branches-po.spec.cjs` 用「Confirmed 筛选」+「Quote Pending 下我的行消失」做反向断言，绕开缺失项 |

## D5 · P1 · `/po/orders` 筛选缺 `quote_pending` / `quoted`

| 项 | 内容 |
|---|---|
| 现象 | 客户 PO 列表的筛选下拉里没有「待报价 / 已报价」 |
| 根因 | `config/poConstants.js:38-49` 的选项表缺这两项 |
| 实测 | 库内真实存在 `quote_pending` 40 单、`quoted` 33 单 |
| 影响 | 客户无法按报价状态筛自己的单 |

## D6 · P1 · `/po/orders/:id` 的 "For Research Use Only" 声明恒显示

| 项 | 内容 |
|---|---|
| 现象 | 非 RUO 产品也显示 RUO 声明 |
| 根因 | `PoOrderDetail.vue:105` 用 `it.is_ruo !== false` 判定，而 `OrderItemSerializer`（`serializers.py:24-35`）**不返回 `is_ruo`** ⇒ `undefined !== false` 恒为真 |
| 实测 | 明细 `items[]` 里无 `is_ruo` 键 |
| 影响 | **合规声明误用**（把非 RUO 试剂标成仅科研用） |

## D7 · P2 · a11y：25 个页面 50 处 `color-contrast` + 1 处 critical 未清

| 项 | 内容 |
|---|---|
| 实测 | 35 页扫描：**10 页通过**、25 页有 `serious`（color-contrast，共 50 处） |
| critical | 仅剩 `ResearchGoalIndex` 1 处（axe 报 `.el-table th`，疑 Element Plus 库判定问题，未修） |
| 已修 | 本轮之前已把全站 critical 从 **10 处 / 4 页**降到 **1 处 / 1 页**（AppInput 39 实例、AppSelect 14 实例的 for/id 与 aria-label 透传） |
| 为什么没继续修 | 改对比度要动设计令牌（`frontend/src/assets/css/main.css`），会连带 `visual-tokens.spec.cjs` 的"全站一致"断言 ⇒ 需单独一轮 |

## D8 · P3 · `PoSubmit.vue:156-159` 第三条 alert 是死代码

| 项 | 内容 |
|---|---|
| 现象 | 该 `alert('Delivery date cannot be in the past.')` 在 UI 路径上**永远不执行** |
| 根因 | `#po-f5` 带 `:min="minDeliveryDate"`（`PoSubmit.vue:232`），浏览器先做 HTML5 约束校验并直接拦掉 `submit` 事件，`handleSubmit` 根本不进 |
| 实测 | 失败现场为原生 `rangeUnderflow` 气泡；`validity.rangeUnderflow === true`；`/api/v1/orders/po/` 请求数 **0** |
| 处理 | 已把**真实行为**固化成断言（alert 不出现 + 0 次请求），避免误判成"漏测" |

## D9 · P3 · `/po/addresses` 顶部 callout 文案过期

| 项 | 内容 |
|---|---|
| 现象 | 页面顶部写着「后端 `/addresses/` CRUD 计划 P1 落地」 |
| 实测 | 新增→编辑→删除闭环**全通**（`po-addresses-crud.spec.cjs` 1 passed） |
| 处置 | 删掉/更正该 callout（改文案，不动逻辑） |

## D10 · P2 · `/orders` `/ops/orders` 无持久错误横幅，只有瞬时 toast

| 项 | 内容 |
|---|---|
| 现象 | 列表请求 500 时，用户只看到 4 秒 toast，页面落成"空态"（看起来像"你没有订单"） |
| 证据 | `src/utils/http.js:96-97` 全局 toast；`src/stores/orders.js:22-24` 与 `admin/AdminOrdersPage.vue:33-35` 只 `console.error` |
| 影响 | **静默失败**：接口挂了与"真的没数据"对用户不可区分 |
| 对比 | `/ops/orders/:id` 的动作失败**有**持久 `.error-banner`（`AdminOrderDetail.vue:125`）⇒ 全站错误提示不统一 |

---

## 附：这些缺陷是怎么被"测"出来的（方法论）

1. **状态分支穷举**（S 维）：每页先读源码列出全部状态分支，再**逐分支走一遍**，且优先写**反向断言**（"在 A 状态可见、在 B 状态必须不可见"）。D3/D6 都是反向断言抓出来的。
2. **故障注入**（错误路径）：D10 是用 `page.route` 把接口打成 500 后看页面反应抓到的。
3. **相对断言替代绝对断言**：D1 是"换机构看右表变不变"，不依赖任何计数。
4. **禁止把 skipped 当通过**：D1 的正确预期写成 `test.fixme` 而不是删掉，保证缺陷不会被"绿了"掩盖。
