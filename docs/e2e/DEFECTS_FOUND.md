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
| D3 | P1 | `/ops/po/invoicing` ~~一开票订单就消失~~ | ✅ **已修 2026-10-21** |
| D4 | P1 | `/ops/orders` ~~状态筛选缺 PO 流程态（且无分页）~~ | ✅ **已修 2026-10-21** |
| D5 | P1 | `/po/orders` ~~筛选缺 `quote_pending` / `quoted`~~ | ✅ **已修 2026-10-21** |
| D6 | P1 | ~~`/po/orders/:id` RUO 声明恒显示~~ | ✅ **已修 2026-10-21** |
| D7 | P2 | ~~a11y 对比度（25 页、180 处节点）~~ | ✅ **已修 2026-10-21**（**180 → 0**） |
| D8 | P3 | ~~`PoSubmit.vue` 死代码 alert~~ | ✅ **已删 2026-10-21** |
| D9 | P3 | ~~`/po/addresses` 过期 callout~~ | ✅ **已删 2026-10-21**（附守卫用例） |
| D10 | P2 | ~~错误只有 4 秒 toast（静默失败）~~ | ✅ **已修 2026-10-21**（4 页统一持久横幅） |
| D11 | P2 | ~~`AppInput` 的 label 与输入框从未真正关联（EP 吞 id）~~ | ✅ **已修 2026-10-21**（改 aria-label；补表单态 a11y 扫描） |

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

## D3 · P1 · ✅ **已修（2026-10-21）** · `/ops/po/invoicing` 一开票，订单就从列表消失，再也进不去「记录收款」

| 项 | 内容 |
|---|---|
| 现象 | 对 DELIVERED 订单开票后，点「Refresh」刷新队列，该订单**消失**，无法再进入「Record Payment」 |
| 根因 | 队列过滤 `all.filter(o => o.status === 'delivered' \|\| o.invoice)`（`PoInvoicingDesk.vue` 的 `load()`），但列表用的 `OrderListSerializer.fields`（`serializers.py:56-61`）**不含 `invoice`** ⇒ `o.invoice` 恒 `undefined`；开票又把订单推进成 `invoiced` ⇒ 两个条件同时不成立 |
| 为什么难发现 | **详情接口**用的是 `OrderDetailSerializer`（含 `invoice`）⇒ 详情能正常显示发票，**只有队列坏掉**；开票后不刷新页面也看不出来（`issue()` 只调 `openOrder`，不调 `load()`） |
| 影响 | 开票后**收不回款也记不上收款**（资金链闭环断了） |
| **修法** | 队列改为**只看状态**：`['delivered','invoiced'].includes(o.status)`。不再依赖"列表 payload 里恰好带了 invoice"这种脆弱前提；语义与状态机一致（`delivered` 待开票 / `invoiced` 待收款 / `paid·completed·cancelled` 离开） |
| **为什么 `invoiced` 必须留在队列** | 部分付款时 `PaymentArService.pay` **不**改订单状态（只有付清才 `Order.Status.PAID`，`services.py:520-530`）⇒ 停在 `invoiced` 的单还欠款，必须留在收款队列 |
| **前置核实（防漏收）** | 查过全库 `Invoice.status × Order.status`：`issued` 发票全部挂在 **cancelled** 订单上，**不存在"已开票但订单已 paid/completed"** ⇒ 按状态过滤不会漏掉应收款订单 |
| **验证** | `frontend/e2e/po-invoicing-queue.spec.cjs` **2 例**：①开票→Refresh→订单仍在队列且状态 invoiced、点进去仍能记录收款 ②反向断言：`paid` 订单**必须离开**队列（防修成"什么都留着"）。实测 **2 passed / 9.1s** |
| **变异验证（证明测试有效）** | 把过滤临时改回 `o.status === 'delivered'` 重跑 ⇒ 用例精确红在「开票后订单从队列消失（D3）」，随后按 sha 还原（`a6ee9ed4ed77` 一致） |
| **测试数据纪律** | 本 spec 首次用了公共前缀 `PO-E2E-PR-*`，跑完无法与别的 spec 区分 ⇒ **改为唯一标记 `PO-E2E-D3-<ts>-<rand>`** 并 DELETE 清理（级联删发票）；实测标记残留 **0** |
| ⚠️ 同类未修 | 本页 `getOrders({page_size: 200})` ⇒ **队列只看最新 200 单**，更早的 delivered 单会被静默截断。要修需后端支持 `status__in` + 分页（与 D4 一并做） |

