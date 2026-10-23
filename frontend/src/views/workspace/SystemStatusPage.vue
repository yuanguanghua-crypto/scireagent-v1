<script setup>
/**
 * 系统状态 —— 运营台"排障第一眼"。
 *
 * 为什么要有这一页：2026-10 这一个月反复出同类故障，每次都要进容器跑 shell 才知道
 *   ① EMAIL_BACKEND 悄悄变成 console（邮件只打日志，用户永远收不到）
 *   ② outbox 长期 pending / 被误标 SENT / 大量 failed
 *   ③ cron 到底在不在跑（队列空时完全看不出来）
 * 这些本该一眼可见，而不是靠人记命令。
 */
import { onMounted, ref, computed } from 'vue'
import { getSystemStatus } from '@/api/system'
import { extractErrorMessage } from '@/utils/http'

const data = ref(null)
const loading = ref(false)
const error = ref('')
const loadedAt = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await getSystemStatus()
    data.value = res.data ?? res
    loadedAt.value = new Date()
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load system status.")
  } finally {
    loading.value = false
  }
}

const email = computed(() => data.value?.email || {})
const queue = computed(() => data.value?.queue || {})
const qc = computed(() => queue.value.counts || {})
const dispatch = computed(() => data.value?.dispatch || {})
const db = computed(() => data.value?.database || {})
const counts = computed(() => data.value?.counts || {})

const emailOk = computed(() => email.value.delivery_available === true)
const dispatchStale = computed(() => dispatch.value.stale === true)

function fmtTime(v) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return String(v)
  }
}

