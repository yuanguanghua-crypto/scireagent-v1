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
