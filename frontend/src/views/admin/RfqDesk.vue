<script setup>
/**
 * RFQ Inbox —— 运营台「询价单收件箱」。
 *
 * 存在原因（2026-10-22）：此前客户提交的 RFQ **只有创建入口，没有任何查询入口** ——
 * 详情按 `contact_email == 当前用户邮箱` 过滤，连 staff 也 404，运营只能进 Django admin。
 * 本页对接 `GET /quote-requests/manage/`（`IsProcurementOrAdmin`）。
 *
 * ⚠️ 本页是**只读**：RFQ 的状态流转（pending→reviewing→quoted→closed）目前没有产品入口，
 *    后端也没提供状态更新端点。要改状态只能走 Django admin。这一点别在 UI 上"假装能改"。
 */
import { onMounted, ref, computed } from 'vue'
import { getQuoteRequests, getQuoteRequestDetail } from '@/api/rfq'
import { extractErrorMessage } from '@/utils/http'
import ErrorBanner from '@/components/common/ErrorBanner.vue'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

const search = ref('')
const statusFilter = ref('')

const detail = ref(null)
const detailLoading = ref(false)
const detailError = ref('')

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'reviewing', label: 'Reviewing' },
  { value: 'quoted', label: 'Quoted' },
  { value: 'closed', label: 'Closed' },
]

const subtitle = computed(() => {
  if (loading.value) return 'Loading…'
  if (!total.value) return 'No quote requests'
  return `${total.value} quote request(s)`
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page_size: 100 }
    if (search.value.trim()) params.search = search.value.trim()
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getQuoteRequests(params)
    const payload = res.data ?? res
    rows.value = Array.isArray(payload) ? payload : (payload.results || [])
    total.value = res.meta?.pagination?.count ?? rows.value.length
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load quote requests.")
  } finally {
    loading.value = false
  }
}

async function openRow(r) {
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    const res = await getQuoteRequestDetail(r.id)
    detail.value = res.data ?? res
  } catch (e) {
    detailError.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load this quote request.")
  } finally {
    detailLoading.value = false
  }
}

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString()
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">RFQ Inbox</h1>
        <p class="po-page-subtitle">{{ subtitle }} · customer quote requests (read-only)</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load" :disabled="loading">Refresh</button>
    </div>

    <ErrorBanner :message="error" title="Couldn't load quote requests" kind="load" />

    <div class="po-filter-row">
      <input
        v-model.trim="search"
        class="po-input"
        style="max-width: 280px"
        placeholder="Search name, email, company…"
        @keyup.enter="load"
      />
      <select v-model="statusFilter" class="po-input" style="max-width: 180px" @change="load">
        <option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <button class="po-btn po-btn-primary" @click="load" :disabled="loading">Apply</button>
    </div>

    <div class="rfq-grid">
      <!-- 左：列表 -->
      <div class="po-card">
        <table class="po-table" v-if="rows.length">
          <thead>
            <tr>
              <th>ID</th><th>Received</th><th>Contact</th><th>Company</th>
              <th>Country</th><th>Items</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id" :class="{ 'is-active': detail && detail.id === r.id }">
              <td class="po-mono">#{{ r.id }}</td>
              <td class="po-muted">{{ fmtDate(r.created_at) }}</td>
              <td>
                <div>{{ r.contact_name }}</div>
                <div class="po-muted po-mono">{{ r.contact_email }}</div>
              </td>
              <td>{{ r.company_name || '—' }}</td>
              <td>{{ r.country || '—' }}</td>
              <td class="po-num">{{ r.items_count }}</td>
              <td><span class="po-tag">{{ r.status }}</span></td>
              <td><button class="po-btn po-btn-outline po-btn-sm" @click="openRow(r)">View</button></td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="loading" class="po-empty">Loading…</div>
        <div v-else class="po-empty">No quote requests yet.</div>
      </div>

      <!-- 右：详情 -->
      <div class="po-card" v-if="detailLoading || detail || detailError">
        <div v-if="detailLoading" class="po-empty">Loading…</div>
        <ErrorBanner v-else-if="detailError" :message="detailError" title="Couldn't load this quote request" kind="load" />
        <template v-else-if="detail">
          <h2 class="rfq-detail-title">RFQ #{{ detail.id }}</h2>
          <dl class="rfq-detail-list">
            <dt>Contact</dt><dd>{{ detail.contact_name }}</dd>
            <dt>Email</dt><dd class="po-mono">{{ detail.contact_email }}</dd>
            <dt>Phone</dt><dd>{{ detail.contact_phone || '—' }}</dd>
            <dt>Company</dt><dd>{{ detail.company_name || '—' }}</dd>
            <dt>Country</dt><dd>{{ detail.country || '—' }}</dd>
            <dt>Status</dt><dd><span class="po-tag">{{ detail.status }}</span></dd>
            <dt>Received</dt><dd>{{ fmtDate(detail.created_at) }}</dd>
            <dt>Notes</dt><dd>{{ detail.notes || '—' }}</dd>
          </dl>

          <h3 class="rfq-items-title">Items ({{ (detail.items || []).length }})</h3>
          <table class="po-table" v-if="(detail.items || []).length">
            <thead>
              <tr><th>Product</th><th>SKU</th><th>Qty</th><th>Note</th></tr>
            </thead>
            <tbody>
              <tr v-for="it in detail.items" :key="it.id">
                <td>{{ it.product_name || `#${it.product_id}` }}</td>
                <td class="po-mono">{{ it.sku_code || '—' }}</td>
                <td class="po-num">{{ it.quantity }}</td>
                <td>{{ it.note || '—' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="po-empty">No items.</div>

          <p class="po-muted rfq-hint">
            只读：状态流转目前没有产品入口（后端未提供更新端点）。
          </p>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-filter-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.rfq-grid { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 16px; }
.po-table tbody tr.is-active { background: var(--color-bg-subtle, #f8f9fa); }
.rfq-detail-title { font-size: 16px; font-weight: 700; margin: 0 0 12px; }
.rfq-items-title { font-size: 14px; font-weight: 700; margin: 16px 0 8px; }
.rfq-detail-list { display: grid; grid-template-columns: 96px 1fr; gap: 6px 12px; margin: 0; }
.rfq-detail-list dt { color: var(--color-text-tertiary); font-size: 12px; }
.rfq-detail-list dd { margin: 0; font-size: 13px; word-break: break-word; }
.rfq-hint { font-size: 12px; margin-top: 12px; }
@media (max-width: 1024px) {
  .rfq-grid { grid-template-columns: 1fr; }
}
</style>
