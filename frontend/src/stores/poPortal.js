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
  // ★ 2026-10-21 修 D5：分页状态。此前完全没有 page 概念 ⇒ 恒第 1 页（后端 PAGE_SIZE=20）。
  const page = ref(1)
  const pageSize = ref(20)

  async function fetchOrders(params = {}) {
    loading.value = true
    try {
      const reqPage = Number(params.page ?? page.value) || 1
      const reqSize = Number(params.page_size ?? pageSize.value) || 20
      const res = await getMyOrders({ ...params, page: reqPage, page_size: reqSize })

      // ★ 2026-10-21 修 D5：信封形状是
      //   `{ success, data: [本页条目], meta: { pagination: { count, next, previous } } }`
      //   （后端 `core/renderers.py:31-37` 把分页信息挪进 meta、data 直接换成数组）。
      //   旧代码读 `payload.meta?.pagination?.count`，而 `payload` 已是数组
      //   ⇒ 前两个分支永远 undefined ⇒ `total` 恒等于当前页条数（20），
      //   页面副标题「{{ total }} order(s)」因此永远显示 20（D2 同款错误）。
      const meta = (res && typeof res.meta === 'object' && res.meta) || {}
      const payload = res && res.data !== undefined ? res.data : res
      orders.value = Array.isArray(payload) ? payload : (payload?.results || payload?.data || [])
      const pmeta = meta.pagination || {}
      total.value = Number(pmeta.count ?? payload?.count ?? orders.value.length)
      page.value = reqPage
      pageSize.value = reqSize
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
    page, pageSize,
    fetchOrders, fetchOrder, clearCurrent,
  }
})
