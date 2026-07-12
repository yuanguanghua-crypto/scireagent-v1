<script setup>
import { onMounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { usePoPortalStore } from '@/stores/poPortal'
import { downloadInvoicePdf, downloadPoAttachment } from '@/api/poPortal'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const store = usePoPortalStore()
const { orders, loading } = storeToRefs(store)

onMounted(() => store.fetchOrders({ page_size: 100 }))

const rows = computed(() =>
  orders.value
    .map((o) => ({
      order: o,
      invoice: o.invoice || null,
      attachments: o.attachments || [],
    }))
    .filter((r) => r.invoice || r.attachments.length)
)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Download Center</h1>
        <p class="po-page-subtitle">Invoices and PO attachments for your orders.</p>
      </div>
    </div>

    <div class="po-card">
      <table class="po-table" v-if="rows.length">
        <thead>
          <tr><th>Order</th><th>Status</th><th>Invoice</th><th>PO Attachments</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.order.id">
            <td class="po-mono">{{ r.order.order_no }}</td>
            <td><StatusBadge :status="r.order.status" :label="r.order.status?.replace(/_/g,' ')" /></td>
            <td>
              <span v-if="r.invoice" class="po-tag">{{ r.invoice.invoice_no }}</span>
              <span v-else class="po-muted">—</span>
            </td>
            <td>{{ r.attachments.length || '—' }}</td>
            <td>
              <div class="po-row">
                <button
                  v-if="r.invoice"
                  class="po-btn po-btn-primary po-btn-sm"
                  @click="downloadInvoicePdf(r.invoice.id)"
                >Invoice PDF</button>
                <button
                  v-for="a in r.attachments"
                  :key="a.id"
                  class="po-btn po-btn-outline po-btn-sm"
                  @click="downloadPoAttachment(a.id, a.original_filename)"
                >PO {{ a.id }}</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="po-empty">Loading…</div>
      <div v-else class="po-empty">No downloadable documents yet.</div>
    </div>
  </div>
</template>
