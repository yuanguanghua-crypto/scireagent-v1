import http from '@/utils/http'

export function getProducts(params) {
  return http.get('/products', { params })
}

export function getProduct(id) {
  return http.get(`/products/${id}`)
}

export function createProduct(data) {
  return http.post('/products', data)
}

export function updateProduct(id, data) {
  return http.put(`/products/${id}`, data)
}

export function deleteProduct(id) {
  return http.delete(`/products/${id}`)
}

export function uploadDocument(productId, formData) {
  return http.post(`/products/${productId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getDocuments(productId) {
  return http.get(`/products/${productId}/documents`)
}

export function deleteDocument(docId) {
  return http.delete(`/documents/${docId}`)
}

export function getCategories() {
  return http.get('/categories')
}

/**
 * Fetch aggregated product detail (V1.2 spec endpoint).
 * Returns: product, applications, protocols, references, related_products, faq, compatibility, graph, jsonld
 */
export function getProductDetail(id) {
  // ⚠️ 尾斜杠不能省：少了它 Django 的 APPEND_SLASH 会回 301，
  //   浏览器得再走一次完整往返（生产实测白白多花 8 秒）。
  // ⚠️ 30s：全局默认 15s，而详情响应有几十 KB，在低带宽/高 RTT 链路上
  //   15s 会被误判为失败（实测已发生）。只放宽这一个请求。
  return http.get(`/products/${id}/detail/`, { timeout: 30000 })
}
