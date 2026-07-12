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
  return http.get(`/products/${id}/detail`)
}
