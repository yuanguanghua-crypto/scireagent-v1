<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Inventory Desk</h1>
        <p class="po-page-sub">Stock levels, receipts and adjustments (internal)</p>
      </div>
      <div class="po-page-actions">
        <button class="po-btn po-btn-outline" @click="load" :disabled="loading">Refresh</button>
        <button class="po-btn po-btn-accent" @click="openReceiptNew" data-testid="inv-receipt-new">+ New Stock Row</button>
      </div>
    </div>

    <div class="po-card" style="margin-bottom: 12px">
      <div class="po-filter-row">
        <div class="po-field" style="flex: 2">
          <label class="po-label">Search</label>
          <input v-model.trim="filters.search" class="po-input" placeholder="SKU code or product name"
                 data-testid="inv-search" @keyup.enter="load" />
        </div>
        <div class="po-field">
          <label class="po-label">Location</label>
          <select v-model="filters.location" class="po-select" data-testid="inv-location">
            <option value="">All</option>
            <option value="MAIN">Main Warehouse</option>
            <option value="EU">EU Warehouse</option>
            <option value="US">US Warehouse</option>
          </select>
        </div>
        <div class="po-field">
          <label class="po-label">Low stock ≤</label>
          <input v-model.number="filters.lowStock" type="number" min="0" class="po-input"
                 data-testid="inv-low-stock" @keyup.enter="load" />
        </div>
        <div class="po-field" style="align-self: flex-end">
          <button class="po-btn po-btn-primary" @click="load" :disabled="loading">Apply</button>
        </div>
      </div>
    </div>

    <!-- ★ 2026-10-28（4a）：已纳管、但一行库存都没有的 SKU。
         它们的可用量为 0 ⇒ 下单会被全部拦下；而库存表只列 Inventory 行，
         所以它们在下面**根本不会出现** ⇒ 必须单独在这里给可见性。 -->
    <div v-if="gaps.count" class="po-card" data-testid="inv-tracked-gaps"
         style="border-left:4px solid var(--color-red-600, #dc2626); background:rgba(220,38,38,.06)">
      <strong>{{ gaps.count }} SKU(s) tracked but with no stock rows</strong>
      <p class="po-muted" style="margin:4px 0 8px">
        These SKUs are marked as stock-managed but have zero available —
        <b>every order for them will be blocked</b>. They do not appear in the table below
        (it only lists inventory rows). Add a receipt, or stop tracking them.
      </p>
      <div class="po-mono" style="font-size:13px">
        {{ gaps.items.slice(0, 10).map(i => i.sku_code).join(' · ') }}
        <span v-if="gaps.items.length > 10"> … +{{ gaps.items.length - 10 }} more</span>
      </div>
    </div>

    <!-- ★ A-260：脱管被拒 ⇒ 三个数落页（原先只有 3 秒 toast，抄不下来） -->
    <div v-if="stopError" class="po-callout danger" data-testid="inv-stop-error"
         style="margin-bottom: 12px">
      <div class="po-between">
        <strong data-testid="inv-stop-error-title">
          Could not stop tracking {{ stopError.skuCode }}
        </strong>
        <button class="po-btn po-btn-outline po-btn-sm" data-testid="inv-stop-error-dismiss"
                @click="stopError = null">Dismiss</button>
      </div>
      <p class="po-muted" style="margin:6px 0 10px">{{ stopError.message }}</p>
      <div class="po-row" style="gap:28px">
        <span>available: <b class="po-mono" data-testid="inv-stop-available">{{ stopError.available }}</b></span>
        <span>allocated: <b class="po-mono" data-testid="inv-stop-allocated">{{ stopError.allocated }}</b></span>
        <span>reserved allocations:
          <b class="po-mono" data-testid="inv-stop-reserved">{{ stopError.reserved }}</b></span>
      </div>
      <p class="po-muted" style="margin:10px 0 0">
        Clear them first — adjust the stock to 0, or release the reservations from the order side.
      </p>
    </div>

    <div class="po-card">
      <table class="po-table" data-testid="inv-table">
        <thead>
          <tr>
            <th>SKU</th><th>Product</th><th>Lot</th><th>Location</th>
            <th style="text-align:right">Available</th><th style="text-align:right">Allocated</th>
            <th style="text-align:right">On hand</th><th>Tracked</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="9" style="text-align:center">Loading…</td></tr>
          <tr v-else-if="!rows.length"><td colspan="9" style="text-align:center">No inventory rows.</td></tr>
          <tr v-for="r in rows" :key="r.id" :data-testid="'inv-row-' + r.sku_code"
              :data-location="r.location"
              :data-tracked="r.is_stock_tracked === false ? 'no' : 'yes'"
              :class="{ 'po-row-low': r.is_stock_tracked !== false && r.available <= lowStockThreshold,
                        'po-row-untracked': r.is_stock_tracked === false }">
            <td class="po-mono">{{ r.sku_code }}</td>
            <td>{{ r.product_name }}</td>
            <td>{{ r.lot_number || '—' }}</td>
            <td>{{ r.location }}</td>
            <td style="text-align:right" class="po-mono">{{ r.available }}</td>
            <td style="text-align:right" class="po-mono">{{ r.allocated }}</td>
            <td style="text-align:right" class="po-mono">{{ r.on_hand }}</td>
            <!-- ★ A-260：`is_stock_tracked === false` 才显示 No。字段缺失（老响应/缓存）
                 时按 Yes 处理 —— 与后端默认值一致，宁可"看起来正常"也不误标成脱管。 -->
            <td class="po-mono" data-testid="inv-tracked-cell">
              <span v-if="r.is_stock_tracked === false" data-testid="inv-tracked-no">No</span>
              <span v-else data-testid="inv-tracked-yes">Yes</span>
            </td>
            <td style="white-space: nowrap">
              <button class="po-btn po-btn-primary po-btn-sm" data-testid="inv-receipt-btn"
                      @click="openReceipt(r)">Receipt</button>
              <button class="po-btn po-btn-outline po-btn-sm" data-testid="inv-adjust-btn"
                      @click="openAdjust(r)">Adjust</button>
              <button class="po-btn po-btn-outline po-btn-sm" data-testid="inv-detail-btn"
                      @click="openDetail(r)">History</button>
              <!-- ★ A-260：已脱管的行不再渲染「Stop tracking」—— 点了后端是 no-op 却返回 200，
                   正是 QA 报的"点了没任何反应"。 -->
              <button v-if="r.is_stock_tracked !== false" class="po-btn po-btn-outline po-btn-sm"
                      data-testid="inv-untrack-btn" @click="stopTracking(r)">Stop tracking</button>
              <span v-else class="po-muted" data-testid="inv-untracked-note">Not tracked</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 入库弹窗 -->
    <div v-if="receipt.visible" class="po-modal-mask" data-testid="inv-receipt-modal">
      <div class="po-card po-modal">
        <h2 class="po-modal-title">Stock Receipt</h2>
        <div v-if="receipt.searchMode" class="po-field">
          <label class="po-label">Search product</label>
          <input v-model.trim="receipt.search" class="po-input" placeholder="Product name / SKU"
                 @input="searchProducts" data-testid="inv-receipt-search" />
          <div v-if="receipt.results.length" class="po-search-pop">
            <button v-for="p in receipt.results" :key="p.id" type="button"
                    class="po-search-item" data-testid="inv-search-item" @click="pickProduct(p)">
              {{ p.name }}
            </button>
          </div>
          <div v-if="receipt.productName" class="po-search-picked">已选：{{ receipt.productName }}</div>
        </div>
        <div v-else class="po-field"><label class="po-label">Product</label>
          <div>{{ receipt.productName }}</div></div>
        <div class="po-field"><label class="po-label">SKU</label>
          <select v-model="receipt.skuId" class="po-select" data-testid="inv-receipt-sku">
            <option value="" disabled>— SKU —</option>
            <option v-for="s in receipt.skus" :key="s.id" :value="s.id">
              {{ s.sku_code }} · {{ s.pack_size }}
            </option>
          </select>
        </div>
        <div class="po-field"><label class="po-label">Location</label>
          <select v-model="receipt.location" class="po-select" data-testid="inv-receipt-location">
            <option value="MAIN">Main Warehouse</option>
            <option value="EU">EU Warehouse</option>
            <option value="US">US Warehouse</option>
          </select>
        </div>
        <div class="po-field"><label class="po-label">Quantity</label>
          <input v-model.number="receipt.quantity" type="number" min="1" class="po-input"
                 data-testid="inv-receipt-qty" />
        </div>
        <div class="po-field"><label class="po-label">Reason *</label>
          <input v-model.trim="receipt.reason" class="po-input" data-testid="inv-receipt-reason"
                 placeholder="e.g. PO-1234 到货 / 盘盈" />
        </div>
        <div class="po-modal-actions">
          <button class="po-btn po-btn-outline" @click="receipt.visible = false">Cancel</button>
          <button class="po-btn po-btn-accent" data-testid="inv-receipt-submit"
                  :disabled="submitting" @click="submitReceipt">Confirm Receipt</button>
        </div>
      </div>
    </div>

    <!-- 调整弹窗 -->
    <div v-if="adjust.visible" class="po-modal-mask" data-testid="inv-adjust-modal">
      <div class="po-card po-modal">
        <h2 class="po-modal-title">Stock Adjust</h2>
        <div class="po-field"><label class="po-label">Row</label>
          <div class="po-mono">{{ adjust.skuCode }} @ {{ adjust.location }} (available {{ adjust.available }})</div>
        </div>
        <div class="po-field"><label class="po-label">Delta（±，结果不可为负）</label>
          <input v-model.number="adjust.delta" type="number" class="po-input" data-testid="inv-delta" />
        </div>
        <div class="po-field"><label class="po-label">Reason *</label>
          <input v-model.trim="adjust.reason" class="po-input" data-testid="inv-adjust-reason"
                 placeholder="e.g. 盘点差异 -2" />
        </div>
        <div class="po-modal-actions">
          <button class="po-btn po-btn-outline" @click="adjust.visible = false">Cancel</button>
          <button class="po-btn po-btn-primary" data-testid="inv-adjust-submit"
                  :disabled="submitting" @click="submitAdjust">Confirm Adjust</button>
        </div>
      </div>
    </div>

    <!-- 详情/流水弹窗 -->
    <div v-if="detail.visible" class="po-modal-mask" data-testid="inv-detail-modal">
      <div class="card po-modal">
        <h2 class="po-modal-title">History — {{ detail.skuCode }} @ {{ detail.location }}</h2>
        <h3 class="po-sub-title">Current reserved allocations</h3>
        <table class="po-table" v-if="detail.allocations.length">
          <thead><tr><th>Order item</th><th>Qty</th><th>Status</th></tr></thead>
          <tbody>
            <tr v-for="a in detail.allocations" :key="a.id">
              <td class="po-mono">#{{ a.order_item_id }}</td>
              <td class="po-mono">{{ a.quantity }}</td>
              <td>{{ a.status }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="po-muted">No reserved allocations.</p>
        <h3 class="po-sub-title">Movements（最近 50）</h3>
        <table class="po-table" data-testid="inv-movements-table" v-if="detail.movements.length">
          <thead><tr><th>Kind</th><th>ΔAvail</th><th>ΔAlloc</th><th>Reason</th><th>At</th></tr></thead>
          <tbody>
            <tr v-for="m in detail.movements" :key="m.id">
              <td class="po-mono">{{ m.kind }}</td>
              <td class="po-mono">{{ m.delta_available }}</td>
              <td class="po-mono">{{ m.delta_allocated }}</td>
              <!-- ★ 2026-11-27（S6 A-086）：reason 里有机器占位符（`PLACEHOLDER:100`），
                   直接铺到表格里运营看不懂。做一层人类可读映射，未知格式仍原样显示
                   （不吞信息）。 -->
              <td>{{ humanReason(m.reason) }}</td>
              <td class="po-mono">{{ (m.created_at || '').slice(0, 19).replace('T', ' ') }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="po-muted">No movements.</p>
        <div class="po-modal-actions">
          <button class="po-btn po-btn-outline" @click="detail.visible = false">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getProducts, getProductDetail } from '@/api/products'
import {
  adjustStock, getInventoryDetail, getInventoryList,
  getTrackedGaps, receiptStock, setStockTracked,
} from '@/api/inventory'
import { useConfirm } from '@/composables/useConfirm'
import { toast } from '@/components/common'
import { extractErrorMessage } from '@/utils/http'

const { ask } = useConfirm()

const lowStockThreshold = 10
const loading = ref(false)
const submitting = ref(false)
const rows = ref([])
// ★ 2026-10-28（4a）：已纳管但无库存行的 SKU
const gaps = ref({ count: 0, items: [] })
const filters = reactive({ search: '', location: '', lowStock: '' })

/**
 * ★ A-260（2026-11-18 / S4）：脱管被拒的**持久**落位。
 *
 * 为什么不能只靠 toast：`POST /inventory/track/` 被拒时后端返回 400 + `STOCK_NOT_EMPTY`，
 * 响应体里其实已经把三个数算好了（`meta.error.details[0]`：
 * `available / allocated / reserved_allocations`）。但原先前端只读了
 * `meta.error.message`，然后 `toast.error(...)` —— 3 秒就没了。
 * 运营要照着这三个数去"调平库存 / 释放占用"，必须能在页面上**边看边操作**，
 * 所以三个数必须落页，而不是从一句滚动消失的提示里抄。
 *
 * 形状：`{ skuCode, message, available, allocated, reserved }`；`null` = 无错误。
 */
const stopError = ref(null)

/**
 * 把 `InventoryMovement.reason` 的机器写法翻成人类可读（S6 A-086）。
 *
 * 现状：占位库存的 reason 是 `PLACEHOLDER:100` —— 表格里原样显示，运营看不懂
 * 这是"初始占位 100 件"还是"某次真实入库"。
 * 其它已知格式（`receipt:*` / `adjust:*` / `cancel:*` / `timeout:168h:*`）本来就带业务含义，
 * 保持原样；**未知格式一律原样返回**，不做猜测、不吞信息。
 */
function humanReason(raw) {
  const r = (raw || '').trim()
  if (!r) return '—'
  const m = /^PLACEHOLDER:(\d+)$/.exec(r)
  if (m) return `初始占位 ${m[1]} 件（未真实入库，上线前需替换）`
  return r
}

async function load() {
  loading.value = true
  try {
    // ★ 2026-11-27（S6 A-227）：**必须显式要满页**。
    //   改前 params 里没有 page_size ⇒ 后端用默认 20 行 ⇒ 生产 25 行库存只显示 20 行，
    //   剩下 5 行（含 7 个无库存行的 SKU 中排在后面的）永远看不到。
    //   与 S5 P-2 修的"运营台只取一页导致漏单"完全同族。
    const params = { page_size: 500 }
    if (filters.search) params.search = filters.search
    if (filters.location) params.location = filters.location
    if (filters.lowStock !== '' && filters.lowStock !== null) params.low_stock = filters.lowStock
    const res = await getInventoryList(params)
    const data = res.data || res
    rows.value = Array.isArray(data) ? data : (data.results || [])
  } catch (e) {
    console.error('[InventoryDesk] load failed:', e)
  } finally {
    loading.value = false
  }
}
async function loadGaps() {
  try {
    const res = await getTrackedGaps()
    const data = res.data || res
    gaps.value = { count: data.count || 0, items: data.items || [] }
  } catch (e) { console.error('[InventoryDesk] tracked-gaps failed:', e) }
}

/** 脱管：后端要求该 SKU 无库存、无占用，否则 400 STOCK_NOT_EMPTY。 */
async function stopTracking(row) {
  const ok = await ask({
    title: 'Stop tracking stock',
    message:
      `Stop tracking ${row.sku_code}?\n\n` +
      'It will no longer be validated against stock on checkout ' +
      '(treated as made-to-order / unlimited). ' +
      'Blocked if it still holds stock or allocations.',
    confirmText: 'Stop tracking',
    danger: true,
  })
  if (!ok) return
  stopError.value = null
  try {
    await setStockTracked(row.sku_id, false)
    toast.success(`Stopped tracking ${row.sku_code}`)
    // 脱管**不会删掉 Inventory 行**（后端只翻 SKU.is_stock_tracked）⇒ 行会带着
    // `is_stock_tracked=false` 重新出现在表里，前端标 No 并置灰。这正是要的行为：
    // 行消失会让人以为数据被删了。
    await Promise.all([load(), loadGaps()])
  } catch (e) {
    const data = e?.response?.data ?? e
    const err = data?.meta?.error || {}
    const d = Array.isArray(err.details) ? (err.details[0] || {}) : {}
    // ⚠️ 这里**刻意不再** `toast.error(...)`：`utils/http.js` 的响应拦截器
    //    已经对每个失败响应弹过一次 `ElMessage.error(extractErrorMessage(...))`。
    //    原先 `alert → toast` 那一轮改出来的 `toast.error` 与拦截器叠加，会一次失败
    //    弹两条一模一样的红条（实测代码路径：http.js 错误分支 → 直接 reject）。
    //    持久信息由下面的 `stopError` 横幅承担，瞬时不重复。
    stopError.value = {
      skuCode: row.sku_code,
      message: extractErrorMessage(data, 'Could not stop tracking this SKU.'),
      available: d.available,
      allocated: d.allocated,
      reserved: d.reserved_allocations,
    }
  }
}

onMounted(() => { load(); loadGaps() })

/* ── 入库 ── */
const receipt = reactive({
  visible: false, searchMode: false, search: '', results: [], productName: '',
  skuId: '', skus: [], location: 'MAIN', quantity: 1, batchId: null, reason: '',
})

function openReceipt(row) {
  receipt.visible = true; receipt.searchMode = false
  receipt.productName = row.product_name; receipt.search = ''
  receipt.results = []; receipt.skus = [{ id: row.sku_id, sku_code: row.sku_code, pack_size: '' }]
  receipt.skuId = row.sku_id; receipt.location = row.location
  receipt.quantity = 1; receipt.reason = ''
}

async function openReceiptNew() {
  receipt.visible = true; receipt.searchMode = true
  receipt.productName = ''; receipt.search = ''; receipt.results = []
  receipt.skus = []; receipt.skuId = ''; receipt.location = 'MAIN'
  receipt.quantity = 1; receipt.reason = ''
}

let _searchTimer = null
async function searchProducts() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(async () => {
    if (!receipt.search) { receipt.results = []; return }
    try {
      const res = await getProducts({ search: receipt.search, page_size: 8 })
      const data = res.data || res
      receipt.results = Array.isArray(data) ? data : (data.results || [])
    } catch (e) { console.error('[InventoryDesk] search failed:', e) }
  }, 250)
}

