/**
 * 运营台系统状态 —— 邮件通道、投递队列、调度心跳、DB、关键表计数。
 *
 * 对应的痛点（2026-10 反复出现）：`EMAIL_BACKEND` 悄悄变 console、
 * outbox 长期 pending/failed 没人知道、cron 停没停看不出来。
 */
import http from '@/utils/http'

/** 内部人员可读（IsProcurementOrAdmin）。 */
export function getSystemStatus() {
  return http.get('/ops/system-status/')
}

// ── 用户与角色（IsAdmin）────────────────────────────────────────────────
// 刻意只开这三条写操作：改 role / 启停 / 验证邮箱 / 触发重置邮件。
// 没有"直接改密码"——密码只能由本人通过邮件链接设置。

export function getUsers(params = {}) {
  return http.get('/ops/users/', { params })
}

/** 只接受 { role, is_active }；传其它字段后端会 400（不静默忽略）。 */
export function patchUser(id, payload) {
  return http.patch(`/ops/users/${id}/`, payload)
}

export function verifyUserEmail(id) {
  return http.post(`/ops/users/${id}/verify-email/`)
}

export function sendUserPasswordReset(id) {
  return http.post(`/ops/users/${id}/send-password-reset/`)
}

// ── 邮件模板 ──────────────────────────────────────────────────────────
// 只允许改文案，不能改 key（key 是代码里的契约，改了 enqueue 就找不到模板）。

export function getEmailTemplates() {
  return http.get('/ops/email-templates/')
}

export function getEmailTemplate(key) {
  return http.get(`/ops/email-templates/${key}/`)
}

export function updateEmailTemplate(key, payload) {
  return http.patch(`/ops/email-templates/${key}/`, payload)
}

/**
 * 试渲染（不写库不发信）。
 * 不传 ctx 时后端自动用最近一条同模板真实 outbox 记录的 context_json ——
 * 比手编示例可靠（真实字段名、真实格式）。
 * 传 overrides 可预览"编辑未保存的草稿"。
 */
export function previewEmailTemplate(key, payload = {}) {
  return http.post(`/ops/email-templates/${key}/preview/`, payload)
}

/** 发一封测试信给**自己**（后端固定收件人为当前登录邮箱，不接受前端指定）。 */
export function sendTestEmail(key, payload = {}) {
  return http.post(`/ops/email-templates/${key}/send-test/`, payload)
}

// ── 投递队列 ──────────────────────────────────────────────────────────

export function getEmailOutbox(params = {}) {
  return http.get('/ops/email-outbox/', { params })
}

/** action: 'retry' | 'discard' */
export function emailOutboxAction(id, action) {
  return http.post(`/ops/email-outbox/${id}/${action}/`)
}

// ── 审计日志（只读）────────────────────────────────────────────────────
// ⚠️ AuditLog 目前**只记录产品**变更（CREATE/UPDATE/DELETE/RESTORE/HARD_DELETE）。
//    订单/用户/报价/邮件都不记 —— UI 上必须如实标注，否则会被当成全局审计。

export function getAuditLogs(params = {}) {
  return http.get('/ops/audit-logs/', { params })
}

/** 详情含 snapshot（变更前/后的字段值）。 */
export function getAuditLog(id) {
  return http.get(`/ops/audit-logs/${id}/`)
}
