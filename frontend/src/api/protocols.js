import http from '@/utils/http'

export function getProtocols(params = {}) {
  return http.get('/protocols/', { params })
}

export function getProtocol(id) {
  return http.get(`/protocols/${id}/`)
}

export function createProtocol(data) {
  return http.post('/protocols/', data)
}

export function updateProtocol(id, data) {
  return http.patch(`/protocols/${id}/`, data)
}