## D4 · P1 · ✅ **已修（2026-10-21）** · `/ops/orders` 状态筛选缺 PO 流程态（且无分页）

| 项 | 内容 |
|---|---|
| 现象 | ① 状态下拉只有 legacy 9 态，**没有** `po_received`/`in_production`/`delivered`/`cancelled`；② **完全没有分页** |
| 根因 | ① `AdminOrdersPage.vue` 模板内联写死了一套旧 option（既不完整、又与 `poConstants` 重复）；② `fetchOrders` 从不传 `page` ⇒ 后端 `PAGE_SIZE=20`，**991 单只看得到最新 20 单**；③ 同文件 `statusColors` 缺 3 态 ⇒ 徽章拼出 `undefined15` 非法 CSS |
| 实测（修前） | `selectOption('po_received')` 45s 内报 `did not find some options`；分页控件不存在 |
| 影响 | 运营筛不出待审单；且更早的订单**永久不可达**（比筛选缺失更严重） |
| **修法** | ① 状态词表**统一到 `config/poConstants.js`**（`ORDER_STATUS_FILTERS` = All + 9 个 PO 流程态；`LEGACY_STATUS_FILTERS` = 6 个历史/报价态），两页都用 `<optgroup>` 分组渲染 —— 从此只有**一个真相来源**；② 加 `page/pageSize/total` 与 `DataPagination`（`layout` 不含 `sizes`，避免 Element Plus 无可访问名的每页条数 combobox）；③ `statusColors` 改用 `ORDER_STATUS_COLORS`（覆盖全 15 态） |
| **验证** | `frontend/e2e/order-status-filters.spec.cjs` 3 例：①下拉含 4 个 PO 流程态 ②选 `po_received` 后每行都是 PO Received ③分页总数 > 20 且第 2 页内容不同 |

## D5 · P1 · ✅ **已修（2026-10-21）** · `/po/orders` 筛选缺 `quote_pending` / `quoted`

| 项 | 内容 |
|---|---|
| 现象 | 客户 PO 列表的筛选下拉里没有「待报价 / 已报价」；且副标题的总单数**恒显示 20** |
| 根因 | ① `poConstants.ORDER_STATUS_FILTERS` 只有 PO 流程态、缺 legacy 6 态；② `stores/poPortal.js` 的 `total` 读了 `res.data.meta`，而分页信息在**信封** `res.meta`（`data` 已是数组）⇒ 恒等于当前页条数（D2 同款）；③ 无分页控件 |
| 实测（修前） | 库内真实存在 `quote_pending` 40 单、`quoted` 33 单；下拉 option 实测为 `["", po_received, confirmed, in_production, shipped, delivered, invoiced, paid, completed, cancelled]` |
| 影响 | 客户无法按报价状态筛自己的单；`quoted` 33 单里最多只能看到 20 单，且看不出来被截断 |
| **修法** | ① 补 `LEGACY_STATUS_FILTERS` 并用 `<optgroup>` 渲染；② `poPortal.fetchOrders` 改读**信封** `meta.pagination.count` 并显式传 `page/page_size`；③ 加 `DataPagination`（layout 不含 `sizes`）；④ 切换筛选时**回到第 1 页**（否则停在越界页会显示空表） |
| **验证** | `order-status-filters.spec.cjs` 3 例：①下拉含 `quote_pending`/`quoted` ②选 `quoted` 后每行都是 Quoted、副标题总单数 > 20 ③能翻到第 2 页看到不同的单 |

## D6 · P1 · ✅ **已修（2026-10-21）** · `/po/orders/:id` 的 "For Research Use Only" 声明恒显示

