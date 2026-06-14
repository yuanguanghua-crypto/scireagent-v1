/**
 * Orders Pinia store
 * @module stores/orders
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getOrders, getOrder } from '@/api/orders'

export const useOrdersStore = defineStore('orders', () => {
  const orders = ref([])
  const currentOrder = ref(null)
  const total = ref(0)
  const loading = ref(false)

  async function fetchOrders(params = {}) {
    loading.value = true
    try {
      const res = await getOrders(params)
      const data = res.data || res
      orders.value = data.results || data.data || data || []
      total.value = data.count || data.meta?.pagination?.count || orders.value.length
    } catch (err) {
      console.error('[Orders] fetchOrders failed:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchOrder(id) {
    loading.value = true
    try {
      const res = await getOrder(id)
      currentOrder.value = res.data || res
    } catch (err) {
      console.error('[Orders] fetchOrder failed:', err)
    } finally {
      loading.value = false
    }
  }

  function clearCurrent() {
    currentOrder.value = null
  }

  return {
    orders, currentOrder, total, loading,
    fetchOrders, fetchOrder, clearCurrent,
  }
})
