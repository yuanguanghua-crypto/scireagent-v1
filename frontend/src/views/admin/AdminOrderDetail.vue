<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAdminOrder, completeOrder, enterQuote, cancelOrder } from '@/api/orders'
import {
  approveOrder, createShipment, markShipped, markDelivered,
  issueInvoice, payInvoice,
} from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'
import { extractErrorMessage } from '@/utils/http'
import { statusBadgeStyle, formatStatus } from '@/config/poConstants'
import { LoadingSpinner, ErrorBanner, StatusBadge } from '@/components/common'

const route = useRoute()
const router = useRouter()
const order = ref(null)
const loading = ref(false)
const actionLoading = ref(false)
const actionError = ref('')
// ★ 2026-10-21 修 D10：加载失败此前只 console.error ⇒ 整页空白 + 4 秒 toast
const loadError = ref('')

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
  loadError.value = ''
  try {
    const res = await getAdminOrder(route.params.id)
    order.value = res.data || res
  } catch (err) {
    console.error(err)
    loadError.value = extractErrorMessage(
      err?.response?.data ?? err?.data ?? err,
      'Failed to load this order.',
    )
  } finally {
    loading.value = false
  }
})

// ★ 2026-10-28：状态色/文案改取 `@/config/poConstants` 单一真相源。
//   原内联表 12 态（缺 `completed` 之外的 legacy 项也不一致）且底色
//   `statusColors[s] + '15'` 是非法 CSS（令牌是 var()）⇒ 底色恒透明。
function getStatusLabel(s) { return formatStatus(s) }

/* 当前未签收的发货记录（用于 Mark as Delivered） */
function activeShipment() {
  if (!order.value?.shipments?.length) return null
  return order.value.shipments.find(s => s.status !== 'delivered') || null
}

/* ★ 2026-10-28 新增：发货记录与状态时间线。
 *   `AdminOrderDetailView` 用的是 **OrderDetailSerializer**（admin_order_views.py:63），
 *   该序列化器本来就带 shipments 与 status_logs —— 数据一直在响应里，只是本页
 *   一个都没渲染。实测 /ops/orders/33 上搜不到运单号 SF-TEST-20261028-001，
 *   运营想知道"这单到底发了没、谁签收的、状态被谁改过"只能查库。
 *   ★ 批次状态刻意用 StatusBadge（根类 `.po-badge`）而不是 `.status-badge`：
 *     order-error-paths.spec.cjs:417 用 `page.locator('.status-badge')` 严格模式
 *     断言整页只有一个徽标。 */
const ACTION_LABELS = {
  status_change: 'Status Change',
  rep_assigned: 'Rep Assigned',
  rejected: 'Rejected',
  cancelled: 'Cancelled',
  noted: 'Note',
  shipment: 'Shipment',
  invoice: 'Invoice',
}

const shipments = computed(() => order.value?.shipments || [])
const timeline = computed(() =>
  (order.value?.status_logs || []).slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
)

function statusTransition(log) {
  if (log.from_status && log.to_status) return `${formatStatus(log.from_status)} → ${formatStatus(log.to_status)}`
  return ACTION_LABELS[log.action_type] || formatStatus(log.action_type) || 'Event'
}

