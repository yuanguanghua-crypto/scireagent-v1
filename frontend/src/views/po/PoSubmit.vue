<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { submitPo, getOrderDetail } from '@/api/poPortal'
import { getProducts, getProductDetail } from '@/api/products'
import { SHIPPING_METHODS } from '@/config/poConstants'
import { formatCurrency } from '@/utils/helpers'

const router = useRouter()
const route = useRoute()
const submitting = ref(false)
const successOrderNo = ref('')
const reorderSourceId = ref('')

onMounted(() => {
  if (route.query.reorder) {
    reorderSourceId.value = route.query.reorder
    loadReorder()
  }
})

const form = reactive({
  po_number: '',
  grant_code: '',
  shipping_method: '',
  requested_delivery_date: '',
  shipping_name: '',
  shipping_address: '',
  shipping_phone: '',
  shipping_email: '',
  billing_name: '',
  billing_address: '',
  notes: '',
})

const items = ref([])
const files = ref([])
const searchTerm = ref('')

function addItem() {
  items.value.push({
    productId: null,
    productName: '',
    skus: [],
    skuId: null,
    quantity: 1,
    unitPrice: '',
    searchResults: [],
    searching: false,
  })
}

async function searchProducts(row, q) {
  if (!q || q.length < 2) {
    row.searchResults = []
    return
  }
  row.searching = true
  try {
    const res = await getProducts({ search: q, page_size: 8 })
    const payload = res.data || res
    row.searchResults = payload.results || payload.data || payload || []
  } finally {
    row.searching = false
  }
}

async function selectProduct(row, product) {
  row.productId = product.id
  row.productName = product.name
  row.searchResults = []
  try {
    const res = await getProductDetail(product.id)
    const detail = res.data || res
    // detail 端点把数据嵌套在 data.product 下（与 products store 一致）
    row.skus = detail.product?.skus || detail.skus || []
  } catch {
    row.skus = []
  }
}

function onSkuChange(row) {
  const sku = row.skus.find((s) => s.id === row.skuId)
  if (sku) row.unitPrice = sku.price
}

function removeItem(idx) {
  items.value.splice(idx, 1)
}

function onFileChange(e) {
  files.value = Array.from(e.target.files || [])
}

const grandTotal = computed(() =>
  items.value.reduce((sum, it) => sum + (Number(it.quantity) || 0) * (Number(it.unitPrice) || 0), 0)
)

async function loadReorder() {
  if (!reorderSourceId.value) return
  const res = await getOrderDetail(reorderSourceId.value)
  const o = res.data || res
  if (!o) return
  form.po_number = ''
  form.grant_code = o.grant_code || ''
  form.shipping_method = o.shipping_method || ''
  form.shipping_name = o.shipping_name || ''
  form.shipping_address = o.shipping_address || ''
  form.shipping_phone = o.shipping_phone || ''
  form.shipping_email = o.shipping_email || ''
  form.billing_name = o.billing_name || ''
  form.billing_address = o.billing_address || ''
  ;(o.items || []).forEach((it) => {
    items.value.push({
      productId: it.product_id,
      productName: it.product_name || `Product #${it.product_id}`,
      skus: it.sku_id ? [{ id: it.sku_id, sku_code: it.sku_code, pack_size: it.pack_size, price: it.unit_price }] : [],
      skuId: it.sku_id,
      quantity: it.quantity,
      unitPrice: it.unit_price,
      searchResults: [],
      searching: false,
    })
  })
}

