import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getApplications,
  getApplication,
  createApplication,
  updateApplication,
  deleteApplication,
} from '@/api/applications'

export const useApplicationsStore = defineStore('applications', () => {
  const applications = ref([])
  const currentApplication = ref(null)
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
    category: '',
  })

  const totalPages = computed(() =>
    Math.ceil(pagination.value.total / pagination.value.pageSize)
  )

  const activeApplications = computed(() =>
    applications.value.filter((app) => app.status === 'active')
  )

  async function fetchApplications(params = {}) {
    loading.value = true
    error.value = null
    try {
      const result = await getApplications({
        page: pagination.value.page,
        page_size: pagination.value.pageSize,
        search: filters.value.search || undefined,
        status: filters.value.status || undefined,
        category: filters.value.category || undefined,
        ...params,
      })
      applications.value = result.data || []
      pagination.value.total = result.meta?.pagination?.count || 0
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchApplication(id) {
    loading.value = true
    error.value = null
    try {
      const result = await getApplication(id)
      currentApplication.value = result.data
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function addApplication(data) {
    loading.value = true
    error.value = null
    try {
      const result = await createApplication(data)
      applications.value.unshift(result.data)
      pagination.value.total += 1
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function editApplication(id, data) {
    loading.value = true
    error.value = null
    try {
      const result = await updateApplication(id, data)
      const index = applications.value.findIndex((app) => app.id === id)
      if (index !== -1) {
        applications.value[index] = result.data
      }
      if (currentApplication.value?.id === id) {
        currentApplication.value = result.data
      }
      return result
    } catch (err) {
      error.value = err
      throw err
    } finally {
      loading.value = false
    }
  }

  async function removeApplication(id) {
    loading.value = true
    error.value = null
    try {
      await deleteApplication(id)
      applications.value = applications.value.filter((app) => app.id !== id)
      pagination.value.total -= 1
      if (currentApplication.value?.id === id) {
        currentApplication.value = null
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
    filters.value = { search: '', status: '', category: '' }
    pagination.value.page = 1
  }

  function clearCurrent() {
    currentApplication.value = null
  }

  return {
    applications,
    currentApplication,
    loading,
    error,
    pagination,
    filters,
    totalPages,
    activeApplications,
    fetchApplications,
    fetchApplication,
    addApplication,
    editApplication,
    removeApplication,
    setPage,
    setFilters,
    resetFilters,
    clearCurrent,
  }
})