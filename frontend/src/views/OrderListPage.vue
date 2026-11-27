<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { getMyQuoteRequests, respondToQuote } from '@/api/rfq'
import { useConfirm } from '@/composables/useConfirm'
import { toast } from '@/components/common'
import { statusBadgeStyle, formatStatus } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { LoadingSpinner, EmptyState, DataPagination, ErrorBanner } from '@/components/common'

const router = useRouter()
const store = useOrdersStore()
const { ask, askText } = useConfirm()

/**
 * ★ 2026-11-27（A-170 / A-264）：客户侧的询价（RFQ）区块。
 *
 * 改前：`/orders` 只有订单 —— 客户提交过询价、运营也报了价，但客户**在界面上
 * 永远看不到**（详情 API `GET /quote-requests/{id}/` 明明是 200，只是没有门），
 * 更没有"接受 / 拒绝报价"的入口（枚举里连 accepted/rejected 都没有）。
 * 现在这里列出「我提交过的询价」，报价到了可以直接接受或拒绝。
 */
const rfqs = ref([])
const rfqsLoading = ref(false)
const rfqBusyId = ref(null)

async function loadRfqs() {
  rfqsLoading.value = true
  try {
    const res = await getMyQuoteRequests()
    rfqs.value = res.data || res || []
  } catch {
    rfqs.value = []      // 拉不到就整块不显示：不该让询价故障拖垮订单列表
  } finally {
    rfqsLoading.value = false
  }
}

async function respond(q, action) {
  let note = ''
  if (action === 'accept') {
    const ok = await ask({
      title: 'Accept this quotation?',
      message: `Accept the quotation for RFQ #${q.id}`
        + (q.quoted_total != null ? ` (${formatCurrency(q.quoted_total, q.quoted_currency || 'USD')})` : '')
        + '?\n\nOur team will follow up with the order.',
      confirmText: 'Accept quotation',
    })
    if (!ok) return
  } else {
    const reason = await askText({
      title: 'Reject this quotation',
      message: `Reject the quotation for RFQ #${q.id}?\n`
        + 'A reason is optional, but it is what our sales team sees.',
      placeholder: 'Optional reason…',
      confirmText: 'Reject',
      danger: true,
    })
    if (reason === null) return
    note = reason
  }
  rfqBusyId.value = q.id
  try {
    const res = await respondToQuote(q.id, { action, note })
    const updated = res.data || res
    const idx = rfqs.value.findIndex((x) => x.id === q.id)
    if (idx >= 0) rfqs.value[idx] = updated
    toast.success(action === 'accept' ? 'Quotation accepted' : 'Quotation rejected')
  } catch (e) {
    toast.error(
      e?.response?.data?.meta?.error?.message || e?.message || 'Could not record your answer.',
    )
  } finally {
    rfqBusyId.value = null
  }
}

function fmtDate(v) {
  return v ? new Date(v).toLocaleDateString() : '—'
}

onMounted(() => {
  store.fetchOrders()
  loadRfqs()
})

// ★ 2026-10-21 修 D2（P0）：此前本页**没有任何分页控件**，store 也从不传 page
//   ⇒ 客户只能看到最近 20 单，第 21 单起永久不可达（后端 `PAGE_SIZE=20`）。
//   点页码/改每页条数都重新向后端取数（不在前端切片，否则仍拿不到第 21 单）。
function onPageChange({ page, pageSize }) {
  store.fetchOrders({ page, page_size: pageSize })
}

// ★ 2026-10-28：本页原先内联的 statusColors / getStatusLabel 缺
//   `po_received` / `in_production` / `delivered` 三态（PO 主流程正好全缺），
//   且底色用的是 `statusColors[s] + '15'`（非法 CSS，实测恒透明）。
//   现统一取 `@/config/poConstants` 的单一真相源，与运营台口径一致。
//   `getStatusLabel` 的旧实现与 `formatStatus` 完全等价，直接换掉。
function getStatusLabel(status) {
  return formatStatus(status)
}

