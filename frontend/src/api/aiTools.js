/**
 * AI Tools API
 *
 * Product validation, protocol recommendation, and literature recommendation
 * endpoints for the admin AI tools panel.
 */
import http from '@/utils/http'

/** Validate a product against PubChem and BioProCorpus. */
export function validateProduct(id) {
  return http.post(`/products/${id}/validate/`)
}

/** Recommend protocols from BioProCorpus for a product. */
export function recommendProtocols(id, topK = 5) {
  return http.post(`/products/${id}/recommend-protocols/`, { top_k: topK })
}

/** Recommend literature from PubMed for a product. */
export function recommendLiterature(id, topK = 5) {
  return http.post(`/products/${id}/recommend-literature/`, { top_k: topK })
}

/** Batch validate multiple products at once. */
export function batchValidate(productIds) {
  return http.post('/products/batch-validate/', { product_ids: productIds })
}

/** Batch recommend literature for multiple products at once. */
export function batchRecommendLiterature(productIds) {
  return http.post('/products/batch-recommend-literature/', { product_ids: productIds })
}