function fmtDateTime(v) {
  return v ? new Date(v).toLocaleString('en-US') : '—'
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
  <!-- ★ D10：加载失败的持久横幅必须放在 `v-if="order"` **外面**，
       否则 order 为 null 时整块（含横幅）都不渲染（改造时踩过）。 -->
  <div v-if="!order && loadError" class="admin-order-detail-error">
    <ErrorBanner :message="loadError" kind="load" title="Couldn't load this order." />
  </div>

  <div class="admin-order-detail" v-if="order">
    <!-- Header -->
    <div class="order-header">
      <div>
        <h1 class="order-title">Order {{ order.order_no }}</h1>
        <p class="order-date">{{ new Date(order.created_at).toLocaleString() }}</p>
      </div>
      <span class="status-badge" :style="statusBadgeStyle(order.status)">
        {{ getStatusLabel(order.status) }}
      </span>
    </div>

    <!-- Error -->
    <ErrorBanner :message="actionError" kind="action" />

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

    <!-- Shipments（多批次） -->
    <section v-if="shipments.length" class="detail-section">
      <h2 class="section-title">Shipments ({{ shipments.length }})</h2>
      <div v-for="s in shipments" :key="s.id" class="shipment-card">
        <div class="shipment-head">
          <StatusBadge :status="s.status" :label="formatStatus(s.status)" />
          <span class="mono">{{ s.tracking_number || '—' }}</span>
          <span class="shipment-carrier">{{ s.carrier || '—' }}</span>
          <a v-if="s.tracking_url" :href="s.tracking_url" target="_blank" rel="noopener" class="shipment-track">Track</a>
        </div>
        <div class="shipment-meta">
          <span><b>Shipped</b> {{ fmtDateTime(s.shipped_at) }}</span>
          <span><b>Est. Delivery</b> {{ s.estimated_delivery || '—' }}</span>
          <span><b>Delivered</b> {{ fmtDateTime(s.delivered_at) }}</span>
          <span><b>Received By</b> {{ s.received_by || '—' }}</span>
        </div>
        <table v-if="s.items && s.items.length" class="items-table shipment-items">
          <thead><tr><th>SKU</th><th>Qty Shipped</th></tr></thead>
          <tbody>
            <tr v-for="si in s.items" :key="si.id">
              <td class="mono">{{ si.sku_code || si.order_item_id }}</td>
              <td>{{ si.quantity }}</td>
            </tr>
          </tbody>
        </table>
      </div>
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

    <!-- Status timeline（谁在什么时候把状态从哪改到哪） -->
    <section v-if="timeline.length" class="detail-section">
      <h2 class="section-title">Status Timeline</h2>
      <ol class="timeline">
        <li v-for="log in timeline" :key="log.id" class="timeline-item">
          <span class="timeline-dot" aria-hidden="true"></span>
          <div>
            <p class="timeline-title">{{ statusTransition(log) }}</p>
            <p class="timeline-time">
              {{ fmtDateTime(log.created_at) }}
              <span v-if="log.actor_id"> · user #{{ log.actor_id }}</span>
            </p>
            <p v-if="log.note" class="timeline-note">{{ log.note }}</p>
          </div>
        </li>
      </ol>
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

/* ── 发货批次 / 状态时间线（2026-10-28 新增） ── */
.shipment-card {
  border: 1px solid var(--color-border-light); border-radius: var(--radius-md);
  padding: 14px; margin-bottom: 12px; background: var(--color-bg);
}
.shipment-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.shipment-carrier { font-size: 13px; color: var(--color-text-secondary); }
.shipment-track { font-size: 13px; font-weight: 600; color: var(--color-primary); text-decoration: none; }
.shipment-track:hover { text-decoration: underline; }
.shipment-meta {
  display: flex; flex-wrap: wrap; gap: 6px 20px; margin-top: 10px;
  font-size: 13px; color: var(--color-text-secondary);
}
.shipment-meta b { color: var(--color-text-tertiary); font-weight: 600; margin-right: 4px; }
.shipment-items { margin-top: 10px; }
.shipment-items th, .shipment-items td { padding: 6px 8px; font-size: 13px; }

.timeline { list-style: none; margin: 0; padding: 0; }
.timeline-item {
  position: relative; display: flex; padding: 0 0 14px 4px; margin-left: 3px;
  border-left: 1px solid var(--color-border);
}
.timeline-item:last-child { border-left-color: transparent; padding-bottom: 0; }
.timeline-dot {
  position: absolute; left: -4px; top: 4px;
  width: 7px; height: 7px; border-radius: 50%; background: var(--color-primary);
}
.timeline-item > div { padding-left: 10px; }
.timeline-title { margin: 0; font-size: 14px; font-weight: 600; color: var(--color-text); }
.timeline-time { margin: 2px 0 0; font-size: 12px; color: var(--color-text-tertiary); }
.timeline-note { margin: 4px 0 0; font-size: 13px; color: var(--color-text-secondary); }

</style>
