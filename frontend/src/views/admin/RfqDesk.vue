<script setup>
/**
 * RFQ Inbox —— 运营台「询价单收件箱」。
 *
 * 存在原因（2026-10-22）：此前客户提交的 RFQ **只有创建入口，没有任何查询入口** ——
 * 详情按 `contact_email == 当前用户邮箱` 过滤，连 staff 也 404，运营只能进 Django admin。
 * 本页对接 `GET /quote-requests/manage/`（`IsProcurementOrAdmin`）。
 *
 * 2026-10-23 起**不再是只读**：详情页可填写报价并通知客户，
 * 对接 `POST /quote-requests/:id/quote/`。后端会把状态推进到 `quoted`。
 * （此前 `QUOTED` 只在枚举里定义、全仓没有代码会写它 —— 运营点得到"已报价"状态但永远走不到。）
 */
import { onMounted, ref, computed } from 'vue'
import { getQuoteRequests, getQuoteRequestDetail, saveQuote } from '@/api/rfq'
import { extractErrorMessage } from '@/utils/http'
import ErrorBanner from '@/components/common/ErrorBanner.vue'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

const search = ref('')
const statusFilter = ref('')

const detail = ref(null)
const detailLoading = ref(false)
const detailError = ref('')

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'reviewing', label: 'Reviewing' },
  { value: 'quoted', label: 'Quoted' },
  { value: 'closed', label: 'Closed' },
]

const subtitle = computed(() => {
  if (loading.value) return 'Loading…'
  if (!total.value) return 'No quote requests'
  return `${total.value} quote request(s)`
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page_size: 100 }
    if (search.value.trim()) params.search = search.value.trim()
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getQuoteRequests(params)
    const payload = res.data ?? res
    rows.value = Array.isArray(payload) ? payload : (payload.results || [])
    total.value = res.meta?.pagination?.count ?? rows.value.length
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load quote requests.")
  } finally {
    loading.value = false
  }
}

async function openRow(r) {
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  resetQuoteForm()
  try {
    const res = await getQuoteRequestDetail(r.id)
    const d = res.data ?? res
    detail.value = d
    // 回显已有报价：否则重新打开详情时表单是空的，容易重复报价
    if (d.quoted_total != null || d.quoted_note) {
      quoteForm.value = {
        quoted_total: d.quoted_total != null ? String(d.quoted_total) : '',
        quoted_currency: d.quoted_currency || 'USD',
        quoted_valid_until: d.quoted_valid_until || '',
        quoted_note: d.quoted_note || '',
      }
    }
  } catch (e) {
    detailError.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load this quote request.")
  } finally {
    detailLoading.value = false
  }
}

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString()
}

/**
 * 明细的"产品"标签。
 *
 * ⚠️ RFQ 明细允许**只填产品名不挂产品**（`product_id` 可为 null；客户从自由文本提交时就是这种），
 *    所以 `product_name` 与 `product_id` 都可能为空。此时必须显示占位符 ——
 *    原实现写 `#${it.product_id}`，为空时会渲染成 **`#null`**（实测截图确认过），
 *    运营看到会以为是数据坏了。
 */
function itemProductLabel(it) {
  if (it.product_name) return it.product_name
  if (it.product_id) return `#${it.product_id}`
  return '—'
}

// ── 报价表单 ──────────────────────────────────────────────────────────
// 设计取舍：
//  - 金额允许留空：可以只回执"请联系我们"，不必为了走完流程编一个数字
//  - 默认勾选"通知客户"：填了报价本来就是要发出去的，默认关反而要人多点一下
//  - 提交成功后重新拉详情+列表，而不是本地改状态 —— 以后端为准，避免 UI 与库不一致
const CURRENCY_OPTIONS = ['USD', 'EUR', 'GBP', 'CNY', 'JPY', 'AUD']

function emptyQuoteForm() {
  return {
    quoted_total: '',
    quoted_currency: 'USD',
    quoted_valid_until: '',
    quoted_note: '',
  }
}

const quoteForm = ref(emptyQuoteForm())
const quoting = ref(false)
const quoteError = ref('')
const quoteResult = ref(null)

function resetQuoteForm() {
  quoteForm.value = emptyQuoteForm()
  quoteError.value = ''
  quoteResult.value = null
}

