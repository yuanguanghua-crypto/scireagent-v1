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
import { computed, onMounted, ref, watch } from 'vue'
import http from '@/utils/http'
import { getAdminOrders } from '@/api/orders'
import { formatCurrency } from '@/utils/helpers'
import { extractErrorMessage } from '@/utils/http'
import { StatusBadge } from '@/components/common'
import IsoDateInput from '@/components/common/IsoDateInput.vue'

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
  // ★ 2026-11-27（A-163）：原来只有 today/7d/30d/mtd，想看"全部历史"只能手填起点。
  //   起点用 2000-01-01 而不是查"最早订单日"：后端对区间只做过滤、不做拒绝，
  //   趋势图另有 `MAX_TREND_DAYS=400` 兜底（report_views.py:58），不会被拖垮。
  //   代价是 `data.range.days` 会是个大数（~9800），所以下面对 ALL_TIME_START
  //   单独显示成 "All time"，不把那个天文数字摆给用户看。
  { key: 'all', label: 'All time' },
]

/**
 * 「全部历史」用**后端的 `?all=1` 开关**，不是塞一个很早的 start。
 *
 * ⚠️ 我第一版就是塞 start=2000-01-01，实测被后端 400 打回：
 *    `RANGE_TOO_LARGE`（区间最多 400 天，`report_views.py:131` 有硬守卫，
 *    且 `test_sales_report.py::test_rejects_absurdly_long_range` 专门钉着）。
 *    两者语义不同：那个守卫说的是"区间太长，请缩小"；这里要的是"我要全部"。
 */
const allTime = ref(false)

function applyPreset(key) {
  const now = new Date()
  // 任何 preset 都先退出"全部历史"模式
  allTime.value = key === 'all'
  if (key === 'all') {
    end.value = iso(now)
    load()
    return
  }
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
  // ★ 2026-11-27（S6 A-248）：日期不完整时不发请求。
  //   `<input type="date" @change="load">` 在用户**改年份/手输**的过程中会触发 change，
  //   此时值可能是空串或只改了一半 ⇒ 原来直接打后端，拿回 400 后把后端那句
  //   技术性错误当成"异常提示"显示给运营。
  //   现在：空 ⇒ 静默不发（不发就不会有错）；起止倒置 ⇒ 给一句人话。
  const s0 = (start.value || '').trim()
  const e0 = (end.value || '').trim()
  // A-163：全部历史模式不依赖 start/end，跳过这两条守卫（否则会被"空值静默不发"卡住）
  if (!allTime.value) {
    if (!s0 || !e0) {
      err.value = ''
      loading.value = false
      return
    }
    if (s0 > e0) {
      err.value = '开始日期不能晚于结束日期'
      loading.value = false
      return
    }
  }

  loading.value = true
  err.value = ''
  try {
    const res = await http.get('/ops/sales-report/', {
      params: allTime.value ? { all: 1 } : { start: s0, end: e0 },
    })
    data.value = res.data || res
    // A-163：全部历史时把"真实区间"回填到日期框 —— 否则框里还停在上一次的
    // 30 天区间，而数字是全量，两者对不上会让人怀疑报表。
    if (data.value?.range?.all_time) {
      start.value = data.value.range.start
      end.value = data.value.range.end
    }
    loadDetails()
  } catch (e) {
    err.value = e?.response?.data?.meta?.error?.message || e?.message || 'Failed to load'
  } finally {
    loading.value = false
  }
}

// ★ 2026-11-27（S6 A-229）：默认范围由「本月」改为「最近 30 天」。
//   「本月」在月初只有几天数据，运营打开会以为业绩断崖；30 天滚动窗口对"最近表现"更直观。
//   若确实需要"本月"口径，改回 'mtd' 即可（一行）。
onMounted(() => { applyPreset('30d') })

/** 手改日期即退出"全部历史"模式（否则框里是新日期、请求却仍走 all=1）。 */
function onManualDateChange() {
  allTime.value = false
  load()
}

const summary = computed(() => data.value?.summary || {})
const trend = computed(() => data.value?.trend || [])
const topProducts = computed(() => data.value?.top_products || [])
const topCustomers = computed(() => data.value?.top_customers || [])
const byStatus = computed(() => data.value?.by_status || [])

/* ── A-162：区间订单明细 + 产品搜索 ───────────────────────────────
 * 报表此前只有聚合（KPI / 趋势 / Top N），运营问"这个试剂这个月卖给谁了"
 * 只能切到 Order Management 手筛日期。这里补一张区间明细，并按**产品名/货号**
 * 可搜（后端 `?search=` 已扩到 items.product 维度，见 views.py）。
 * ⚠️ 只取前 50 条：报表页不是订单管理台，全量翻页交给 /ops/orders。
 */
const DETAIL_LIMIT = 50
const detailRows = ref([])
const detailTotal = ref(0)
const detailLoading = ref(false)
const detailErr = ref('')
const productSearch = ref('')
let detailTimer = null

async function loadDetails() {
  const r = data.value?.range
  if (!r) return
  detailLoading.value = true
  detailErr.value = ''
  try {
    const res = await getAdminOrders({
      created_from: r.start,
      created_to: r.end,
      page: 1,
      page_size: DETAIL_LIMIT,
      ...(productSearch.value.trim() ? { search: productSearch.value.trim() } : {}),
    })
    const payload = res && res.data !== undefined ? res.data : res
    detailRows.value = Array.isArray(payload) ? payload : (payload?.results || [])
    detailTotal.value = Number(res?.meta?.pagination?.count ?? detailRows.value.length)
  } catch (e) {
    detailErr.value = extractErrorMessage(e?.response?.data ?? e, 'Could not load order rows.')
    detailRows.value = []
    detailTotal.value = 0
  } finally {
    detailLoading.value = false
  }
}

