<script setup>
/**
 * 缺货告警台（2026-10-28）—— 运营侧「有人想买但没货」的跟进清单。
 *
 * 为什么需要它：客户下单被缺货拦下后，**根本不会产生订单**（拦截发生在建单之前），
 * 所以运营在 Orders / Order Review 里什么也看不到。没有这张表，被拦的需求就凭空消失，
 * 既不知道谁想买、也不知道该不该补货。
 *
 * 数据来源：`GET /api/v1/inventory/shortage-alerts/`（IsProcurementOrAdmin），
 * 后端在两条下单路径（PO 提交 / 购物车结账）被拦时写入 `StockShortageAlert`。
 *
 * 运营的两条闭环路径：
 *   ① 补库存 → 点「Restock」跳库存台入库；入库后客户可正常下单
 *   ② 联系客户换产品 → 点「Contacted」，备注里写沟通结果
 */
import { onMounted, ref, computed } from 'vue'
import { getShortageAlerts, resolveShortageAlert } from '@/api/shortageAlerts'
import { extractErrorMessage } from '@/utils/http'
import { ErrorBanner, DataPagination } from '@/components/common'

const rows = ref([])
const total = ref(0)
const counts = ref({ new: 0, restocked: 0, contacted: 0, dismissed: 0 })
const loading = ref(false)
const error = ref('')
const search = ref('')
const statusFilter = ref('')
const page = ref(1)
const pageSize = ref(20)
const busyId = ref(null)
const notes = ref({})

// ★ 2026-10-28：后端 choices 的 display 名是中文（与其他模型的 verbose_name 一致），
//   但运营台 UI 全英文 ⇒ 这里做一次英文映射，不把中文漏到界面上。
const REASON_TEXT = { out_of_stock: 'SKU marked out of stock', insufficient: 'Not enough on hand' }
const SOURCE_TEXT = { po_submit: 'PO submit', checkout: 'Checkout' }
const STATUS_TEXT = { new: 'Pending', restocked: 'Restocked', contacted: 'Contacted', dismissed: 'Dismissed' }

const TABS = [
  { value: '', label: 'All', key: null },
  { value: 'new', label: 'Pending', key: 'new' },
  { value: 'restocked', label: 'Restocked', key: 'restocked' },
  { value: 'contacted', label: 'Contacted', key: 'contacted' },
  { value: 'dismissed', label: 'Dismissed', key: 'dismissed' },
]

const subtitle = computed(() => {
  if (loading.value) return 'Loading…'
  if (!total.value) return 'No shortage alerts'
  return `${total.value} shortage alert(s)`
})

function tabCount(tab) {
  return tab.key ? (counts.value[tab.key] || 0) : Object.values(counts.value).reduce((a, b) => a + b, 0)
}

async function load(opts = {}) {
  loading.value = true
  error.value = ''
  try {
    const params = {
      page: opts.page ?? page.value,
      page_size: opts.page_size ?? pageSize.value,
    }
    if (statusFilter.value) params.status = statusFilter.value
    if (search.value.trim()) params.search = search.value.trim()

    const res = await getShortageAlerts(params)
    rows.value = Array.isArray(res.data) ? res.data : (res.data?.results || [])
    const pag = res.meta?.pagination || {}
    total.value = Number(pag.count ?? rows.value.length)
    page.value = Number(pag.page ?? params.page)
    pageSize.value = Number(pag.pageSize ?? params.page_size)
    if (res.meta?.counts) counts.value = res.meta.counts
  } catch (err) {
    error.value = extractErrorMessage(err?.response?.data ?? err?.data ?? err, 'Failed to load shortage alerts.')
  } finally {
    loading.value = false
  }
}

function pickTab(tab) {
  statusFilter.value = tab.value
  load({ page: 1 })
}

function onPageChange(p) {
  load({ page: p.page, page_size: p.pageSize })
}

function onSearch() {
  load({ page: 1 })
}

async function mark(row, status) {
  busyId.value = row.id
  try {
    await resolveShortageAlert(row.id, status, notes.value[row.id] || '')
    await load()
  } catch (err) {
    error.value = extractErrorMessage(err?.response?.data ?? err?.data ?? err, 'Failed to update alert.')
  } finally {
    busyId.value = null
  }
}

function fmt(dt) {
  return dt ? new Date(dt).toLocaleString('en-US') : '—'
}

