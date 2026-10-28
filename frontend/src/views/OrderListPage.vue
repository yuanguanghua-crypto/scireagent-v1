<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { statusBadgeStyle, formatStatus } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { LoadingSpinner, EmptyState, DataPagination, ErrorBanner } from '@/components/common'

const router = useRouter()
const store = useOrdersStore()

onMounted(() => store.fetchOrders())

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
</script>

<template>
  <div class="order-list-page">
    <h1 class="page-title">My Orders</h1>

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
      <table class="order-table">
        <thead>
          <tr>
            <th>Order #</th>
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
