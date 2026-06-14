/**
 * Orders API module
 * @module api/orders
 */
import http from '@/utils/http'

/**
 * Create order from basket (checkout)
 * @param {Object} data - Checkout data
 * @param {string} data.payment_method - 'purchase_order' | 'credit_card' | 'wire_transfer' | 'quote'
 * @param {string} [data.po_number] - PO number (required for purchase_order)
 * @param {string} data.shipping_name - Recipient name
 * @param {string} data.shipping_address - Shipping address
 */
export function checkout(data) {
  return http.post('/checkout/', data)
}

/**
 * Get current user's orders
 * @param {Object} [params] - Query params (page, status)
 */
export function getOrders(params = {}) {
  return http.get('/orders/', { params })
}

/**
 * Get order detail
 * @param {number} id - Order ID
 */
export function getOrder(id) {
  return http.get(`/orders/${id}/`)
}

/**
 * Cancel order
 * @param {number} id - Order ID
 */
export function cancelOrder(id) {
  return http.post(`/orders/${id}/cancel/`)
}

/**
 * Accept or reject quote
 * @param {number} id - Order ID
 * @param {string} action - 'accept' | 'reject'
 */
export function respondToQuote(id, action) {
  return http.post(`/orders/${id}/confirm-quote/`, { action })
}

/**
 * Submit payment proof
 * @param {number} id - Order ID
 * @param {Object} data - Payment proof data
 */
export function submitPaymentProof(id, data) {
  return http.post(`/orders/${id}/pay/`, data)
}

// ── Admin endpoints ──

/**
 * Get all orders (admin)
 * @param {Object} [params] - Query params (page, status, search)
 */
export function getAdminOrders(params = {}) {
  return http.get('/admin/orders/', { params })
}

/**
 * Get order detail (admin)
 * @param {number} id - Order ID
 */
export function getAdminOrder(id) {
  return http.get(`/admin/orders/${id}/`)
}

/**
 * Confirm order (admin)
 * @param {number} id - Order ID
 */
export function confirmOrder(id) {
  return http.post(`/admin/orders/${id}/confirm/`)
}

/**
 * Generate invoice (admin)
 * @param {number} id - Order ID
 */
export function generateInvoice(id) {
  return http.post(`/admin/orders/${id}/invoice/`)
}

/**
 * Ship order (admin)
 * @param {number} id - Order ID
 * @param {Object} data - Shipping info { carrier, tracking_number }
 */
export function shipOrder(id, data) {
  return http.post(`/admin/orders/${id}/ship/`, data)
}

/**
 * Complete order (admin)
 * @param {number} id - Order ID
 */
export function completeOrder(id) {
  return http.post(`/admin/orders/${id}/complete/`)
}

/**
 * Enter quote price (admin)
 * @param {number} id - Order ID
 * @param {Object} data - { grand_total, valid_until?, notes? }
 */
export function enterQuote(id, data) {
  return http.post(`/admin/orders/${id}/quote/`, data)
}

/**
 * Verify payment (admin)
 * @param {number} invoiceId - Invoice ID
 * @param {Object} data - { payment_id, action: 'verify'|'reject', notes? }
 */
export function verifyPayment(invoiceId, data) {
  return http.post(`/admin/invoices/${invoiceId}/verify-payment/`, data)
}
