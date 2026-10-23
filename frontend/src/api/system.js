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
