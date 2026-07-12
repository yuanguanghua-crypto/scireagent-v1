<script setup>
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { formatCurrency } from '@/utils/helpers'
import { LoadingSpinner, EmptyState } from '@/components/common'

const router = useRouter()
const store = useOrdersStore()

onMounted(() => store.fetchOrders())

const statusColors = {
  draft: 'var(--color-text-tertiary)',
  confirmed: 'var(--color-primary)',
  invoiced: 'var(--color-info)',
  paid: 'var(--color-success)',
  processing: 'var(--color-info)',             /* 蓝色 - 处理中 */
  shipped: 'var(--color-warning)',
  completed: 'var(--color-success)',
  cancelled: 'var(--color-danger)',
  quote_pending: 'var(--color-warning)',       /* 琥珀色 - 待报价 */
  quoted: 'var(--color-accent)',               /* 琥珀色 - 已报价 */
  quote_accepted: 'var(--color-success)',
  quote_rejected: 'var(--color-danger)',
}

function getStatusLabel(status) {
  return status?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || status
}

function goToDetail(order) {
  router.push(`/orders/${order.id}`)
}
</script>

<template>
  <div class="order-list-page">
    <h1 class="page-title">My Orders</h1>

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
              <span class="status-badge" :style="{ color: statusColors[order.status], background: statusColors[order.status] + '15' }">
                {{ getStatusLabel(order.status) }}
              </span>
            </td>
            <td class="order-payment">{{ order.payment_method?.replace(/_/g, ' ') }}</td>
            <td class="order-total">{{ formatCurrency(order.grand_total, order.currency) }}</td>
            <td><span class="view-link">View →</span></td>
          </tr>
        </tbody>
      </table>
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
