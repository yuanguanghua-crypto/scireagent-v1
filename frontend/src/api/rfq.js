/**
 * RFQ（询价单）—— 内部运营台用。
 *
 * 注意三条面不同权限（见 backend/apps/quotes/api/v1/views.py 顶部说明）：
 *   创建：`POST /quote-requests/`（匿名可提交，获客入口）
 *   查询：`GET /quote-requests/manage/`（内部人员，本模块用）
 *   报价：`POST /quote-requests/:id/quote/`（内部人员；推进状态到 quoted 并通知客户）
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

/**
 * 填写报价并通知客户。
 *
 * payload: { quoted_total, quoted_currency, quoted_valid_until, quoted_note, notify_customer }
 * - `quoted_total` 可为 null：表示只回执"请联系我们"，不必编一个价格
 * - `notify_customer=false` 只记账不发信
 * - 后端把状态推进到 `quoted`，邮件入队失败也不会回滚报价
 */
export function saveQuote(id, payload) {
  return http.post(`/quote-requests/${id}/quote/`, payload)
}
