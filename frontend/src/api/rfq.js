/**
 * RFQ（询价单）—— 内部运营台用。
 *
 * 注意两条面不同权限（见 backend/apps/quotes/api/v1/views.py 顶部说明）：
 *   创建：`POST /quote-requests/`（匿名可提交，获客入口）
 *   查询：`GET /quote-requests/manage/`（内部人员，本模块用）
 */
import http from '@/utils/http'

/** 收件箱列表（内部人员）。params: { page_size, search, status } */
export function getQuoteRequests(params = {}) {
  return http.get('/quote-requests/manage/', { params })
}

/** 单条详情（内部人员可看任意；普通客户仅自己） */
export function getQuoteRequestDetail(id) {
  return http.get(`/quote-requests/${id}/`)
}