onMounted(() => load({ page: 1 }))
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Stock Shortage Alerts</h1>
        <p class="po-page-subtitle">{{ subtitle }}</p>
      </div>
      <div class="po-row">
        <input
          v-model.trim="search"
          class="po-input"
          style="width:230px"
          placeholder="SKU / product / user / email"
          aria-label="Search shortage alerts"
          @keyup.enter="onSearch"
        />
        <button class="po-btn po-btn-outline" @click="onSearch">Search</button>
        <button class="po-btn po-btn-outline" @click="load()">Refresh</button>
      </div>
    </div>

    <ErrorBanner :message="error" kind="load" title="Couldn't load shortage alerts." />

    <div class="po-row" style="margin-bottom:16px; flex-wrap:wrap">
      <button
        v-for="t in TABS"
        :key="t.value || 'all'"
        class="po-btn po-btn-sm"
        :class="statusFilter === t.value ? 'po-btn-primary' : 'po-btn-outline'"
        @click="pickTab(t)"
      >
        {{ t.label }} ({{ tabCount(t) }})
      </button>
    </div>

    <div class="po-card">
      <table class="po-table" v-if="rows.length">
        <thead>
          <tr>
            <th>Requested At</th>
            <th>Customer</th>
            <th>SKU</th>
            <th>Product</th>
            <th>Wanted</th>
            <th>Available</th>
            <th>Reason</th>
            <th>Source</th>
            <th>Status</th>
            <th>Note / Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.id">
            <td class="po-muted" style="white-space:nowrap">
              {{ fmt(r.created_at) }}
              <span v-if="r.occurrences > 1" class="po-repeat" :title="`同一用户对该 SKU 已重复尝试 ${r.occurrences} 次`">
                ×{{ r.occurrences }}
              </span>
            </td>
            <td>
              <div>{{ r.user_display }}</div>
              <div class="po-muted" style="font-size:12px">{{ r.user_email || '—' }}</div>
            </td>
            <td class="po-mono">{{ r.sku_code || '—' }}</td>
            <td>{{ r.product_name || '—' }}</td>
            <td class="po-num">{{ r.requested_quantity }}</td>
            <td class="po-num" :class="{ 'po-short': r.available_quantity < r.requested_quantity }">
              {{ r.available_quantity }}
            </td>
            <td class="po-muted">{{ REASON_TEXT[r.reason] || r.reason_label }}</td>
            <td class="po-muted">{{ SOURCE_TEXT[r.source] || r.source_label }}</td>
            <td><span class="po-state" :class="`po-state--${r.status}`">{{ STATUS_TEXT[r.status] || r.status_label }}</span></td>
            <td>
              <div class="po-row" style="gap:6px; flex-wrap:wrap; align-items:center">
                <input
                  v-model="notes[r.id]"
                  class="po-input"
                  style="width:150px"
                  :placeholder="r.note || 'Note (optional)'"
                  :aria-label="`Note for alert ${r.id}`"
                />
                <button class="po-btn po-btn-outline po-btn-sm" :disabled="busyId === r.id"
                        @click="mark(r, 'restocked')">Mark restocked</button>
                <button class="po-btn po-btn-outline po-btn-sm" :disabled="busyId === r.id"
                        @click="mark(r, 'contacted')">Mark contacted</button>
                <button v-if="r.status === 'new'" class="po-btn po-btn-outline po-btn-sm"
                        :disabled="busyId === r.id" @click="mark(r, 'dismissed')">Dismiss</button>
                <button v-else class="po-btn po-btn-outline po-btn-sm"
                        :disabled="busyId === r.id" @click="mark(r, 'new')">Reopen</button>
                <router-link to="/ops/inventory" class="po-btn po-btn-accent po-btn-sm">
                  Restock →
                </router-link>
              </div>
              <div v-if="r.note" class="po-muted" style="font-size:12px; margin-top:4px">
                {{ r.handled_by_name || 'staff' }} · {{ fmt(r.handled_at) }} — {{ r.note }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="po-empty">Loading…</div>
      <div v-else class="po-empty">No shortage alerts. Nothing is out of stock right now.</div>

      <DataPagination
        v-if="total > pageSize"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @change="onPageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.po-repeat {
  display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 4px;
  background: var(--color-warning-bg); color: var(--color-warning);
  font-size: 11px; font-weight: 700;
}
.po-short { color: var(--color-danger); font-weight: 700; }
.po-state {
  display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
}
.po-state--new { background: var(--color-warning-bg); color: var(--color-warning); }
.po-state--restocked { background: var(--color-success-bg); color: var(--color-success); }
.po-state--contacted { background: var(--color-info-bg); color: var(--color-info); }
.po-state--dismissed { background: var(--color-gray-100); color: var(--color-gray-600); }
</style>
