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

/**
 * 关闭询价（A-223，2026-11-26）。
 *
 * 为什么需要：`Status.CLOSED` 在枚举里一直存在，但**没有任何写入口**——
 * 已报价的 RFQ 在运营台上找不到关闭按钮，收件箱只增不减。
 * 客户撤回、重复提交、明显无效的询价都清不出去。
 *
 * payload: { reason? } —— 可选，会以 `[关闭]` 前缀追加到 notes（不覆盖客户原文）
 * 已关闭的再关返回 409 `ALREADY_CLOSED`。
 */
export function closeQuoteRequest(id, reason = '') {
  return http.post(`/quote-requests/${id}/close/`, { reason })
}

/**
 * 把询价标为「审核中」（A-020，P0，2026-11-27）。
 *
 * 为什么需要：`Status.REVIEWING` 在枚举里一直存在，但全仓**没有写它的路径** ——
 * 运营拿到一条询价后无法表示"我已经在看这条了"，收件箱里 "pending" 与
 * "没人管" 永远分不开。
 *
 * 只允许 pending → reviewing；已在 reviewing 或更往后返回 409。
 */
export function startQuoteReview(id) {
  return http.post(`/quote-requests/${id}/review/`)
}

/**
 * 客户接受 / 拒绝报价（A-264，2026-11-27）。
 *
 * payload: { action: 'accept' | 'reject', note? }
 * 只有该 RFQ 的客户本人、且状态为 quoted 时可答复（否则 409/404）。
 * 答复后状态变 accepted / rejected，并记录客户答复时间。
 */
export function respondToQuote(id, payload) {
  return http.post(`/quote-requests/${id}/respond/`, payload)
}

/** 我提交过的询价（A-170）—— 客户侧用，按 user 或 contact_email 归属 */
export function getMyQuoteRequests() {
  return http.get('/quote-requests/mine/')
}
