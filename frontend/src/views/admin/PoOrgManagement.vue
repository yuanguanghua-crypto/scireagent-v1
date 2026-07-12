<script setup>
import { onMounted, ref } from 'vue'
import { getOrganizations, getOrgOrders } from '@/api/adminPo'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const orgs = ref([])
const loading = ref(false)
const selectedOrg = ref(null)
const orgOrders = ref([])
const orgLoading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await getOrganizations({ page_size: 100 })
    const payload = res.data || res
    orgs.value = payload.results || payload.data || payload || []
  } finally {
    loading.value = false
  }
}

async function selectOrg(org) {
  selectedOrg.value = org
  orgLoading.value = true
  try {
    const res = await getOrgOrders(org.id, { page_size: 100 })
    const payload = res.data || res
    orgOrders.value = payload.results || payload.data || payload || []
  } finally {
    orgLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Organization Management</h1>
        <p class="po-page-subtitle">View organizations, their addresses and order history.</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-form-grid">
      <div class="po-card">
        <h2 class="po-section-title">Organizations</h2>
        <table class="po-table" v-if="orgs.length">
          <thead><tr><th>Name</th><th>Type</th><th>Country</th></tr></thead>
          <tbody>
            <tr v-for="o in orgs" :key="o.id" :class="{ 'po-row-selected': selectedOrg?.id === o.id }" @click="selectOrg(o)" style="cursor:pointer">
              <td>{{ o.name }}</td>
              <td>{{ o.org_type || '—' }}</td>
              <td>{{ o.country || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="loading" class="po-empty">Loading…</div>
        <div v-else class="po-empty">No organizations.</div>
      </div>

      <div class="po-card" v-if="selectedOrg">
        <h2 class="po-section-title">{{ selectedOrg.name }} — Orders</h2>
        <table class="po-table" v-if="orgOrders.length">
          <thead><tr><th>Order</th><th>Status</th><th>Total</th><th>Created</th></tr></thead>
          <tbody>
            <tr v-for="o in orgOrders" :key="o.id">
              <td class="po-mono">{{ o.order_no }}</td>
              <td><StatusBadge :status="o.status" :label="o.status?.replace(/_/g,' ')" /></td>
              <td class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</td>
              <td class="po-muted">{{ new Date(o.created_at).toLocaleDateString() }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="orgLoading" class="po-empty">Loading…</div>
        <div v-else class="po-empty">No orders for this organization.</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-row-selected { background: var(--color-primary-subtle); }
</style>