async function pickProduct(p) {
  receipt.productName = p.name; receipt.results = []
  try {
    const res = await getProductDetail(p.id)
    const data = res.data || res
    const prod = data.product || data
    receipt.skus = prod.skus || []
    receipt.skuId = receipt.skus.length ? receipt.skus[0].id : ''
  } catch (e) { console.error('[InventoryDesk] product detail failed:', e) }
}

async function submitReceipt() {
  // ★ A-260 顺带修（同一类"点了没反应"）：原先这里静默 return —— 一个请求都不发，
  //   页面也没有任何提示，用户只会觉得按钮坏了。失败响应的 toast 由 http 拦截器负责，
  //   这里只补**根本没发请求**的那条路径。
  if (!receipt.skuId || receipt.quantity < 1 || !receipt.reason) {
    toast.warning('Pick a SKU, enter a quantity ≥ 1, and fill in the reason.')
    return
  }
  submitting.value = true
  try {
    await receiptStock({
      sku_id: receipt.skuId, location: receipt.location, quantity: receipt.quantity,
      batch_id: receipt.batchId || null, reason: receipt.reason,
    })
    receipt.visible = false
    await load()
  } catch (e) { console.error('[InventoryDesk] receipt failed:', e) } finally { submitting.value = false }
}

/* ── 调整 ── */
const adjust = reactive({ visible: false, id: null, skuCode: '', location: '', available: 0, delta: 0, reason: '' })

