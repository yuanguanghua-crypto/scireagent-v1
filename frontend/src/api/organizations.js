import http from '@/utils/http'

/**
 * Search organizations by query string.
 * @param {Object} params - Query parameters (e.g. { q: 'search term' })
 * @returns {Promise}
 */
export function searchOrganizations(params) {
  return http.get('/organizations', { params })
}

/**
 * Create a new organization.
 * @param {Object} data - Organization data { name, org_type, ... }
 * @returns {Promise}
 */
export function createOrganization(data) {
  return http.post('/organizations/create', data)
}
