import http from '@/utils/http'

export function search(query, params = {}) {
  return http.get('/search', { params: { q: query, ...params } })
}

export function searchSuggest(query) {
  return http.get('/search/suggest', { params: { q: query } })
}