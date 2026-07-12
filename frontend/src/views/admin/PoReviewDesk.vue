<script setup>
import { onMounted, ref } from 'vue'
import { getPendingReviews, approveOrder, rejectOrder, assignRep } from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const orders = ref([])
const loading = ref(false)
const rejectReason = ref({})
const assignRepId = ref({})
const repInput = ref('')

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
      </div>
    </div>

    <div v-if="!orders.length && !loading" class="po-empty">No orders pending review.</div>
    <div v-if="loading" class="po-empty">Loading…</div>
  </div>
</template>