| 项 | 内容 |
|---|---|
| 现象 | 非 RUO 产品也显示 RUO 声明 |
| 根因 | `PoOrderDetail.vue:105` 用 `it.is_ruo !== false` 判定，而 `OrderItemSerializer` **不返回 `is_ruo`** ⇒ `undefined !== false` 恒为真 |
| 实测（修前） | 明细 `items[]` 里无 `is_ruo` 键；单测报 `KeyError: 'is_ruo'` |
| 影响 | **合规声明误用**（把非 RUO 试剂标成仅科研用） |
| **修法** | ① 后端 `OrderItemSerializer` 增加 `is_ruo`（`SerializerMethodField`，来源 `Product.research_use_only`，`apps/commerce/models.py:157`）；② **三态语义**：`True` 确认 RUO / `False` 确认非 RUO / `None` 无法判定（`OrderItem.product` 是 `SET_NULL`，产品被删）⇒ 前端保留 `!== false`，**无法判定时保守显示**（合规优先：宁可多声明，不可漏声明）；③ 前端补注释说明为什么不能"简化"成 `=== true` |
| **验证（后端）** | `apps/transactions/tests/test_serializers.py::OrderItemIsRuoTest` 3 例（真 / 假 / 产品已删=null）——修前 `KeyError` 红，修后 **17 passed** |
| **验证（端到端）** | `frontend/e2e/po-ruo-declaration.spec.cjs` 4 例：①接口必须返回布尔 `is_ruo` ②`true` ⇒ 显示 ③`false` ⇒ **不显示**（反向，带"明细表已渲染"对照防白屏）④字段缺失 ⇒ 保守显示。**4 passed** |
| **变异验证** | 把前端判定改成 `=== true` 重跑 ⇒ 第 4 例精确红（无法判定时不显示了）⇒ 证明该断言钉住了"保守显示"语义；随后按 sha 还原 |
| ⚠️ 覆盖边界 | dev 库 **127 个产品全是 `research_use_only=True`**，所以"非 RUO 不显示"这条无法用真实数据端到端覆盖 ⇒ 用 `page.route` 注入 `is_ruo=false` 走 UI 判定；后端真实取值由单测覆盖。**零写入** |

## D7 · P2 · ✅ **已修（2026-10-21）** · a11y 对比度：25 页、**180 处**节点全部清零

> ⚠️ **口径更正**：此前台账写"50 处"，那是按**违规组**粗数的。本次用一次性探针把 axe 的
> 每个 `color-contrast` **节点**连 `fgColor/bgColor/ratio` 全量 dump 出来，实测是 **180 处 / 25 页**。
> 覆盖率（A 维 44/44）从来不代表合格，这一条才是真账。

| 项 | 内容 |
|---|---|
| 实测（修前） | 180 处节点、**仅 15 种色值组合**（前 6 种占 88%） |
| 关键洞察 | 180 处**不是 180 个问题**，而是 **6 个令牌 + 2 处局部样式** —— 这也是"改令牌"终于可行的原因 |
| 修法（6 个令牌，`frontend/src/assets/css/main.css`） | ① `--color-accent` amber-600→**amber-700**（白字 3.19→5.02，23 处 `.po-btn-accent`）② `--color-warning` amber-600→**amber-800**（压 amber-100 上 2.86→6.37，15 处 `.truncation-hint`/`.status-tag`）③ `--color-danger` `#E53E3E`→**red-700** `#B91C1C`（白底 4.13→6.47，50 处）④ `--color-info` `#3B82F6`→**blue-700** `#1D4ED8`（白底 3.68→6.70，21 处）⑤ EP `--el-color-success` 默认 `#67c23a`→**emerald-700**（压浅绿底 2.08→5.08，**60 处，占 33%**）⑥ EP 表头 `--el-table-header-text-color`→gray-600（3.08→7.58，2 处） |
| 修法（2 处局部，`MethodIndex.vue`） | `.result-badge` 字色与 `.filter-chip.active` 激活底从 `--color-secondary`(emerald-400，1.82/1.92) 改用 `--color-primary`(5.9/5.48)。**没有**动 `--color-secondary` 令牌本身——它还被边框/装饰用，那些不需要文字对比度 |
| **踩到的坑（重要）** | EP 把 `--el-table-header-text-color` 定义在 **`.el-table` 作用域**，写进 `:root` 会被组件级声明压掉（实测改了没效果，还剩 2 处）。改成 `.el-table { --el-table-header-text-color: … }` 才生效 |
| 选色原则 | 一律取**调色板里已有的 700/800 级**（不新增野色值）；amber-700 在白字方向 5.02 已达标，但作**字色**压在 amber-100 上只有 4.51（临界）⇒ 该场景改用 amber-800，**accent 与 warning 分工**：accent 当底色、warning 当字色 |
| **验证** | 一次性探针复测：**180 → 0**；`a11y.spec.cjs` 35 页全绿（0 critical / 0 serious）；`visual-tokens.spec.cjs` 1 passed（accent 断言已从 `#D97706` 更新为 `#B45309`，否则会撞） |
| **顺带修掉的 2 处非对比度 a11y** | ① `ResearchGoalIndex` **critical=1**：`el-select` 的内部 `<input role="combobox">` 无可访问名（EP 的 `id` 不透传，只认 `aria-label`）⇒ 补 `aria-label`；② `WsKnowledgeIntake` **serious=1**：`.ki-product-list` 是 `max-height + overflow-y:auto` 的可滚动区却不可键盘聚焦（`scrollable-region-focusable`）⇒ 补 `tabindex="0" role="group" aria-label` |
| **最终口径** | 35 页扫描 **36 passed**（35 页 0 critical / 0 serious + 令牌一致 1 条）。A 维从此是**真通过**，不再是"有覆盖但 25 页不合格" |

