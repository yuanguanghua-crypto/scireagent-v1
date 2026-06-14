import { ref } from 'vue'
import { getGraph } from '@/api/graph'

/**
 * Composable for fetching and managing knowledge graph data.
 * @param {string} type - Entity type
 * @param {number|Ref} id - Entity ID (reactive)
 * @param {object} opts - Options: depth, maxNodes, maxEdges
 */
export function useGraph(type, id, opts = {}) {
  const nodes = ref([])
  const edges = ref([])
  const loading = ref(false)
  const error = ref(null)
  const meta = ref(null)

  async function fetch() {
    loading.value = true
    error.value = null
    try {
      const idVal = typeof id === 'object' && id.value !== undefined ? id.value : id
      if (!idVal) {
        nodes.value = []
        edges.value = []
        return
      }
      const resp = await getGraph(type, idVal, opts)
      nodes.value = resp.data?.nodes || []
      edges.value = resp.data?.edges || []
      meta.value = resp.meta || null
    } catch (e) {
      error.value = e
      nodes.value = []
      edges.value = []
    } finally {
      loading.value = false
    }
  }

  return { nodes, edges, loading, error, meta, fetch }
}
