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
      // ★ 2026-11-27（A-176）：页码越界时后端返回 404 "Invalid page."，
      //   前端此前只把红字打在页面上、**卡片仍是上一页内容**（QA 点第 1429 页复现）。
      //   这里收敛成"回到最后一个有效页（无 total 时回第 1 页）并重试一次"，
      //   用户看到的是一次正常翻页，而不是一句英文报错 + 不动的列表。
      const detail = err?.response?.data?.meta?.error?.message
        || err?.response?.data?.detail || ''
      const invalidPage = err?.response?.status === 404 && /invalid page/i.test(String(detail))
      if (invalidPage && !params.__pageRetried) {
        const pageSize = pagination.value.pageSize || 20
        const total = pagination.value.total || 0
        const lastPage = total > 0 ? Math.max(1, Math.ceil(total / pageSize)) : 1
        const requested = Number(params.page) || pagination.value.page || 1
        // 优先落到最后一个有效页；算不出（无 total）或本来就在第一页 ⇒ 回第 1 页
        pagination.value.page = (lastPage > 1 && lastPage < requested) ? lastPage : 1
        return fetchApplications({ ...params, __pageRetried: true })
      }
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