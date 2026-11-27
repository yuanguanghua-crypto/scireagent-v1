<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getAdminOrders } from '@/api/orders'
import { formatCurrency } from '@/utils/helpers'
import { extractErrorMessage } from '@/utils/http'
import { LoadingSpinner, EmptyState, DataPagination, ErrorBanner } from '@/components/common'
import { ORDER_STATUS_FILTERS, LEGACY_STATUS_FILTERS, statusBadgeStyle } from '@/config/poConstants'

const router = useRouter()
const route = useRoute()
const orders = ref([])
const loading = ref(false)
// ★ 2026-11-27（A-083）：支持 `?status=paid` 这类直达。
//   Invoicing Desk 只维护"待开票/待收款"队列（paid 有意离队），运营要看
//   已结清的发票得能一步跳到对应筛选 —— 原来链接过来是空筛选，等于没跳。
const statusFilter = ref(String(route.query.status || ''))
const searchQuery = ref('')
// ★ 2026-10-21 修 D4：此前**没有任何分页状态** ⇒ 后端 PAGE_SIZE=20，
//   991 单里只能看到最新 20 单，更早的单永久不可达。
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
// ★ 2026-10-21 修 D10：加载失败此前只 console.error ⇒ 表格空 + 4 秒 toast，看着像"没有订单"
const error = ref('')

// ★ 2026-10-21 修 D4：状态色表改为引用统一常量（原先内联且缺 3 个状态 ⇒ 徽章 undefined15 无底色）
// ★ 2026-10-28：底色也改走统一入口 —— `ORDER_STATUS_COLORS[s] + '15'` 是非法 CSS
//   （令牌是 var()，拼出 `var(--x)15`），实测底色恒透明。

function getStatusLabel(status) {
  const hit = [...ORDER_STATUS_FILTERS, ...LEGACY_STATUS_FILTERS].find((f) => f.value === status)
  if (hit) return hit.label
  return status?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || status
}

