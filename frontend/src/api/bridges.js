/**
 * bridges 双 edge 端点封装（Phase 4 产品详情页 + C3 workspace 审核）。
 *
 * - derived_relevance：机器派生缓存（allow-list 源重建）
 * - verified_applicability：研究员策展事实（evidence 三件套）
 *
 * 公开读：GET /api/v1/products/{id}/methods/（双 edge 分离，仅 ACTIVE verified）
 * workspace：GET /api/v1/verified/（IsStaffUser，全状态审核列表）+ approve/reject
 * 路径风格：不带 /api/v1 前缀（http 实例已内置 baseURL），与 products.js 一致。
 */
import http from '@/utils/http'

export function getProductMethods(productId) {
  return http.get(`/products/${productId}/methods/`).then((r) => r.data)
}

// ── C3 workspace 审核 ──
export function listVerified(params = {}) {
  return http.get('/verified/', { params }).then((r) => r.data)
}

export function approveVerified(id) {
  return http.post(`/verified/${id}/approve/`, {}).then((r) => r.data)
}

export function rejectVerified(id, note = '') {
  return http.post(`/verified/${id}/reject/`, { note }).then((r) => r.data)
}
