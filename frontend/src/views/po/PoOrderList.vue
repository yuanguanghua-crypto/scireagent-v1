<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePoPortalStore } from '@/stores/poPortal'
import { ORDER_STATUS_FILTERS, formatStatus } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const router = useRouter()
const store = usePoPortalStore()
const { orders, total, loading } = storeToRefs(store)
const statusFilter = ref('')

async function load() {
  await store.fetchOrders(statusFilter.value ? { status: statusFilter.value } : {})
}

onMounted(load)
watch(statusFilter, load)

function goDetail(id) {
  router.push({ name: 'PoOrderDetail', params: { id } })
}
function reorder(id) {
  router.push({ name: 'PoSubmit', query: { reorder: id } })
}
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">My Purchase Orders</h1>
        <p class="po-page-subtitle">{{ total }} order(s)</p>
      </div>
      <div class="po-row">
        <select v-model="statusFilter" class="po-select" style="width:180px">
          <option v-for="f in ORDER_STATUS_FILTERS" :key="f.value" :value="f.value">{{ f.label }}</option>
        </select>
        <router-link :to="{ name: 'PoSubmit' }" class="po-btn po-btn-accent">+ New PO</router-link>
      </div>
    </div>

    <div class="po-card">
      <table class="po-table" v-if="orders.length">
        <thead>
          <tr>
            <th>Order No</th>
            <th>PO Number</th>
            <th>Status</th>
            <th>Items</th>
            <th>Total</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id">
            <td class="po-mono">{{ o.order_no }}</td>
            <td class="po-mono">{{ o.po_number || '—' }}</td>
            <td><StatusBadge :status="o.status" :label="formatStatus(o.status)" /></td>
            <td>{{ o.items_count }}</td>
            <td class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</td>
            <td class="po-muted">{{ new Date(o.created_at).toLocaleDateString() }}</td>
            <td>
              <div class="po-row">
                <button class="po-btn po-btn-outline po-btn-sm" @click="goDetail(o.id)">View</button>
                <button class="po-btn po-btn-outline po-btn-sm" @click="reorder(o.id)">Re-order</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="po-empty">Loading…</div>
      <div v-else class="po-empty">No purchase orders found.</div>
    </div>
  </div>
</template>
