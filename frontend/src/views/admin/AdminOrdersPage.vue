<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getAdminOrders } from '@/api/orders'
import { formatCurrency } from '@/utils/helpers'

const router = useRouter()
const orders = ref([])
const loading = ref(false)
const statusFilter = ref('')
const searchQuery = ref('')

const statusColors = {
  draft: '#6B7280', confirmed: '#0F766E', invoiced: '#2563EB', paid: '#059669',
  processing: '#7C3AED', shipped: '#D97706', completed: '#059669', cancelled: '#DC2626',
  quote_pending: '#7C3AED', quoted: '#7C3AED', quote_accepted: '#059669', quote_rejected: '#DC2626',
}

function getStatusLabel(status) {
  return status?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || status
}

async function fetchOrders() {
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value) params.status = statusFilter.value
    if (searchQuery.value) params.search = searchQuery.value
    const res = await getAdminOrders(params)
    const data = res.data || res
    orders.value = data.results || data.data || data || []
  } catch (err) {
    console.error('Failed to fetch orders:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchOrders)

function goToDetail(order) {
  router.push(`/admin/orders/${order.id}`)
}
</script>

<template>
  <div class="admin-orders-page">
    <h1 class="page-title">Order Management</h1>

    <!-- Filters -->
    <div class="filters">
      <select v-model="statusFilter" class="filter-select" @change="fetchOrders">
        <option value="">All Statuses</option>
        <option value="draft">Draft</option>
        <option value="confirmed">Confirmed</option>
        <option value="invoiced">Invoiced</option>
        <option value="paid">Paid</option>
        <option value="processing">Processing</option>
        <option value="shipped">Shipped</option>
        <option value="completed">Completed</option>
        <option value="quote_pending">Quote Pending</option>
        <option value="quoted">Quoted</option>
      </select>
      <div class="search-wrap">
        <input v-model="searchQuery" class="search-input" placeholder="Search order #, PO #..." @keyup.enter="fetchOrders" />
        <button class="search-btn" @click="fetchOrders">Search</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">Loading...</div>

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
            <td>{{ order.user_id }}</td>
            <td class="mono">{{ order.po_number || '—' }}</td>
            <td>
              <span class="status-badge" :style="{ color: statusColors[order.status], background: statusColors[order.status] + '15' }">
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
      <div v-if="orders.length === 0" class="empty-state">No orders found.</div>
    </div>
  </div>
</template>

<style scoped>
.admin-orders-page { }
.page-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0 0 16px; }

.filters { display: flex; gap: 12px; margin-bottom: 16px; }
.filter-select {
  height: 40px; padding: 0 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 14px; color: var(--color-text); background: var(--color-surface); font-family: var(--font-sans);
}
.search-wrap { display: flex; flex: 1; gap: 8px; }
.search-input {
  flex: 1; height: 40px; padding: 0 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 14px; font-family: var(--font-sans);
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
  color: var(--color-text-tertiary); text-transform: uppercase; border-bottom: 1px solid var(--color-border);
}
.order-table td { padding: 12px; font-size: 14px; border-bottom: 1px solid var(--color-border-light); }
.order-row { cursor: pointer; transition: background 0.1s; }
.order-row:hover { background: var(--color-bg); }
.mono { font-family: var(--font-mono); font-size: 13px; }
.total-cell { font-weight: 600; font-variant-numeric: tabular-nums; }
.view-link { color: var(--color-primary); font-weight: 600; }

.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: var(--radius-full);
  font-size: 12px; font-weight: 600; text-transform: capitalize;
}

.empty-state { text-align: center; padding: 40px 0; color: var(--color-text-secondary); }
.loading-state { text-align: center; padding: 40px 0; color: var(--color-text-secondary); }
</style>
