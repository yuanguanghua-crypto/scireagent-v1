import http from '@/utils/http'

export function getResearchGoals(params = {}) {
  return http.get('/research-goals/', { params })
}

export function getResearchGoal(id) {
  return http.get(`/research-goals/${id}/`)
}

export function createResearchGoal(data) {
  return http.post('/research-goals/', data)
}

export function updateResearchGoal(id, data) {
  return http.put(`/research-goals/${id}/`, data)
}

export function deleteResearchGoal(id) {
  return http.delete(`/research-goals/${id}/`)
}