function fmtRelative(minutes) {
  if (minutes == null) return '—'
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${Math.round(minutes)} min ago`
  const h = Math.floor(minutes / 60)
  if (h < 24) return `${h} h ago`
  return `${Math.floor(h / 24)} d ago`
}

onMounted(load)
</script>

<template>
  <div class="sys-page">
    <div class="sys-header">
      <div>
        <h1 class="sys-title">System Status</h1>
        <p class="sys-sub">
          Email pipeline, delivery queue and scheduler health
          <span v-if="loadedAt" class="sys-sub-time">· updated {{ loadedAt.toLocaleTimeString() }}</span>
        </p>
      </div>
      <button class="sys-btn" :disabled="loading" @click="load">
        {{ loading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <div v-if="error" class="sys-alert sys-alert--err">{{ error }}</div>

    <div v-if="data" class="sys-grid">
      <!-- 邮件通道 -->
      <section class="sys-card">
        <header class="sys-card-head">
          <h2>Email channel</h2>
          <span class="sys-badge" :class="emailOk ? 'ok' : 'err'">
            {{ emailOk ? 'Delivering' : 'Not delivering' }}
          </span>
        </header>
        <dl class="sys-kv">
          <dt>Provider</dt><dd>{{ email.provider }}</dd>
          <dt>Backend</dt><dd class="sys-mono sys-wrap">{{ email.backend }}</dd>
          <dt>From</dt><dd class="sys-mono">{{ email.from_email }}</dd>
        </dl>
        <p v-if="!emailOk" class="sys-hint sys-hint--err">
          当前后端不投递（console / dummy / filebased）。注册会降级放行、投递任务会空转 ——
          用户收不到任何邮件。
        </p>
      </section>

      <!-- 投递队列 -->
      <section class="sys-card">
        <header class="sys-card-head">
          <h2>Delivery queue</h2>
          <span v-if="qc.failed" class="sys-badge err">{{ qc.failed }} failed</span>
          <span v-else class="sys-badge ok">clean</span>
        </header>
        <div class="sys-stats">
          <div class="sys-stat"><b>{{ qc.pending ?? 0 }}</b><span>pending</span></div>
          <div class="sys-stat"><b>{{ qc.sent ?? 0 }}</b><span>sent</span></div>
          <div class="sys-stat"><b>{{ qc.failed ?? 0 }}</b><span>failed</span></div>
          <div class="sys-stat"><b>{{ qc.total ?? 0 }}</b><span>total</span></div>
        </div>
        <dl class="sys-kv">
          <dt>Last sent</dt><dd>{{ fmtTime(queue.last_sent_at) }}</dd>
        </dl>
        <div v-if="(queue.recent_failures || []).length" class="sys-fails">
          <p class="sys-fails-title">Recent failures</p>
          <ul>
            <li v-for="f in queue.recent_failures" :key="f.id">
              <span class="sys-mono">#{{ f.id }}</span>
              <span class="sys-fail-key">{{ f.template_key || '—' }}</span>
              <span class="sys-fail-to">{{ f.to_emails }}</span>
              <span class="sys-fail-err">{{ f.last_error || '(no message)' }}</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- 调度心跳 -->
      <section class="sys-card">
        <header class="sys-card-head">
          <h2>Scheduler heartbeat</h2>
          <span class="sys-badge" :class="dispatchStale ? 'err' : 'ok'">
            {{ dispatchStale ? 'Stale' : 'Alive' }}
          </span>
        </header>
        <dl class="sys-kv">
          <dt>Last run</dt><dd>{{ fmtTime(dispatch.last_run_at) }}</dd>
          <dt>Age</dt><dd>{{ fmtRelative(dispatch.minutes_ago) }}</dd>
          <dt>Threshold</dt><dd>{{ dispatch.stale_threshold_minutes }} min</dd>
        </dl>
        <p class="sys-hint">{{ dispatch.note }}</p>
        <p v-if="dispatchStale" class="sys-hint sys-hint--err">
          超过阈值没有心跳 ⇒ 定时任务可能已停。检查服务器 crontab 的
          <span class="sys-mono">send_outbox_emails</span> 那一行。
        </p>
      </section>

      <!-- 数据库 -->
      <section class="sys-card">
        <header class="sys-card-head">
          <h2>Database</h2>
          <span class="sys-badge" :class="db.ok ? 'ok' : 'err'">{{ db.ok ? 'Connected' : 'Down' }}</span>
        </header>
        <dl class="sys-kv">
          <dt>Vendor</dt><dd>{{ db.vendor || '—' }}</dd>
          <dt>Name</dt><dd class="sys-mono sys-wrap">{{ db.name || '—' }}</dd>
        </dl>
        <p v-if="db.error" class="sys-hint sys-hint--err">{{ db.error }}</p>
      </section>

      <!-- 数据量 -->
      <section class="sys-card sys-card--wide">
        <header class="sys-card-head"><h2>Records</h2></header>
        <div class="sys-stats">
          <div class="sys-stat"><b>{{ counts.users ?? 0 }}</b><span>users</span></div>
          <div class="sys-stat"><b>{{ counts.users_unverified ?? 0 }}</b><span>unverified</span></div>
          <div class="sys-stat"><b>{{ counts.products ?? 0 }}</b><span>products</span></div>
          <div class="sys-stat"><b>{{ counts.orders ?? 0 }}</b><span>orders</span></div>
          <div class="sys-stat"><b>{{ counts.rfq_total ?? 0 }}</b><span>RFQ total</span></div>
          <div class="sys-stat"><b>{{ counts.rfq_quoted ?? 0 }}</b><span>RFQ quoted</span></div>
        </div>
      </section>
    </div>

    <p v-else-if="loading" class="sys-empty">Loading…</p>
  </div>
</template>

<style scoped>
.sys-page { padding: 24px; max-width: 1180px; }
.sys-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.sys-title { font-size: 20px; font-weight: 700; margin: 0 0 4px; color: var(--color-text, #111827); }
.sys-sub { font-size: 13px; color: var(--color-text-tertiary, #6b7280); margin: 0; }
.sys-sub-time { opacity: .8; }
.sys-btn {
  padding: 7px 14px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  background: var(--color-bg, #fff); color: var(--color-text, #111827);
  font-size: 13px; cursor: pointer; white-space: nowrap;
}
.sys-btn:disabled { opacity: .6; cursor: not-allowed; }
.sys-alert { padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 14px; }
.sys-alert--err { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }

.sys-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
.sys-card {
  border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px;
  padding: 14px 16px; background: var(--color-bg, #fff);
  display: flex; flex-direction: column; min-width: 0;
}
.sys-card--wide { grid-column: 1 / -1; }
.sys-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.sys-card-head h2 { font-size: 14px; font-weight: 700; margin: 0; color: var(--color-text, #111827); }

.sys-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.sys-badge.ok { background: #dcfce7; color: #15803d; }
.sys-badge.err { background: #fee2e2; color: #b91c1c; }

.sys-kv { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 5px 10px; margin: 0; }
.sys-kv dt { font-size: 12px; color: var(--color-text-tertiary, #6b7280); }
.sys-kv dd { margin: 0; font-size: 12.5px; color: var(--color-text, #111827); }
.sys-mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.sys-wrap { overflow-wrap: anywhere; word-break: break-all; }

.sys-stats { display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 10px; }
.sys-stat { display: flex; flex-direction: column; }
.sys-stat b { font-size: 19px; font-weight: 700; color: var(--color-text, #111827); line-height: 1.2; }
.sys-stat span { font-size: 11px; color: var(--color-text-tertiary, #6b7280); }

.sys-hint { font-size: 12px; color: var(--color-text-tertiary, #6b7280); margin: 8px 0 0; line-height: 1.55; }
.sys-hint--err { color: #b91c1c; }

.sys-fails { margin-top: 10px; border-top: 1px dashed var(--color-border, #e5e7eb); padding-top: 8px; }
.sys-fails-title { font-size: 12px; font-weight: 600; margin: 0 0 6px; color: var(--color-text, #111827); }
.sys-fails ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.sys-fails li { display: flex; gap: 8px; font-size: 11.5px; align-items: baseline; flex-wrap: wrap; }
.sys-fail-key { color: var(--color-text, #111827); }
.sys-fail-to { color: var(--color-text-tertiary, #6b7280); }
.sys-fail-err { color: #b91c1c; overflow-wrap: anywhere; flex-basis: 100%; }

.sys-empty { font-size: 13px; color: var(--color-text-tertiary, #6b7280); padding: 20px 0; }

@media (max-width: 640px) {
  .sys-page { padding: 16px; }
  .sys-kv { grid-template-columns: 80px minmax(0, 1fr); }
}
</style>
