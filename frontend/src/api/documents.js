/**
 * COA / SDS / Batch 文档端点统一封装。
 *
 * ⚠️ 与 products.js 完全一致：所有 documents 端点均经全局 EnvelopeRenderer 包装为
 * { success, data, meta }：
 *   - 详情 / 动作（generate / approve / withdraw / create / qc）→ data 为对象
 *   - 列表（getSdsList / getCoaList / getBatches）→ data 直接为数组
 *     （分页 results 已被渲染器提取进 data，不再有 .results 层）
 *
 * 因此这里直接复用共享 http 实例，函数统一返回信封中的 data 载荷，
 * 不另起 axios 实例、不自行解析裸 DRF。
 *
 * 响应解析约定（与 products.js 同）：
 *   - 列表   → r.data（数组）
 *   - 详情/动作 → r.data（对象）
 *   - 错误   → 由 @/utils/http 拦截器统一提示；调用方能捕获到信封对象
 *
 * 路径风格：不带 /api/v1 前缀（http 实例已内置 baseURL）。
 */
import http from '@/utils/http'

// ── SDS ──────────────────────────────────────────────
export function generateSds(productId) {
  return http.post('/sds-revisions/generate/', { product_id: productId }).then((r) => r.data)
}

export function approveSds(id) {
  return http.post(`/sds-revisions/${id}/approve/`).then((r) => r.data)
}

export function withdrawSds(id) {
  return http.post(`/sds-revisions/${id}/withdraw/`).then((r) => r.data)
}

export function getSdsList(productId) {
  return http.get('/sds-revisions/', { params: { product_id: productId } }).then((r) => r.data)
}

// ── COA ──────────────────────────────────────────────
export function createCoa(payload) {
  return http.post('/coas/create-coa/', payload).then((r) => r.data)
}

export function updateCoaQc(id, payload) {
  return http.put(`/coas/${id}/qc-results/`, payload).then((r) => r.data)
}

export function approveCoa(id, payload = {}) {
  return http.post(`/coas/${id}/approve/`, payload).then((r) => r.data)
}

export function withdrawCoa(id) {
  return http.post(`/coas/${id}/withdraw/`).then((r) => r.data)
}

export function getCoaList(params = {}) {
  return http.get('/coas/', { params }).then((r) => r.data)
}

// ── Batch ────────────────────────────────────────────
export function getBatches(params = {}) {
  return http.get('/batches/', { params }).then((r) => r.data)
}

// ── 下载 URL（GET 匿名可下载，无需写入鉴权头）──────────
export function downloadSdsUrl(id) {
  return `/api/v1/sds-revisions/${id}/download/`
}

export function downloadCoaUrl(id) {
  return `/api/v1/coas/${id}/download/`
}

export default {
  generateSds,
  approveSds,
  withdrawSds,
  getSdsList,
  createCoa,
  updateCoaQc,
  approveCoa,
  withdrawCoa,
  getCoaList,
  getBatches,
  downloadSdsUrl,
  downloadCoaUrl,
}
