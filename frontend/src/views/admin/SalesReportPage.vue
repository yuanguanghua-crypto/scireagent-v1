<script setup>
/**
 * 销售报表（2026-10-29）
 *
 * 口径由后端 `apps/transactions/api/v1/report_views.py` 定义，这里只负责展示。
 * 最重要的一条：**GMV ≠ 实收**。
 *   · GMV   = 区间内「下单」金额（含未付款）
 *   · 实收  = 区间内「已核验付款」金额（只看 verified）
 * 两个数字差很远是正常的，页面上必须让人一眼看出区别，否则会被当成 bug。
 */
import { computed, onMounted, ref } from 'vue'
import http from '@/utils/http'
import { formatCurrency } from '@/utils/helpers'

const data = ref(null)
const loading = ref(false)
const err = ref('')
const start = ref('')
const end = ref('')

function iso(d) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
function shift(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d
}

const PRESETS = [
  { key: 'today', label: 'Today' },
  { key: '7d', label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: 'mtd', label: 'This month' },
]

function applyPreset(key) {
  const now = new Date()
  if (key === 'today') {
    start.value = iso(now)
    end.value = iso(now)
  } else if (key === '7d') {
    start.value = iso(shift(-6))
    end.value = iso(now)
  } else if (key === '30d') {
    start.value = iso(shift(-29))
    end.value = iso(now)
  } else {
    start.value = iso(new Date(now.getFullYear(), now.getMonth(), 1))
    end.value = iso(now)
  }
  load()
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const res = await http.get('/ops/sales-report/', {
      params: { start: start.value, end: end.value },
    })
    data.value = res.data || res
  } catch (e) {
    err.value = e?.response?.data?.meta?.error?.message || e?.message || 'Failed to load'
  } finally {
    loading.value = false
  }
}

onMounted(() => { applyPreset('mtd') })

const summary = computed(() => data.value?.summary || {})
const trend = computed(() => data.value?.trend || [])
const topProducts = computed(() => data.value?.top_products || [])
const topCustomers = computed(() => data.value?.top_customers || [])
const byStatus = computed(() => data.value?.by_status || [])

/** 趋势表只渲染**有订单**的日期。
 *  后端会把区间内空白日也补成全 0（那样折线不会"跳过"某天而看起来像连续增长），
 *  但用表格呈现时，29 行里 24 行是 `—` 纯属噪音，还会把 Top 产品挤到需要滚屏。
 *  想看完整区间就调日期范围 —— 区间本身写在页头。 */
const visibleTrend = computed(() => trend.value.filter((t) => t.orders > 0))
const ccy = computed(() => summary.value.primary_currency || 'USD')

/** 趋势条形的相对宽度基准：用区间内单日最大 GMV，至少 1 防止除零。 */
const trendMax = computed(() =>
  Math.max(1, ...trend.value.map((t) => Number(t.gmv) || 0)))

