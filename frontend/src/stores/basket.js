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
    // 记录本次取数时是否处于匿名态。游客条目来自 X-Session-Key 作用域，
    // 账户条目来自 user 作用域 —— 两者不可混为一谈（见 mergeLocalBasket）。
    const fetchedAsGuest = !localStorage.getItem('token')
    try {
      const result = await getBasket()
      // http interceptor returns full envelope: {success, data: {items, total, count}, meta}
      const data = result.data || result
      items.value = (data.items || []).map((i) => ({ ...i, _guest: fetchedAsGuest }))
      total.value = data.total || '0.00'
      // count = TOTAL units (sum of quantities), not distinct line items, so that
      // re-adding the same SKU bumps the badge. Must match the localStorage fallback
      // path below (which already sums quantities).
      count.value = items.value.reduce((s, i) => s + (Number(i.quantity) || 0), 0)
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
   * Merge guest basket into the authenticated user's server basket.
   *
   * P0-2：匿名加购主要落在**服务端** —— 后端 `AddToBasketView` 按 `X-Session-Key`
   * 写库（Basket.user 为 NULL），而 `BasketItemSerializer` 不输出 `_local` 字段。
   * 所以旧实现 `items.value.filter(i => i._local)` 在主路径恒为空数组 ⇒ 提前
   * return，压根不会调用后端合并接口。`_local` 只出现在 addItem 的兜底分支。
   *
   *⚠️ 只能合并**游客作用域**的条目（`_guest`）。后端合并是叠加语义
   *   （get_or_create 后 `quantity += n`），若把账户自己的行回传，每次重新登录
   *   都会让数量翻倍（实测 2 → 4、3 → 6）。`_guest` 由 loadBasket() 在取数当下
   *   打的标记，登录后 loadBasket() 重新取到的账户行不带该标记，故天然被排除。
   *
   * ⚠️ 合并成功后必须清掉 session key：后端不会删除游客的 session_key 行，
   *   若保留，登出后再登录会把同一批陈旧行二次合并（实测 3 → 6）。
   *
   * @param {Array<{sku?: number, sku_id?: number, quantity: number}>} [itemsToMerge]
   * @returns {Promise<boolean>} 是否合并成功；失败返回 false，绝不抛出（不得阻断登录）
   */
  async function mergeLocalBasket(itemsToMerge) {
    const source = itemsToMerge || items.value.filter((i) => i._guest || i._local)
    const payload = source
      .filter((i) => i && (i.sku ?? i.sku_id) && Number(i.quantity) > 0)
      .map((i) => ({
        sku_id: i.sku ?? i.sku_id,
        quantity: Number(i.quantity),
      }))
    if (payload.length === 0) return false

    try {
      await mergeBasketApi(payload)
      // 仅在成功后清理：失败时保留本地副本，游客下次登录仍可重试。
      localStorage.removeItem(LOCAL_STORAGE_KEY)
      // 使这批游客行不再可达，否则登出→再登录会二次合并导致数量翻倍。
      // ⚠️ 必须立刻重新生成：getSessionKey() 只在 store 初始化时调用一次，
      //   若只删不补，本次会话内登出后匿名加购会因缺 X-Session-Key 被后端
      //   400 拒绝（AddToBasketView 要求该头）。
      localStorage.removeItem(SESSION_KEY_KEY)
      getSessionKey()
      await loadBasket()
      return true
    } catch (err) {
      // 合并失败不得阻断登录：用户已登录成功。保留本地副本，仅记录日志。
      console.error('[Basket] mergeLocalBasket failed:', err)
      return false
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
