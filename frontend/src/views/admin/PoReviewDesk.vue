<script setup>
import { onMounted, ref } from 'vue'
import { getPendingReviews, approveOrder, rejectOrder, assignRep, getOrderDetail } from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const orders = ref([])
const loading = ref(false)
const rejectReason = ref({})
const assignRepId = ref({})
const repInput = ref('')

// ★ P1-1 库存匹配：展开订单时拉明细（含 sku_available），缺货行高亮
const expandedItems = ref({})
const expanded = ref({})
// ★ 2026-10-28：库存/信息完整度的**持久**摘要，展开过一次就留在卡片上。
//   为什么不在 onMounted 就给每单算：评审队列可能很多单，逐单拉明细是 N+1。
//   为什么要有它：审核员若不展开明细，就完全不知道这单是否全部缺货（实测 8/8 行
//   AVAILABLE=0，Approve 按钮照样可点 —— 状态机不校验库存）。摘要至少在他看过一次
//   之后一直挂在那儿，避免"点完才想起没备货"。
const stockSummary = ref({})
// ★ 2026-10-28：卡片上那三格（Grant Code / Shipping Method / Ship-to）此前恒显示 "—"，
//   一度以为是"客户没填"。**真实原因是列表接口没返回这些字段** ——
//   `OrderListSerializer.Meta.fields` 当时不含这 4 个字段，模板 `|| '—'` 就把
//   undefined 渲染成破折号（实测 ORD-A382B455 真实 Ship-to 是 `test001 — test`）。
//   现已给序列化器补上 grant_code / shipping_method / shipping_name / shipping_address
//   ⇒ 列表一进来就有值，**不再需要展开明细**（此前为绕过缺陷临时做成三态
//   "Expand to load"，现在收敛回两态：有值 / 客户确实没填）。

function isBlank(v) {
  return v === null || v === undefined || String(v).trim() === ''
}

function disp(o, key) {
  return isBlank(o[key]) ? 'Not provided by customer' : o[key]
}

function isMissing(o, key) {
  return isBlank(o[key])
}

function shiptoText(o) {
  const joined = [o.shipping_name, o.shipping_address].filter((x) => !isBlank(x)).join(' — ')
  return joined || 'Not provided by customer'
}

function shipMissing(o) {
  return isBlank(o.shipping_name) || isBlank(o.shipping_address)
}

async function toggleItems(o) {
  if (expanded.value[o.id]) {
    expanded.value[o.id] = false
    return
  }
  expanded.value[o.id] = true
  if (!expandedItems.value[o.id]) {
    try {
      const res = await getOrderDetail(o.id)
      const d = res.data || res
      expandedItems.value[o.id] = d.items || []
    } catch {
      expandedItems.value[o.id] = []
    }
    const items = expandedItems.value[o.id] || []
    stockSummary.value[o.id] = {
      total: items.length,
      short: items.filter((it) => Number(it.quantity) > Number(it.sku_available)).length,
    }
  }
}

async function load() {
  loading.value = true
  try {
    const res = await getPendingReviews()
    const payload = res.data || res
    orders.value = payload.results || payload.data || payload || []
  } finally {
    loading.value = false
  }
}

