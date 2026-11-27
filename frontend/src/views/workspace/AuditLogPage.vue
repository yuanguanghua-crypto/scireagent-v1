<script setup>
/**
 * 审计日志 —— 追溯"谁在什么时候对哪个产品做了什么，改之前是什么值"。
 *
 * ⚠️ 覆盖范围要如实标注：AuditLog 目前**只记录产品**变更。
 *    订单 / 用户 / 报价 / 邮件都不记。不标清楚会被当成"全局审计"，
 *    到时候查不到订单的变更记录反而更困惑。
 *    （要扩范围得在对应视图层加 AuditLog.log(...)，不是改这个页面。）
 */
import { onMounted, ref } from 'vue'
import { getAuditLogs, getAuditLog } from '@/api/system'
import { extractErrorMessage } from '@/utils/http'
import IsoDateInput from '@/components/common/IsoDateInput.vue'

const rows = ref([])
const total = ref(0)
const coverage = ref(null)
const loading = ref(false)
const error = ref('')

const actionFilter = ref('')
const userFilter = ref('')
const search = ref('')
const since = ref('')
const until = ref('')

const ACTIONS = [
  { value: '', label: 'All actions' },
  { value: 'CREATE', label: 'Create' },
  { value: 'UPDATE', label: 'Update' },
  { value: 'DELETE', label: 'Delete (archive)' },
  { value: 'RESTORE', label: 'Restore' },
  { value: 'HARD_DELETE', label: 'Hard delete' },
]

const detail = ref(null)
const detailLoading = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  detail.value = null
  try {
    const params = { limit: 200 }
    if (actionFilter.value) params.action = actionFilter.value
    if (userFilter.value.trim()) params.username = userFilter.value.trim()
    if (search.value.trim()) params.search = search.value.trim()
    if (since.value) params.since = since.value
    if (until.value) params.until = until.value
    const res = await getAuditLogs(params)
    const payload = res.data ?? res
    rows.value = Array.isArray(payload) ? payload : (payload.results || [])
    total.value = res.meta?.pagination?.count ?? rows.value.length
    coverage.value = res.meta?.coverage ?? null
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load audit logs.")
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  if (detail.value && detail.value.id === row.id) { detail.value = null; return }
  detailLoading.value = true
  try {
    const res = await getAuditLog(row.id)
    detail.value = res.data ?? res
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load this record.")
  } finally {
    detailLoading.value = false
  }
}

function fmtTime(v) {
  if (!v) return '—'
  try { return new Date(v).toLocaleString() } catch { return String(v) }
}

function actionClass(a) {
  if (a === 'HARD_DELETE') return 'err'
  if (a === 'DELETE') return 'warn'
  if (a === 'CREATE') return 'ok'
  if (a === 'RESTORE') return 'ok'
  return 'muted'
}

onMounted(load)
</script>

