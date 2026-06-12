import { ref } from 'vue'

export function useApi(apiFn) {
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function execute(...args) {
    loading.value = true
    error.value = null
    try {
      const result = await apiFn(...args)
      data.value = result.data
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, execute }
}