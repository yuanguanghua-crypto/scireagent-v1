/**
 * AI Tools API
 *
 * Product validation, protocol recommendation, literature recommendation,
 * and PubChem data enrichment endpoints for the admin AI tools panel.
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

/** Validate an unsaved product (new product page, no productId). */
export function validateUnsavedProduct(name, cas, smiles) {
  return http.post('/products/validate-unsaved/', { name, cas, smiles })
}

/** Recommend protocols for an unsaved product (new product page). */
export function recommendProtocolsUnsaved(name, topK = 5) {
  return http.post('/products/recommend-protocols-unsaved/', { name, top_k: topK })
}

/** Recommend literature for an unsaved product (new product page). */
export function recommendLiteratureUnsaved(name, cas, topK = 5) {
  return http.post('/products/recommend-literature-unsaved/', { name, cas, top_k: topK })
}

/** Batch validate multiple products at once. */
export function batchValidate(productIds) {
  return http.post('/products/batch-validate/', { product_ids: productIds })
}

/** Batch recommend literature for multiple products at once. */
export function batchRecommendLiterature(productIds) {
  return http.post('/products/batch-recommend-literature/', { product_ids: productIds })
}

/** Enrich product chemical properties from PubChem by name/CAS. */
export function enrichFromPubchem(productName, cas = null) {
  return http.post('/products/enrich-from-pubchem/', {
    product_name: productName,
    cas: cas,
  })
}

/** Batch enrich multiple products from PubChem. */
export function batchEnrichFromPubchem(productIds) {
  return http.post('/products/enrich-from-pubchem/', { product_ids: productIds })
}
