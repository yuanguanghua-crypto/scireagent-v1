<script setup>
/**
 * 投递队列 —— 看 EmailOutbox 里每封信的真实状态，并能重试/丢弃。
 *
 * 为什么需要：之前 49 条 failed 只能进容器跑 shell 才看得到；
 * 而"失败原因"往往就是排障的全部线索（比如 domain not verified）。
 *
 * 两条规则：
 * - 已 sent 的不能重试（会重复打扰收件人），后端也会拒
 * - 通道不可用时后端拒绝重试（重试只会再失败一次，还可能把状态搞乱）
 */
import { onMounted, ref, computed } from 'vue'
import { getEmailOutbox, emailOutboxAction } from '@/api/system'
import { extractErrorMessage } from '@/utils/http'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const flash = ref('')
const busyId = ref(null)

const statusFilter = ref('')
const keyFilter = ref('')

const STATUSES = ['', 'pending', 'sent', 'failed']

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { limit: 200 }
    if (statusFilter.value) params.status = statusFilter.value
    if (keyFilter.value.trim()) params.template_key = keyFilter.value.trim()
    const res = await getEmailOutbox(params)
    const payload = res.data ?? res
    rows.value = Array.isArray(payload) ? payload : (payload.results || [])
    total.value = res.meta?.pagination?.count ?? rows.value.length
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load the queue.")
  } finally {
    loading.value = false
  }
}

function say(msg) {
  flash.value = msg
  window.setTimeout(() => { flash.value = '' }, 3000)
}

function fmtTime(v) {
  if (!v) return '—'
  try { return new Date(v).toLocaleString() } catch { return String(v) }
}

async function act(row, action) {
  const label = action === 'retry' ? '重试' : '丢弃（标记失败，不再重试）'
  if (!window.confirm(`对 #${row.id} 执行「${label}」？`)) return
  busyId.value = row.id
  error.value = ''
  try {
    await emailOutboxAction(row.id, action)
    say(`#${row.id} 已${action === 'retry' ? '重置为待发送' : '标记为失败'}`)
    await load()
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Action failed.")
  } finally {
    busyId.value = null
  }
}

const badgeClass = (s) => (s === 'sent' ? 'ok' : s === 'failed' ? 'err' : 'warn')

onMounted(load)
</script>

<template>
  <div class="ob-page">
    <div class="ob-header">
      <div>
        <h1 class="ob-title">Delivery Queue</h1>
        <p class="ob-sub">{{ total }} record(s) · 收件人已脱敏</p>
      </div>
      <button class="ob-btn" :disabled="loading" @click="load">
        {{ loading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <div v-if="error" class="ob-alert ob-alert--err">{{ error }}</div>
    <div v-if="flash" class="ob-alert ob-alert--ok">{{ flash }}</div>

    <div class="ob-filters">
      <select v-model="statusFilter" class="ob-input" @change="load">
        <option v-for="s in STATUSES" :key="s" :value="s">{{ s || 'All statuses' }}</option>
      </select>
      <input
        v-model.trim="keyFilter"
        class="ob-input"
        placeholder="template_key (e.g. quote_ready)"
        @keyup.enter="load"
      />
      <button class="ob-btn ob-btn--primary" :disabled="loading" @click="load">Apply</button>
    </div>

    <div class="ob-table-wrap">
      <table class="ob-table">
        <thead>
          <tr>
            <th>ID</th><th>Template</th><th>To</th><th>Subject</th>
            <th>Status</th><th>Retries</th><th>Created</th><th>Error</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td class="ob-mono">#{{ r.id }}</td>
            <td class="ob-mono ob-key">{{ r.template_key || '—' }}</td>
            <td class="ob-mono">{{ r.to_emails }}</td>
            <td class="ob-subj">{{ r.subject || '(empty)' }}</td>
            <td><span class="ob-badge" :class="badgeClass(r.status)">{{ r.status }}</span></td>
            <td class="ob-num">{{ r.retry_count }}</td>
            <td class="ob-dim">{{ fmtTime(r.created_at) }}</td>
            <td class="ob-err">{{ r.last_error || '—' }}</td>
            <td class="ob-actions">
              <button
                v-if="r.status !== 'sent'"
                class="ob-btn ob-btn--xs"
                :disabled="busyId === r.id"
                @click="act(r, 'retry')"
              >Retry</button>
              <button
                v-if="r.status === 'pending'"
                class="ob-btn ob-btn--xs"
                :disabled="busyId === r.id"
                @click="act(r, 'discard')"
              >Discard</button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="9" class="ob-empty">Queue is empty.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="ob-foot">
      已发送（sent）的记录不允许重试 —— 会重复打扰收件人。
      通道不可达时后端也会拒绝重试，避免"重试一次、失败一次"白折腾。
    </p>
  </div>
</template>

<style scoped>
.ob-page { padding: 24px; max-width: 1400px; }
.ob-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.ob-title { font-size: 20px; font-weight: 700; margin: 0 0 4px; color: var(--color-text, #111827); }
.ob-sub { font-size: 13px; color: var(--color-text-tertiary, #6b7280); margin: 0; }

.ob-alert { padding: 9px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 12px; }
.ob-alert--err { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
.ob-alert--ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d; }

.ob-filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.ob-input {
  padding: 7px 10px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  font-size: 13px; background: var(--color-bg, #fff); color: var(--color-text, #111827); min-width: 180px;
}
.ob-btn {
  padding: 7px 12px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  background: var(--color-bg, #fff); color: var(--color-text, #111827); font-size: 13px; cursor: pointer;
}
.ob-btn--primary { background: var(--color-primary, #2563eb); border-color: var(--color-primary, #2563eb); color: #fff; }
.ob-btn--xs { padding: 4px 8px; font-size: 12px; }
.ob-btn:disabled { opacity: .45; cursor: not-allowed; }

.ob-table-wrap { overflow-x: auto; border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; }
.ob-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ob-table th {
  text-align: left; font-size: 11.5px; font-weight: 600; color: var(--color-text-tertiary, #6b7280);
  padding: 9px 10px; border-bottom: 1px solid var(--color-border, #e5e7eb); white-space: nowrap;
}
.ob-table td { padding: 7px 10px; border-bottom: 1px solid var(--color-border, #f3f4f6); vertical-align: top; }
.ob-mono { font-family: ui-monospace, Menlo, monospace; }
.ob-key { max-width: 150px; overflow-wrap: anywhere; }
.ob-subj { max-width: 200px; overflow-wrap: anywhere; }
.ob-err { max-width: 260px; color: #b91c1c; overflow-wrap: anywhere; font-size: 11.5px; }
.ob-dim { color: var(--color-text-tertiary, #6b7280); white-space: nowrap; }
.ob-num { text-align: right; }
.ob-actions { display: flex; gap: 5px; white-space: nowrap; }
.ob-empty { text-align: center; padding: 24px; color: var(--color-text-tertiary, #6b7280); }

.ob-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.ob-badge.ok { background: #dcfce7; color: #15803d; }
.ob-badge.err { background: #fee2e2; color: #b91c1c; }
.ob-badge.warn { background: #fef3c7; color: #92400e; }

.ob-foot { font-size: 12px; color: var(--color-text-tertiary, #6b7280); margin-top: 12px; line-height: 1.6; }
@media (max-width: 720px) { .ob-page { padding: 16px; } }
</style>
