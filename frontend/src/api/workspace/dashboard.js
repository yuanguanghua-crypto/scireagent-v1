import { http } from '@/api/http'

export function getDashboardStats() {
  return http.get('/admin/dashboard-stats/')
}

export function getRecentProducts(limit = 10) {
  return http.get('/products/', { params: { page_size: limit, ordering: '-updated_at' } })
}