## D11 · P2 · ✅ **已修（2026-10-21，组件单测发现）** · `AppInput` 的 label 与输入框**从未真正关联**

| 项 | 内容 |
|---|---|
| 怎么发现的 | 引入 vitest 写第一批组件单测，`AppInput.spec.js` 断言 `input[id] === label[for]` 时直接红了 |
| 真相 | 2026-10-20 那版给 `el-input` 加 `:id`、给 `<label>` 加 `:for`，**看起来**就关联上了。但实测 **Element Plus 的 `el-input` 会吞掉 `id`**：内部 `<input class="el-input__inner">` 没有 id，连 `.el-input` 根 div 上也没有 ⇒ `<label for="v-0">` 指向**不存在的元素**，是孤儿 label |
| 对照实验（同一组件） | `aria-label` / `name` / `data-*` / `placeholder` **都能**透传到内部 input，**唯独 `id` 不能** |
| ⚠️ 为什么 axe 没报 | 这 7 个输入都有 **placeholder**，axe 的 `label` 规则允许 `non-empty-placeholder` 作为可访问名候选 ⇒ **automated 层面 0 违规**，所以 D7 全绿也没暴露它 |
| 真实影响 | 屏幕阅读器听到的是 placeholder（如 "Dr. John Smith"），而**label 里的必填标记 "Recipient Name *" 丢失** ⇒ 读屏用户不知道哪个字段必填 |
| 影响面 | 全站 **39 个 AppInput 实例**里只有 **CheckoutPage 的 7 个**传了 label；其余 32 个在 ProductEditPage，多用外层 `<label>…<AppInput/></label>` **包裹式**关联（那种是有效的） |
| **修法** | `AppInput` 改走 **`aria-label`**（`:aria-label="label \|\| placeholder \|\| undefined"`），并去掉 `label` 的 `for`（避免指向不存在目标）；`:id` 保留（无害，将来 EP 支持自动生效） |
| **验证** | ① vitest 断言内部 input 的 `aria-label === label`；② 新增 a11y 用例「CheckoutPage（购物车非空）」——**此前扫描时购物车是空的、表单根本不渲染**，这 7 个输入从没被扫过；③ 该用例加**可访问名精确断言** `getByRole('textbox', { name: 'Recipient Name *' })`；④ 变异验证：把 `aria-label` 置为 undefined ⇒ 该断言立刻红（可访问名退回 placeholder） |

> ★ 附带发现：`AppSelect` 里 `:aria-label="label \|\| placeholder \|\| 'Select an option'"` 的**第三级兜底是无效代码** ——
> label 与 placeholder 都为空时，EP 会用自己的默认 `Please select` 覆盖传入值（实测读到 'Please select'）。
> 已改成 `\|\| undefined`，让代码与事实一致。

