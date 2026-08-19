import http from '@/utils/http'

/**
 * Fetch a knowledge graph subgraph around an entity.
 * @param {string} type - Entity type: product, application, method, protocol, reference
 * @param {number} id - Entity ID
 * @param {object} opts - Optional params: depth, max_nodes, max_edges
 * @returns {Promise<{nodes: Array, edges: Array}>}
 */
export function getGraph(type, id, opts = {}) {
  return http.get('/graph', {
    params: {
      type,
      id,
      depth: opts.depth ?? 3,
      max_nodes: opts.maxNodes ?? 50,
      max_edges: opts.maxEdges ?? 100,
    },
  })
}
