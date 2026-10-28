<script setup>
import { onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { respondToQuote } from '@/api/orders'
import { downloadInvoicePdf } from '@/api/poPortal'
import { statusBadgeStyle, formatStatus } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { LoadingSpinner, ErrorBanner, StatusBadge } from '@/components/common'

const route = useRoute()
const router = useRouter()
const store = useOrdersStore()

onMounted(() => store.fetchOrder(route.params.id))
onUnmounted(() => store.clearCurrent())

const order = computed(() => store.currentOrder)

// ★ 2026-10-28：状态色/文案改取 `@/config/poConstants` 单一真相源。
//   原内联表缺 `po_received`/`in_production`/`delivered`（PO 主流程全缺）⇒ 徽标无颜色；
//   底色 `statusColors[s] + '15'` 是非法 CSS（令牌是 var()，拼出来 `var(--x)15`）⇒ 恒透明。
function getStatusLabel(status) {
  return formatStatus(status)
}

/* ── 发货记录 / 状态时间线（2026-10-28 新增）────────────────────────
 * ★ 此前本页有一段 `v-if="order.shipping"` 的「Shipping」区块，但
 *   `OrderDetailSerializer` 返回的是 **`shipments` 数组**（多批次发货），
 *   从来没有 `shipping` 字段 ⇒ 该区块是**死代码，永远不渲染**。
 *   实测：GET /orders/32/ 返回 shipments 1 条（DHL / DHL-TEST-… / received_by），
 *   页面上一个字段都看不到。运营侧走完 approve→ship→deliver 后，客户全程无感。
 *   现按 shipments 数组渲染全部批次，并补 Status Timeline（status_logs 同样是
 *   接口已有数据，此前也没渲染）。
 * ★ 刻意**不用** `.status-badge` 类：state-branches-commerce.spec.cjs:554/567 用
 *   `page.locator('.status-badge')` 严格模式断言整页只有一个徽标，批次状态改用
 *   共用组件 StatusBadge（根类 `.po-badge`），互不干扰。
 */
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
  <!-- ★ D10：加载失败的持久横幅。此前失败时 `v-if="order"` 让整页空白，
       用户只会看到一个 4 秒 toast，然后以为页面坏了。 -->
  <div v-if="!order && store.error" class="order-detail-error">
    <ErrorBanner :message="store.error" kind="load" title="Couldn't load this order." />
    <router-link to="/orders" class="btn-primary">Back to orders</router-link>
  </div>

  <div class="order-detail-page" v-if="order">
    <!-- Header -->
    <div class="order-header">
      <div>
        <h1 class="order-title">Order {{ order.order_no }}</h1>
        <p class="order-date">Placed on {{ new Date(order.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) }}</p>
      </div>
      <span class="status-badge" :style="statusBadgeStyle(order.status)">
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
          <span class="info-value">{{ formatStatus(order.invoice.status) }}</span>
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
      <!-- ★ 2026-10-28：后端 `GET /invoices/<id>/pdf/` 对**下单本人**也是 200/application/pdf
           （实测 2328B），但本页一直没有下载入口，客户只能去 PO 门户（而那个页面 UI 上无入口）。 -->
      <div class="invoice-actions">
        <button class="btn-outline" @click="downloadInvoicePdf(order.invoice.id)">Download PDF</button>
      </div>
    </section>

    <!-- Shipments（多批次） -->
    <section v-if="shipments.length" class="detail-section">
      <h2 class="section-title">Shipments ({{ shipments.length }})</h2>
      <div v-for="s in shipments" :key="s.id" class="shipment-card">
        <div class="shipment-head">
          <StatusBadge :status="s.status" :label="formatStatus(s.status)" />
          <span class="mono">{{ s.tracking_number || '—' }}</span>
          <span class="shipment-carrier">{{ s.carrier || '—' }}</span>
        </div>
        <div class="info-grid shipment-meta">
          <div class="info-item">
            <span class="info-label">Shipped</span>
            <span class="info-value">{{ fmtDateTime(s.shipped_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Est. Delivery</span>
            <span class="info-value">{{ s.estimated_delivery || '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Delivered</span>
            <span class="info-value">{{ fmtDateTime(s.delivered_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Received By</span>
            <span class="info-value">{{ s.received_by || '—' }}</span>
          </div>
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
        <a v-if="s.tracking_url" :href="s.tracking_url" target="_blank" rel="noopener" class="btn-outline">
          Track Package
        </a>
      </div>
    </section>

    <!-- Status timeline -->
    <section v-if="timeline.length" class="detail-section">
      <h2 class="section-title">Status Timeline</h2>
      <ol class="timeline">
        <li v-for="log in timeline" :key="log.id" class="timeline-item">
          <span class="timeline-dot" aria-hidden="true"></span>
          <div>
            <p class="timeline-title">{{ statusTransition(log) }}</p>
            <p class="timeline-time">{{ fmtDateTime(log.created_at) }}</p>
            <p v-if="log.note" class="timeline-note">{{ log.note }}</p>
          </div>
        </li>
      </ol>
    </section>

    <!-- Notes -->
    <section v-if="order.notes" class="detail-section">
      <h2 class="section-title">Notes</h2>
      <p class="notes-text">{{ order.notes }}</p>
    </section>
  </div>

  <!-- Loading -->
  <LoadingSpinner v-else-if="store.loading" text="Loading order..." />
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

/* ── 发货批次 / 状态时间线（2026-10-28 新增） ── */
.invoice-actions { margin-top: 12px; }

.btn-outline {
  display: inline-block; padding: 8px 16px; background: white; color: var(--color-primary);
  border: 1px solid var(--color-primary); border-radius: var(--radius-md);
  font-size: 13px; font-weight: 600; font-family: var(--font-sans);
  text-decoration: none; cursor: pointer;
}
.btn-outline:hover { background: var(--color-primary-light); }

.shipment-card {
  border: 1px solid var(--color-border-light); border-radius: var(--radius-md);
  padding: 16px; margin-bottom: 12px;
}
.shipment-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.shipment-carrier { font-size: 13px; color: var(--color-text-secondary); }
.shipment-meta { margin-top: 12px; }
.shipment-items { margin-top: 12px; }
.shipment-items th, .shipment-items td { padding: 6px 12px; font-size: 13px; }

.timeline { list-style: none; margin: 0; padding: 0; }
.timeline-item {
  position: relative; display: flex; gap: 12px;
  padding: 0 0 16px 4px; margin-left: 3px;
  border-left: 1px solid var(--color-border);
}
.timeline-item:last-child { border-left-color: transparent; padding-bottom: 0; }
.timeline-dot {
  position: absolute; left: -4px; top: 4px;
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--color-primary); flex-shrink: 0;
}
.timeline-item > div { padding-left: 10px; }
.timeline-title { margin: 0; font-size: 14px; font-weight: 600; color: var(--color-text); }
.timeline-time { margin: 2px 0 0; font-size: 12px; color: var(--color-text-tertiary); }
.timeline-note { margin: 4px 0 0; font-size: 13px; color: var(--color-text-secondary); }
</style>
