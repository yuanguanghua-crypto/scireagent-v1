<script setup>
import { onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { respondToQuote } from '@/api/orders'
import { formatCurrency } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const store = useOrdersStore()

onMounted(() => store.fetchOrder(route.params.id))
onUnmounted(() => store.clearCurrent())

const order = computed(() => store.currentOrder)

const statusColors = {
  draft: '#6B7280', confirmed: '#0F766E', invoiced: '#2563EB', paid: '#059669',
  processing: '#7C3AED', shipped: '#D97706', completed: '#059669', cancelled: '#DC2626',
  quote_pending: '#7C3AED', quoted: '#7C3AED', quote_accepted: '#059669', quote_rejected: '#DC2626',
}

function getStatusLabel(status) {
  return status?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || status
}

async function handleQuoteAction(action) {
  try {
    await respondToQuote(order.value.id, action)
    store.fetchOrder(route.params.id)
  } catch (err) {
    alert(err?.data?.meta?.error?.message || 'Action failed')
  }
}
</script>

<template>
  <div class="order-detail-page" v-if="order">
    <!-- Header -->
    <div class="order-header">
      <div>
        <h1 class="order-title">Order {{ order.order_no }}</h1>
        <p class="order-date">Placed on {{ new Date(order.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) }}</p>
      </div>
      <span class="status-badge" :style="{ color: statusColors[order.status], background: statusColors[order.status] + '15' }">
        {{ getStatusLabel(order.status) }}
      </span>
    </div>

    <!-- Quote actions -->
    <div v-if="order.status === 'quoted'" class="action-bar">
      <p class="action-info">A quote has been provided for this order. Please review and respond.</p>
      <div class="action-buttons">
        <button class="btn-accept" @click="handleQuoteAction('accept')">Accept Quote</button>
        <button class="btn-reject" @click="handleQuoteAction('reject')">Reject Quote</button>
      </div>
    </div>

    <!-- Order items -->
    <section class="detail-section">
      <h2 class="section-title">Items</h2>
      <table class="items-table">
        <thead>
          <tr>
            <th>Product</th>
            <th>SKU</th>
            <th>Qty</th>
            <th>Unit Price</th>
            <th>Subtotal</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in order.items" :key="item.id">
            <td>{{ item.product_name || `Product #${item.product_id}` }}</td>
            <td class="mono">{{ item.sku_code || item.sku_id }}</td>
            <td>{{ item.quantity }}</td>
            <td>{{ formatCurrency(item.unit_price, order.currency) }}</td>
            <td class="total-cell">{{ formatCurrency(item.subtotal || item.unit_price * item.quantity, order.currency) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="order-total-row">
        <span>Total</span>
        <span class="total-value">{{ formatCurrency(order.grand_total, order.currency) }}</span>
      </div>
    </section>

    <!-- Payment info -->
    <section class="detail-section">
      <h2 class="section-title">Payment</h2>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Method</span>
          <span class="info-value">{{ order.payment_method?.replace(/_/g, ' ') }}</span>
        </div>
        <div v-if="order.po_number" class="info-item">
          <span class="info-label">PO Number</span>
          <span class="info-value mono">{{ order.po_number }}</span>
        </div>
        <div v-if="order.payment_terms" class="info-item">
          <span class="info-label">Terms</span>
          <span class="info-value">{{ order.payment_terms }}</span>
        </div>
        <div v-if="order.payment_due_date" class="info-item">
          <span class="info-label">Due Date</span>
          <span class="info-value">{{ order.payment_due_date }}</span>
        </div>
      </div>
    </section>

    <!-- Shipping info -->
    <section class="detail-section">
      <h2 class="section-title">Shipping Address</h2>
      <div class="address-block">
        <p><strong>{{ order.shipping_name }}</strong></p>
        <p>{{ order.shipping_address }}</p>
        <p v-if="order.shipping_phone">{{ order.shipping_phone }}</p>
        <p v-if="order.shipping_email">{{ order.shipping_email }}</p>
      </div>
    </section>

    <!-- Invoice -->
    <section v-if="order.invoice" class="detail-section">
      <h2 class="section-title">Invoice</h2>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Invoice #</span>
          <span class="info-value mono">{{ order.invoice.invoice_no }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Status</span>
          <span class="info-value">{{ order.invoice.status }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Due Date</span>
          <span class="info-value">{{ order.invoice.due_date }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Amount</span>
          <span class="info-value">{{ formatCurrency(order.invoice.grand_total, order.currency) }}</span>
        </div>
      </div>
    </section>

    <!-- Shipping record -->
    <section v-if="order.shipping" class="detail-section">
      <h2 class="section-title">Shipping</h2>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Carrier</span>
          <span class="info-value">{{ order.shipping.carrier }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Tracking #</span>
          <span class="info-value mono">{{ order.shipping.tracking_number }}</span>
        </div>
        <div v-if="order.shipping.shipped_at" class="info-item">
          <span class="info-label">Shipped</span>
          <span class="info-value">{{ new Date(order.shipping.shipped_at).toLocaleDateString() }}</span>
        </div>
      </div>
    </section>

    <!-- Notes -->
    <section v-if="order.notes" class="detail-section">
      <h2 class="section-title">Notes</h2>
      <p class="notes-text">{{ order.notes }}</p>
    </section>
  </div>

  <!-- Loading -->
  <div v-else-if="store.loading" class="loading-state">Loading order...</div>
</template>

<style scoped>
.order-detail-page { }
.order-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.order-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0 0 4px; }
.order-date { font-size: 14px; color: var(--color-text-secondary); margin: 0; }

.status-badge {
  display: inline-block; padding: 4px 12px; border-radius: var(--radius-full);
  font-size: 13px; font-weight: 600; text-transform: capitalize;
}

.action-bar { padding: 16px; background: var(--color-primary-light); border-radius: var(--radius-md); margin-bottom: 24px; }
.action-info { font-size: 14px; color: var(--color-text); margin: 0 0 12px; }
.action-buttons { display: flex; gap: 8px; }
.btn-accept { padding: 8px 20px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); font-weight: 600; cursor: pointer; font-family: var(--font-sans); }
.btn-reject { padding: 8px 20px; background: white; color: var(--color-danger); border: 1px solid var(--color-danger); border-radius: var(--radius-md); font-weight: 600; cursor: pointer; font-family: var(--font-sans); }

.detail-section { margin-bottom: 24px; }
.section-title { font-size: 16px; font-weight: 700; color: var(--color-text); margin: 0 0 12px; }

.items-table { width: 100%; border-collapse: collapse; }
.items-table th {
  text-align: left; padding: 8px 12px; font-size: 12px; font-weight: 600;
  color: var(--color-text-tertiary); text-transform: uppercase; border-bottom: 1px solid var(--color-border);
}
.items-table td { padding: 12px; font-size: 14px; border-bottom: 1px solid var(--color-border-light); }
.mono { font-family: var(--font-mono); font-size: 13px; }
.total-cell { font-weight: 600; font-variant-numeric: tabular-nums; }

.order-total-row {
  display: flex; justify-content: space-between; padding: 12px 0; margin-top: 8px;
  border-top: 2px solid var(--color-border); font-size: 16px; font-weight: 700;
}
.total-value { color: var(--color-primary); }

.info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.info-item { display: flex; flex-direction: column; gap: 2px; }
.info-label { font-size: 12px; font-weight: 600; color: var(--color-text-tertiary); text-transform: uppercase; }
.info-value { font-size: 14px; color: var(--color-text); }

.address-block { font-size: 14px; color: var(--color-text-secondary); line-height: 1.6; }
.address-block p { margin: 0; }
.address-block strong { color: var(--color-text); }

.notes-text { font-size: 14px; color: var(--color-text-secondary); line-height: 1.6; }

.loading-state { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
</style>