<template>
  <div class="al-page">
    <div class="al-header">
      <div>
        <h1 class="al-title">Audit Log</h1>
        <!-- ★ 2026-11-26（A-012）：加载中说 Loading…，不要显示 0 条 -->
        <p class="al-sub">{{ loading ? 'Loading…' : `${total} record(s) · newest first` }}</p>
      </div>
      <button class="al-btn" :disabled="loading" @click="load">
        {{ loading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <!-- 覆盖范围：必须显式告知，否则会被当成全局审计 -->
    <div v-if="coverage" class="al-coverage">
      <b>Coverage:</b>
      models = {{ (coverage.models || []).join(', ') || '—' }} ·
      actions = {{ (coverage.actions || []).join(' / ') }}
      <div class="al-coverage-note">{{ coverage.note }}</div>
    </div>

    <div v-if="error" class="al-alert al-alert--err">{{ error }}</div>

    <div class="al-filters">
      <select v-model="actionFilter" class="al-input" @change="load">
        <option v-for="a in ACTIONS" :key="a.value" :value="a.value">{{ a.label }}</option>
      </select>
      <!-- ★ 2026-11-26（A-165）：表里把「无操作人」显示成 system，所以这里也必须能按
           system 搜到那批 —— 后端对 username=system 特判为 `user IS NULL`。
           placeholder 明写，否则这个特值没人发现得了。 -->
      <input v-model.trim="userFilter" class="al-input al-input--sm"
             placeholder="Operator (or: system)" @keyup.enter="load" />
      <!-- ★ 2026-11-26（A-166）：Object 列是「名称 + #id」两段拼的，所以这里既能按名称、
           也能按编号搜（纯数字或 #数字 会同时精确匹配 object_id）。placeholder 把这点写明。 -->
      <input v-model.trim="search" class="al-input" placeholder="Object name or #id…" @keyup.enter="load" />
      <!-- ★ 2026-11-27（A-249 收尾）：`type=date` 换成 IsoDateInput ——
           原生分段输入会把手打的 2026-11-27 吃成 202611-02-07。
           `@change` 语义不变（归一成功才触发，且不会像原生的那样在改年份中途触发）。 -->
      <label class="al-date">
        <span>from</span>
        <IsoDateInput v-model="since" class="al-input al-input--date" aria-label="Audit log from date" @change="load" @invalid="(m) => { error = m }" />
      </label>
      <label class="al-date">
        <span>to</span>
        <IsoDateInput v-model="until" class="al-input al-input--date" aria-label="Audit log to date" @change="load" @invalid="(m) => { error = m }" />
      </label>
      <button class="al-btn al-btn--primary" :disabled="loading" @click="load">Apply</button>
    </div>

    <div class="al-table-wrap">
      <table class="al-table">
        <thead>
          <tr>
            <th>Time</th><th>Action</th><th>Object</th><th>Model</th>
            <th>Operator</th><th>Snapshot</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="r in rows" :key="r.id">
            <tr class="al-row" @click="openDetail(r)">
              <td class="al-dim">{{ fmtTime(r.timestamp) }}</td>
              <td><span class="al-badge" :class="actionClass(r.action)">{{ r.action_display || r.action }}</span></td>
              <td>
                <span class="al-obj">{{ r.object_repr || '(no name)' }}</span>
                <span class="al-oid">#{{ r.object_id }}</span>
              </td>
              <td class="al-mono">{{ r.model }}</td>
              <td>{{ r.username || 'system' }}</td>
              <td class="al-dim" :title="r.has_snapshot
                ? '有快照：点击本行展开'
                : '无快照：该记录由早期写入路径（批量脚本/旧版本）产生，未采集字段值'">
                {{ r.has_snapshot ? 'yes' : '—' }}
              </td>
            </tr>
            <!-- 内联展开快照 -->
            <tr v-if="detail && detail.id === r.id" class="al-detail-row">
              <td colspan="6">
                <div v-if="detailLoading" class="al-dim">Loading…</div>
                <div v-else class="al-snapshot">
                  <!-- ★ 2026-11-27（A-094）：快照其实有**两种**，页面文案此前一律说成
                       "变更前/后的字段值"，与实现不符 —— `AuditLog.log()` 默认只存
                       `build_snapshot(instance)`（**操作后的单一状态**），
                       只有少数路径显式传 `{before, after}`。这里按实际内容分开呈现。 -->
                  <template v-if="detail.snapshot && detail.snapshot.before && detail.snapshot.after">
                    <p class="al-snapshot-title">变更前 / 变更后</p>
                    <p class="al-dim" style="margin:2px 0 4px">Before</p>
                    <pre class="al-pre">{{ JSON.stringify(detail.snapshot.before, null, 2) }}</pre>
                    <p class="al-dim" style="margin:8px 0 4px">After</p>
                    <pre class="al-pre">{{ JSON.stringify(detail.snapshot.after, null, 2) }}</pre>
                  </template>
                  <template v-else>
                    <p class="al-snapshot-title">
                      Snapshot
                      <span class="al-dim">
                        ({{ Object.keys(detail.snapshot || {}).length }} top-level keys · 操作后状态，非前后对比)
                      </span>
                    </p>
                    <pre v-if="Object.keys(detail.snapshot || {}).length" class="al-pre">{{ JSON.stringify(detail.snapshot, null, 2) }}</pre>
                    <p v-else class="al-dim">该记录没有快照（早期写入路径未采集字段值，例如批量归档脚本）。</p>
                  </template>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="!rows.length && !loading">
            <td colspan="6" class="al-empty">No audit records match.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="al-foot">
      点击任意一行展开快照。注意两种形态：<b>「变更前 / 变更后」</b>仅部分动作记录；
      多数动作只留<b>操作后的单一状态</b>（历史批量脚本产生的记录可能完全没有快照）。
      当前只记录产品变更 —— 订单、用户、报价、邮件的操作不在审计范围内。
    </p>
  </div>
</template>

<style scoped>
.al-page { padding: 24px; max-width: 1300px; }
.al-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.al-title { font-size: 20px; font-weight: 700; margin: 0 0 4px; color: var(--color-text, #111827); }
.al-sub { font-size: 13px; color: var(--color-text-tertiary, #6b7280); margin: 0; }

.al-coverage {
  background: #f8fafc; border: 1px solid var(--color-border, #e5e7eb); border-radius: 6px;
  padding: 9px 12px; font-size: 12.5px; color: var(--color-text, #111827); margin-bottom: 12px;
}
.al-coverage-note { font-size: 11.5px; color: #92400e; margin-top: 3px; }

.al-alert { padding: 9px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 12px; }
.al-alert--err { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }

.al-filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
.al-input {
  padding: 7px 10px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  font-size: 13px; background: var(--color-bg, #fff); color: var(--color-text, #111827); min-width: 160px;
}
.al-input--sm { min-width: 120px; }
.al-input--date { min-width: 130px; }
.al-date { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--color-text-tertiary, #6b7280); }

.al-btn {
  padding: 7px 12px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  background: var(--color-bg, #fff); color: var(--color-text, #111827); font-size: 13px; cursor: pointer;
}
.al-btn--primary { background: var(--color-primary, #2563eb); border-color: var(--color-primary, #2563eb); color: #fff; }
.al-btn:disabled { opacity: .5; cursor: not-allowed; }

.al-table-wrap { border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; overflow-x: auto; }
.al-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.al-table th {
  text-align: left; font-size: 11.5px; font-weight: 600; color: var(--color-text-tertiary, #6b7280);
  padding: 9px 10px; border-bottom: 1px solid var(--color-border, #e5e7eb); white-space: nowrap;
}
.al-table td { padding: 8px 10px; border-bottom: 1px solid var(--color-border, #f3f4f6); vertical-align: top; }
.al-row { cursor: pointer; }
.al-row:hover { background: #f9fafb; }
.al-mono { font-family: ui-monospace, Menlo, monospace; }
.al-obj { color: var(--color-text, #111827); }
.al-oid { margin-left: 6px; font-size: 11px; color: var(--color-text-tertiary, #6b7280); font-family: ui-monospace, Menlo, monospace; }
.al-dim { color: var(--color-text-tertiary, #6b7280); white-space: nowrap; }
.al-empty { text-align: center; padding: 24px; color: var(--color-text-tertiary, #6b7280); }

.al-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.al-badge.ok { background: #dcfce7; color: #15803d; }
.al-badge.warn { background: #fef3c7; color: #92400e; }
.al-badge.err { background: #fee2e2; color: #b91c1c; }
.al-badge.muted { background: #f3f4f6; color: #6b7280; }

.al-detail-row td { background: #fafafa; }
.al-snapshot-title { font-size: 12px; font-weight: 600; margin: 0 0 6px; }
.al-pre {
  margin: 0; background: var(--color-bg, #fff); border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 6px; padding: 10px 12px; font-size: 11.5px; line-height: 1.55;
  max-height: 320px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere;
}
.al-foot { font-size: 12px; color: var(--color-text-tertiary, #6b7280); margin-top: 12px; line-height: 1.6; }
@media (max-width: 720px) { .al-page { padding: 16px; } }
</style>
