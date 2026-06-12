import http from '@/utils/http'

/**
 * Get current basket (guest or authenticated)
 * @returns {Promise<{items: Array, total: string, count: number}>}
 */
export function getBasket() {
  return http.get('/basket')
}

/**
 * Add item to basket
 * @param {number} sku_id - SKU ID to add
 * @param {number} quantity - Quantity to add (default 1)
 * @returns {Promise}
 */
export function addToBasket(sku_id, quantity = 1) {
  return http.post('/basket/items', { sku_id, quantity })
}

/**
 * Update basket item quantity
 * @param {number} id - Basket item ID
 * @param {number} quantity - New quantity
 * @returns {Promise}
 */
export function updateBasketItem(id, quantity) {
  return http.patch(`/basket/items/${id}`, { quantity })
}

/**
 * Remove item from basket
 * @param {number} id - Basket item ID
 * @returns {Promise}
 */
export function removeBasketItem(id) {
  return http.delete(`/basket/items/${id}/delete`)
}

/**
 * Merge guest basket into authenticated user basket
 * @param {Array<{sku_id: number, quantity: number}>} items - Local items to merge
 * @returns {Promise}
 */
export function mergeBasket(items) {
  return http.post('/basket/merge', { items })
}
