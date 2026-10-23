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