async function fetchOrders(opts = {}) {
  loading.value = true
  error.value = ''
  try {
    // 换筛选/换搜索时回到第 1 页；翻页时保持
    const nextPage = Number(opts.page ?? page.value) || 1
    const params = { page: nextPage, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (searchQuery.value) params.search = searchQuery.value
    const res = await getAdminOrders(params)
    // 信封形状：{ success, data: [本页条目], meta: { pagination: { count, next, previous } } }
    // （后端 `core/renderers.py:31-37`）—— 旧代码读 `res.data.meta`，而 `data` 已是数组 ⇒ 取不到
    const payload = res && res.data !== undefined ? res.data : res
    orders.value = Array.isArray(payload) ? payload : (payload?.results || payload?.data || [])
    total.value = Number(res?.meta?.pagination?.count ?? payload?.count ?? orders.value.length)
    page.value = nextPage
  } catch (err) {
    console.error('Failed to fetch orders:', err)
    error.value = extractErrorMessage(err?.response?.data ?? err?.data ?? err, 'Failed to load orders.')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  fetchOrders({ page: 1 })
}

function onPageChange({ page: p, pageSize: s }) {
  pageSize.value = s
  fetchOrders({ page: p })
}

onMounted(fetchOrders)

function goToDetail(order) {
  router.push(`/ops/orders/${order.id}`)
}
</script>

<template>
  <div class="admin-orders-page">
    <h1 class="page-title">Order Management</h1>

    <!-- Filters -->
    <div class="filters">
      <select v-model="statusFilter" class="filter-select" @change="onFilterChange" aria-label="Filter orders by status">
        <!-- ★ 2026-10-21 修 D4：选项改由 `poConstants` 统一提供（此前内联 9 项、缺整套 PO 流程态） -->
        <option v-for="f in ORDER_STATUS_FILTERS" :key="f.value" :value="f.value">{{ f.label }}</option>
        <optgroup label="Historical / Quote states">
          <option v-for="f in LEGACY_STATUS_FILTERS" :key="f.value" :value="f.value">{{ f.label }}</option>
        </optgroup>
      </select>
      <div class="search-wrap">
        <input v-model="searchQuery" class="search-input" placeholder="Search order #, PO #..." @keyup.enter="onFilterChange" />
        <button class="search-btn" @click="onFilterChange">Search</button>
      </div>
    </div>

    <!-- ★ D10：加载失败的持久横幅 -->
    <ErrorBanner :message="error" kind="load" title="Couldn't load orders." />

    <!-- Loading -->
    <LoadingSpinner v-if="loading" text="Loading..." />

    <!-- Table -->
    <div v-else class="table-wrap">
      <table class="order-table">
        <thead>
          <tr>
            <th>Order #</th>
            <th>Customer</th>
            <th>PO #</th>
            <th>Status</th>
            <th>Payment</th>
            <th>Total</th>
            <th>Date</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="order in orders" :key="order.id" @click="goToDetail(order)" class="order-row">
            <td class="mono">{{ order.order_no }}</td>
            <!-- ★ 2026-11-26（A-077）：此前这里是 `{{ order.user_id }}` —— 一个裸数字 id，
                 user 为 NULL 的历史单整列空白，运营既联系不上客户也判断不出是谁下的。
                 现在显示客户名 + 邮箱 + 组织名（后端 `CustomerFieldsMixin` 的同一份取值）。 -->
            <td>
              <div class="cust-name">{{ order.customer_name || '—' }}</div>
              <div v-if="order.customer_email" class="cust-sub">{{ order.customer_email }}</div>
              <div v-if="order.organization_name" class="cust-sub">{{ order.organization_name }}</div>
            </td>
            <td class="mono">{{ order.po_number || '—' }}</td>
            <td>
              <span class="status-badge" :style="statusBadgeStyle(order.status)">
                {{ getStatusLabel(order.status) }}
              </span>
            </td>
            <td>{{ order.payment_method?.replace(/_/g, ' ') }}</td>
            <td class="total-cell">{{ formatCurrency(order.grand_total, order.currency) }}</td>
            <td>{{ new Date(order.created_at).toLocaleDateString() }}</td>
            <td><span class="view-link">→</span></td>
          </tr>
        </tbody>
      </table>
      <EmptyState v-if="orders.length === 0" title="No orders found" icon="List" />

      <!-- ★ 2026-10-21 修 D4：加分页。⚠️ 不用 `sizes` 布局：
           Element Plus 的每页条数选择器会渲染一个无可访问名的 combobox，
           实测会让本页 a11y critical 0→1（同 D2 的处理方式）。 -->
      <!-- ★ 2026-11-27（A-079 / A-219）：结果总数必须**总是**可见。
           此前总数只由 DataPagination 的 "total" 槽渲染，而它挂在
           `v-if="total > pageSize"` 上 ⇒ 一筛选（如 Paid 2 单）就掉到一页以内，
           分页整块消失，总数也跟着没了。运营刚筛完反而不知道筛出了几条。
           现在单独给一行计数，分页只负责翻页（layout 去掉 total，避免两个数字打架）。 -->
      <p class="list-count" data-testid="orders-total">
        {{ loading ? 'Loading…' : `${total} order${total === 1 ? '' : 's'}` }}
        <span v-if="statusFilter || searchQuery" class="list-count-scope">matching filter</span>
      </p>
      <DataPagination
        v-if="total > pageSize"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @change="onPageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.admin-orders-page { }
.page-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0 0 16px; }
.list-count {
  margin: 12px 0 0; font-size: 13px; color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.list-count-scope { color: var(--color-text-tertiary); }

.filters { display: flex; gap: 12px; margin-bottom: 16px; }
.filter-select {
  height: 40px; padding: 0 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 14px; color: var(--color-text); background: var(--color-surface); font-family: var(--font-sans);
}
.search-wrap { display: flex; flex: 1; gap: 8px; }
.search-input {
  flex: 1; height: 40px; padding: 0 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 14px; font-family: var(--font-sans); background: var(--color-surface); color: var(--color-text);
}
.search-input:focus { border-color: var(--color-primary); outline: none; }
.search-btn {
  height: 40px; padding: 0 16px; background: var(--color-primary); color: white; border: none;
  border-radius: var(--radius-md); font-weight: 600; cursor: pointer; font-family: var(--font-sans);
}

.table-wrap { overflow-x: auto; }
.order-table { width: 100%; border-collapse: collapse; }
.order-table th {
  text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 600;
  color: var(--color-gray-600); text-transform: uppercase; border-bottom: 1px solid var(--color-border);
}
.order-table td { padding: 12px; font-size: 14px; border-bottom: 1px solid var(--color-border-light); }
.order-row { cursor: pointer; transition: background 0.1s; }
.order-row:hover { background: var(--color-bg); }
.mono { font-family: var(--font-mono); font-size: 13px; }
/* A-077：客户列的副行（邮箱 / 组织名），主行是姓名 */
.cust-name { font-weight: 600; }
.cust-sub { font-size: 12px; color: var(--color-text-secondary); line-height: 1.35; }
.total-cell { font-weight: 600; font-variant-numeric: tabular-nums; }
.view-link { color: var(--color-primary); font-weight: 600; }

.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: var(--radius-full);
  font-size: 12px; font-weight: 600; text-transform: capitalize;
}
</style>