## D8 · P3 · ✅ **已删（2026-10-21）** · `PoSubmit.vue` 第三条 alert 是死代码

| 项 | 内容 |
|---|---|
| 现象 | 该 `alert('Requested delivery date cannot be in the past.')` 在 UI 路径上**永远不执行** |
| 根因 | `#po-f5` 带 `:min="minDeliveryDate"`（`PoSubmit.vue:232`），浏览器先做 HTML5 约束校验并直接拦掉 `submit` 事件，`handleSubmit` 根本不进 |
| 实测 | 失败现场为原生 `rangeUnderflow` 气泡；`validity.rangeUnderflow === true`；`/api/v1/orders/po/` 请求数 **0** |
| **处置** | **删除**该不可达分支（保留另两条真校验 alert），把"过去日期"交给原生校验——提示更早、还带本地化文案。删掉比"改成可达"更好：改可达就要去掉 `:min`，等于丢掉原生校验 |
| **回归** | `order-error-paths.spec.cjs` 已固化「原生 rangeUnderflow 拦截 + 0 次 PO 请求」，删除后该断言仍绿 |

## D9 · P3 · ✅ **已删（2026-10-21）** · `/po/addresses` 顶部 callout 文案过期

| 项 | 内容 |
|---|---|
| 现象 | 页面顶部写着「Backend `/addresses/` CRUD is scheduled for P1. Save actions will surface an error toast until the endpoint ships.」 |
| 实测 | 新增→编辑→删除闭环**全通**（`po-addresses-crud.spec.cjs` 1 passed）⇒ 文案已过期，会让用户以为功能不可用 |
| **处置** | 删除整个 callout（不改逻辑） |
| **回归** | 新增守卫用例「页面不得再显示『CRUD 未上线』的过期提示」（断言不含 `scheduled for P1` / `until the endpoint ships`）。删除前证据：`git show HEAD:...PoAddressList.vue` 第 76 行确有该文案 |

## D10 · P2 · ✅ **已修（2026-10-21）** · 错误只留 4 秒 toast（静默失败），全站不统一

| 项 | 内容 |
|---|---|
| 现象 | 列表请求 500 时，用户只看到 4 秒 toast，页面落成"空态"（看起来像"你没有订单"） |
| 证据 | `src/utils/http.js:96-97` 全局 toast；`src/stores/orders.js:22-24` 与 `admin/AdminOrdersPage.vue:33-35` 只 `console.error` |
| 影响 | **静默失败**：接口挂了与"真的没数据"对用户不可区分 |
| 对比 | `/ops/orders/:id` 的动作失败**有**持久 `.error-banner`（`AdminOrderDetail.vue:125`）⇒ 全站错误提示不统一 |
| **修法** | 抽公共组件 `components/common/ErrorBanner.vue`（`role="alert"` + `data-kind` 区分 `load`/`action`），**4 个页面统一使用**：`/orders`、`/orders/:id`、`/ops/orders`、`/ops/orders/:id`。错误文案用 `extractErrorMessage(err.response.data, fallback)`（从 `utils/http.js` 导出）⇒ 与全局 toast **同一句后端文案**，不会各说一套。顺带删掉 `AdminOrderDetail` 内联的重复 `.error-banner` 样式 |
| **两个实现要点（都踩过）** | ① 横幅必须放在 `v-if="order"` **外面**，否则加载失败时 `order=null`，整块含横幅都不渲染；② `/orders/:id` 原来失败时**整页空白**，现在给横幅 + "Back to orders" 出口 |
| **验证** | `order-error-paths.spec.cjs` **7 passed**：4 条错误路径全部新增「持久横幅可见且文案 = 后端 detail」断言（修前实测红：`element(s) not found`）；`/ops/orders/:id` 那条还区分 `data-kind="load"` vs `"action"`，防止把"动作失败横幅"误当加载错误 |
| **⚠️ 本改动第一版有 bug（已修，2026-10-21 同日）** | `ErrorBanner` 第一版写 `v-if="message \|\| title"`，而调用方传的是**固定 title**（"Couldn't load orders."）⇒ 横幅在**一切正常**的页面也常显。当时 E2E 全绿——因为它只断言"出错时出现"，没断言"正常时不出现"（典型假绿）。**是视觉抽检截图看出来的**（正常列表页顶上挂着一条红横幅）。<br>修法：判据改为只看 `message`；并补**反向断言**「正常加载时 `.error-banner` 必须为 0」（变异验证：改回旧判据立刻红）。<br>教训：**"出现"类断言必须配"不该出现"的反向断言**，否则等于没测。 |

