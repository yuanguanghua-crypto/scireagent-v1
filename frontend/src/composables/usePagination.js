import { ref, computed } from 'vue'

export function usePagination(fetchFn, defaultPageSize = 20) {
  const currentPage = ref(1)
  const pageSize = ref(defaultPageSize)
  const total = ref(0)
  const items = ref([])

  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

  async function load(params = {}) {
    const result = await fetchFn({
      page: currentPage.value,
      page_size: pageSize.value,
      ...params,
    })
    items.value = result.data || []
    total.value = result.meta?.pagination?.count || 0
    return result
  }

  function setPage(page) {
    currentPage.value = page
  }

  function reset() {
    currentPage.value = 1
    total.value = 0
    items.value = []
  }

  return { currentPage, pageSize, total, items, totalPages, load, setPage, reset }
}