function goToDetail(order) {
  router.push(`/orders/${order.id}`)
}

// ★ A-263：单号搜索（服务端 `?search=`，覆盖全量而不只是当前页）
const orderSearch = ref('')
function applyOrderSearch() {
  store.fetchOrders({ page: 1, search: orderSearch.value || undefined })
}
function clearOrderSearch() {
  orderSearch.value = ''
  store.fetchOrders({ page: 1 })
}
</script>

<template>
  <div class="order-list-page">
    <h1 class="page-title">My Orders</h1>

    <!-- ★ 2026-11-27（A-170 / A-264）：我提交过的询价 + 报价答复入口 -->
    <section v-if="rfqs.length" class="rfq-block" data-testid="my-rfqs">
      <h2 class="rfq-block-title">Quote Requests ({{ rfqs.length }})</h2>
      <table class="order-table">
        <thead>
          <tr>
            <th>RFQ</th><th>Submitted</th><th>Items</th><th>Status</th><th>Quoted</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="q in rfqs" :key="q.id">
            <td class="mono">#{{ q.id }}</td>
            <td>{{ fmtDate(q.created_at) }}</td>
            <td>{{ (q.items || []).length }}</td>
            <td><span class="po-tag" :data-testid="`rfq-status-${q.id}`">{{ q.status }}</span></td>
            <td class="mono">
              {{ q.quoted_total != null
                ? formatCurrency(q.quoted_total, q.quoted_currency || 'USD')
                : '—' }}
              <div v-if="q.quoted_valid_until" class="rfq-valid">
                valid until {{ q.quoted_valid_until }}
              </div>
            </td>
            <td>
              <template v-if="q.status === 'quoted'">
                <button
                  class="btn-sm btn-primary" :disabled="rfqBusyId === q.id"
                  :data-testid="`rfq-accept-${q.id}`" @click="respond(q, 'accept')"
                >Accept quote</button>
                <button
                  class="btn-sm btn-ghost" :disabled="rfqBusyId === q.id"
                  :data-testid="`rfq-reject-${q.id}`" @click="respond(q, 'reject')"
                >Reject</button>
              </template>
              <span v-else-if="q.status === 'accepted'" class="rfq-answered">You accepted this quote.</span>
              <span v-else-if="q.status === 'rejected'" class="rfq-answered">You rejected this quote.</span>
              <span v-else class="rfq-answered">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ★ D10：加载失败的持久横幅（此前只有 4 秒 toast ⇒ 看起来像"你没有订单"） -->
    <ErrorBanner :message="store.error" kind="load" title="Couldn't load orders." />

    <!-- Loading -->
    <LoadingSpinner v-if="store.loading" text="Loading orders..." />

    <!-- Empty -->
    <EmptyState
      v-else-if="store.orders.length === 0"
      title="No orders yet"
      description="You have no orders yet."
      icon="List"
    >
      <template #action>
        <router-link to="/products" class="btn-primary">Browse Products</router-link>
      </template>
    </EmptyState>

    <!-- Order list -->
    <div v-else class="order-table-wrap">
      <!-- ★ 2026-11-27（A-263）：客户订单列表此前**没有单号搜索** —— 全站搜索框只搜
           产品/方法/协议，填订单号回车会被带到搜索页。这里补一个本地输入框，
           回车/点 Search 走服务端 `?search=`（按 order_no / po_number 模糊匹配）。 -->
      <div class="order-search">
        <input
          v-model.trim="orderSearch"
          class="order-search-input"
          placeholder="Search by order # or PO #…"
          data-testid="orders-search"
          @keyup.enter="applyOrderSearch"
        />
        <button class="btn-sm btn-ghost" data-testid="orders-search-apply" @click="applyOrderSearch">Search</button>
        <button v-if="orderSearch" class="btn-sm btn-ghost" @click="clearOrderSearch">Clear</button>
      </div>
      <table class="order-table">
        <thead>
          <tr>
            <th>Order #</th>
            <!-- ★ 2026-11-27（A-236）：本页此前只有 Order #，PO 号要去 /po/orders 或详情页看 -->
            <th>PO #</th>
            <th>Date</th>
            <th>Status</th>
            <th>Payment</th>
            <th>Total</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="order in store.orders" :key="order.id" @click="goToDetail(order)" class="order-row">
            <td class="order-no">{{ order.order_no }}</td>
            <td class="order-date">{{ new Date(order.created_at).toLocaleDateString() }}</td>
            <td>
              <span class="status-badge" :style="statusBadgeStyle(order.status)">
                {{ getStatusLabel(order.status) }}
              </span>
            </td>
            <td class="order-payment">{{ order.payment_method?.replace(/_/g, ' ') }}</td>
            <td class="order-total">{{ formatCurrency(order.grand_total, order.currency) }}</td>
            <td><span class="view-link">View →</span></td>
          </tr>
        </tbody>
      </table>

      <!-- D2：分页。total 来自后端真实 count（store 已修正读取位置）
           ⚠️ 刻意**不用** `sizes` 布局：Element Plus 的每页条数选择器会渲染一个
           `<input class="el-select__input" role="combobox">` 但**不带可访问名字**，
           实测让本页 a11y 从 critical=0 变成 **critical=1**（`label: Form elements must have labels`）。
           本页只要「能翻到第 21 单以后」，不需要改每页条数 ⇒ 用最小的 layout 避免引入新违规。
           （等 DataPagination 支持给内部 select 传 aria-label 后，可再放开 sizes。） -->
      <DataPagination
        v-if="store.total > store.pageSize"
        :current-page="store.page"
        :page-size="store.pageSize"
        :total="store.total"
        layout="total, prev, pager, next"
        @change="onPageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.order-list-page { }
