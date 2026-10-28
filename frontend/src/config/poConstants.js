/**
 * PO 采购门户共享常量 — 与后端 TextChoices 一一对应（ARCHITECTURE.md §7）。
 * 禁止魔法字符串，前端统一引用本表。
 */

export const SHIPPING_METHODS = [
  { value: 'ambient', label: 'Ambient' },
  { value: 'cold_pack', label: 'Cold Pack' },
  { value: 'dry_ice', label: 'Dry Ice' },
  { value: 'blue_ice', label: 'Blue Ice' },
]

export const PAYMENT_TERMS = [
  { value: 'NET30', label: 'Net 30' },
  { value: 'NET45', label: 'Net 45' },
  { value: 'NET60', label: 'Net 60' },
]

export const PAYMENT_METHODS = [
  { value: 'online', label: 'Online' },
  { value: 'wire', label: 'Wire Transfer' },
  { value: 'check', label: 'Check' },
]

export const ADDRESS_TYPES = [
  { value: 'billing', label: 'Bill-to' },
  { value: 'shipping', label: 'Ship-to' },
  { value: 'other', label: 'Other' },
]

/**
 * 订单状态筛选 —— **与后端 `Order.Status` 一一对应**
 * （`backend/apps/transactions/models.py` 的 `class Order.Status`）。
 *
 * ★ 2026-10-21 修 D4/D5：此前这里是**三套互不一致**的清单 ——
 *   ① 后端 15 态；② 本文件只列了 PO 流程 9 态（缺 `quote_pending`/`quoted` 等 legacy，D5）；
 *   ③ `AdminOrdersPage.vue` 又内联了另一套 9 态（缺 `po_received`/`in_production`/`delivered`/`cancelled`，D4）。
 *   ⇒ 运营筛不出待审单、客户筛不出报价中的单。现在**统一以本文件为唯一来源**，两页都引用它。
 *
 * 分组：PO 主流程（新流程，当前写入）+ 历史/报价态（legacy，库里仍有数据，仅供筛选与展示）。
 */
export const ORDER_STATUS_FILTERS = [
  { value: '', label: 'All' },
  { value: 'po_received', label: 'PO Received' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'in_production', label: 'In Production' },
  { value: 'shipped', label: 'Shipped' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'invoiced', label: 'Invoiced' },
  { value: 'paid', label: 'Paid' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

/**
 * 历史 / 报价状态（legacy）。新流程不再写入，但库内仍有历史单：
 * 实测 dev 库 `quote_pending` 40 单、`quoted` 33 单 ⇒ 客户必须能筛出来。
 */
export const LEGACY_STATUS_FILTERS = [
  { value: 'quote_pending', label: 'Quote Pending' },
  { value: 'quoted', label: 'Quoted' },
  { value: 'quote_accepted', label: 'Quote Accepted' },
  { value: 'quote_rejected', label: 'Quote Rejected' },
  { value: 'processing', label: 'Processing' },
  { value: 'draft', label: 'Draft' },
]

/**
 * 状态 → 徽标**文字**色（覆盖后端全部 15 态）。
 * ★ 此前 `AdminOrdersPage.vue` 内联的 statusColors 缺 `po_received`/`in_production`/`delivered`
 *   ⇒ 徽章拼出 `undefined15`（非法 CSS，徽章无底色）。
 * 用的都是 `main.css` 里已存在的语义令牌，避免引入未定义变量。
 */
export const ORDER_STATUS_COLORS = {
  po_received: 'var(--color-warning)',
  confirmed: 'var(--color-primary)',
  in_production: 'var(--color-warning)',
  shipped: 'var(--color-warning)',
  delivered: 'var(--color-success)',
  invoiced: 'var(--color-info)',
  paid: 'var(--color-success)',
  completed: 'var(--color-success)',
  // ★ 2026-10-28：gray-500(#64748B) 压在新底色 gray-100 上实测仅 ~4.47:1，卡在 AA 4.5 线下
  //   （压白底时是 4.55:1 才勉强过）。底色一旦真的生效就变成不合格 ⇒ 降到 gray-600（~6.9:1）。
  cancelled: 'var(--color-gray-600)',
  draft: 'var(--color-gray-600)',
  processing: 'var(--color-info)',
  quote_pending: 'var(--color-warning)',
  quoted: 'var(--color-warning)',
  quote_accepted: 'var(--color-success)',
  quote_rejected: 'var(--color-danger)',
}

/**
 * 状态 → 徽标**浅底色**（与 `ORDER_STATUS_COLORS` 一一对应，同样是 15 态全覆盖）。
 *
 * ★ 为什么必须单独一张表（2026-10-28 实测）：
 *   原代码四处都写 `backgroundColor: statusColors[s] + '15'`，意图是把 `#047857`
 *   拼成 8 位十六进制 `#04785715`。但令牌 `--color-success` 的值是
 *   `var(--color-emerald-700)`（**不是**字面量），拼出来是
 *   `var(--color-emerald-700)15` —— 不是合法颜色 ⇒ 整条 `background` 声明作废。
 *   浏览器实测：`background: var(--color-success)15` 的计算值 = `rgba(0, 0, 0, 0)`。
 *   ⇒ 所有状态徽标的浅底色**一直是透明的**（三个页面、15 个状态全中）。
 *
 * 现在改用项目已定义的 `-bg` / `-light` 语义令牌：纯静态值，不依赖 `color-mix()`
 * 之类较新的浏览器特性，旧浏览器也不会静默失效。
 */
export const ORDER_STATUS_BG = {
  po_received: 'var(--color-warning-bg)',
  confirmed: 'var(--color-primary-light)',
  in_production: 'var(--color-warning-bg)',
  shipped: 'var(--color-warning-bg)',
  delivered: 'var(--color-success-bg)',
  invoiced: 'var(--color-info-bg)',
  paid: 'var(--color-success-bg)',
  completed: 'var(--color-success-bg)',
  cancelled: 'var(--color-gray-100)',
  draft: 'var(--color-gray-100)',
  processing: 'var(--color-info-bg)',
  quote_pending: 'var(--color-warning-bg)',
  quoted: 'var(--color-warning-bg)',
  quote_accepted: 'var(--color-success-bg)',
  quote_rejected: 'var(--color-danger-bg)',
}

/**
 * 状态徽标的内联样式 —— 各页面**唯一**取值入口。
 *
 * 未知状态返回 `{}`（不写任何声明）⇒ 徽标退回继承色 + 透明底，
 * 而不是拼出 `undefined15` 这种非法值。新增状态时只需在上面两张表各加一行。
 */
export function statusBadgeStyle(status) {
  const fg = ORDER_STATUS_COLORS[status]
  if (!fg) return {}
  return { color: fg, background: ORDER_STATUS_BG[status] || 'transparent' }
}

export function formatStatus(s) {
  if (!s) return s
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