/** 有订单的日期才显示条形，全 0 的日子留空（避免一屏全是空条）。 */
function barWidth(row) {
  const v = Number(row.gmv) || 0
  return v > 0 ? `${Math.max(2, Math.round((v / trendMax.value) * 100))}%` : '0'
}
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Sales Report</h1>
        <p class="po-page-subtitle" v-if="data">
          {{ data.range.start }} → {{ data.range.end }} ({{ data.range.days }} days)
        </p>
      </div>
      <div class="po-flex">
        <button v-for="p in PRESETS" :key="p.key"
                class="po-btn po-btn-outline po-btn-sm" @click="applyPreset(p.key)"
                :data-testid="'sr-preset-' + p.key">{{ p.label }}</button>
        <input v-model="start" type="date" class="po-input sr-date" @change="load" />
        <span class="po-muted">→</span>
        <input v-model="end" type="date" class="po-input sr-date" @change="load" />
        <button class="po-btn po-btn-primary po-btn-sm" @click="load" :disabled="loading">
          {{ loading ? 'Loading…' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div v-if="err" class="po-card sr-error" data-testid="sr-error">{{ err }}</div>

    <div class="sr-kpis">
      <div class="po-card sr-kpi" data-testid="sr-kpi-gmv">
        <span class="sr-kpi-label">GMV (ordered)</span>
        <span class="sr-kpi-value po-num">{{ formatCurrency(summary.gmv || 0, ccy) }}</span>
        <span class="sr-kpi-hint">all non-cancelled orders in range, paid or not</span>
      </div>
      <div class="po-card sr-kpi" data-testid="sr-kpi-orders">
        <span class="sr-kpi-label">Orders</span>
        <span class="sr-kpi-value po-num">{{ summary.order_count || 0 }}</span>
        <span class="sr-kpi-hint">same filter as GMV</span>
      </div>
      <div class="po-card sr-kpi" data-testid="sr-kpi-aov">
        <span class="sr-kpi-label">Avg order value</span>
        <span class="sr-kpi-value po-num">{{ formatCurrency(summary.avg_order_value || 0, ccy) }}</span>
        <span class="sr-kpi-hint">GMV ÷ orders</span>
      </div>
      <div class="po-card sr-kpi" data-testid="sr-kpi-paid">
        <span class="sr-kpi-label">Collected</span>
        <span class="sr-kpi-value po-num">{{ formatCurrency(summary.paid_amount || 0, ccy) }}</span>
        <span class="sr-kpi-hint">
          verified payments only · {{ summary.paid_count || 0 }} payment(s)
          <b v-if="(summary.by_currency || []).length > 1">· multi-currency</b>
        </span>
      </div>
    </div>

    <div v-if="(summary.by_currency || []).length > 1" class="po-card sr-warn">
      多币种：下面主指标只统计 <b>{{ ccy }}</b>，其余币种见
      <span v-for="c in summary.by_currency" :key="c.currency" class="sr-chip">
        {{ c.currency }} {{ c.gmv }} ({{ c.order_count }})
      </span>
    </div>

    <div class="po-card" v-if="data">
      <h2 class="sr-section">Daily trend <span class="sr-section-note">(days with orders)</span></h2>
      <table class="po-table" data-testid="sr-trend">
        <thead>
          <tr><th style="width:120px">Date</th><th>GMV</th><th style="width:110px;text-align:right">Orders</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in visibleTrend" :key="row.date" :data-testid="'sr-trend-' + row.date">
            <td class="po-mono">{{ row.date }}</td>
            <td>
              <div class="sr-bar-wrap">
                <div class="sr-bar" :style="{ width: barWidth(row) }"></div>
                <span class="sr-bar-val po-num" v-if="Number(row.gmv) > 0">
                  {{ formatCurrency(row.gmv, ccy) }}
                </span>
                <span class="po-muted" v-else>—</span>
              </div>
            </td>
            <td style="text-align:right" class="po-mono">{{ row.orders }}</td>
          </tr>
          <tr v-if="!visibleTrend.length">
            <td colspan="3" style="text-align:center" class="po-muted">No orders in this range.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="sr-two-col">
      <div class="po-card">
        <h2 class="sr-section">Top products (by amount)</h2>
        <table class="po-table" data-testid="sr-top-products">
          <thead><tr><th>Product</th><th>Catalog</th><th style="text-align:right">Qty</th><th style="text-align:right">Amount</th></tr></thead>
          <tbody>
            <tr v-for="p in topProducts" :key="p.product_id">
              <td>{{ p.name }}</td>
              <td class="po-mono">{{ p.catalog_no || '—' }}</td>
              <td style="text-align:right" class="po-mono">{{ p.quantity }}</td>
              <td style="text-align:right" class="po-num">{{ formatCurrency(p.amount, ccy) }}</td>
            </tr>
            <tr v-if="!topProducts.length"><td colspan="4" style="text-align:center" class="po-muted">No data.</td></tr>
          </tbody>
        </table>
      </div>

      <div class="po-card">
        <h2 class="sr-section">Top customers</h2>
        <table class="po-table" data-testid="sr-top-customers">
          <thead><tr><th>Customer</th><th>Organization</th><th style="text-align:right">Orders</th><th style="text-align:right">Amount</th></tr></thead>
          <tbody>
            <tr v-for="c in topCustomers" :key="c.user_id">
              <td>{{ c.username || ('user #' + c.user_id) }}</td>
              <td>{{ c.organization || '—' }}</td>
              <td style="text-align:right" class="po-mono">{{ c.orders }}</td>
              <td style="text-align:right" class="po-num">{{ formatCurrency(c.amount, ccy) }}</td>
            </tr>
            <tr v-if="!topCustomers.length"><td colspan="4" style="text-align:center" class="po-muted">No data.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="po-card" v-if="byStatus.length">
      <h2 class="sr-section">Order status breakdown</h2>
      <div class="sr-chips">
        <span v-for="s in byStatus" :key="s.status" class="sr-chip" data-testid="sr-status-chip">
          {{ s.status }} · <b>{{ s.count }}</b>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sr-date { width: 150px; }
.sr-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.sr-kpi { display: flex; flex-direction: column; gap: 4px; }
.sr-kpi-label { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--color-text-secondary); }
.sr-kpi-value { font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; }
.sr-kpi-hint { font-size: 11px; color: var(--color-text-tertiary, #6b7280); line-height: 1.4; }
.sr-section { font-size: 14px; font-weight: 700; margin: 0 0 10px; color: var(--color-text); }
.sr-section-note { font-weight: 400; font-size: 12px; color: var(--color-text-secondary); }
.sr-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 900px) { .sr-two-col { grid-template-columns: 1fr; } }
.sr-bar-wrap { display: flex; align-items: center; gap: 8px; }
.sr-bar { height: 10px; background: var(--color-primary); border-radius: 3px; min-width: 0; }
.sr-bar-val { font-size: 12px; white-space: nowrap; }
.sr-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.sr-chip {
  font-size: 12px; padding: 3px 8px; border-radius: 999px;
  background: var(--color-bg-subtle, #f3f4f6); color: var(--color-text-secondary);
}
.sr-error { border-left: 4px solid var(--color-danger, #dc2626); color: var(--color-danger, #dc2626); }
.sr-warn { border-left: 4px solid var(--color-warning, #f59e0b); font-size: 13px; }
</style>