async function submitQuote() {
  if (!detail.value) return
  quoteError.value = ''
  quoteResult.value = null
  quoting.value = true
  try {
    const raw = quoteForm.value
    const payload = {
      quoted_currency: raw.quoted_currency || 'USD',
      quoted_note: (raw.quoted_note || '').trim(),
      // ★ 空串必须转 null：后端 DecimalField 收到 '' 会直接 400
      quoted_total: raw.quoted_total === '' ? null : raw.quoted_total,
      // ★ 日期同理：空串会让 Django DateField 报格式错误，必须传 null
      quoted_valid_until: raw.quoted_valid_until || null,
      notify_customer: true,
    }
    const res = await saveQuote(detail.value.id, payload)
    quoteResult.value = res.data ?? res
    const id = detail.value.id
    await openRow({ id })   // 重新拉详情，状态以后端为准
    await load()
  } catch (e) {
    quoteError.value = extractErrorMessage(
      e?.response?.data ?? e, "Couldn't save the quotation.",
    )
  } finally {
    quoting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">RFQ Inbox</h1>
        <p class="po-page-subtitle">{{ subtitle }} · customer quote requests</p>
      </div>
      <button class="po-btn po-btn-outline" @click="load" :disabled="loading">Refresh</button>
    </div>

    <ErrorBanner :message="error" title="Couldn't load quote requests" kind="load" />

    <div class="po-filter-row">
      <input
        v-model.trim="search"
        class="po-input"
        style="max-width: 280px"
        placeholder="Search name, email, company…"
        @keyup.enter="load"
      />
      <select v-model="statusFilter" class="po-input" style="max-width: 180px" @change="load">
        <option v-for="o in STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <button class="po-btn po-btn-primary" @click="load" :disabled="loading">Apply</button>
    </div>

    <div class="rfq-grid">
      <!-- 左：列表 -->
      <div class="po-card">
        <div class="rfq-list-scroll" v-if="rows.length">
        <table class="po-table">
          <thead>
            <tr>
              <th>ID</th><th>Received</th><th>Contact</th><th>Company</th>
              <th>Items</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id" :class="{ 'is-active': detail && detail.id === r.id }">
              <td class="po-mono">#{{ r.id }}</td>
              <td class="po-muted">{{ fmtDate(r.created_at) }}</td>
              <td>
                <div>{{ r.contact_name }}</div>
                <div class="po-muted po-mono rfq-email">{{ r.contact_email }}</div>
              </td>
              <!-- Company / Country 合并一列：8 列在 1.6fr（约 520px）里放不下，
                   拆开必然横向溢出（实测 Country 被压成 "Chi"）。国家放详情里看。 -->
              <td>
                <div>{{ r.company_name || '—' }}</div>
                <div v-if="r.country" class="po-muted">{{ r.country }}</div>
              </td>
              <td class="po-num">{{ r.items_count }}</td>
              <td><span class="po-tag">{{ r.status }}</span></td>
              <td><button class="po-btn po-btn-outline po-btn-sm" @click="openRow(r)">View</button></td>
            </tr>
          </tbody>
        </table>
        </div>
        <div v-else-if="loading" class="po-empty">Loading…</div>
        <div v-else class="po-empty">No quote requests yet.</div>
      </div>

      <!-- 右：详情 -->
      <div class="po-card" v-if="detailLoading || detail || detailError">
        <div v-if="detailLoading" class="po-empty">Loading…</div>
        <ErrorBanner v-else-if="detailError" :message="detailError" title="Couldn't load this quote request" kind="load" />
        <template v-else-if="detail">
          <h2 class="rfq-detail-title">RFQ #{{ detail.id }}</h2>
          <dl class="rfq-detail-list">
            <dt>Contact</dt><dd>{{ detail.contact_name }}</dd>
            <dt>Email</dt><dd class="po-mono">{{ detail.contact_email }}</dd>
            <dt>Phone</dt><dd>{{ detail.contact_phone || '—' }}</dd>
            <dt>Company</dt><dd>{{ detail.company_name || '—' }}</dd>
            <dt>Country</dt><dd>{{ detail.country || '—' }}</dd>
            <dt>Status</dt><dd><span class="po-tag">{{ detail.status }}</span></dd>
            <dt>Received</dt><dd>{{ fmtDate(detail.created_at) }}</dd>
            <dt>Notes</dt><dd>{{ detail.notes || '—' }}</dd>
          </dl>

          <h3 class="rfq-items-title">Items ({{ (detail.items || []).length }})</h3>
          <table class="po-table" v-if="(detail.items || []).length">
            <thead>
              <tr><th>Product</th><th>SKU</th><th>Qty</th><th>Note</th></tr>
            </thead>
            <tbody>
              <tr v-for="it in detail.items" :key="it.id">
                <td>{{ itemProductLabel(it) }}</td>
                <td class="po-mono">{{ it.sku_code || '—' }}</td>
                <td class="po-num">{{ it.quantity }}</td>
                <td>{{ it.note || '—' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="po-empty">No items.</div>

          <!-- 报价：填完即推进状态到 quoted 并给客户发邮件 -->
          <div class="rfq-quote">
            <h3 class="rfq-items-title">
              {{ detail.status === 'quoted' ? 'Quotation' : 'Send a quotation' }}
            </h3>
            <p v-if="detail.quoted_at" class="po-muted rfq-quote-meta">
              Quoted on {{ fmtDate(detail.quoted_at) }}
            </p>

            <ErrorBanner
              v-if="quoteError"
              :message="quoteError"
              title="Couldn't save the quotation"
              kind="load"
            />

            <div class="rfq-quote-grid">
              <label class="rfq-field">
                <span>Total amount</span>
                <input
                  v-model="quoteForm.quoted_total"
                  class="po-input"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="Leave empty to reply without a price"
                />
              </label>
              <label class="rfq-field">
                <span>Currency</span>
                <select v-model="quoteForm.quoted_currency" class="po-input">
                  <option v-for="c in CURRENCY_OPTIONS" :key="c" :value="c">{{ c }}</option>
                </select>
              </label>
              <label class="rfq-field">
                <span>Valid until</span>
                <input v-model="quoteForm.quoted_valid_until" class="po-input" type="date" />
              </label>
            </div>

            <label class="rfq-field rfq-field--full">
              <span>Note to customer</span>
              <textarea
                v-model="quoteForm.quoted_note"
                class="po-input"
                rows="3"
                placeholder="Lead time, shipping terms, minimum order quantity…"
              ></textarea>
            </label>

            <div class="rfq-quote-actions">
              <button class="po-btn po-btn-primary" :disabled="quoting" @click="submitQuote">
                {{ quoting
                  ? 'Saving…'
                  : (detail.status === 'quoted' ? 'Update quotation' : 'Save & notify customer') }}
              </button>
              <span v-if="quoteResult && quoteResult.customer_notified" class="rfq-quote-ok">
                ✓ Saved and emailed to {{ detail.contact_email }}
              </span>
              <span v-else-if="quoteResult" class="rfq-quote-ok">
                ✓ Saved
              </span>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.po-filter-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.rfq-grid { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 16px; align-items: start; }

/* ★ 8 列的表格在 1.6fr 里放不下，会**溢出到右侧详情卡片底下**（实测截图：Country 列被压成 "Chi"）。
   两个 card 都要 `min-width: 0`（grid 子项默认 min-width:auto，不会收缩），
   表格容器自己横向滚动，别让内容顶出去。 */
.rfq-grid > .po-card { min-width: 0; overflow: hidden; }
.rfq-list-scroll { overflow-x: auto; }
/* 不再硬性设 min-width：7 列 + 长邮箱会撑到 876px，容器只有 ~640px ⇒ 必然横向滚动。
   正确做法是让长邮箱**可断行**（`anywhere` 允许在任意位置断开，中文/邮箱都适用），
   让表格自然收缩；横向滚动只作为兜底，不当作常态。 */
/* ★ 必须 `table-layout: fixed` + 显式列宽。
   自动布局下表格**按内容撑宽**，`max-width` 写在单元格内的 div 上完全无效
   （实测：给邮箱 div 设 220/185/168px，表格总宽一直是 652px 不变）。
   固定布局后表格宽度=容器宽度，长邮箱靠 break-all 换行。 */
.rfq-list-scroll .po-table { width: 100%; table-layout: fixed; }
.rfq-list-scroll .po-table th:nth-child(1) { width: 48px; }   /* ID */
.rfq-list-scroll .po-table th:nth-child(2) { width: 92px; }   /* Received */
.rfq-list-scroll .po-table th:nth-child(4) { width: 96px; }   /* Company */
.rfq-list-scroll .po-table th:nth-child(5) { width: 52px; }   /* Items */
.rfq-list-scroll .po-table th:nth-child(6) { width: 84px; }   /* Status */
.rfq-list-scroll .po-table th:nth-child(7) { width: 76px; }   /* View */
.rfq-email { overflow-wrap: anywhere; word-break: break-all; }

.po-table tbody tr.is-active { background: var(--color-bg-subtle, #f8f9fa); }
.rfq-detail-title { font-size: 16px; font-weight: 700; margin: 0 0 12px; }
.rfq-items-title { font-size: 14px; font-weight: 700; margin: 16px 0 8px; }
.rfq-detail-list { display: grid; grid-template-columns: 96px 1fr; gap: 6px 12px; margin: 0; }
.rfq-detail-list dt { color: var(--color-text-tertiary); font-size: 12px; }
.rfq-detail-list dd { margin: 0; font-size: 13px; word-break: break-word; }
.rfq-hint { font-size: 12px; margin-top: 12px; }

/* ── 报价表单 ── */
.rfq-quote {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--color-border);
}
.rfq-quote-meta { font-size: 12px; margin: 0 0 10px; }
.rfq-quote-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px 140px;
  gap: 10px;
}
.rfq-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-bottom: 10px;
  min-width: 0;
}
.rfq-field--full { width: 100%; }
.rfq-field textarea { resize: vertical; font-family: inherit; }
.rfq-quote-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.rfq-quote-ok { font-size: 12px; color: var(--color-success, #16a34a); }
@media (max-width: 1024px) {
  .rfq-quote-grid { grid-template-columns: 1fr; }
}
@media (max-width: 1024px) {
  .rfq-grid { grid-template-columns: 1fr; }
}
</style>
