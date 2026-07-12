<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getOrders, getOrderDetail, issueInvoice, payInvoice } from '@/api/adminPo'
import { PAYMENT_TERMS, PAYMENT_METHODS } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const orders = ref([])
const loading = ref(false)
const selected = ref(null)
const detail = ref(null)
const terms = reactive({})
const pay = reactive({})

async function load() {
  loading.value = true
  try {
    const res = await getOrders({ page_size: 200 })
    const payload = res.data || res
    const all = payload.results || payload.data || payload || []
    orders.value = all.filter((o) => o.status === 'delivered' || o.invoice)
  } finally {
    loading.value = false
  }
}

async function openOrder(o) {
  selected.value = o.id
  const res = await getOrderDetail(o.id)
  detail.value = res.data || res
  terms[o.id] = terms[o.id] || 'NET30'
  pay[o.id] = pay[o.id] || { amount: '', method: 'wire', reference: '' }
}

async function issue(o) {
  await issueInvoice(o.id, terms[o.id])
  openOrder({ id: o.id })
}

async function doPay(invoice) {
  const p = pay[selected.value] || {}
  if (!p.amount) return
  await payInvoice(invoice.id, {
    amount: String(p.amount),
    method: p.method,
    reference: p.reference || '',
  })
  openOrder({ id: selected.value })
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Invoicing Desk</h1>
        <p class="po-page-subtitle">Issue invoices for delivered orders and record payments.</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-form-grid">
      <div class="po-card">
        <h2 class="po-section-title">Delivered / Invoiced Orders</h2>
        <table class="po-table" v-if="orders.length">
          <thead><tr><th>Order</th><th>Status</th><th>Total</th></tr></thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id" :class="{ 'po-row-selected': selected === o.id }" @click="openOrder(o)" style="cursor:pointer">
              <td class="po-mono">{{ o.order_no }}</td>
              <td><StatusBadge :status="o.status" :label="o.status?.replace(/_/g,' ')" /></td>
              <td class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="loading" class="po-empty">Loading…</div>
        <div v-else class="po-empty">No delivered orders.</div>
      </div>

      <div class="po-card" v-if="detail">
        <h2 class="po-section-title">Order {{ detail.order_no }}</h2>

        <div v-if="!detail.invoice" class="po-callout" style="margin-bottom:16px">
          Not yet invoiced.
          <div class="po-row" style="margin-top:12px">
            <select v-model="terms[selected]" class="po-select" style="width:140px">
              <option v-for="t in PAYMENT_TERMS" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <button class="po-btn po-btn-accent" @click="issue(detail)">Issue Invoice</button>
          </div>
        </div>

        <div v-else>
          <div class="po-row">
            <span class="po-tag">{{ detail.invoice.invoice_no }}</span>
            <StatusBadge :status="detail.invoice.status" :label="detail.invoice.status" />
            <span class="po-muted">Due {{ detail.invoice.due_date }}</span>
            <span class="po-num">{{ formatCurrency(detail.invoice.grand_total, detail.invoice.currency) }}</span>
          </div>

          <h3 class="po-subsection-title" style="margin-top:20px">Record Payment</h3>
          <div class="po-form-grid">
            <div class="po-field"><label class="po-label">Amount</label><input v-model="pay[selected].amount" class="po-input" placeholder="0.00" /></div>
            <div class="po-field"><label class="po-label">Method</label>
              <select v-model="pay[selected].method" class="po-select">
                <option v-for="m in PAYMENT_METHODS" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </div>
            <div class="po-field full"><label class="po-label">Reference</label><input v-model="pay[selected].reference" class="po-input" /></div>
          </div>
          <button class="po-btn po-btn-primary" style="margin-top:12px" @click="doPay(detail.invoice)">Record Payment</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-row-selected { background: var(--color-primary-subtle); }
</style>
