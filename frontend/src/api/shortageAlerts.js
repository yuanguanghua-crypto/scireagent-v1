/**
 * 缺货拦截告警台 API（2026-10-28）
 *
 * 端点依据 `backend/apps/inventory/api/v1/urls.py`：
 *   GET  /api/v1/inventory/shortage-alerts/                 列表（含 meta.counts 四态计数）
 *   POST /api/v1/inventory/shortage-alerts/<id>/resolve/    标记已补货/已联系/已忽略/撤回
 *
 * @module api/shortageAlerts
 */
import http from '@/utils/http'

/** 列表：status 为空 = 全部；search 匹配 SKU / 产品名 / 用户名 / 邮箱。 */
export function getShortageAlerts(params = {}) {
  return http.get('/inventory/shortage-alerts/', { params })
}

/** 标记处理。status ∈ new | restocked | contacted | dismissed */
export function resolveShortageAlert(id, status, note = '') {
  return http.post(`/inventory/shortage-alerts/${id}/resolve/`, { status, note })
}
