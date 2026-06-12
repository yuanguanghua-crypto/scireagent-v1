import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getBasket,
  addToBasket as addToBasketApi,
  updateBasketItem as updateBasketItemApi,
  removeBasketItem as removeBasketItemApi,
  mergeBasket as mergeBasketApi,
} from '@/api/basket'

export const useBasketStore = defineStore('basket', () => {
  const items = ref([])
  const total = ref('0.00')
  const count = ref(0)
  const loading = ref(false)

  const LOCAL_STORAGE_KEY = 'scireagent_basket'
  const SESSION_KEY_KEY = 'scireagent_session_key'

  /** Ensure session key exists for guest users */
  function getSessionKey() {
    let key = localStorage.getItem(SESSION_KEY_KEY)
    if (!key) {
      key = 'guest_' + crypto.randomUUID()
      localStorage.setItem(SESSION_KEY_KEY, key)
    }
    return key
  }

  // Auto-create session key on store init so http interceptor can send it
  getSessionKey()

  /** Computed: total computed client-side as a fallback */
  const computedTotal = computed(() => {
    return items.value.reduce((sum, item) => {
      const price = parseFloat(item.unit_price || 0)
      return sum + price * item.quantity
    }, 0)
  })

  /** Load basket from API, fallback to localStorage */
  async function loadBasket() {
    loading.value = true
    try {
      const result = await getBasket()
      // http interceptor returns full envelope: {success, data: {items, total, count}, meta}
      const data = result.data || result
      items.value = data.items || []
      total.value = data.total || '0.00'
      count.value = data.count || items.value.reduce((s, i) => s + i.quantity, 0)
    } catch {
      loadLocalBasket()
    } finally {
      loading.value = false
    }
  }

  /** Load basket from localStorage (guest fallback) */
  function loadLocalBasket() {
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        items.value = parsed.items || []
        count.value = items.value.reduce((sum, i) => sum + i.quantity, 0)
      }
    } catch {
      items.value = []
      count.value = 0
    }
  }

  /** Save basket to localStorage (guest fallback) */
  function saveLocalBasket() {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify({ items: items.value }))
  }

  /**
   * Add an item to the basket
   * @param {number} sku_id - SKU ID
   * @param {number} quantity - Quantity (default 1)
   */
  async function addItem(sku_id, quantity = 1) {
    try {
      const result = await addToBasketApi(sku_id, quantity)
      await loadBasket()
      return result
    } catch (err) {
      console.error('[Basket] addItem API failed:', err)
      // Only fallback to localStorage for guest users (no token)
      const token = localStorage.getItem('token')
      if (!token) {
        const existing = items.value.find(i => i.sku_id === sku_id || i.sku === sku_id)
        if (existing) {
          existing.quantity += quantity
        } else {
          items.value.push({
            sku_id: sku_id,
            sku: sku_id,
            quantity: quantity,
            _local: true,
          })
        }
        saveLocalBasket()
        count.value = items.value.reduce((sum, i) => sum + i.quantity, 0)
      } else {
        // Authenticated user — re-throw so caller can show error
        throw err
      }
    }
  }

  /**
   * Update item quantity
   * @param {number|string} itemId - Basket item ID
   * @param {number} quantity - New quantity
   */
  async function updateQuantity(itemId, quantity) {
    if (quantity < 1) {
      return removeItem(itemId)
    }
    try {
      await updateBasketItemApi(itemId, quantity)
      await loadBasket()
    } catch {
      const item = items.value.find(i => i.id === itemId || i.sku_id === itemId || i.sku === itemId)
      if (item) {
        item.quantity = quantity
      }
      saveLocalBasket()
      count.value = items.value.reduce((sum, i) => sum + i.quantity, 0)
    }
  }

  /**
   * Remove item from basket
   * @param {number|string} itemId - Basket item ID
   */
  async function removeItem(itemId) {
    try {
      await removeBasketItemApi(itemId)
      await loadBasket()
    } catch {
      items.value = items.value.filter(
        i => i.id !== itemId && i.sku_id !== itemId && i.sku !== itemId
      )
      saveLocalBasket()
      count.value = items.value.reduce((sum, i) => sum + i.quantity, 0)
    }
  }

  /**
   * Merge localStorage basket into server after login
   */
  async function mergeLocalBasket() {
    const localItems = items.value
      .filter(i => i._local)
      .map(i => ({
        sku_id: i.sku_id || i.sku,
        quantity: i.quantity,
      }))
    if (localItems.length === 0) return

    try {
      await mergeBasketApi(localItems)
      localStorage.removeItem(LOCAL_STORAGE_KEY)
      await loadBasket()
    } catch {
      // Silently fail — items are still in localStorage
    }
  }

  /** Clear all basket state */
  function clearBasket() {
    items.value = []
    total.value = '0.00'
    count.value = 0
    localStorage.removeItem(LOCAL_STORAGE_KEY)
  }

  return {
    items,
    total,
    count,
    loading,
    computedTotal,
    loadBasket,
    addItem,
    updateQuantity,
    removeItem,
    mergeLocalBasket,
    clearBasket,
    getSessionKey,
  }
})
