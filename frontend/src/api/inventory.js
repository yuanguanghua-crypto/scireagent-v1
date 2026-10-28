/**
 * 库存管理 API（v4.1 DEV-1）—— 后端 apps/inventory/api/v1。
 * 全部端点要求 procurement/admin（IsProcurementOrAdmin）。
 */
import http from '@/utils/http'

/** 库存列表；params: { search?, location?, low_stock?, page? } */
export function getInventoryList(params) {
  return http.get('/inventory/', { params })
}

/** 库存详情：含 movements（最近 50）与 active_allocations（RESERVED） */
export function getInventoryDetail(id) {
  return http.get(`/inventory/${id}/`)
}

/** 入库：(sku, batch, location) 累加可分配量（无则建行）。reason 必填 */
export function receiptStock(data) {
  return http.post('/inventory/receipt/', data)
}

/** 盘点调整：available += delta（结果不可为负）。reason 必填 */
export function adjustStock(id, data) {
  return http.post(`/inventory/${id}/adjust/`, data)
}

/** 已纳管、但一行库存都没有的 SKU（4a 缺口清单）。
 *  这些 SKU 可用量为 0 ⇒ 下单会被全部拦截，而库存表里看不到它们（表里只有库存行）。 */
export function getTrackedGaps() {
  return http.get('/inventory/tracked-gaps/')
}

/** 手工切换「纳入库存管理」开关。
 *  tracked=false 时后端要求该 SKU 无库存、无占用，否则 400 STOCK_NOT_EMPTY。 */
export function setStockTracked(skuId, tracked) {
  return http.post('/inventory/track/', { sku_id: skuId, tracked })
}

/** 变动流水查询；params: { inventory_id? } */
export function getMovements(params) {
  return http.get('/inventory/movements/', { params })
}
