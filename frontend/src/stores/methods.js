import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMethods, getMethod } from '@/api/methods'

export const useMethodsStore = defineStore('methods', () => {
  const methods = ref([])
  const currentMethod = ref(null)
  const loading = ref(false)
  const total = ref(0)

  async function fetchMethods(params = {}) {
    loading.value = true
    try {
      const result = await getMethods(params)
      methods.value = result.data || []
      total.value = result.meta?.pagination?.count || 0
    } catch (err) {
      console.error('Failed to fetch methods:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchMethod(id) {
    loading.value = true
    try {
      const result = await getMethod(id)
      currentMethod.value = result.data
    } catch (err) {
      console.error('Failed to fetch method:', err)
    } finally {
      loading.value = false
    }
  }

  function clearCurrent() {
    currentMethod.value = null
  }

  return { methods, currentMethod, loading, total, fetchMethods, fetchMethod, clearCurrent }
})