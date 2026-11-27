<script setup>
import { onMounted, computed, ref } from 'vue'
import { fetchAllOrderPages } from '@/composables/useOrderQueue'
import { downloadInvoicePdf, downloadPoAttachment } from '@/api/poPortal'
import { extractErrorMessage } from '@/utils/http'
import { StatusBadge } from '@/components/common'

/**
 * ★ 2026-11-20（S5 P-2）：取数改为「服务端筛有文档 + 翻页取全」。
 *
 * 原实现 `store.fetchOrders({ page_size: 100 })` 之后用
 * `o.invoice || o.attachments.length` 在**客户端**筛：
 * 那只在「最新的 100 单」里找有文档的单。本地只读实测（全库 1124 单）：
 * **有发票的共 267 单**，落在最新 100 单之外的客户发票 / PO 附件
 * **在下载中心根本不出现**，而页面会显示 "No downloadable documents yet"
 * —— 客户会以为"确实没有文档"，属于静默漏单（与两个运营台同一个病根）。
 *
 * 现在：
 *   ① 后端 `?has_documents=1` 判定「有发票 **或** 有附件」（见
 *      `backend/apps/transactions/api/v1/filters.py`）；
 *   ② 本页自己按页取全（不再借用 store —— store 的 `orders` 是**分页语义**，
 *      被 PoOrderList 共用，塞进全量会打乱那边的翻页）。
 */
const loading = ref(true)
const error = ref('')
const truncated = ref(false)
const total = ref(0)
const allOrders = ref([])

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    const { orders: rows, total: n, truncated: t } = await fetchAllOrderPages({
      has_documents: 1,
    })
    allOrders.value = rows
    total.value = n
    truncated.value = t
  } catch (e) {
    // 原实现走 store，异常被 store 吞成 console.error ⇒ 取数失败与"没有文档"长得一样
    error.value = extractErrorMessage(e?.response?.data ?? e, 'Could not load your documents.')
  } finally {
    loading.value = false
  }
})

const rows = computed(() =>
  allOrders.value
    .map((o) => ({
      order: o,
      invoice: o.invoice || null,
      attachments: o.attachments || [],
    }))
    // 服务端已按 `has_documents=1` 筛过；这里保留同一判据作为**兜底**，
    // 万一后端参数被忽略，也不至于渲染出一堆没有文档的空行。
    .filter((r) => r.invoice || r.attachments.length)
)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Download Center</h1>
        <p class="po-page-subtitle">
          Invoices and PO attachments for your orders.
          <span class="po-muted" data-testid="download-total">({{ total }})</span>
        </p>
      </div>
    </div>

    <div class="po-card">
      <p v-if="error" class="po-dl-error" data-testid="download-error">{{ error }}</p>
      <p v-if="truncated" class="po-dl-warn" data-testid="download-truncated">
        Showing the first {{ allOrders.length }} of {{ total }} documents — older ones are not
        listed here. Contact us if you need an earlier invoice.
      </p>
      <table class="po-table" v-if="rows.length">
        <thead>
          <tr><th>Order</th><th>Status</th><th>Invoice</th><th>PO Attachments</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.order.id">
            <td class="po-mono">{{ r.order.order_no }}</td>
            <td><StatusBadge :status="r.order.status" /></td>
            <td>
              <span v-if="r.invoice" class="po-tag">{{ r.invoice.invoice_no }}</span>
              <span v-else class="po-muted">—</span>
            </td>
            <td>
              <!-- ★ 2026-11-27（A-244）：「—」既可能是"没有"也可能是"没加载出来"，
                   客户分不清。明确写 No attachment，有附件时给数量。 -->
              <span v-if="r.attachments.length" class="po-tag">
                {{ r.attachments.length }} file{{ r.attachments.length === 1 ? '' : 's' }}
              </span>
              <span v-else class="po-muted" data-testid="no-attachment">No attachment</span>
            </td>
            <td>
              <div class="po-row">
                <button
                  v-if="r.invoice"
                  class="po-btn po-btn-primary po-btn-sm"
                  @click="downloadInvoicePdf(r.invoice.id)"
                >Invoice PDF</button>
                <button
                  v-for="a in r.attachments"
                  :key="a.id"
                  class="po-btn po-btn-outline po-btn-sm"
                  @click="downloadPoAttachment(a.id, a.original_filename)"
                >PO {{ a.id }}</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="po-empty">Loading…</div>
      <div v-else-if="error" class="po-empty" data-testid="download-error-empty">
        Your documents could not be loaded — see the message above.
      </div>
      <!-- ★ 2026-11-27（A-196）：空态此前只有一句 "No downloadable documents yet." ——
           客户带着"我明明有 2 个订单"的预期进来，看到这句会以为系统坏了。
           真实原因有两类，必须说清楚；另外 SDS/COA 本来就不在这个页面
           （它们是**产品级**文档，挂在产品详情页），也要给出可走的路。 -->
      <div v-else class="po-empty" data-testid="download-empty">
        <p style="margin:0 0 8px">No downloadable documents yet.</p>
        <p class="po-muted" style="margin:0 0 8px; font-size:13px; line-height:1.5">
          This page lists <strong>invoices</strong> (available after we issue one) and
          <strong>the PO file you uploaded</strong>. Orders that have neither will not appear here.
        </p>
        <p class="po-muted" style="margin:0; font-size:13px; line-height:1.5">
          Looking for a safety data sheet (SDS) or CoA? Those are product documents —
          open the product page and use its Documents section.
          <router-link to="/products" style="color:var(--color-primary)">Browse products →</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ★ S5 P-2：取数失败 / 超出翻页上限的显式提示（不再静默空态） */
.po-dl-error {
  margin: 0 0 10px;
  padding: 8px 12px;
  border: 1px solid var(--color-danger, #dc2626);
  border-radius: 4px;
  background: var(--color-danger-subtle, #fef2f2);
  color: var(--color-danger, #dc2626);
  font-size: 13px;
  line-height: 1.45;
}
.po-dl-warn {
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
