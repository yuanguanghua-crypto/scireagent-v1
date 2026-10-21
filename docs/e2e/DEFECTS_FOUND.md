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

## D1 · P0 · `/ops/po/organizations` 的「订单查看」忽略机构筛选，显示全库订单

| 项 | 内容 |
|---|---|
| 现象 | 在机构管理页选中任一机构，右侧「\<机构名\> — Orders」表格显示的是**全库 937 单**，与所选机构无关 |
| 复现 | staff 登录 → `/ops/po/organizations` → 点任一机构行 → 对比不同机构右侧表格 |
| 实测 | admin token 下 `organization_id=6` 与 `organization_id=4` 返回**完全同一批**订单（库内 937 单全属 org4，org6 一单也没有） |
| 根因 | 前端 `adminPo.js:93-95` 传 `organization_id=`，但后端 `OrderViewSet.filterset_fields = ['status']`（`transactions/api/v1/views.py:14`）**只认 status**，其余查询参数被静默丢弃 |
| 影响 | **跨机构订单可见**（内部台的租户隔离形同虚设）；运营按机构查单一律拿到错的 |
| 用例 | `frontend/e2e/ops-po-desk-gaps.spec.cjs` 里有一条 `test.fixme` 固化了"正确预期"（选 0 单机构时右表应为空）——修好后把 fixme 去掉即成为回归闸门 |

## D2 · P0 · `/orders` 客户订单历史永久不可达（第 21 单起看不到），且 total 显示成 20

| 项 | 内容 |
|---|---|
| 现象 | 客户订单历史页只显示 20 条，**没有分页也没有筛选**；页面上的总数显示 20，而真值是 976 |
| 复现 | customer 登录 → `/orders` |
| 实测响应 | `data` 是**纯数组 20 条**；`meta.pagination = {count: 976, next: ...page=2}` |
| 根因 | ① `OrderListPage.vue` 全文无分页/筛选控件；② `stores/orders.js:14-22` 从不传 page；③ 后端 `PAGE_SIZE=20`（`config/settings/base.py:174`）；④ `stores/orders.js:19-20` 的 `data.results \|\| data.data \|\| data` 命中**数组分支**，而 `data.count` / `data.meta` 都不存在 ⇒ `total` 落到 `length = 20` |
| 影响 | **客户永远查不到自己 21 单以前的订单**（售后、对账、复购全靠它） |
| 用例 | `state-branches-commerce.spec.cjs`「`/orders` 空态」+ 徽章断言；分页/筛选**故意没写用例**（页面根本没有），在报告里记为缺陷而不是假绿 |

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
