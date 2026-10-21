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
 * 状态 → 语义色（覆盖后端全部 15 态）。
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
  cancelled: 'var(--color-gray-500)',
  draft: 'var(--color-gray-500)',
  processing: 'var(--color-info)',
  quote_pending: 'var(--color-warning)',
  quoted: 'var(--color-warning)',
  quote_accepted: 'var(--color-success)',
  quote_rejected: 'var(--color-danger)',
}

export function formatStatus(s) {
  if (!s) return s
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