---

## D12 — `PATCH /api/v1/verified/<pk>/` 任意登录用户可改任意人的"已验证适用性"证据（P1 越权写 / 审计伪造）

| 项 | 内容 |
|---|---|
| 现象 | 任意注册用户可改**任意 id** 的 verified 证据，且 `curator` 字段保持不变 |
| 证据 | `apps/bridges/api/v1/views.py:118-130` 只有 `permission_classes = [IsAuthenticated]`；`apps/bridges/services/verified_service.py:62-89` 的 `patch_verified()` 只按 `pk + relation_type` 取对象，**既不校验 status 也不校验调用者**；`curator`（`models.py:521`）只在 approve 时写入，patch 不动它 |
| 可枚举性 | `ProductMethodRelation` 的 id 可从**匿名公开**的 `GET /api/v1/products/<pk>/methods/`（`bridges/api/v1/views.py:29-47`，`AllowAny`）批量拿到 ⇒ 不构成"猜不到 id"的障碍 |
| 影响 | 已审核通过（`status=ACTIVE`）的证据可被静默改写，而审计日志会把篡改**记在原审核人名下** ⇒ 知识库"已验证"数据的可信度与审计链同时被破坏 |
| 对比 | 同文件 `VerifiedApproveView`（`:132`）与 `VerifiedRejectView`（`:148`）都是 `IsStaffUser`，只有 patch 漏了 |
| **修法** | ① `permission_classes` → `[IsStaffUser]`；② `patch_verified()` 加状态门：仅 `status == REVIEW` 可改，否则抛 `ValidationError`，View 转 400 `code='invalid_status'`。<br>**为什么收紧权限是安全的**：前端 `frontend/src/api/bridges.js` **没有** PATCH `/verified/<id>/` 的调用（只有 list / create / approve / reject）⇒ 这是**孤儿端点**，收紧零功能损失。<br>**为什么不做"只允许草稿创建者"**：`ProductMethodRelation` **没有** owner/created_by 字段（只有 `curator` 字符串）⇒ 做不到，硬加要改 schema。加状态门则是**落实 `patch_verified` 原本 docstring 写的"REVIEW 草稿可部分更新"**，不是新增约束 |
| **验证** | `apps/bridges/tests/test_verified_patch_guard.py` 4 例。修前红：`test_normal_user_patch_forbidden` 实测 `200 != 403`；`test_staff_patch_active_rejected_with_400_and_no_write` 实测 `200 != 400`。修后全绿，且 ACTIVE 那条会**回库重新读取**断言 `evidence_note` 未被改动（防止"返回 400 但已落库"） |

---

## D13 — 匿名 `GET /api/v1/organizations` 吐出客户名录 + 联系人 PII（P1 泄露）

