<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { usePoPortalStore } from '@/stores/poPortal'
import { ORDER_STATUS_FILTERS, LEGACY_STATUS_FILTERS } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge, DataPagination } from '@/components/common'

const router = useRouter()
const store = usePoPortalStore()
const { orders, total, loading, page, pageSize } = storeToRefs(store)
const statusFilter = ref('')

async function load(opts = {}) {
  const base = { ...(opts || {}) }
  if (statusFilter.value) base.status = statusFilter.value
  await store.fetchOrders(base)
}

onMounted(() => load({ page: 1 }))
// 换筛选 ⇒ 必须回到第 1 页（否则会停在越界页显示空表）
watch(statusFilter, () => load({ page: 1 }))

// ★ 2026-10-21 修 D5：此前没有分页控件，32 单也只显示前 20 单
function onPageChange(p) {
  load({ page: p.page, page_size: p.pageSize })
}

function goDetail(id) {
  router.push({ name: 'PoOrderDetail', params: { id } })
}
function reorder(id) {
  router.push({ name: 'PoSubmit', query: { reorder: id } })
}
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">My Purchase Orders</h1>
        <p class="po-page-subtitle">{{ total }} order(s)</p>
      </div>
      <div class="po-row">
        <select v-model="statusFilter" class="po-select" style="width:180px" aria-label="Filter orders by status">
          <option v-for="f in ORDER_STATUS_FILTERS" :key="f.value" :value="f.value">{{ f.label }}</option>
          <!-- ★ 2026-10-21 修 D5：补 legacy 报价态（库内 quote_pending 40 单 / quoted 33 单） -->
          <optgroup label="Quote / Historical states">
            <option v-for="f in LEGACY_STATUS_FILTERS" :key="f.value" :value="f.value">{{ f.label }}</option>
          </optgroup>
        </select>
        <router-link :to="{ name: 'PoSubmit' }" class="po-btn po-btn-accent">+ New PO</router-link>
      </div>
    </div>

    <div class="po-card">
      <table class="po-table" v-if="orders.length">
        <thead>
          <tr>
            <th>Order No</th>
            <th>PO Number</th>
            <th>Status</th>
            <th>Items</th>
            <th>Total</th>
            <th>Created</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id">
            <td class="po-mono">{{ o.order_no }}</td>
            <td class="po-mono">{{ o.po_number || '—' }}</td>
            <td><StatusBadge :status="o.status" /></td>
            <td>{{ o.items_count }}</td>
            <td class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</td>
            <td class="po-muted">{{ new Date(o.created_at).toLocaleDateString() }}</td>
            <td>
              <div class="po-row">
                <button class="po-btn po-btn-outline po-btn-sm" @click="goDetail(o.id)">View</button>
                <button class="po-btn po-btn-outline po-btn-sm" @click="reorder(o.id)">Re-order</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="po-empty">Loading…</div>
      <div v-else class="po-empty">No purchase orders found.</div>

      <!-- ★ D5：分页（不用 `sizes` 布局，避免 Element Plus 无可访问名的每页条数 combobox） -->
      <DataPagination
        v-if="total > pageSize"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @change="onPageChange"
      />
    </div>
  </div>
</template>
