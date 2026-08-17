/**
 * Product AI endpoints (AUTO MATCH)
 *
 * One-stop enrich (chemical + jena + bioz + literature + protocols),
 * PubChem enrichment, protocol import, bioz adoption, structure render,
 * and admin batch endpoints. The former per-field AI Tools panel
 * (Validate / Recommend Protocols / Literature) has been merged into
 * the one-stop enrich — see `enrichProduct`'s `chemical.mismatches`
 * and `chemical.similar_compounds`.
 */
import http from '@/utils/http'


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

/** One-stop enrich: chemical + literature + protocols + jena + bioz in one call.

 * POST /api/v1/products/enrich/
 * Returns { chemical, literature, protocols, jena, bioz }
 * - jena: 规格凭证 + 归一化规格（purity/storage/...），可填入表单
 * - bioz: 文献证据（依赖 jena 命中 catalog_no），只读预览
 */
export function enrichProduct({ name, cas, smiles, inchi, formula, molecular_weight, productId } = {}) {
  return http.post('/products/enrich/', {
    product_name: name || '',
    cas: cas || '',
    smiles: smiles || '',
    inchi: inchi || '',
    formula: formula || '',
    molecular_weight: molecular_weight ?? null,
    product_id: productId || null,
  }, { timeout: 120000 })
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

/** Adopt bioz references into Reference + ProductReference DB.

 * POST /api/v1/products/<pk>/adopt-bioz-refs/
 * Body: { references: [...], citation_role: 'supporting' }
 * Returns { adopted, skipped, created_refs, linked_refs, errors }
 */
export function adoptBiozRefs(productId, references, citationRole = 'supporting') {
  return http.post(`/products/${productId}/adopt-bioz-refs/`, {
    references: references || [],
    citation_role: citationRole || 'supporting',
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