| 项 | 内容 |
|---|---|
| 现象 | 匿名请求（无需任何凭据）一次可拿到最多 10 条机构的 `contact_email` / `contact_phone` / 完整邮寄地址 / `member_count`（该机构用户数） |
| 证据 | `apps/accounts/api/v1/views.py:221-233` 是 `AllowAny` + `authentication_classes = []`；`q = request.query_params.get('q', '')` ⇒ **不传 q 时 `q=''`**，`name__icontains=''` 命中全部 active 机构；序列化器 `serializers.py:213-231` 用完整 `OrganizationSerializer` |
| 放大因素 | 这些字段由 `OrganizationCreateView`（`views.py:236-251`，任意登录用户可调）写入 ⇒ **字段一旦被填就匿名可见**，是结构性的，不是数据现状问题。配 `AnonRateThrottle` 100/hour 可稳定枚举完整客户清单 |
| **修法** | ① 新建 `OrganizationSummarySerializer`，**只输出** `id / name / short_name / org_type / country`；② `q` 去空白后长度 < 2 直接返回空列表（不是全表），保留 `status='active'` 与 `[:10]` |
| **⚠️ 修完立刻暴露一个功能回退（同日补修）** | `/ops/po/organizations`（`views/admin/PoOrgManagement.vue:16`）调 `getOrganizations({ page_size: 100 })` —— **不带 q**，靠的正是被修掉的那个缺陷行为 ⇒ 左栏 Organizations 表格**恒空白**。该视图 `authentication_classes = []`，即使管理员已登录也是 AnonymousUser ⇒ "给搜索端点放行已登录用户"这条路走不通。<br>**正确修法不是把洞重新打开**：另开 `GET /api/v1/organizations/manage/`（`IsProcurementOrAdmin` + 完整字段 + `meta.pagination.count` + `page_size` 夹紧到 [1,500]），前端改打它；匿名搜索维持收紧。<br>教训：**收紧一个"被别的页面当查询接口滥用"的端点时，必须全仓 grep 它的所有调用点**，不能只看它自己的语义 |
| **验证** | `apps/accounts/tests/test_org_search_privacy.py` 17 例（匿名面 8 + 管理面 9）。修前红 4 条，含 `'contact_email' unexpectedly found in ...`、键集合多出 13 个字段、不带 q 时 `{'success':True,'data':[...]} != []`。<br>关键设计：字段集用 `set(item.keys()) == {5 个}` 断言（加字段立刻红），并用**对照组** `test_manage_exposes_full_fields_unlike_anonymous_search` 钉住"管理面必须含 contact_email、匿名面必须仍然恰好 5 字段" —— 防止将来"顺手把两边统一" |

---

## D14 — nginx `/media/` 同源直出，绕过全部按单授权（P1 越权读）

| 项 | 内容 |
|---|---|
| 现象 | 发票 PDF、PO 附件、COA/SDS 均可通过 `https://<host>/media/<路径>` 直接取到，**不经过 Django 的任何对象级校验** |
| 证据 | `deploy/nginx.conf:138-142` 的 `location /media/ { alias /usr/share/nginx/media/; }`；`docker-compose.yml:53,81` 把同一个卷挂给 backend（写）和 nginx（只读），**nginx 侧完全独立于 Django 的授权逻辑** |
| 被绕过的门控 | ① `InvoicePdfDownloadView`（`po_views.py:331-357`）的 `_is_order_viewer`；② `PoAttachmentDownloadView`（`:360-379`）的同名校验；③ `CoaViewSet` 下载 action（`documents/api/v1/views.py:127-150`）的「未 PUBLISHED 一律 404」；④ `SdsRevisionViewSet` 同上（`:220-240`） |
| 可枚举性 | 发票文件名是 `INV-{年}-{4位序号}`（`services.py` 的 `_next_invoice_no`）⇒ 顺序号可枚举；COA/SDS 落 `media/documents/coa|sds/`，路径同样可预测 |
| 当前缓解（**不可依赖**） | `deploy/nginx.conf:84-85` 的 server 级 `auth_basic` 会被 `/media/` 继承 ⇒ 目前并非全网匿名。但它是**共享口令、不做按单授权**（买了 A 公司发票的人拿同一口令也能读 B 公司的），且注释写明是"仅限内部测试人员"的临时措施 |
| 附带问题 | `/media/` 没有任何 `X-Content-Type-Options`、没有 `Content-Disposition`；CSP 只有 Report-Only（`:81`）⇒ 上传一个 `.html`（把 `Content-Type` 声明成 `image/png`，白名单只校验客户端自报）再让人打开，即可形成同源存储型 XSS |
| **修法** | nginx 在 `location /media/` **之前**插入四段精确拒绝：`^~ /media/invoices/`、`^~ /media/po_attachments/`、`^~ /media/documents/coa/`、`^~ /media/documents/sds/` 全部 `deny all`；`/media/` 块补 `X-Content-Type-Options: nosniff always` 并把 server 级 CSP 原样复制进来（**nginx 的 `add_header` 是"location 有自己的就替换掉 server 级全部"**，不复制等于把 CSP 丢掉） |
| **为什么只禁这四类、不整体封禁** | 前端 `src/` 里**零** `/media/` 直链（已 grep 确认），四类敏感文件全部由 Django `FileResponse` 交付 ⇒ 禁掉零功能损失。但 `media/pdfs/` 与 `media/documents/` 下的产品文档（`ProductDocument.file`）在序列化器里以 URL 返回（`PdfFileSerializer` / `ProductDocumentSerializer` 含 `file` 字段）⇒ **整体封禁会砍掉产品文档**，故必须精确到子树 |
| **验证** | `apps/core/tests/test_nginx_media_guard.py` 7 例（纯文本解析，含"不得整体封禁 `/media/`"的反向断言、三处 CSP 逐字一致断言）。<br>**⚠️ 未做语法级验证**：本机无 `nginx`、无 `docker`，`nginx -t` **没跑过**，上线前必须在容器里补跑 |

