/**
 * PO 采购门户 — 客户侧 store（订单列表 / 详情）
 * @module stores/poPortal
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMyOrders, getOrderDetail } from '@/api/poPortal'

export const usePoPortalStore = defineStore('poPortal', () => {
  const orders = ref([])
  const currentOrder = ref(null)
  const total = ref(0)
  const loading = ref(false)

  async function fetchOrders(params = {}) {
    loading.value = true
    try {
      const res = await getMyOrders(params)
      const payload = res.data || res
      orders.value = payload.results || payload.data || payload || []
      total.value = payload.count || payload.meta?.pagination?.count || orders.value.length
    } catch (err) {
      console.error('[poPortal] fetchOrders failed:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchOrder(id) {
    loading.value = true
    try {
      const res = await getOrderDetail(id)
      currentOrder.value = res.data || res
    } catch (err) {
      console.error('[poPortal] fetchOrder failed:', err)
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