function openAdjust(row) {
  adjust.visible = true; adjust.id = row.id
  adjust.skuCode = row.sku_code; adjust.location = row.location; adjust.available = row.available
  adjust.delta = 0; adjust.reason = ''
}

async function submitAdjust() {
  // 同上：`delta=0` 后端也会 400（`delta 不能为 0`），但那是白跑一次请求；
  // 这里前置拦下并说明原因，避免"点了没反应"。
  if (!adjust.delta || !adjust.reason) {
    toast.warning('Enter a non-zero delta and fill in the reason.')
    return
  }
  submitting.value = true
  try {
    await adjustStock(adjust.id, { delta: adjust.delta, reason: adjust.reason })
    adjust.visible = false
    await load()
  } catch (e) { console.error('[InventoryDesk] adjust failed:', e) } finally { submitting.value = false }
}

/* ── 详情/流水 ── */
const detail = reactive({ visible: false, skuCode: '', location: '', movements: [], allocations: [] })

async function openDetail(row) {
  try {
    const res = await getInventoryDetail(row.id)
    const data = res.data || res
    detail.skuCode = data.sku_code; detail.location = data.location
    detail.movements = data.movements || []
    detail.allocations = data.active_allocations || []
    detail.visible = true
  } catch (e) { console.error('[InventoryDesk] detail failed:', e) }
}
</script>

