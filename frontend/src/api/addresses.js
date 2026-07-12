/**
 * 地址管理 API（节点4 — bill-to / ship-to）
 * 字段依据 ARCHITECTURE.md §3.1.1 accounts.Address。
 * 注意：后端 /addresses/ CRUD 端点按规划应在 P1 落地；此处前端按规划字段对齐，
 * 调用缺失时由 http 拦截器统一 toast 提示，页面仍可编译与占位。
 * @module api/addresses
 */
import http from '@/utils/http'

export function getAddresses(params = {}) {
  return http.get('/addresses/', { params })
}

export function createAddress(data) {
  return http.post('/addresses/', data)
}

export function updateAddress(id, data) {
  return http.put(`/addresses/${id}/`, data)
}

export function deleteAddress(id) {
  return http.delete(`/addresses/${id}/`)
}
