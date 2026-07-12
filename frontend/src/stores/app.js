import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getNavigation } from '@/api/site'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const navigation = ref(null)
  const loading = ref(false)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  async function fetchNavigation() {
    loading.value = true
    try {
      const result = await getNavigation()
      navigation.value = result.data
    } catch (err) {
      console.error('Failed to fetch navigation:', err)
    } finally {
      loading.value = false
    }
  }

  return { sidebarCollapsed, navigation, loading, toggleSidebar, fetchNavigation }
})