<style scoped>
.po-page-actions { display: flex; gap: 8px; }
.po-filter-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
.po-filter-row .po-field { display: flex; flex-direction: column; gap: 4px; }
.po-row-low td { background: rgba(255, 99, 71, 0.08); }
/* ★ A-260：已脱管（SKU 不再参与缺货校验）—— 置灰，别让它看起来像一行普通库存 */
.po-row-untracked td { opacity: .55; }
.po-modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex;
  align-items: flex-start; justify-content: center; z-index: 60; padding-top: 8vh; }
.po-modal { width: min(560px, 92vw); max-height: 82vh; overflow: auto; }
.po-modal-title { font-size: 18px; font-weight: 700; margin-bottom: 12px; }
.po-modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.po-sub-title { font-size: 13px; font-weight: 700; margin: 14px 0 6px; color: #555; }
.po-muted { color: #888; font-size: 13px; }
.po-search-pop { border: 1px solid #ddd; border-radius: 6px; max-height: 180px; overflow: auto; }
.po-search-item { display: block; width: 100%; text-align: left; padding: 6px 10px;
  background: none; border: none; cursor: pointer; }
.po-search-item:hover { background: #f2f4f8; }
.po-search-picked { margin-top: 6px; font-size: 13px; color: #333; }
</style>
