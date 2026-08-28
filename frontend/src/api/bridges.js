/**
 * bridges 双 edge 端点封装（Phase 4：产品详情页双 edge 展示）。
 *
 * - derived_relevance：机器派生缓存（allow-list 源重建）
 * - verified_applicability：研究员策展事实（evidence 三件套）
 *
 * 端点：GET /api/v1/products/{id}/methods/（双 edge 分离，公开读）
 * 响应：经全局拦截器解包信封 → r.data 即载荷：
 *   { related_methods: [...], verified_methods: [...] }
 * 路径风格：不带 /api/v1 前缀（http 实例已内置 baseURL），与 products.js 一致。
 */
import http from '@/utils/http'

export function getProductMethods(productId) {
  return http.get(`/products/${productId}/methods/`).then((r) => r.data)
}
