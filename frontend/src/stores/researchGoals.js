import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getResearchGoals,
  getResearchGoal,
  createResearchGoal,
  updateResearchGoal,
  deleteResearchGoal,
} from '@/api/researchGoals'

export const useResearchGoalsStore = defineStore('researchGoals', () => {
  const goals = ref([])
  const currentGoal = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const pagination = ref({
    page: 1,
    pageSize: 20,
    total: 0,
  })
  const filters = ref({
    search: '',
    status: '',
  })

  const totalPages = computed(() =>
    Math.ceil(pagination.value.total / pagination.value.pageSize)
  )

  /** Fetch paginated research goals list */
  async function fetchGoals(params = {}) {
    loading.value = true
    error.value = null
    try {
      const result = await getResearchGoals({
        page: pagination.value.page,
        page_size: pagination.value.pageSize,
        search: filters.value.search || undefined,
        status: filters.value.status || undefined,
        ...params,
      })
      goals.value = result.data || []
      pagination.value.total = result.meta?.pagination?.count || 0
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /** Fetch a single research goal by ID */
  async function fetchGoal(id) {
    loading.value = true
    error.value = null
    try {
      const result = await getResearchGoal(id)
      currentGoal.value = result.data
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /** Create a new research goal */
  async function addGoal(data) {
    loading.value = true
    error.value = null
    try {
      const result = await createResearchGoal(data)
      goals.value.unshift(result.data)
      pagination.value.total += 1
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /** Update an existing research goal */
  async function editGoal(id, data) {
    loading.value = true
    error.value = null
    try {
      const result = await updateResearchGoal(id, data)
      const index = goals.value.findIndex((g) => g.id === id)
      if (index !== -1) {
        goals.value[index] = result.data
      }
      if (currentGoal.value?.id === id) {
        currentGoal.value = result.data
      }
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  /** Delete a research goal by ID */
  async function removeGoal(id) {
    loading.value = true
    error.value = null
    try {
      await deleteResearchGoal(id)
      goals.value = goals.value.filter((g) => g.id !== id)
      pagination.value.total = Math.max(0, pagination.value.total - 1)
      if (currentGoal.value?.id === id) {
        currentGoal.value = null
      }
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  function setPage(page) {
    pagination.value.page = page
  }

  function setFilters(newFilters) {
    filters.value = { ...filters.value, ...newFilters }
    pagination.value.page = 1
  }

  function resetFilters() {
    filters.value = { search: '', status: '' }
    pagination.value.page = 1
  }

  /** Clear the currently viewed research goal */
  function clearCurrent() {
    currentGoal.value = null
  }

  return {
    goals,
    currentGoal,
    loading,
    error,
    pagination,
    filters,
    totalPages,
    fetchGoals,
    fetchGoal,
    addGoal,
    editGoal,
    removeGoal,
    setPage,
    setFilters,
    resetFilters,
    clearCurrent,
  }
})
