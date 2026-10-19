/**
 * 收藏夹（Wishlist）— 客户侧 API
 * 端点依据 backend/apps/transactions/api/v1/views.py `WishlistViewSet`
 * （路由前缀 /api/v1/wishlist/），序列化为 `WishlistSerializer`：
 *
 *   读：{ id, name, product_count, products: [ProductList…], created_at }
 *   写：{ name?, product_ids?: int[] }   ← product_ids 为**整体替换**语义
 *
 * 注意响应信封：http 拦截器对 `{success,data,meta}` 直接返回**整个信封**，
 * 因此调用方需自行取 `res.data`（见 WishlistPage / ProductDetail 的解包写法）。
 *
 * @module api/wishlist
 */
import http from '@/utils/http'

/**
 * 当前用户的收藏夹列表。
 * GET /api/v1/wishlist/
 * → data: { count, next, previous, results: [{ id, name, product_count, products, created_at }] }
 * ⚠️ 匿名也返回 200，但 results 恒为 []（queryset 为 .none()，不是 401）
 * @param {{ page?: number, page_size?: number }} params
 */
export function getWishlists(params = {}) {
  return http.get('/wishlist/', { params })
}

/**
 * 单个收藏夹详情。
 * GET /api/v1/wishlist/{id}/
 * → data: { id, name, product_count, products, created_at }
 */
export function getWishlist(id) {
  return http.get(`/wishlist/${id}/`)
}

/**
 * 新建收藏夹（必须登录，user 由服务端自动归属）。
 * POST /api/v1/wishlist/
 * @param {{ name?: string, product_ids?: number[] }} data
 * → data: { id, name, product_count, products, created_at }
 */
export function createWishlist(data) {
  return http.post('/wishlist/', data)
}

/**
 * 更新收藏夹（部分更新；必须登录）。
 * PATCH /api/v1/wishlist/{id}/
 * @param {{ name?: string, product_ids?: number[] }} data
 *   ⚠️ product_ids 是**整体替换**：传 [1,2] ⇒ 恰好这两个；传 [] ⇒ 清空；
 *       **省略** ⇒ 产品不变（只改 name 时不会清空）。
 *   ⚠️ 归档产品（archived=true）的 id 会被拒（400，校验阶段失败，不会部分写入）。
 * → data: { id, name, product_count, products, created_at }
 */
export function updateWishlist(id, data) {
  return http.patch(`/wishlist/${id}/`, data)
}

/**
 * 删除收藏夹（必须登录）。
 * DELETE /api/v1/wishlist/{id}/
 * → 204 No Content（拦截器返回 { success: true }）
 */
export function deleteWishlist(id) {
  return http.delete(`/wishlist/${id}/`)
}
