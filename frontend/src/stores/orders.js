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
  // ★ 2026-10-21 新增（D2）：分页状态。此前 store 完全没有 page 概念，导致恒为第 1 页。
  const page = ref(1)
  const pageSize = ref(20)

  async function fetchOrders(params = {}) {
    loading.value = true
    try {
      // ★ 显式带上分页参数：`getOrders` 原文档就写了 "Query params (page, status)"，但一直没人传。
      const reqPage = Number(params.page ?? page.value) || 1
      const reqSize = Number(params.page_size ?? pageSize.value) || 20
      const res = await getOrders({ ...params, page: reqPage, page_size: reqSize })

      // ★ 2026-10-21 修 D2（P0）：响应形状是**整个信封**
      //   `{ success: true, data: [...本页条目...], meta: { pagination: { count, next, previous } } }`
      //   —— 见后端 `core/renderers.py:31-37`（有 `results` 时把分页信息挪进 `meta.pagination`，
      //   并把 `data` 直接替换成结果数组）。
      //   旧代码 `const data = res.data || res` 之后又读 `data.meta?.pagination?.count`，
      //   而 `data` **已经是数组** ⇒ 前两个分支永远 undefined ⇒ `total` 回落成
      //   `orders.value.length`（= 当前页 20 条）⇒ 分页信息全错。
      const meta = res && typeof res.meta === 'object' && res.meta ? res.meta : {}
      const payload = res && res.data !== undefined ? res.data : res
      const list = Array.isArray(payload)
        ? payload
        : (payload?.results || payload?.data || [])

      orders.value = list

      const pmeta = meta.pagination || payload?.meta?.pagination || {}
      // `count` 是后端真实总数；取不到时才退回"当前页条数"（保持旧兜底，但不再是主路径）
      total.value = Number(pmeta.count ?? payload?.count ?? list.length)
      page.value = reqPage
      pageSize.value = reqSize
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
    page, pageSize,
    fetchOrders, fetchOrder, clearCurrent,
  }
})
