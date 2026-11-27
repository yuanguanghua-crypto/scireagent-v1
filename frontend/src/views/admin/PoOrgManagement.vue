<script setup>
import { onMounted, ref } from 'vue'
import { getOrganizations } from '@/api/adminPo'
import { fetchAllOrderPages } from '@/composables/useOrderQueue'
import { extractErrorMessage } from '@/utils/http'
import { formatCurrency } from '@/utils/helpers'
import { StatusBadge } from '@/components/common'

const orgs = ref([])
const loading = ref(false)
const selectedOrg = ref(null)
const orgOrders = ref([])
const orgLoading = ref(false)
// ★ 2026-11-20（S5 P-2）：机构订单队列的真值、截断提示与取数失败态。
//   原实现 `getOrgOrders(org.id, { page_size: 100 })` 只取**一页**且无翻页手段
//   ⇒ 本地 dev 实测 org 4 有 1123 单，按机构查看时**漏 1023**，页面毫无提示。
const orgTotal = ref(0)
const orgTruncated = ref(false)
const orgError = ref('')

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
  orgOrders.value = []
  orgTotal.value = 0
  orgTruncated.value = false
  orgError.value = ''
  orgLoading.value = true
  try {
    const { orders: rows, total, truncated } = await fetchAllOrderPages({
      organization_id: org.id,
    })
    orgOrders.value = rows
    orgTotal.value = total
    orgTruncated.value = truncated
  } catch (e) {
    // 原实现 `finally` 之后什么都不报 ⇒ 取数失败与"该机构没有订单"长得一模一样
    orgError.value = extractErrorMessage(
      e?.response?.data ?? e, 'Could not load orders for this organization.',
    )
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
        <!-- ★ 2026-11-27（A-010）：副标题原来写 "their addresses and order history"，
             但**地址根本展示不了** —— `/addresses/` 按 `request.user.organization` 过滤，
             内部人员无 organization 时直接返回空（`accounts/api/v1/views.py:429` 明确防越权），
             所以运营看不到别家机构的地址。承诺了给不了的东西，就是这条缺陷。
             现在只承诺真的有的（订单历史），并补一句"点一行看订单"——
             原来这个交互没有任何提示，QA 也就只看到三列表格。 -->
        <p class="po-page-subtitle">View organizations and their order history.</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load">Refresh</button>
    </div>

    <div class="po-form-grid">
      <div class="po-card">
        <h2 class="po-section-title">Organizations</h2>
        <p class="po-muted" style="margin:-4px 0 10px;font-size:12px">
          Select an organization to see its orders.
        </p>
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
        <h2 class="po-section-title">
          {{ selectedOrg.name }} — Orders
          <span class="po-muted" data-testid="org-order-total">({{ orgTotal }})</span>
        </h2>
        <p v-if="orgError" class="po-org-error" data-testid="org-order-error">{{ orgError }}</p>
        <p v-if="orgTruncated" class="po-org-warn" data-testid="org-order-truncated">
          Showing the first {{ orgOrders.length }} of {{ orgTotal }} orders — the queue exceeds
          what this page loads in one go. Narrow it down by status from the Orders page.
        </p>
        <table class="po-table" v-if="orgOrders.length">
          <thead><tr><th>Order</th><th>Status</th><th>Total</th><th>Created</th></tr></thead>
          <tbody>
            <tr v-for="o in orgOrders" :key="o.id">
              <td class="po-mono">{{ o.order_no }}</td>
              <td><StatusBadge :status="o.status" /></td>
              <td class="po-num">{{ formatCurrency(o.grand_total, o.currency) }}</td>
              <td class="po-muted">{{ new Date(o.created_at).toLocaleDateString() }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="orgLoading" class="po-empty">Loading…</div>
        <div v-else-if="orgError" class="po-empty" data-testid="org-order-error-empty">
          Orders could not be loaded — see the message above.
        </div>
        <div v-else class="po-empty">No orders for this organization.</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-row-selected { background: var(--color-primary-subtle); }
/* ★ S5 P-2：机构订单取数失败 / 超出翻页上限的显式提示（不再静默空表） */
.po-org-error {
  margin: 0 0 10px;
  padding: 8px 12px;
  border: 1px solid var(--color-danger, #dc2626);
  border-radius: 4px;
  background: var(--color-danger-subtle, #fef2f2);
  color: var(--color-danger, #dc2626);
  font-size: 13px;
  line-height: 1.45;
}
.po-org-warn {
  margin: 0 0 10px;
  padding: 8px 12px;
  border: 1px solid var(--color-warning, #d97706);
  border-radius: 4px;
  background: rgba(217, 119, 6, .06);
  color: inherit;
  font-size: 12px;
  line-height: 1.45;
}
</style>
