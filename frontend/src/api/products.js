import http from '@/utils/http'

export function getProducts(params = {}) {
  return http.get('/products/', { params })
}

export function getProduct(id) {
  return http.get(`/products/${id}/`)
}

export function createProduct(data) {
  return http.post('/products/', data)
}

export function updateProduct(id, data) {
  return http.patch(`/products/${id}/`, data)
}