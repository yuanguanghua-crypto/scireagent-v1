<script setup>
import { computed, onMounted, ref } from 'vue'
import { getArAging } from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'

const data = ref(null)
const loading = ref(false)
// ★ 2026-11-27（A-084）：之前 5 张卡片是死信息 —— 点不动、也没有任何明细，
//   运营看到「Current 1 张 $118.00」之后想催款得自己去开票台一单一单翻。
//   现在点卡片在下方展开该桶的发票明细（发票号 / 订单 / 到期日 / 逾期天数 / 金额）。
const openBucket = ref('')

const BUCKETS = [
  { key: 'current', label: 'Current', color: '#22C55E' },
  { key: '30', label: '1–30 Days', color: '#F59E0B' },
  { key: '60', label: '31–60 Days', color: '#D97706' },
  // ★ 2026-11-26（A-009）：61–90 与 90+ 拆开 —— 催收动作不同档
  { key: '90', label: '61–90 Days', color: '#B45309' },
  { key: '90_plus', label: '90+ Days', color: '#DC2626' },
]

function bucketOf(key) {
  return data.value?.buckets?.[key] || { count: 0, amount: 0, invoices: [] }
}
function toggle(key) {
  openBucket.value = openBucket.value === key ? '' : key
}
const openRows = computed(() => bucketOf(openBucket.value).invoices || [])
const openLabel = computed(
  () => BUCKETS.find((b) => b.key === openBucket.value)?.label || '',
)

async function load() {
  loading.value = true
  try {
    const res = await getArAging()
    data.value = res.data || res
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Accounts Receivable Aging</h1>
        <p class="po-page-subtitle" v-if="data">As of {{ data.as_of }} · click a bucket for the invoice list</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-card" v-if="data">
      <div class="po-ar-grid">
        <button
          v-for="b in BUCKETS" :key="b.key"
          class="po-ar-cell"
          :class="{ 'is-open': openBucket === b.key }"
          :aria-expanded="openBucket === b.key"
          data-testid="ar-bucket"
          @click="toggle(b.key)"
        >
          <span class="po-ar-dot" :style="{ background: b.color }"></span>
          <span class="po-ar-label">{{ b.label }}</span>
          <!-- A-226：原来恒写 "invoices"，1 张时显示 "1 invoices" -->
          <span class="po-ar-count">
            {{ bucketOf(b.key).count }} invoice{{ bucketOf(b.key).count === 1 ? '' : 's' }}
          </span>
          <span class="po-ar-amount po-num">{{ formatCurrency(bucketOf(b.key).amount) }}</span>
        </button>
      </div>

      <!-- A-084：分桶明细（后端 ar_aging 随桶返回，最多 200 行/桶） -->
      <div v-if="openBucket && openRows.length" class="po-ar-detail" data-testid="ar-detail">
        <h3 class="po-ar-detail-title">{{ openLabel }} — {{ openRows.length }} invoice{{ openRows.length === 1 ? '' : 's' }}</h3>
        <table class="po-table">
          <thead>
            <tr>
              <th>Invoice</th><th>Order</th><th>Due</th><th>Days overdue</th><th>Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inv in openRows" :key="inv.id">
              <td class="po-mono">{{ inv.invoice_no }}</td>
              <td>
                <router-link :to="`/ops/orders/${inv.order_id}`" class="po-link">{{ inv.order_no || `#${inv.order_id}` }}</router-link>
              </td>
              <td>{{ inv.due_date }}</td>
              <td class="po-num">{{ inv.days_overdue || 0 }}</td>
              <td class="po-num">{{ formatCurrency(inv.grand_total, inv.currency) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="bucketOf(openBucket).truncated" class="po-ar-trunc">
          …还有 {{ bucketOf(openBucket).truncated }} 张未列出（每桶最多显示 200 行）
        </p>
      </div>
      <p v-else-if="openBucket" class="po-empty">This bucket is empty.</p>

      <div class="po-total-row">
        <span>Total Outstanding</span>
        <span class="po-total-value">{{ formatCurrency(data.total_outstanding || 0) }}</span>
      </div>
    </div>
    <div v-else-if="loading" class="po-empty">Loading…</div>
  </div>
</template>

<style scoped>
/* 5 桶（A-009 加了 61–90）—— 原来写死 4 列，第 5 张必然掉到下一行 */
.po-ar-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
.po-ar-cell {
  border: 1px solid var(--color-border-light);
  border-radius: 4px; padding: 16px;
  display: flex; flex-direction: column; gap: 6px; align-items: flex-start;
  background: transparent; text-align: left; cursor: pointer;
  font: inherit; color: inherit;
}
.po-ar-cell:hover { border-color: var(--color-primary); }
.po-ar-cell.is-open { border-color: var(--color-primary); background: var(--color-primary-subtle); }
.po-ar-dot { width: 8px; height: 8px; border-radius: 50%; }
.po-ar-label { font-size: 13px; font-weight: 700; color: var(--color-text); }
.po-ar-count { font-size: 12px; color: var(--color-text-tertiary); }
.po-ar-amount { font-size: 18px; color: var(--color-text); }
.po-ar-detail { margin-top: 18px; }
.po-ar-detail-title { font-size: 14px; font-weight: 700; margin: 0 0 8px; color: var(--color-text); }
.po-ar-trunc { font-size: 12px; color: var(--color-text-tertiary); margin: 6px 0 0; }
@media (max-width: 1024px) { .po-ar-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