async function approve(id) {
  await approveOrder(id)
  load()
}
async function reject(id) {
  await rejectOrder(id, rejectReason.value[id] || '')
  load()
}
async function assign(id) {
  const rep = assignRepId.value[id]
  if (!rep) return
  await assignRep(id, rep)
  load()
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Order Review Desk</h1>
        <p class="po-page-subtitle">{{ orders.length }} PO(s) awaiting review</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-card" v-for="o in orders" :key="o.id">
      <div class="po-between">
        <div class="po-row">
          <span class="po-mono">{{ o.order_no }}</span>
          <StatusBadge :status="o.status" />
          <span class="po-muted" v-if="o.po_number">PO {{ o.po_number }}</span>
          <span class="po-muted">{{ o.items_count }} line(s)</span>
          <!-- 展开过一次就常驻的库存摘要（见 stockSummary 注释） -->
          <span
            v-if="stockSummary[o.id]"
            class="po-stock-chip"
            :class="{ 'po-stock-chip--short': stockSummary[o.id].short > 0 }"
          >
            {{ stockSummary[o.id].short > 0
              ? `${stockSummary[o.id].short}/${stockSummary[o.id].total} line(s) short of stock`
              : 'Stock sufficient' }}
          </span>
        </div>
        <span class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</span>
      </div>

      <!-- ★ 2026-10-28：三态显示（未展开 / 有值 / 客户确实没填）。
           旧界面在列表接口没返回这些字段的情况下恒显示 "—"，把"字段缺失"伪装成
           "值为空"，会让运营以为客户没填收货地址。 -->
      <div class="po-prop-grid" style="margin-top:12px">
        <span class="po-prop-label">Grant Code</span>
        <span class="po-prop-value" :class="{ 'po-prop-missing': isMissing(o, 'grant_code') }">
          {{ disp(o, 'grant_code') }}
        </span>
        <span class="po-prop-label">Shipping Method</span>
        <span class="po-prop-value" :class="{ 'po-prop-missing': isMissing(o, 'shipping_method') }">
          {{ disp(o, 'shipping_method') }}
        </span>
        <span class="po-prop-label">Ship-to</span>
        <span class="po-prop-value" :class="{ 'po-prop-missing': shipMissing(o) }">
          {{ shiptoText(o) }}
        </span>
      </div>

      <!-- 客户确实没填收货信息时的醒目提示：不阻断 Approve，但必须让运营看到 -->
      <p v-if="shipMissing(o)" class="po-inline-warn">
        ⚠ No ship-to address on this PO — confirm the delivery details with the customer before shipping.
      </p>

      <div class="po-row" style="margin-top:16px">
        <button class="po-btn po-btn-primary" @click="approve(o.id)">Approve</button>
        <input v-model="rejectReason[o.id]" class="po-input" style="width:220px" placeholder="Reject reason" />
        <button class="po-btn po-btn-danger" @click="reject(o.id)">Reject</button>
        <input v-model="assignRepId[o.id]" class="po-input" style="width:100px" placeholder="Rep ID" />
        <button class="po-btn po-btn-outline" @click="assign(o.id)">Assign Rep</button>
        <button class="po-btn po-btn-outline" @click="toggleItems(o)">
          {{ expanded[o.id] ? 'Hide Items' : 'View Items' }}
        </button>
      </div>

      <div v-if="expanded[o.id]" style="margin-top:12px">
        <table class="po-table">
          <thead>
            <tr>
              <th>SKU</th><th>Pack</th><th>Qty</th><th>Available</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in (expandedItems[o.id] || [])" :key="it.id"
                :class="{ 'po-shortage': it.quantity > it.sku_available }">
              <td class="po-mono">{{ it.sku_code || '—' }}</td>
              <td>{{ it.pack_size || '—' }}</td>
              <td>{{ it.quantity }}</td>
              <td>{{ it.sku_available }}</td>
              <td>
                <span v-if="it.quantity > it.sku_available" class="po-shortage-badge">缺货 {{ it.quantity - it.sku_available }}</span>
                <span v-else class="po-muted">可满足</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="!orders.length && !loading" class="po-empty">No orders pending review.</div>
    <div v-if="loading" class="po-empty">Loading…</div>
  </div>
</template>

<style scoped>
.po-shortage td { color: #dc2626; }
.po-shortage td:first-child { border-left: 3px solid #dc2626; }
.po-shortage-badge {
  display: inline-block; padding: 1px 8px; border-radius: 4px;
  background: rgba(220, 38, 38, 0.12); color: #dc2626; font-size: 12px;
}

/* ── 2026-10-28 新增：字段缺失提示 + 库存摘要 ── */
.po-prop-missing { color: var(--color-warning); font-style: italic; }
.po-inline-warn {
  margin: 10px 0 0; padding: 8px 12px;
  background: var(--color-warning-bg); color: var(--color-warning);
  border-left: 3px solid var(--color-warning);
  border-radius: 4px; font-size: 13px; font-weight: 600;
}
.po-stock-chip {
  display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 12px;
  background: var(--color-success-bg); color: var(--color-success); font-weight: 600;
}
.po-stock-chip--short { background: var(--color-danger-bg); color: var(--color-danger); }
</style>
