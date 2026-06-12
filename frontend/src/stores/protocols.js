import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getProtocols, getProtocol } from '@/api/protocols'

export const useProtocolsStore = defineStore('protocols', () => {
  const protocols = ref([])
  const currentProtocol = ref(null)
  const loading = ref(false)
  const total = ref(0)

  async function fetchProtocols(params = {}) {
    loading.value = true
    try {
      const result = await getProtocols(params)
      protocols.value = result.data || []
      total.value = result.meta?.pagination?.count || 0
    } catch (err) {
      console.error('Failed to fetch protocols:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchProtocol(id) {
    loading.value = true
    try {
      const result = await getProtocol(id)
      currentProtocol.value = result.data
    } catch (err) {
      console.error('Failed to fetch protocol:', err)
    } finally {
      loading.value = false
    }
  }

  function clearCurrent() {
    currentProtocol.value = null
  }

  return { protocols, currentProtocol, loading, total, fetchProtocols, fetchProtocol, clearCurrent }
})
