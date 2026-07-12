<script setup>
import { onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePoPortalStore } from '@/stores/poPortal'
import { downloadInvoicePdf, downloadPoAttachment } from '@/api/poPortal'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const route = useRoute()
const store = usePoPortalStore()
const { currentOrder: order, loading } = storeToRefs(store)

const ACTION_LABELS = {
  status_change: 'Status Change',
  rep_assigned: 'Rep Assigned',
  rejected: 'Rejected',
  noted: 'Note',
  shipment: 'Shipment',
  invoice: 'Invoice',
}

onMounted(() => store.fetchOrder(route.params.id))
onUnmounted(() => store.clearCurrent())

const timeline = computed(() => (order.value?.status_logs || []).slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)))
const shipments = computed(() => order.value?.shipments || [])
const attachments = computed(() => order.value?.attachments || [])
const invoice = computed(() => order.value?.invoice || null)

function statusTransition(log) {
  if (log.from_status && log.to_status) {
    return `${log.from_status} → ${log.to_status}`
  }
  return ACTION_LABELS[log.action_type] || log.action_type || 'Event'
}
</script>

<template>
  <div class="po-page" v-if="order">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Order {{ order.order_no }}</h1>
        <p class="po-page-subtitle">
          PO <span class="po-mono">{{ order.po_number || '—' }}</span> ·
          Placed {{ new Date(order.created_at).toLocaleDateString() }}
        </p>
      </div>
      <StatusBadge :status="order.status" :label="order.status?.replace(/_/g, ' ')" />
    </div>

    <!-- Order info -->
    <section class="po-card">
      <h2 class="po-section-title">Order Information</h2>
      <div class="po-prop-grid">
        <span class="po-prop-label">Grant Code</span><span class="po-prop-value">{{ order.grant_code || '—' }}</span>
        <span class="po-prop-label">Shipping Method</span><span class="po-prop-value">{{ order.shipping_method || '—' }}</span>
        <span class="po-prop-label">Requested Delivery</span><span class="po-prop-value">{{ order.requested_delivery_date || '—' }}</span>
        <span class="po-prop-label">ETD</span><span class="po-prop-value">{{ order.etd || '—' }}</span>
        <span class="po-prop-label">Payment Terms</span><span class="po-prop-value">{{ order.payment_terms || '—' }}</span>
        <span class="po-prop-label">Assigned Rep</span><span class="po-prop-value">{{ order.assigned_rep_id || '—' }}</span>
      </div>
    </section>

    <!-- Ship-to / Bill-to -->
    <section class="po-card">
      <h2 class="po-section-title">Addresses</h2>
      <div class="po-form-grid">
        <div>
          <p class="po-subsection-title">Ship-to</p>
          <p style="margin:0;color:var(--color-text-secondary);font-size:14px;line-height:1.6">
            <strong>{{ order.shipping_name }}</strong><br />
            {{ order.shipping_address }}<br />
            <span v-if="order.shipping_phone">{{ order.shipping_phone }} · </span>
            <span v-if="order.shipping_email">{{ order.shipping_email }}</span>
          </p>
        </div>
        <div>
          <p class="po-subsection-title">Bill-to</p>
          <p style="margin:0;color:var(--color-text-secondary);font-size:14px;line-height:1.6">
            <strong>{{ order.billing_name || '—' }}</strong><br />
            {{ order.billing_address || '—' }}
          </p>
        </div>
      </div>
    </section>

    <!-- Items -->
    <section class="po-card">
      <h2 class="po-section-title">Line Items</h2>
      <table class="po-table">
        <thead>
          <tr><th>Product</th><th>SKU</th><th>Qty</th><th>Unit Price</th><th>Subtotal</th></tr>
        </thead>
        <tbody>
          <tr v-for="it in order.items" :key="it.id">
            <td>{{ it.product_name || `Product #${it.product_id}` }}</td>
            <td class="po-mono">{{ it.sku_code || it.sku_id }}</td>
            <td>{{ it.quantity }}</td>
            <td>{{ formatCurrency(it.unit_price, order.currency) }}</td>
            <td class="po-num">{{ formatCurrency(it.subtotal || it.unit_price * it.quantity, order.currency) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="po-total-row">
        <span>Grand Total</span>
        <span class="po-total-value">{{ formatCurrency(order.grand_total, order.currency) }}</span>
      </div>
    </section>

    <!-- Invoice -->
    <section class="po-card" v-if="invoice">
      <h2 class="po-section-title">Invoice</h2>
      <div class="po-row">
        <span class="po-tag">{{ invoice.invoice_no }}</span>
        <StatusBadge :status="invoice.status" :label="invoice.status" />
        <span class="po-muted">Due {{ invoice.due_date }}</span>
        <span class="po-num">{{ formatCurrency(invoice.grand_total, invoice.currency) }}</span>
        <button class="po-btn po-btn-primary po-btn-sm" @click="downloadInvoicePdf(invoice.id)">Download PDF</button>
      </div>
    </section>

    <!-- Shipments (multi-batch) -->
    <section class="po-card" v-if="shipments.length">
      <h2 class="po-section-title">Shipments ({{ shipments.length }})</h2>
      <div v-for="s in shipments" :key="s.id" class="po-shipment">
        <div class="po-between">
          <div class="po-row">
            <StatusBadge :status="s.status" :label="s.status" />
            <span class="po-mono">{{ s.tracking_number || '—' }}</span>
          </div>
          <span class="po-muted">{{ s.carrier || '—' }}</span>
        </div>
        <div class="po-prop-grid" style="margin-top:8px">
          <span class="po-prop-label">Shipped</span><span class="po-prop-value">{{ s.shipped_at ? new Date(s.shipped_at).toLocaleString() : '—' }}</span>
          <span class="po-prop-label">Est. Delivery</span><span class="po-prop-value">{{ s.estimated_delivery || '—' }}</span>
          <span class="po-prop-label">Delivered</span><span class="po-prop-value">{{ s.delivered_at ? new Date(s.delivered_at).toLocaleString() : '—' }}</span>
          <span class="po-prop-label">Received By</span><span class="po-prop-value">{{ s.received_by || '—' }}</span>
        </div>
        <div v-if="s.tracking_url" style="margin-top:6px">
          <a :href="s.tracking_url" target="_blank" class="po-btn po-btn-outline po-btn-sm">Track Package</a>
        </div>
        <table class="po-table" v-if="s.items && s.items.length" style="margin-top:8px">
          <thead><tr><th>SKU</th><th>Qty</th></tr></thead>
          <tbody>
            <tr v-for="si in s.items" :key="si.id">
              <td class="po-mono">{{ si.sku_code }}</td>
              <td>{{ si.quantity }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- PO Attachments -->
    <section class="po-card" v-if="attachments.length">
      <h2 class="po-section-title">PO Attachments</h2>
      <div>
        <span v-for="a in attachments" :key="a.id" class="po-file-chip">
          {{ a.original_filename || `file-${a.id}` }}
          <button class="po-link-btn" @click="downloadPoAttachment(a.id)">↓</button>
        </span>
      </div>
    </section>

    <!-- Status timeline -->
    <section class="po-card">
      <h2 class="po-section-title">Status Timeline</h2>
      <div class="po-timeline">
        <div v-for="log in timeline" :key="log.id" class="po-timeline-item">
          <span class="po-timeline-dot"></span>
          <div class="po-timeline-title">{{ statusTransition(log) }}</div>
          <div class="po-timeline-time">{{ new Date(log.created_at).toLocaleString() }}</div>
          <div v-if="log.note" class="po-timeline-note">{{ log.note }}</div>
        </div>
        <div v-if="!timeline.length" class="po-muted">No timeline events yet.</div>
      </div>
    </section>
  </div>
  <div v-else-if="loading" class="po-page"><div class="po-empty">Loading…</div></div>
</template>

<style scoped>
.po-shipment {
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  padding: 16px;
  margin-bottom: 16px;
}
.po-link-btn {
  border: none; background: none; color: var(--color-primary);
  cursor: pointer; font-weight: 700; margin-left: 4px;
}
</style>
