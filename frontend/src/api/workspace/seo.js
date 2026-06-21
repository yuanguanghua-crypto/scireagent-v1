import { http } from '@/api/http'

export function generateSeo(productId) {
  return http.post(`/products/${productId}/generate-seo/`)
}