---

## D15 — PO 提交的 `unit_price` 可写 + `POST /api/v1/orders/` 是孤儿写口（P2 纵深防御 / 数据污染）

| 项 | 内容 |
|---|---|
| 现象 | ① `PoSubmitItemSerializer.unit_price` 允许客户端提交单价；② `OrderViewSet` 的 POST/PATCH/DELETE 开放，可造 `user=NULL` 的孤儿订单，缺 `order_no` 则 `IntegrityError` → 500 |
| 证据 | ① `transactions/api/v1/serializers.py:277-288`；② `transactions/api/v1/views.py:12-46` 无 `perform_create`，`Order.user` 是 `null=True`（`models.py:77-80`），`order_no` 非 read_only 且 `unique=True` 无默认值 |
| 为什么 ① 目前**不构成**篡改 | `services.py:132-141` 用 `sku.price` 强制覆盖（注释写明"客户端提交不可信"）⇒ 实测"传 1% 的价格仍按真实价落库"。但这是**单点防御**：任何人新增一个复用该序列化器的写端点、或改动 `PoSubmissionService`，价格篡改立刻敞开 |
| 为什么 ② 可以只读化 | 前端对 `/orders/` **只有 GET**（`api/orders.js:24`、`api/poPortal.js:69,101`、`api/adminPo.js:12,34,94` 全是 `http.get`，全仓无 `post('/orders/'`）。真实下单走 `CheckoutView` / `POSubmitView` ⇒ 这是孤儿写口 |
| **修法** | ① `unit_price` 改 `read_only=True`（DRF 对 read_only **忽略入参**，前端继续发也不会 400 ⇒ **前端零改动**），服务层那道覆盖**保留**作第二道防线；② `OrderViewSet` 加 `http_method_names = ['get','head','options']`，与同文件 `QuoteViewSet:54` 完全同一做法；`filterset_fields`（D1 刚修的）与匿名空列表契约**不动** |
| **验证** | `test_po_unit_price_readonly.py` 2 例（修前红：`'unit_price' unexpectedly found in {...}`；而"篡改价仍按 sku.price 落库"那条**一开始就是绿的**，正好实证了"唯一防线在服务层"）；`test_order_viewset_readonly.py` 5 例（修前红：POST `400 != 405`、PATCH `200 != 405`、DELETE `204 != 405`） |

---

## 附：这些缺陷是怎么被"测"出来的（方法论）

1. **状态分支穷举**（S 维）：每页先读源码列出全部状态分支，再**逐分支走一遍**，且优先写**反向断言**（"在 A 状态可见、在 B 状态必须不可见"）。D3/D6 都是反向断言抓出来的。
2. **故障注入**（错误路径）：D10 是用 `page.route` 把接口打成 500 后看页面反应抓到的。
3. **相对断言替代绝对断言**：D1 是"换机构看右表变不变"，不依赖任何计数。
4. **禁止把 skipped 当通过**：D1 的正确预期写成 `test.fixme` 而不是删掉，保证缺陷不会被"绿了"掩盖。
