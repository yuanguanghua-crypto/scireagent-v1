/**
 * PO 采购门户 — 内部台 API（节点 A~E）
 * 端点依据 backend/apps/transactions/api/v1/po_views.py + urls.py
 * @module api/adminPo
 */
import http from '@/utils/http'

/* ── A 订单审核台 ── */

/** 待审 PO 列表：status=po_received（OrderViewSet.list，admin 看全部）。 */
export function getPendingReviews(params = {}) {
  return http.get('/orders/', { params: { status: 'po_received', ...params } })
}

/** PO_RECEIVED → CONFIRMED */
export function approveOrder(id) {
  return http.post(`/orders/${id}/approve/`)
}

/** → CANCELLED，body: { reason } */
export function rejectOrder(id, reason = '') {
  return http.post(`/orders/${id}/reject/`, { reason })
}

/** 分配/改派 Rep（Admin），body: { rep_id } */
export function assignRep(id, repId) {
  return http.post(`/orders/${id}/assign-rep/`, { rep_id: repId })
}

/* ── 通用订单查询（内部台列表） ── */

/** 任意状态订单列表（admin 全量）。 */
export function getOrders(params = {}) {
  return http.get('/orders/', { params })
}

export function getOrderDetail(id) {
  return http.get(`/orders/${id}/`)
}

/* ── B 发货台 ── */

/**
 * 新建发货记录（分批发）。body:
 *   { carrier, tracking_number, tracking_url, estimated_delivery, notes, items: [{order_item_id, quantity}] }
 */
export function createShipment(id, data) {
  const payload = { ...data }
  // 后端 DateField(required=False, allow_null=True) 不接受空字符串，需传 null 或 omit
  if (payload.estimated_delivery === '') {
    payload.estimated_delivery = null
  }
  return http.post(`/orders/${id}/shipments/`, payload)
}

/** 标记发货 POST /shipments/<id>/mark-shipped/ */
export function markShipped(shipmentId) {
  return http.post(`/shipments/${shipmentId}/mark-shipped/`)
}

/** 标记签收 POST /shipments/<id>/mark-delivered/ body: { received_by } */
export function markDelivered(shipmentId, receivedBy = '') {
  return http.post(`/shipments/${shipmentId}/mark-delivered/`, { received_by: receivedBy })
}

/* ── C 发票台 ── */

/** 对 DELIVERED 订单开票 body: { payment_terms: 'NET30'|'NET45'|'NET60' } */
export function issueInvoice(id, paymentTerms = 'NET30') {
  return http.post(`/orders/${id}/invoice/`, { payment_terms: paymentTerms })
}

/** 收款 POST /invoices/<id>/pay/ body: { amount, method, paid_at?, reference?, notes? } */
export function payInvoice(invoiceId, data) {
  return http.post(`/invoices/${invoiceId}/pay/`, data)
}

/* ── D AR 报表 ── */

/** GET /ar/aging/ → { as_of, buckets:{current,30,60,90_plus}, total_outstanding } */
export function getArAging() {
  return http.get('/ar/aging/')
}

/* ── E 客户/机构管理 ── */

/** 机构搜索（OrganizationSearchView）。 */
export function getOrganizations(params = {}) {
  return http.get('/organizations', { params })
}

/** 指定机构的订单（OrderViewSet，admin 全量，按 organization_id 过滤）。 */
export function getOrgOrders(orgId, params = {}) {
  return http.get('/orders/', { params: { organization_id: orgId, ...params } })
}
