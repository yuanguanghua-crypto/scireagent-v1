<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAdminOrder, completeOrder, enterQuote, cancelOrder } from '@/api/orders'
import {
  approveOrder, createShipment, markShipped, markDelivered,
  issueInvoice, payInvoice,
} from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'
import { LoadingSpinner } from '@/components/common'

const route = useRoute()
const router = useRouter()
const order = ref(null)
const loading = ref(false)
const actionLoading = ref(false)
const actionError = ref('')

/* Shipment form */
const shipForm = ref({ carrier: 'FedEx', tracking_number: '' })

/* Quote form */
const quoteForm = ref({ grand_total: '', valid_until: '', notes: '' })

/* Payment form */
const payForm = ref({ amount: '', method: 'wire' })

/* 可取消的态（非终态且状态机允许 → cancelled） */
const CANCELABLE = [
  'po_received', 'confirmed', 'in_production', 'shipped',
  'delivered', 'invoiced', 'quote_pending',
]

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
  po_received: 'var(--color-warning)', confirmed: 'var(--color-primary)',
  in_production: 'var(--color-info)', shipped: 'var(--color-warning)',
  delivered: 'var(--color-info)', invoiced: 'var(--color-info)',
  paid: 'var(--color-success)', completed: 'var(--color-success)', cancelled: 'var(--color-danger)',
  quote_pending: 'var(--color-warning)', quoted: 'var(--color-accent)',
  quote_accepted: 'var(--color-success)', quote_rejected: 'var(--color-danger)',
}

function getStatusLabel(s) { return s?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || s }

/* 当前未签收的发货记录（用于 Mark as Delivered） */
function activeShipment() {
  if (!order.value?.shipments?.length) return null
  return order.value.shipments.find(s => s.status !== 'delivered') || null
}

async function doAction(action) {
  actionLoading.value = true
  actionError.value = ''
  try {
    const id = order.value.id
    const o = order.value
    if (action === 'approve') {
      await approveOrder(id)
    } else if (action === 'ship') {
      // 建发货记录（含全部明细）并立即标记发货 → 订单推进 SHIPPED
      const items = (o.items || []).map(it => ({ order_item_id: it.id, quantity: it.quantity }))
      const ship = await createShipment(id, {
        carrier: shipForm.value.carrier,
        tracking_number: shipForm.value.tracking_number,
        items,
      })
      const shipId = ship?.id ?? ship?.data?.id
      if (shipId) await markShipped(shipId)
    } else if (action === 'deliver') {
      const s = activeShipment()
      if (s) await markDelivered(s.id)
    } else if (action === 'invoice') {
      await issueInvoice(id, 'NET30')
    } else if (action === 'pay') {
      const invId = o.invoice?.id
      if (!invId) throw new Error('No invoice to pay')
      await payInvoice(invId, {
        amount: payForm.value.amount || o.grand_total,
        method: payForm.value.method,
      })
    } else if (action === 'complete') {
      await completeOrder(id)
    } else if (action === 'quote') {
      await enterQuote(id, quoteForm.value)
    } else if (action === 'cancel') {
      await cancelOrder(id)
    }
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

    <!-- Action buttons based on canonical PO state machine -->
    <div class="action-bar">
      <button v-if="order.status === 'po_received'" class="btn-action" :disabled="actionLoading" @click="doAction('approve')">Approve</button>

      <div v-if="order.status === 'confirmed' || order.status === 'in_production'" class="ship-form">
        <h3>Create Shipment</h3>
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
        <button class="btn-action" :disabled="actionLoading" @click="doAction('ship')">Create &amp; Mark Shipped</button>
      </div>

      <button v-if="order.status === 'shipped'" class="btn-action" :disabled="actionLoading || !activeShipment()" @click="doAction('deliver')">Mark as Delivered</button>

      <button v-if="order.status === 'delivered'" class="btn-action" :disabled="actionLoading" @click="doAction('invoice')">Generate Invoice</button>

      <div v-if="order.status === 'invoiced'" class="pay-form">
        <h3>Record Payment</h3>
        <div class="form-row">
          <div class="form-group">
            <label>Amount</label>
            <input v-model="payForm.amount" type="number" step="0.01" class="form-input" :placeholder="String(order.grand_total)" />
          </div>
          <div class="form-group">
            <label>Method</label>
            <select v-model="payForm.method" class="form-input">
              <option value="wire">Wire Transfer</option>
              <option value="online">Online Payment</option>
              <option value="check">Check</option>
            </select>
          </div>
        </div>
        <button class="btn-action" :disabled="actionLoading" @click="doAction('pay')">Record Payment</button>
      </div>

      <button v-if="order.status === 'paid'" class="btn-action" :disabled="actionLoading" @click="doAction('complete')">Mark as Completed</button>

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

      <button v-if="CANCELABLE.includes(order.status)" class="btn-action btn-cancel" :disabled="actionLoading" @click="doAction('cancel')">Cancel Order</button>
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

  <LoadingSpinner v-else-if="loading" text="Loading..." />
</template>

<style scoped>
.admin-order-detail { }
.order-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.order-title { font-size: 22px; font-weight: 800; margin: 0 0 4px; }
.order-date { font-size: 14px; color: var(--color-text-secondary); margin: 0; }
.status-badge { display: inline-block; padding: 4px 12px; border-radius: var(--radius-full); font-size: 13px; font-weight: 600; }

.action-bar { margin-bottom: 24px; padding: 16px; background: var(--color-bg); border-radius: var(--radius-md); display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
.btn-action {
  padding: 10px 20px; background: var(--color-primary); color: white; border: none;
  border-radius: var(--radius-md); font-weight: 600; cursor: pointer; font-family: var(--font-sans);
}
.btn-action:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-cancel { background: var(--color-danger); }

.quote-form, .ship-form, .pay-form { width: 100%; }
.quote-form h3, .ship-form h3, .pay-form h3 { font-size: 14px; font-weight: 600; margin: 0 0 12px; }
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

.error-banner { padding: 12px; background: var(--color-danger-bg); border: 1px solid var(--color-danger); border-radius: var(--radius-md); color: var(--color-danger); margin-bottom: 16px; }
</style>