.order-search { display: flex; gap: 8px; align-items: center; margin: 0 0 12px; }
.order-search-input {
  width: 260px; padding: 7px 10px; font-size: 13px;
  border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-surface);
  color: var(--color-text);
}
/* A-170 / A-264：询价区块（与订单表同款表格，视觉上区分一层底） */
.rfq-block { margin-bottom: 22px; padding: 14px 16px; border: 1px solid var(--color-border);
  border-radius: 8px; background: var(--color-surface); }
.rfq-block-title { font-size: 15px; font-weight: 700; margin: 0 0 10px; color: var(--color-text); }
.rfq-valid { font-size: 11px; color: var(--color-text-tertiary); }
.rfq-answered { font-size: 12px; color: var(--color-text-secondary); }
.page-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0 0 20px; }

.order-table-wrap { overflow-x: auto; }
.order-table { width: 100%; border-collapse: collapse; }
.order-table th {
  text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 600;
  color: var(--color-text-tertiary); text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 1px solid var(--color-border);
}
.order-table td { padding: 14px 12px; font-size: 14px; border-bottom: 1px solid var(--color-border-light); }
.order-row { cursor: pointer; transition: background 0.1s; }
.order-row:hover { background: var(--color-bg); }
.order-no { font-weight: 600; font-family: var(--font-mono); font-size: 13px; }
.order-date { color: var(--color-text-secondary); }
.order-payment { color: var(--color-text-secondary); text-transform: capitalize; }
.order-total { font-weight: 600; font-variant-numeric: tabular-nums; }
.view-link { font-size: 13px; color: var(--color-primary); font-weight: 500; }

.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: var(--radius-full);
  font-size: 12px; font-weight: 600; text-transform: capitalize;
}

.btn-primary {
  display: inline-block; padding: 10px 20px; background: var(--color-primary); color: white;
  border-radius: var(--radius-md); text-decoration: none; font-weight: 600; font-size: 14px;
}
</style>
