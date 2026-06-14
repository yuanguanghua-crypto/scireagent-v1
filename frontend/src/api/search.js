import http from '@/utils/http'

export function search(query, params = {}) {
  return http.get('/search', { params: { q: query, ...params } })
}

export function searchSuggest(query) {
  return http.get('/search/suggest', { params: { q: query } })
}

/**
 * Grouped search — results organized by entity type.
 * @param {string} query
 * @param {string} [type] - Optional type filter: product, application, method, protocol, reference
 */
export function searchGrouped(query, type = '') {
  const params = { q: query }
  if (type) params.type = type
  return http.get('/search/grouped', { params })
}