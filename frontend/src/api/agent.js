import http from '@/utils/http'

/**
 * Fetch JSON-LD structured data for a product.
 *
 * @param {number|string} id - The product ID (primary key).
 * @returns {Promise<Object>} The JSON-LD data for the product.
 */
export function getProductJsonLd(id) {
  return http.get(`/products/${id}/json-ld/`)
}

/**
 * Fetch JSON-LD structured data for a method.
 *
 * @param {number|string} id - The method ID (primary key).
 * @returns {Promise<Object>} The JSON-LD data for the method.
 */
export function getMethodJsonLd(id) {
  return http.get(`/methods/${id}/json-ld/`)
}

/**
 * Fetch JSON-LD structured data for a protocol.
 *
 * @param {number|string} id - The protocol ID (primary key).
 * @returns {Promise<Object>} The JSON-LD data for the protocol.
 */
export function getProtocolJsonLd(id) {
  return http.get(`/protocols/${id}/json-ld/`)
}