// 搜索防抖：逐字发请求会让"谁后到谁生效"决定表格内容（A-141 同款坑）
watch(productSearch, () => {
  if (detailTimer) clearTimeout(detailTimer)
  detailTimer = setTimeout(loadDetails, 300)
})

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
          <!-- A-163：全部历史由后端 `range.all_time` 判定，起点是"最早订单日"而非固定日期 -->
          <template v-if="data.range.all_time">
            All time (since {{ data.range.start }}) → {{ data.range.end }}
            · {{ data.range.days }} days
            <span v-if="data.range.trend_truncated" class="po-muted">
              · daily trend shows the last {{ 400 }} days only (totals cover the full range)
            </span>
          </template>
          <template v-else>
            {{ data.range.start }} → {{ data.range.end }} ({{ data.range.days }} days)
          </template>
        </p>
      </div>
      <div class="po-flex">
        <button v-for="p in PRESETS" :key="p.key"
                class="po-btn po-btn-outline po-btn-sm" @click="applyPreset(p.key)"
                :data-testid="'sr-preset-' + p.key">{{ p.label }}</button>
        <!-- ★ 2026-11-27（A-249 收尾）：换成 IsoDateInput。
             原 `type=date` 手打 YYYY-MM-DD 会被浏览器分段吃成脏值；
             新组件的 `@change` 只在归一成功后触发 ⇒ A-248 那个
             "改年份中途触发请求打回 400" 的根源直接消失（守卫仍保留作双保险）。 -->
        <IsoDateInput v-model="start" class="po-input sr-date" data-testid="sr-start" aria-label="Report start date" @change="onManualDateChange" @invalid="(m) => { err = m }" />
        <span class="po-muted">→</span>
        <IsoDateInput v-model="end" class="po-input sr-date" data-testid="sr-end" aria-label="Report end date" @change="onManualDateChange" @invalid="(m) => { err = m }" />
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

    <!-- ★ 2026-11-27（A-162）：区间订单明细 + 产品搜索。
         报表原来只有聚合，运营问"这个试剂这段时间卖给了谁"只能切到订单管理手筛。
         这里按当前区间列出订单，并可按产品名/货号搜。只取前 50 条 ——
         报表页不是订单台，全量翻页仍去 /ops/orders。 -->
    <div class="po-card" data-testid="sr-order-rows">
      <div class="po-between" style="align-items:flex-end;gap:12px;flex-wrap:wrap">
        <h2 class="sr-section" style="margin:0">
          Orders in this range
          <span class="po-muted" data-testid="sr-order-rows-total">({{ detailTotal }})</span>
          <!-- ★ 实测同一页 KPI 66 vs 明细 300 —— 因为 KPI 只算 SALES_STATUSES
               （不含 cancelled/draft 等），明细列的是区间内**全部状态**。
               不写清楚就又是一个"计数自相矛盾"（A-110 / A-138 同族）。 -->
          <span class="po-muted" style="font-size:12px;font-weight:400">· all statuses (GMV counts sales statuses only)</span>
        </h2>
        <input
          v-model="productSearch"
          class="po-input"
          style="width:260px"
          type="search"
          placeholder="Search product name / catalog no. / order no."
          aria-label="Search order rows by product or order number"
        />
      </div>

      <p v-if="detailErr" class="sr-error-plain" data-testid="sr-order-rows-error">{{ detailErr }}</p>
      <p v-if="detailTotal > detailRows.length" class="po-dl-warn" style="margin-top:10px">
        Showing the first {{ detailRows.length }} of {{ detailTotal }} orders —
        open <router-link :to="{ name: 'AdminOrders' }" style="color:var(--color-primary)">Order Management</router-link>
        for the complete list.
      </p>

      <table class="po-table" v-if="detailRows.length" style="margin-top:10px">
        <thead>
          <tr><th>Order</th><th>Customer</th><th>Status</th><th style="text-align:right">Total</th><th>Created</th></tr>
        </thead>
        <tbody>
          <tr v-for="o in detailRows" :key="o.id">
            <td class="po-mono">{{ o.order_no }}</td>
            <td>
              {{ o.customer_name || o.user_name || ('user #' + (o.user_id ?? o.user)) }}
              <span v-if="o.organization_name" class="po-muted">· {{ o.organization_name }}</span>
            </td>
            <td><StatusBadge :status="o.status" /></td>
            <td style="text-align:right" class="po-num">{{ formatCurrency(o.grand_total, o.currency || ccy) }}</td>
            <td class="po-muted">{{ new Date(o.created_at).toLocaleDateString() }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="detailLoading" class="po-empty">Loading…</div>
      <div v-else class="po-empty" data-testid="sr-order-rows-empty">
        No orders in this range{{ productSearch.trim() ? ' match that search' : '' }}.
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
.sr-error-plain { color: var(--color-danger, #dc2626); font-size: 13px; margin: 10px 0 0; }
.sr-warn { border-left: 4px solid var(--color-warning, #f59e0b); font-size: 13px; }
</style>
