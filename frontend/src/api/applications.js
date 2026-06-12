import http from '@/utils/http'

export function getApplications(params = {}) {
  return http.get('/applications/', { params })
}

export function getApplication(id) {
  return http.get(`/applications/${id}/`)
}

export function createApplication(data) {
  return http.post('/applications/', data)
}

export function updateApplication(id, data) {
  return http.patch(`/applications/${id}/`, data)
}

export function deleteApplication(id) {
  return http.delete(`/applications/${id}/`)
}