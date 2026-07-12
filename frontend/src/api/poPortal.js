/**
 * PO 采购门户 — 客户侧 API（节点 1~6）
 * 端点依据 backend/apps/transactions/api/v1/po_views.py + serializers.py
 * 信封统一 {success,data,meta}；http 拦截器已拆封，调用方拿 data。
 *
 * @module api/poPortal
 */
import http from '@/utils/http'

/**
 * 节点1 — 提交 PO。multipart/form-data：
 *   标量字段 + items[<i>][sku_id|quantity|unit_price|product_id] + attachments[]
 * 成功响应 data: { order_no, status }
 */
export function submitPo({ data, files = [] }) {
  const scalarFields = [
    'po_number', 'quote_id', 'grant_code', 'shipping_method', 'requested_delivery_date',
    'shipping_name', 'shipping_address', 'shipping_phone', 'shipping_email',
    'billing_name', 'billing_address', 'shipping_address_ref_id', 'billing_address_ref_id', 'notes',
  ]
  const buildItems = () =>
    (data.items || []).map((it) => ({
      product_id: it.product_id,
      sku_id: it.sku_id,
      quantity: Number(it.quantity),
      unit_price: String(it.unit_price ?? ''),
    }))

  // 无附件：发 JSON。后端 PoSubmitSerializer 期望嵌套 items list，
  // 而 DRF 的 multipart 解析器不展开 items[i][field] 方括号格式，会导致 items 缺失校验失败。
  if (!files || files.length === 0) {
    const payload = {}
    scalarFields.forEach((k) => {
      const v = data[k]
      if (v !== undefined && v !== null && v !== '') payload[k] = v
    })
    payload.items = buildItems()
    return http.post('/orders/po/', payload, {
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // 有附件：multipart，items 作为 JSON 字符串字段（后端 POSubmitView 会 json.loads 还原）。
  const fd = new FormData()
  scalarFields.forEach((k) => {
    const v = data[k]
    if (v !== undefined && v !== null && v !== '') fd.append(k, v)
  })
  fd.append('items', JSON.stringify(buildItems()))
  ;(files || []).forEach((f) => fd.append('attachments', f))
  return http.post('/orders/po/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/**
 * 节点2 — 当前用户 PO 列表（OrderViewSet.list，按 user 过滤）。
 * params: { status?, page? }
 */
export function getMyOrders(params = {}) {
  return http.get('/orders/', { params })
}

/**
 * 节点3 — 订单详情（OrderViewSet.retrieve → OrderDetailSerializer）。
 * 含 items / invoice / shipments / status_logs。
 */
export function getOrderDetail(id) {
  return http.get(`/orders/${id}/`)
}

/**
 * 节点3 — 发票 PDF 下载（best-effort：后端若未实现该端点将 404 提示）。
 */
export function downloadInvoicePdf(invoiceId, filename = `invoice-${invoiceId}.pdf`) {
  return http
    .get(`/invoices/${invoiceId}/pdf/`, { responseType: 'blob' })
    .then((blob) => triggerDownload(blob, filename))
}

/** 节点3 — PO 附件下载（best-effort）。 */
export function downloadPoAttachment(attachmentId, filename = `po-attachment-${attachmentId}`) {
  return http
    .get(`/orders/attachments/${attachmentId}/download/`, { responseType: 'blob' })
    .then((blob) => triggerDownload(blob, filename))
}

/**
 * 节点2/6 — 全部已生成发票列表（用于下载中心）。复用 OrderViewSet 拿发票信息，
 * 这里直接通过订单列表聚合客户侧可见发票。
 */
export function getMyInvoices(params = {}) {
  return http.get('/orders/', { params: { ...params } })
}

/** 节点5 — 拉取历史订单用于 Re-order 预填。 */
export function getReorderSource(id) {
  return getOrderDetail(id)
}

function triggerDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
