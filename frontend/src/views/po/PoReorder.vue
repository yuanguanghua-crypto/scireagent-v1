<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePoPortalStore } from '@/stores/poPortal'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const router = useRouter()
const store = usePoPortalStore()
const { orders, loading } = storeToRefs(store)
const selectedId = ref(null)

onMounted(() => store.fetchOrders({ status: 'completed' }))

function reorder(id) {
  router.push({ name: 'PoSubmit', query: { reorder: id } })
}
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Re-order</h1>
        <p class="po-page-subtitle">Copy line items from a completed order into a new PO.</p>
      </div>
    </div>

    <div class="po-card">
      <table class="po-table" v-if="orders.length">
        <thead>
          <tr><th>Order No</th><th>PO Number</th><th>Status</th><th>Items</th><th>Total</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id" :class="{ 'po-row-selected': selectedId === o.id }">
            <td class="po-mono">{{ o.order_no }}</td>
            <td class="po-mono">{{ o.po_number || '—' }}</td>
            <td><StatusBadge :status="o.status" :label="o.status?.replace(/_/g,' ')" /></td>
            <td>{{ o.items_count }}</td>
            <td class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</td>
            <td><button class="po-btn po-btn-accent po-btn-sm" @click="reorder(o.id)">Re-order</button></td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="po-empty">Loading…</div>
      <div v-else class="po-empty">No completed orders available to re-order.</div>
    </div>
  </div>
</template>

<style scoped>
.po-row-selected { background: var(--color-primary-subtle); }
</style>