async function handleSubmit() {
  if (!form.po_number) {
    alert('PO Number is required.')
    return
  }
  if (items.value.length === 0) {
    alert('Add at least one line item.')
    return
  }
  const invalid = items.value.some((it) => !it.skuId || !it.quantity || !it.unitPrice)
  if (invalid) {
    alert('Each line item requires a SKU, quantity and unit price.')
    return
  }
  submitting.value = true
  try {
    const payload = {
      ...form,
      items: items.value.map((it) => ({
        product_id: it.productId,
        sku_id: it.skuId,
        quantity: Number(it.quantity),
        unit_price: String(it.unitPrice),
      })),
    }
    const res = await submitPo({ data: payload, files: files.value })
    const data = res.data || res
    successOrderNo.value = data.order_no || 'submitted'
  } catch (err) {
    // 拦截器已 toast；此处静默
    console.error('[PoSubmit] submit failed:', err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="po-page">
    <div class="po-page-header">
      <div>
        <h1 class="po-page-title">Submit Purchase Order</h1>
        <p class="po-page-subtitle">Upload your PO and line items; we’ll confirm within 1 business day.</p>
      </div>
      <div class="po-row">
        <input v-model="reorderSourceId" class="po-input" style="width:120px" placeholder="Order ID" />
        <button class="po-btn po-btn-outline po-btn-sm" @click="loadReorder">Load from Order</button>
      </div>
    </div>

    <div v-if="successOrderNo" class="po-callout" style="margin-bottom:24px">
      PO submitted successfully. Order No: <strong class="po-mono">{{ successOrderNo }}</strong>
      <router-link :to="{ name: 'PoOrders' }" class="po-btn po-btn-primary po-btn-sm" style="margin-left:12px">
        View My Orders
      </router-link>
    </div>

    <form class="po-card" @submit.prevent="handleSubmit">
      <h2 class="po-section-title">PO Information</h2>
      <div class="po-form-grid">
        <div class="po-field">
          <label class="po-label">PO Number *</label>
          <input v-model="form.po_number" class="po-input" required />
        </div>
        <div class="po-field">
          <label class="po-label">Grant / Sponsor Code</label>
          <input v-model="form.grant_code" class="po-input" />
        </div>
        <div class="po-field">
          <label class="po-label">Shipping Method</label>
          <select v-model="form.shipping_method" class="po-select">
            <option value="">— Select —</option>
            <option v-for="m in SHIPPING_METHODS" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </div>
        <div class="po-field">
          <label class="po-label">Requested Delivery Date</label>
          <input v-model="form.requested_delivery_date" type="date" class="po-input" />
        </div>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">Ship-to</h2>
      <div class="po-form-grid">
        <div class="po-field">
          <label class="po-label">Recipient Name</label>
          <input v-model="form.shipping_name" class="po-input" />
        </div>
        <div class="po-field">
          <label class="po-label">Phone</label>
          <input v-model="form.shipping_phone" class="po-input" />
        </div>
        <div class="po-field full">
          <label class="po-label">Address</label>
          <textarea v-model="form.shipping_address" class="po-textarea" />
        </div>
        <div class="po-field">
          <label class="po-label">Email</label>
          <input v-model="form.shipping_email" type="email" class="po-input" />
        </div>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">Bill-to</h2>
      <div class="po-form-grid">
        <div class="po-field">
          <label class="po-label">Billing Name</label>
          <input v-model="form.billing_name" class="po-input" />
        </div>
        <div class="po-field full">
          <label class="po-label">Billing Address</label>
          <textarea v-model="form.billing_address" class="po-textarea" />
        </div>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">PO Attachments</h2>
      <label class="po-dropzone">
        <input type="file" multiple accept=".pdf,.png,.jpeg,.jpg" style="display:none" @change="onFileChange" />
        Drag &amp; drop or click to upload (PDF / PNG / JPEG, ≤10MB)
      </label>
      <div>
        <span v-for="(f, i) in files" :key="i" class="po-file-chip">{{ f.name }}</span>
      </div>

      <h2 class="po-section-title" style="margin-top:24px">Line Items</h2>
      <table class="po-table" v-if="items.length">
        <thead>
          <tr>
            <th style="width:30%">Product</th>
            <th style="width:18%">SKU</th>
            <th style="width:10%">Qty</th>
            <th style="width:14%">Unit Price</th>
            <th style="width:14%">Subtotal</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in items" :key="idx">
            <td>
              <input
                class="po-input"
                :placeholder="row.productName || 'Search product…'"
                @input="searchProducts(row, $event.target.value)"
              />
              <div v-if="row.searching" class="po-muted">Searching…</div>
              <div v-if="row.searchResults.length" class="po-search-pop">
                <button
                  v-for="p in row.searchResults"
                  :key="p.id"
                  type="button"
                  class="po-search-item"
                  @click="selectProduct(row, p)"
                >
                  {{ p.name }} <span class="po-mono" v-if="p.catalog_no">{{ p.catalog_no }}</span>
                </button>
              </div>
              <div v-if="row.productName && !row.searchResults.length" class="po-muted">{{ row.productName }}</div>
            </td>
            <td>
              <select v-model="row.skuId" class="po-select" :disabled="!row.skus.length" @change="onSkuChange(row)">
                <option value="">— SKU —</option>
                <option v-for="s in row.skus" :key="s.id" :value="s.id">
                  {{ s.sku_code }} · {{ s.pack_size }}
                </option>
              </select>
            </td>
            <td><input v-model.number="row.quantity" type="number" min="1" class="po-input" /></td>
            <td><input v-model="row.unitPrice" class="po-input" placeholder="0.00" /></td>
            <td class="po-num">{{ formatCurrency((Number(row.quantity) || 0) * (Number(row.unitPrice) || 0)) }}</td>
            <td><button type="button" class="po-btn po-btn-danger po-btn-sm" @click="removeItem(idx)">Remove</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="po-muted">No line items yet.</p>
      <button type="button" class="po-btn po-btn-outline po-btn-sm" style="margin-top:12px" @click="addItem">+ Add Line Item</button>

      <div class="po-total-row">
        <span>Estimated Total</span>
        <span class="po-total-value">{{ formatCurrency(grandTotal) }}</span>
      </div>

      <div class="po-row" style="margin-top:16px">
        <button type="submit" class="po-btn po-btn-accent po-btn-lg" :disabled="submitting">
          {{ submitting ? 'Submitting…' : 'Submit PO' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.po-search-pop {
  position: absolute;
  z-index: 20;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  margin-top: 2px;
  max-height: 200px;
  overflow: auto;
  width: 100%;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12);
}
.po-search-item {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: none;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--color-text);
}
.po-search-item:hover { background: var(--color-primary-subtle); }
td { position: relative; }
</style>
