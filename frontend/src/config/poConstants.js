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

export function formatStatus(s) {
  if (!s) return s
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
