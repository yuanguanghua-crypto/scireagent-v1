<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getOrderDetail, issueInvoice, payInvoice } from '@/api/adminPo'
import { fetchOrderQueue } from '@/composables/useOrderQueue'
import { PAYMENT_TERMS, PAYMENT_METHODS } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'
import { verifyPayment } from '@/api/orders'
import { useConfirm } from '@/composables/useConfirm'
import { extractErrorMessage } from '@/utils/http'

const { askText } = useConfirm()

const orders = ref([])
const loading = ref(false)
const selected = ref(null)
const detail = ref(null)
const terms = reactive({})
const pay = reactive({})
// A-099：记账请求进行中 / 成功提示 / 失败提示
const paying = ref(false)
const payError = ref('')
const payInfo = ref('')

/**
 * 队列取数状态（★ S5 P-2，与 Shipment Desk 同构）。
 *
 * 原实现 `getOrders({page_size:200})` 拉一页再客户端筛 ⇒ 越过 200 单后被挤出的
 * delivered/invoiced 订单**永远进不了开票队列**，且页面不提示。
 * 现走服务端 `status__in` + 翻页取全，并显式显示队列总数。
 */
const QUEUE_STATUSES = ['delivered', 'invoiced']
const queueTotal = ref(0)
const queueTruncated = ref(false)
const queueError = ref('')

