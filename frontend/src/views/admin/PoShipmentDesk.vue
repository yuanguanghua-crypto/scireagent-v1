<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  getOrders, getOrderDetail, createShipment, markShipped, markDelivered,
} from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const orders = ref([])
const loading = ref(false)
const selected = ref(null)
const detail = ref(null)

const shipForm = reactive({
  carrier: '',
  tracking_number: '',
  tracking_url: '',
  estimated_delivery: '',
  notes: '',
  items: [],
})
const receivedBy = ref({})

async function load() {
  loading.value = true
  try {
    const res = await getOrders({ page_size: 200 })
    const payload = res.data || res
    const all = payload.results || payload.data || payload || []
    // 多选状态：后端 filterset 为精确匹配，客户端过滤
    orders.value = all.filter((o) => ['confirmed', 'shipped', 'in_production'].includes(o.status))
  } finally {
    loading.value = false
  }
}

async function openOrder(o) {
  selected.value = o.id
  const res = await getOrderDetail(o.id)
  detail.value = res.data || res
  shipForm.items = (detail.value.items || []).map((it) => ({
    order_item_id: it.id,
    sku_code: it.sku_code,
    quantity: it.quantity,
  }))
}

async function submitShipment() {
  if (!selected.value) return
  await createShipment(selected.value, { ...shipForm })
  openOrder({ id: selected.value })
}

async function doMarkShipped(id) {
  await markShipped(id)
  if (selected.value) openOrder({ id: selected.value })
}
async function doMarkDelivered(s) {
  await markDelivered(s.id, receivedBy.value[s.id] || '')
  if (selected.value) openOrder({ id: selected.value })
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Shipment Desk</h1>
        <p class="po-page-subtitle">Create multi-batch shipments and mark shipped / delivered.</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-form-grid">
      <div class="po-card">
        <h2 class="po-section-title">Confirmed / In-Transit Orders</h2>
        <table class="po-table" v-if="orders.length">
          <thead><tr><th>Order</th><th>Status</th><th>Items</th></tr></thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id" :class="{ 'po-row-selected': selected === o.id }" @click="openOrder(o)" style="cursor:pointer">
              <td class="po-mono">{{ o.order_no }}</td>
              <td><StatusBadge :status="o.status" :label="o.status?.replace(/_/g,' ')" /></td>
              <td>{{ o.items_count }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="loading" class="po-empty">Loading…</div>
        <div v-else class="po-empty">No orders to ship.</div>
      </div>

      <div class="po-card" v-if="detail">
        <h2 class="po-section-title">Order {{ detail.order_no }}</h2>

        <!-- New shipment -->
        <h3 class="po-subsection-title">New Shipment</h3>
        <div class="po-form-grid">
          <div class="po-field"><label class="po-label">Carrier</label><input v-model="shipForm.carrier" class="po-input" /></div>
          <div class="po-field"><label class="po-label">Tracking #</label><input v-model="shipForm.tracking_number" class="po-input" /></div>
          <div class="po-field"><label class="po-label">Tracking URL</label><input v-model="shipForm.tracking_url" class="po-input" /></div>
          <div class="po-field"><label class="po-label">Est. Delivery</label><input v-model="shipForm.estimated_delivery" type="date" class="po-input" /></div>
        </div>
        <table class="po-table" style="margin-top:12px">
          <thead><tr><th>SKU</th><th>Qty to Ship</th></tr></thead>
          <tbody>
            <tr v-for="(it, i) in shipForm.items" :key="i">
              <td class="po-mono">{{ it.sku_code }}</td>
              <td><input v-model.number="it.quantity" type="number" min="0" class="po-input" style="width:100px" /></td>
            </tr>
          </tbody>
        </table>
        <button class="po-btn po-btn-accent" style="margin-top:12px" @click="submitShipment">Create Shipment</button>

        <!-- Existing shipments -->
        <h3 class="po-subsection-title" style="margin-top:24px">Shipments</h3>
        <div v-for="s in (detail.shipments || [])" :key="s.id" class="po-shipment">
          <div class="po-between">
            <div class="po-row">
              <StatusBadge :status="s.status" :label="s.status" />
              <span class="po-mono">{{ s.tracking_number || '—' }}</span>
              <span class="po-muted">{{ s.carrier }}</span>
            </div>
            <div class="po-row">
              <button v-if="s.status !== 'shipped' && s.status !== 'delivered'" class="po-btn po-btn-primary po-btn-sm" @click="doMarkShipped(s.id)">Mark Shipped</button>
              <template v-if="s.status === 'shipped'">
                <input v-model="receivedBy[s.id]" class="po-input" style="width:120px" placeholder="Received by" />
                <button class="po-btn po-btn-primary po-btn-sm" @click="doMarkDelivered(s)">Mark Delivered</button>
              </template>
            </div>
          </div>
        </div>
        <div v-if="!(detail.shipments || []).length" class="po-muted">No shipments yet.</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-row-selected { background: var(--color-primary-subtle); }
.po-shipment { border:1px solid var(--color-border-light); border-radius:4px; padding:12px; margin-top:12px; }
</style>
