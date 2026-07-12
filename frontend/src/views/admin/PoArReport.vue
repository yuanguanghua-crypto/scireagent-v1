<script setup>
import { onMounted, ref } from 'vue'
import { getArAging } from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'

const data = ref(null)
const loading = ref(false)

const BUCKETS = [
  { key: 'current', label: 'Current', color: '#22C55E' },
  { key: '30', label: '1–30 Days', color: '#F59E0B' },
  { key: '60', label: '31–60 Days', color: '#D97706' },
  { key: '90_plus', label: '90+ Days', color: '#DC2626' },
]

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
        <p class="po-page-subtitle" v-if="data">As of {{ data.as_of }}</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-card" v-if="data">
      <div class="po-ar-grid">
        <div v-for="b in BUCKETS" :key="b.key" class="po-ar-cell">
          <span class="po-ar-dot" :style="{ background: b.color }"></span>
          <span class="po-ar-label">{{ b.label }}</span>
          <span class="po-ar-count">{{ data.buckets[b.key]?.count || 0 }} invoices</span>
          <span class="po-ar-amount po-num">{{ formatCurrency(data.buckets[b.key]?.amount || 0) }}</span>
        </div>
      </div>

      <div class="po-total-row">
        <span>Total Outstanding</span>
        <span class="po-total-value">{{ formatCurrency(data.total_outstanding || 0) }}</span>
      </div>
    </div>
    <div v-else-if="loading" class="po-empty">Loading…</div>
  </div>
</template>

<style scoped>
.po-ar-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.po-ar-cell {
  border: 1px solid var(--color-border-light);
  border-radius: 4px; padding: 16px;
  display: flex; flex-direction: column; gap: 6px;
}
.po-ar-dot { width: 8px; height: 8px; border-radius: 50%; }
.po-ar-label { font-size: 13px; font-weight: 700; color: var(--color-text); }
.po-ar-count { font-size: 12px; color: var(--color-text-tertiary); }
.po-ar-amount { font-size: 18px; color: var(--color-text); }
@media (max-width: 768px) { .po-ar-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
