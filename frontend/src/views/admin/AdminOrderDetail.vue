<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAdminOrder, confirmOrder, generateInvoice, shipOrder, completeOrder, enterQuote, verifyPayment } from '@/api/orders'
import { formatCurrency } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const order = ref(null)
const loading = ref(false)
const actionLoading = ref(false)
const actionError = ref('')

/* Shipping form */
const shipForm = ref({ carrier: 'FedEx', tracking_number: '' })

/* Quote form */
const quoteForm = ref({ grand_total: '', valid_until: '', notes: '' })

onMounted(async () => {
  loading.value = true
  try {
    const res = await getAdminOrder(route.params.id)
    order.value = res.data || res
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
})

const statusColors = {
  draft: '#6B7280', confirmed: '#0F766E', invoiced: '#2563EB', paid: '#059669',
  processing: '#7C3AED', shipped: '#D97706', completed: '#059669', cancelled: '#DC2626',
  quote_pending: '#7C3AED', quoted: '#7C3AED', quote_accepted: '#059669', quote_rejected: '#DC2626',
}

function getStatusLabel(s) { return s?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || s }

async function doAction(action) {
  actionLoading.value = true
  actionError.value = ''
  try {
    const id = order.value.id
    if (action === 'confirm') await confirmOrder(id)
    else if (action === 'invoice') await generateInvoice(id)
    else if (action === 'complete') await completeOrder(id)
    else if (action === 'ship') await shipOrder(id, shipForm.value)
    else if (action === 'quote') await enterQuote(id, quoteForm.value)
    // Refresh
    const res = await getAdminOrder(id)
    order.value = res.data || res
  } catch (err) {
    actionError.value = err?.data?.meta?.error?.message || err?.message || 'Action failed'
  } finally {
    actionLoading.value = false
  }
}
</script>

<template>
  <div class="admin-order-detail" v-if="order">
    <!-- Header -->
    <div class="order-header">
      <div>
        <h1 class="order-title">Order {{ order.order_no }}</h1>
        <p class="order-date">{{ new Date(order.created_at).toLocaleString() }}</p>
      </div>
      <span class="status-badge" :style="{ color: statusColors[order.status], background: statusColors[order.status] + '15' }">
        {{ getStatusLabel(order.status) }}
      </span>
    </div>

    <!-- Error -->
    <div v-if="actionError" class="error-banner">{{ actionError }}</div>

    <!-- Action buttons based on status -->
    <div class="action-bar">
      <button v-if="order.status === 'draft'" class="btn-action" :disabled="actionLoading" @click="doAction('confirm')">Confirm Order</button>

      <button v-if="order.status === 'confirmed'" class="btn-action" :disabled="actionLoading" @click="doAction('invoice')">Generate Invoice</button>

      <div v-if="order.status === 'quote_pending'" class="quote-form">
        <h3>Enter Quote</h3>
        <div class="form-row">
          <div class="form-group">
            <label>Total Price</label>
            <input v-model="quoteForm.grand_total" type="number" step="0.01" class="form-input" />
          </div>
          <div class="form-group">
            <label>Valid Until</label>
            <input v-model="quoteForm.valid_until" type="date" class="form-input" />
          </div>
        </div>
        <button class="btn-action" :disabled="actionLoading" @click="doAction('quote')">Submit Quote</button>
      </div>

      <div v-if="order.status === 'paid' || order.status === 'processing'" class="ship-form">
        <h3>Ship Order</h3>
        <div class="form-row">
          <div class="form-group">
            <label>Carrier</label>
            <select v-model="shipForm.carrier" class="form-input">
              <option>FedEx</option><option>UPS</option><option>DHL</option><option>USPS</option><option>Other</option>
            </select>
          </div>
          <div class="form-group">
            <label>Tracking Number</label>
            <input v-model="shipForm.tracking_number" class="form-input" placeholder="1234567890" />
          </div>
        </div>
        <button class="btn-action" :disabled="actionLoading" @click="doAction('ship')">Mark as Shipped</button>
      </div>

      <button v-if="order.status === 'shipped'" class="btn-action" :disabled="actionLoading" @click="doAction('complete')">Mark as Completed</button>
    </div>

    <!-- Items -->
    <section class="detail-section">
      <h2 class="section-title">Items</h2>
      <table class="items-table">
        <thead><tr><th>Product</th><th>SKU</th><th>Qty</th><th>Price</th><th>Subtotal</th></tr></thead>
        <tbody>
          <tr v-for="item in order.items" :key="item.id">
            <td>{{ item.product_name || `#${item.product_id}` }}</td>
            <td class="mono">{{ item.sku_code || item.sku_id }}</td>
            <td>{{ item.quantity }}</td>
            <td>{{ formatCurrency(item.unit_price, order.currency) }}</td>
            <td class="total-cell">{{ formatCurrency(item.subtotal || item.unit_price * item.quantity, order.currency) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="total-row">
        <span>Total</span>
        <span class="total-value">{{ formatCurrency(order.grand_total, order.currency) }}</span>
      </div>
    </section>

    <!-- Customer & Payment -->
    <div class="info-columns">
      <section class="detail-section">
        <h2 class="section-title">Customer</h2>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">User ID</span><span>{{ order.user_id }}</span></div>
          <div class="info-item"><span class="info-label">Org ID</span><span>{{ order.organization_id || '—' }}</span></div>
        </div>
      </section>
      <section class="detail-section">
        <h2 class="section-title">Payment</h2>
        <div class="info-grid">
          <div class="info-item"><span class="info-label">Method</span><span>{{ order.payment_method?.replace(/_/g, ' ') }}</span></div>
          <div class="info-item"><span class="info-label">PO #</span><span class="mono">{{ order.po_number || '—' }}</span></div>
          <div class="info-item"><span class="info-label">Terms</span><span>{{ order.payment_terms }}</span></div>
          <div class="info-item"><span class="info-label">Due Date</span><span>{{ order.payment_due_date || '—' }}</span></div>
        </div>
      </section>
    </div>

    <!-- Shipping address -->
    <section class="detail-section">
      <h2 class="section-title">Shipping Address</h2>
      <p><strong>{{ order.shipping_name }}</strong></p>
      <p>{{ order.shipping_address }}</p>
      <p v-if="order.shipping_phone">{{ order.shipping_phone }}</p>
    </section>

    <!-- Invoice -->
    <section v-if="order.invoice" class="detail-section">
      <h2 class="section-title">Invoice {{ order.invoice.invoice_no }}</h2>
      <div class="info-grid">
        <div class="info-item"><span class="info-label">Status</span><span>{{ order.invoice.status }}</span></div>
        <div class="info-item"><span class="info-label">Due</span><span>{{ order.invoice.due_date }}</span></div>
        <div class="info-item"><span class="info-label">Amount</span><span>{{ formatCurrency(order.invoice.grand_total) }}</span></div>
      </div>
    </section>

    <!-- Internal notes -->
    <section class="detail-section">
      <h2 class="section-title">Internal Notes</h2>
      <textarea v-model="order.internal_notes" class="form-textarea" rows="3" placeholder="Admin-only notes..."></textarea>
    </section>
  </div>

  <div v-else-if="loading" class="loading-state">Loading...</div>
</template>

<style scoped>
.admin-order-detail { }
.order-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.order-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.order-date { font-size: 14px; color: var(--color-text-secondary); margin: 0; }
.status-badge { display: inline-block; padding: 4px 12px; border-radius: var(--radius-full); font-size: 13px; font-weight: 600; }

.action-bar { margin-bottom: 24px; padding: 16px; background: var(--color-bg); border-radius: var(--radius-md); }
.btn-action {
  padding: 10px 20px; background: var(--color-primary); color: white; border: none;
  border-radius: var(--radius-md); font-weight: 600; cursor: pointer; font-family: var(--font-sans);
}
.btn-action:disabled { opacity: 0.6; }
.btn-action + .btn-action { margin-left: 8px; }

.quote-form, .ship-form { }
.quote-form h3, .ship-form h3 { font-size: 14px; font-weight: 600; margin: 0 0 12px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.form-input {
  height: 36px; padding: 0 10px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 13px; font-family: var(--font-sans);
}
.form-textarea { width: 100%; padding: 10px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-family: var(--font-sans); resize: vertical; }

.detail-section { margin-bottom: 20px; }
.section-title { font-size: 15px; font-weight: 700; margin: 0 0 10px; }
.items-table { width: 100%; border-collapse: collapse; }
.items-table th { text-align: left; padding: 8px; font-size: 12px; font-weight: 600; color: var(--color-text-tertiary); text-transform: uppercase; border-bottom: 1px solid var(--color-border); }
.items-table td { padding: 10px 8px; font-size: 14px; border-bottom: 1px solid var(--color-border-light); }
.mono { font-family: var(--font-mono); font-size: 13px; }
.total-cell { font-weight: 600; }
.total-row { display: flex; justify-content: space-between; padding: 12px 0; border-top: 2px solid var(--color-border); font-weight: 700; font-size: 16px; }
.total-value { color: var(--color-primary); }

.info-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.info-grid { display: flex; flex-direction: column; gap: 8px; }
.info-item { display: flex; gap: 8px; font-size: 14px; }
.info-label { font-size: 12px; font-weight: 600; color: var(--color-text-tertiary); min-width: 80px; }

.error-banner { padding: 12px; background: #FEF2F2; border: 1px solid #FCA5A5; border-radius: var(--radius-md); color: #DC2626; margin-bottom: 16px; }
.loading-state { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
</style>
