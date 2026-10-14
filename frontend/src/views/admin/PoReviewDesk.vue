<script setup>
import { onMounted, ref } from 'vue'
import { getPendingReviews, approveOrder, rejectOrder, assignRep, getOrderDetail } from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const orders = ref([])
const loading = ref(false)
const rejectReason = ref({})
const assignRepId = ref({})
const repInput = ref('')

// ★ P1-1 库存匹配：展开订单时拉明细（含 sku_available），缺货行高亮
const expandedItems = ref({})
const expanded = ref({})

async function toggleItems(o) {
  if (expanded.value[o.id]) {
    expanded.value[o.id] = false
    return
  }
  expanded.value[o.id] = true
  if (!expandedItems.value[o.id]) {
    try {
      const res = await getOrderDetail(o.id)
      const d = res.data || res
      expandedItems.value[o.id] = d.items || []
    } catch {
      expandedItems.value[o.id] = []
    }
  }
}

async function load() {
  loading.value = true
  try {
    const res = await getPendingReviews()
    const payload = res.data || res
    orders.value = payload.results || payload.data || payload || []
  } finally {
    loading.value = false
  }
}

async function approve(id) {
  await approveOrder(id)
  load()
}
async function reject(id) {
  await rejectOrder(id, rejectReason.value[id] || '')
  load()
}
async function assign(id) {
  const rep = assignRepId.value[id]
  if (!rep) return
  await assignRep(id, rep)
  load()
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Order Review Desk</h1>
        <p class="po-page-subtitle">{{ orders.length }} PO(s) awaiting review</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-card" v-for="o in orders" :key="o.id">
      <div class="po-between">
        <div class="po-row">
          <span class="po-mono">{{ o.order_no }}</span>
          <StatusBadge :status="o.status" :label="o.status?.replace(/_/g,' ')" />
          <span class="po-muted" v-if="o.po_number">PO {{ o.po_number }}</span>
        </div>
        <span class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</span>
      </div>

      <div class="po-prop-grid" style="margin-top:12px">
        <span class="po-prop-label">Grant Code</span><span class="po-prop-value">{{ o.grant_code || '—' }}</span>
        <span class="po-prop-label">Shipping Method</span><span class="po-prop-value">{{ o.shipping_method || '—' }}</span>
        <span class="po-prop-label">Ship-to</span><span class="po-prop-value">{{ o.shipping_name }} — {{ o.shipping_address }}</span>
      </div>

      <div class="po-row" style="margin-top:16px">
        <button class="po-btn po-btn-primary" @click="approve(o.id)">Approve</button>
        <input v-model="rejectReason[o.id]" class="po-input" style="width:220px" placeholder="Reject reason" />
        <button class="po-btn po-btn-danger" @click="reject(o.id)">Reject</button>
        <input v-model="assignRepId[o.id]" class="po-input" style="width:100px" placeholder="Rep ID" />
        <button class="po-btn po-btn-outline" @click="assign(o.id)">Assign Rep</button>
        <button class="po-btn po-btn-outline" @click="toggleItems(o)">
          {{ expanded[o.id] ? 'Hide Items' : 'View Items' }}
        </button>
      </div>

      <div v-if="expanded[o.id]" style="margin-top:12px">
        <table class="po-table">
          <thead>
            <tr>
              <th>SKU</th><th>Pack</th><th>Qty</th><th>Available</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in (expandedItems[o.id] || [])" :key="it.id"
                :class="{ 'po-shortage': it.quantity > it.sku_available }">
              <td class="po-mono">{{ it.sku_code || '—' }}</td>
              <td>{{ it.pack_size || '—' }}</td>
              <td>{{ it.quantity }}</td>
              <td>{{ it.sku_available }}</td>
              <td>
                <span v-if="it.quantity > it.sku_available" class="po-shortage-badge">缺货 {{ it.quantity - it.sku_available }}</span>
                <span v-else class="po-muted">可满足</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="!orders.length && !loading" class="po-empty">No orders pending review.</div>
    <div v-if="loading" class="po-empty">Loading…</div>
  </div>
</template>

<style scoped>
.po-shortage td { color: #dc2626; }
.po-shortage td:first-child { border-left: 3px solid #dc2626; }
.po-shortage-badge {
  display: inline-block; padding: 1px 8px; border-radius: 4px;
  background: rgba(220, 38, 38, 0.12); color: #dc2626; font-size: 12px;
}
</style>