async function load() {
  loading.value = true
  queueError.value = ''
  try {
    // ★ 2026-10-21 修 D3（P1）保留其结论：队列**只看状态**，不看 `o.invoice`
    //   （`OrderListSerializer` 不含 `invoice`，旧判据恒假）。
    //   delivered ⇒ 待开票；invoiced ⇒ 已开票待收款（部分付款仍停在此态，必须留队列）；
    //   paid/completed/cancelled ⇒ 已结清/已终结，离开队列。
    //   回归：`frontend/e2e/po-invoicing-queue.spec.cjs`（正+反两条断言）。
    const { orders: rows, total, truncated } = await fetchOrderQueue(QUEUE_STATUSES)
    orders.value = rows
    queueTotal.value = total
    queueTruncated.value = truncated
  } catch (e) {
    // 取数失败必须落在页面上，否则空表会被读成"没有待开票订单"
    queueError.value = extractErrorMessage(
      e?.response?.data ?? e, 'Could not load the invoicing queue.')
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
  if (!p.amount || paying.value) return
  // ★ 2026-11-27（A-099）：三个缺陷一起修（QA 实测：记完账表单原样保留、
  //   按钮仍可点，发票已是 Paid 却没有拦截）：
  //   ① 没有 in-flight 标志 ⇒ 手快能连点两次，前端完全不挡；
  //   ② 成功后不清表单 ⇒ 同一个金额停在输入框里，下次误点就是重复入账；
  //   ③ 失败时异步异常直接冒泡，运营看不到任何提示。
  paying.value = true
  payError.value = ''
  try {
    await payInvoice(invoice.id, {
      amount: String(p.amount),
      method: p.method,
      reference: p.reference || '',
    })
    // 清表单（保留 method 的默认值，避免下次还要重新选）
    pay[selected.value] = { amount: '', method: p.method || 'wire', reference: '' }
    payInfo.value = `Recorded ${p.amount} ${invoice.currency || ''} for ${invoice.invoice_no}`.trim()
    await openOrder({ id: selected.value })   // 重新拉详情：余额/状态/付款明细都会变
  } catch (e) {
    payError.value = extractErrorMessage(e?.response?.data ?? e, 'Could not record this payment.')
  } finally {
    paying.value = false
  }
}

/* ── 客户上传的待核验凭证（2026-10-29）────────────────── */
const pendingPayments = computed(() =>
  (detail.value?.invoice?.payments || []).filter((p) => p.status === 'pending'))

async function doVerify(p, action) {
  let notes = ''
  if (action === 'reject') {
    // ★ 2026-11-18（S4）：`window.prompt` → 页内 `askText`。
    //   原写法 `window.prompt(...) || ''` 把**取消**（null）和**留空确认**（''）
    //   压成同一个空串 ⇒ 点取消也会把凭证判为 rejected。现在两者分开：
    //   取消 ⇒ 不发请求；确认且留空 ⇒ 照常拒绝，只是没有备注。
    const reason = await askText({
      title: 'Reject this payment proof',
      message: 'Why is this proof rejected?\n'
        + 'A reason is optional, but the customer-side record keeps it for later disputes.',
      placeholder: 'Optional reason…',
      confirmText: 'Reject proof',
      danger: true,
    })
    if (reason === null) return
    notes = reason
  }
  await verifyPayment(detail.value.invoice.id, {
    payment_id: p.id, action, notes,
  })
  await openOrder({ id: selected.value })
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
        <h2 class="po-section-title">
          Delivered / Invoiced Orders
          <span class="po-muted" data-testid="queue-total">({{ queueTotal }})</span>
        </h2>
        <p v-if="queueError" class="po-queue-error" data-testid="queue-error">{{ queueError }}</p>
        <p v-if="queueTruncated" class="po-queue-warn" data-testid="queue-truncated">
          Showing the first {{ orders.length }} of {{ queueTotal }} orders — the queue exceeds
          the page cap, so the rest is not listed here.
        </p>
        <table class="po-table" v-if="orders.length">
          <thead><tr><th>Order</th><th>Status</th><th>Total</th></tr></thead>
          <tbody>
            <tr v-for="o in orders" :key="o.id" :class="{ 'po-row-selected': selected === o.id }" @click="openOrder(o)" style="cursor:pointer">
              <td class="po-mono">{{ o.order_no }}</td>
              <td><StatusBadge :status="o.status" /></td>
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
            <StatusBadge :status="detail.invoice.status" />
            <span class="po-muted">Due {{ detail.invoice.due_date }}</span>
            <span class="po-num">{{ formatCurrency(detail.invoice.grand_total, detail.invoice.currency) }}</span>
          </div>

          <!-- ★ 2026-10-29：客户上传的电汇凭证。没这个区块，客户传了运营也不知道。 -->
          <div v-if="pendingPayments.length" class="proof-box" data-testid="pending-proofs">
            <strong>{{ pendingPayments.length }} payment proof(s) awaiting verification</strong>
            <div v-for="p in pendingPayments" :key="p.id" class="proof-line">
              <span class="po-num">{{ formatCurrency(p.amount, p.currency) }}</span>
              <span class="po-mono po-muted">{{ p.reference || '—' }}</span>
              <a v-if="p.proof_file" :href="p.proof_file" target="_blank" rel="noopener"
                 class="proof-link" data-testid="proof-download">View proof</a>
              <span v-else class="po-muted">no file</span>
              <button class="po-btn po-btn-primary po-btn-sm"
                      @click="doVerify(p, 'verify')" data-testid="proof-verify">Verify</button>
              <button class="po-btn po-btn-outline po-btn-sm"
                      @click="doVerify(p, 'reject')" data-testid="proof-reject">Reject</button>
            </div>
          </div>

          <!-- ★ 2026-11-27（A-099）：已付清的发票不该再出现记账表单 ——
               原来只要"有发票"就渲染，发票变 Paid 后按钮照样能点，是重复入账入口。 -->
          <template v-if="detail.invoice.status !== 'paid'">
            <h3 class="po-subsection-title" style="margin-top:20px">Record Payment</h3>
            <p v-if="Number(detail.invoice.balance_due) > 0" class="po-muted" style="margin:0 0 8px">
              Balance due {{ formatCurrency(detail.invoice.balance_due, detail.invoice.currency) }}
              <span v-if="Number(detail.invoice.amount_paid) > 0">
                (paid {{ formatCurrency(detail.invoice.amount_paid, detail.invoice.currency) }})
              </span>
            </p>
            <div class="po-form-grid">
              <div class="po-field"><label class="po-label">Amount</label><input v-model="pay[selected].amount" class="po-input" placeholder="0.00" data-testid="pay-amount" /></div>
              <div class="po-field"><label class="po-label">Method</label>
                <select v-model="pay[selected].method" class="po-select" aria-label="Payment method">
                  <option v-for="m in PAYMENT_METHODS" :key="m.value" :value="m.value">{{ m.label }}</option>
                </select>
              </div>
              <div class="po-field full"><label class="po-label">Reference</label><input v-model="pay[selected].reference" class="po-input" data-testid="pay-reference" /></div>
            </div>
            <p v-if="payError" class="po-pay-error" data-testid="pay-error">{{ payError }}</p>
            <p v-if="payInfo" class="po-pay-ok" data-testid="pay-info">{{ payInfo }}</p>
            <button
              class="po-btn po-btn-primary"
              style="margin-top:12px"
              data-testid="pay-submit"
              :disabled="paying"
              @click="doPay(detail.invoice)"
            >{{ paying ? 'Recording…' : 'Record Payment' }}</button>
          </template>
          <p v-else class="po-muted" style="margin-top:20px" data-testid="invoice-settled">
            This invoice is fully paid — nothing left to record.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-row-selected { background: var(--color-primary-subtle); }
/* A-099：记账的成功/失败必须落在页面上（原来异常直接冒泡，运营看不到任何反馈） */
.po-pay-error {
  margin: 8px 0 0; padding: 8px 12px; border-radius: 4px;
  border: 1px solid var(--color-danger, #dc2626);
  background: var(--color-danger-subtle, #fef2f2); color: var(--color-danger, #dc2626);
  font-size: 13px;
}
.po-pay-ok {
  margin: 8px 0 0; padding: 8px 12px; border-radius: 4px;
  border: 1px solid #86efac; background: #f0fdf4; color: #15803d; font-size: 13px;
}
/* ★ S5 P-2：队列取数失败 / 超出翻页上限，都必须留在页面上 */
.po-queue-error {
  margin: 0 0 10px; padding: 8px 12px;
  border: 1px solid var(--color-danger, #dc2626); border-radius: 4px;
  background: var(--color-danger-subtle, #fef2f2); color: var(--color-danger, #dc2626);
  font-size: 12px; line-height: 1.45;
}
.po-queue-warn {
  margin: 0 0 10px; padding: 8px 12px;
  border: 1px solid var(--color-warning, #d97706); border-radius: 4px;
  background: rgba(217, 119, 6, .06);
  font-size: 12px; line-height: 1.45;
}
.proof-box {
  margin-top: 16px; padding: 12px; border-radius: var(--radius-md);
  border-left: 4px solid var(--color-warning, #d97706);
  background: rgba(217, 119, 6, .06);
  display: flex; flex-direction: column; gap: 8px; font-size: 13px;
}
.proof-line { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.proof-link { color: var(--color-primary); font-size: 12px; text-decoration: underline; }
</style>
