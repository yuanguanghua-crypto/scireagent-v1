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

    <div class="po-card">
      <table class="po-table" data-testid="inv-table">
        <thead>
          <tr>
            <th>SKU</th><th>Product</th><th>Lot</th><th>Location</th>
            <th style="text-align:right">Available</th><th style="text-align:right">Allocated</th>
            <th style="text-align:right">On hand</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="8" style="text-align:center">Loading…</td></tr>
          <tr v-else-if="!rows.length"><td colspan="8" style="text-align:center">No inventory rows.</td></tr>
          <tr v-for="r in rows" :key="r.id" :class="{ 'po-row-low': r.available <= lowStockThreshold }">
            <td class="po-mono">{{ r.sku_code }}</td>
            <td>{{ r.product_name }}</td>
            <td>{{ r.lot_number || '—' }}</td>
            <td>{{ r.location }}</td>
            <td style="text-align:right" class="po-mono">{{ r.available }}</td>
            <td style="text-align:right" class="po-mono">{{ r.allocated }}</td>
            <td style="text-align:right" class="po-mono">{{ r.on_hand }}</td>
            <td style="white-space: nowrap">
              <button class="po-btn po-btn-primary po-btn-sm" data-testid="inv-receipt-btn"
                      @click="openReceipt(r)">Receipt</button>
              <button class="po-btn po-btn-outline po-btn-sm" data-testid="inv-adjust-btn"
                      @click="openAdjust(r)">Adjust</button>
              <button class="po-btn po-btn-outline po-btn-sm" data-testid="inv-detail-btn"
                      @click="openDetail(r)">History</button>
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
                    class="po-search-item" @click="pickProduct(p)">
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
              <td>{{ m.reason || '—' }}</td>
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
import { adjustStock, getInventoryDetail, getInventoryList, receiptStock } from '@/api/inventory'

const lowStockThreshold = 10
const loading = ref(false)
const submitting = ref(false)
const rows = ref([])
const filters = reactive({ search: '', location: '', lowStock: '' })

async function load() {
  loading.value = true
  try {
    const params = {}
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
onMounted(load)

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
  if (!receipt.skuId || receipt.quantity < 1 || !receipt.reason) return
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
  if (!adjust.delta || !adjust.reason) return
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
