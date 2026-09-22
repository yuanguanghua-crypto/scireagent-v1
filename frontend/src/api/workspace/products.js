import { http } from '@/api/http'

export function getProducts(params = {}) {
  return http.get('/products/', { params: { page_size: params.page_size || 500, ...params } })
}

export function getProduct(id) {
  return http.get(`/products/${id}/`)
}

export function createProduct(data) {
  return http.post('/products/', data)
}

export function updateProduct(id, data) {
  return http.put(`/products/${id}/`, data)
}

export function updateProductLinks(id, methodIds, protocolIds) {
  return http.put(`/products/${id}/`, { method_ids: methodIds, protocol_ids: protocolIds })
}

export function archiveProduct(id) {
  return http.post(`/products/${id}/archive/`)
}

export function reactivateProduct(id) {
  return http.patch(`/products/${id}/`, { status: 'active' })
}

// S4-4f 退出目录（停产/弃用）：status='deprecated'。
// 与「回收站」语义不同：**编号不释放**（唯一性全表永久）、**页面保留**
// （公开详情仍 200，前端显示 Discontinued 提示），只是退出店铺列表与在售状态。
// 这才是真实网站里「从目录移除」的正确动作 —— 回收站只用于撤销误操作。
export function discontinueProduct(id) {
  return http.patch(`/products/${id}/`, { status: 'deprecated' })
}

export function deleteProduct(id) {
  return http.delete(`/products/${id}/`)
}

// S1 回收站：staff-only。?archived=1 只是「不再隐藏」，返回全部产品
// （含正常 + 回收站），前端自行按 archived 字段分区。
export function getArchivedProducts(params = {}) {
  return http.get('/products/', { params: { ...params, archived: 1, page_size: params.page_size || 500 } })
}

export function restoreProduct(id) {
  return http.post(`/products/${id}/restore/`)
}

/**
 * Q6：批量恢复 —— 走**幂等**端点，替代前端逐条循环 `restoreProduct`。
 *  - 幂等：已在售（archived=false）的对象计入 `skipped`，且**不重复写 RESTORE 审计**
 *    （单条 `restore/` 是无条件写审计的，非幂等）
 *  - 容错：不存在 / 非法 id 计入 `not_found`，不会让整批失败
 * 返回 { restored, skipped, not_found }
 */
export function batchRestoreProducts(ids) {
  return http.post('/products/batch-restore/', { ids })
}
