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

/** Enrich product chemical properties from PubChem.

 * Passes all available identifiers — backend picks the best one.
 * Priority: CAS > name > SMILES > InChI
 */
export function enrichFromPubchem({ name, cas, smiles, inchi } = {}) {
  return http.post('/products/enrich-from-pubchem/', {
    product_name: name || '',
    cas: cas || '',
    smiles: smiles || '',
    inchi: inchi || '',
  })
}

/** Batch enrich multiple products from PubChem. */
export function batchEnrichFromPubchem(productIds) {
  return http.post('/products/enrich-from-pubchem/', { product_ids: productIds })
}

/** One-stop enrich: chemical + literature + protocols in one call.

 * POST /api/v1/products/enrich/
 * Returns { chemical, literature, protocols }
 */
export function enrichProduct({ name, cas, smiles, inchi } = {}) {
  return http.post('/products/enrich/', {
    product_name: name || '',
    cas: cas || '',
    smiles: smiles || '',
    inchi: inchi || '',
  })
}

/** Import a BioProCorpus protocol into knowledge base.

 * POST /api/v1/products/import-protocol/
 * Returns { method_id, protocol_id, step_count }
 */
export function importProtocol({
  method_name, protocol_title, protocol_url,
  objective, reagents, equipment, materials,
  steps, method_ids,
} = {}) {
  return http.post('/products/import-protocol/', {
    method_name: method_name || '',
    protocol_title: protocol_title || '',
    protocol_url: protocol_url || '',
    objective: objective || '',
    reagents: reagents || '',
    equipment: equipment || '',
    materials: materials || '',
    steps: steps || [],
    method_ids: method_ids || [],
  })
}

/** Render SMILES to publication-quality SVG via RDKit backend.

 * POST /api/v1/products/render-structure/
 * Returns { svg, format, canonical_smiles }
 */
export function renderStructure(smiles, width = 500, height = 400) {
  return http.post('/products/render-structure/', {
    smiles: smiles || '',
    width,
    height,
  })
}
