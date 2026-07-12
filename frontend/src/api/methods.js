import http from '@/utils/http'

export function getMethods(params = {}) {
  return http.get('/methods/', { params })
}

export function getMethod(id) {
  return http.get(`/methods/${id}/`)
}

export function createMethod(data) {
  return http.post('/methods/', data)
}

export function updateMethod(id, data) {
  return http.patch(`/methods/${id}/`, data)
}