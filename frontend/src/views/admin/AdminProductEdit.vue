<script setup>
/**
 * AdminProductEdit — Single-page product editor with knowledge fields.
 * Admin-only access. No tabs, all fields on one page.
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createProduct, updateProduct, getProduct, getCategories } from '@/api/products'
import { useAuthStore } from '@/stores/auth'
import http from '@/utils/http'
import AiToolsPanel from './components/AiToolsPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isEdit = computed(() => !!route.params.id)
const loading = ref(false)
const saving = ref(false)
const saveMessage = ref('')
const saveMessageType = ref('success')

/* ── Access Control ── */
const isAdmin = computed(() => auth.role === 'admin' || auth.isOrgAdmin || auth.user?.is_superuser)

/* ── Categories ── */
const categories = ref({})
const categoryL1Options = computed(() =>
  Object.entries(categories.value).map(([key, val]) => ({ value: key, label: val.label }))
)
const categoryL2Options = computed(() => {
  const l1 = form.category_l1
  if (!l1 || !categories.value[l1]) return []
  return categories.value[l1].children || []
})

/* ── Form Data ── */
const form = reactive({
  name: '', slug: '', catalog_no: '', cas: '', smiles: '', synonyms: '',
  inchi: '', formula: '', molecular_weight: null, purity: '', concentration: '',
  storage: '', shipping: '', lead_time: '', handling_notes: '', shelf_life: '',
  research_use_only: true, overview: '', structure_svg: '',
  seo_title: '', seo_description: '',
  category_l1: '', category_l2: '', category_l3: '',
  status: 'draft', product_class_id: null,
})

/* ── Knowledge Fields ── */
const methodIds = ref([])
const protocolIds = ref([])
const researchGoalIds = ref([])
const applicationIds = ref([])

const GOAL_OPTIONS = ref([])
const APP_OPTIONS = ref([])
const METHOD_OPTIONS = ref([])
const PROTOCOL_OPTIONS = ref([])

async function loadKnowledgeOptions() {
  try {
    const [goals, apps, methods, protocols] = await Promise.all([
      http.get('/research-goals/'),
      http.get('/applications/'),
      http.get('/methods/'),
      http.get('/protocols/'),
    ])
    GOAL_OPTIONS.value = (goals.data || goals || []).map(g => ({ id: g.id, name: g.name }))
    APP_OPTIONS.value = (apps.data || apps || []).map(a => ({ id: a.id, name: a.name }))
    METHOD_OPTIONS.value = (methods.data || methods || []).map(m => ({ id: m.id, name: m.name }))
    PROTOCOL_OPTIONS.value = (protocols.data || protocols || []).map(p => ({ id: p.id, name: p.name }))
  } catch { /* ignore */ }
}

function toggleItem(arr, id) {
  const idx = arr.indexOf(id)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(id)
}

/* ── SKUs ── */
const skus = ref([])
function addSku() {
  skus.value.push({
    _key: Date.now(),
    sku_code: '', pack_size: '', concentration: '', price: '0.00', currency: 'USD',
    inventory_status: 'in_stock', lead_time: '', is_default: false,
  })
}
function removeSku(idx) { skus.value.splice(idx, 1) }

/* ── Validation ── */
const errors = reactive({})
function validate() {
  const e = {}
  if (!form.name.trim()) e.name = 'Product name is required'
  if (form.molecular_weight !== null && form.molecular_weight !== '' && isNaN(Number(form.molecular_weight)))
    e.molecular_weight = 'Must be a number'
  if (form.cas && !/^\d{2,7}-\d{2}-\d$/.test(form.cas))
    e.cas = 'CAS format: XXXXXXX-XX-X'
  Object.keys(errors).forEach(k => delete errors[k])
  Object.assign(errors, e)
  return Object.keys(e).length === 0
}

/* ── Load (edit mode) ── */
async function loadProduct() {
  loading.value = true
  try {
    const res = await getProduct(route.params.id)
    const data = res.data || res
    Object.keys(form).forEach(k => {
      if (data[k] !== undefined) form[k] = data[k]
    })
    if (form.category_l2 && form.category_l2.includes(' | ')) {
      const parts = form.category_l2.split(' | ')
      form.category_l2 = parts[0]
      form.category_l3 = parts.slice(1).join(' | ')
    }
    if (data.skus) {
      skus.value = data.skus.map(s => ({ ...s, _key: s.id }))
    }
    // Load knowledge relationships
    try {
      const detailRes = await http.get(`/products/${route.params.id}/detail/`)
      const detail = detailRes.data || detailRes
      methodIds.value = (detail.compatibility?.methods || []).map(m => m.id)
      protocolIds.value = (detail.protocols || []).map(p => p.id)
      applicationIds.value = (detail.applications || []).map(a => a.id)
    } catch { /* ignore */ }
  } catch (err) {
    saveMessage.value = 'Failed to load product.'
    saveMessageType.value = 'error'
  } finally {
    loading.value = false
  }
}

/* ── Save ── */
async function handleSave() {
  if (!validate()) return
  saving.value = true
  saveMessage.value = ''
  try {
    const payload = { ...form }
    if (payload.category_l3) {
      payload.category_l2 = `${payload.category_l2} | ${payload.category_l3}`
    }
    delete payload.category_l3
    if (payload.molecular_weight === '' || payload.molecular_weight === undefined) payload.molecular_weight = null
    if (!payload.product_class_id) delete payload.product_class_id
    payload.skus = skus.value.map(s => { const { _key, ...rest } = s; return rest })
    if (methodIds.value.length) payload.method_ids = methodIds.value
    if (protocolIds.value.length) payload.protocol_ids = protocolIds.value
    if (researchGoalIds.value.length) payload.research_goal_ids = researchGoalIds.value
    if (applicationIds.value.length) payload.application_ids = applicationIds.value

    if (isEdit.value) {
      await updateProduct(route.params.id, payload)
      saveMessage.value = 'Product updated successfully.'
    } else {
      const res = await createProduct(payload)
      saveMessage.value = 'Product created successfully.'
      const newId = res.data?.id || res.id
      if (newId) setTimeout(() => router.push(`/admin/products/${newId}/edit`), 1500)
    }
    saveMessageType.value = 'success'
  } catch (err) {
    saveMessage.value = err?.data?.meta?.error?.message || err?.message || 'Save failed.'
    saveMessageType.value = 'error'
  } finally {
    saving.value = false
  }
}

/* ── Init ── */
onMounted(async () => {
  if (!isAdmin.value) {
    router.push('/')
    return
  }
  try {
    const res = await getCategories()
    categories.value = res.data || res || {}
  } catch { /* ignore */ }
  loadKnowledgeOptions()
  if (isEdit.value) loadProduct()
})
</script>

<template>
  <div class="admin-edit" v-if="isAdmin">
    <!-- Header -->
    <div class="admin-header">
      <div>
        <h1 class="admin-title">{{ isEdit ? 'Edit Product' : 'New Product' }}</h1>
        <p class="admin-subtitle">Admin product management with knowledge fields</p>
      </div>
      <div class="admin-actions">
        <button class="btn-save" :disabled="saving" @click="handleSave">
          {{ saving ? 'Saving...' : 'Save Product' }}
        </button>
        <button class="btn-cancel" @click="router.push('/products')">Cancel</button>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="saveMessage" class="toast" :class="saveMessageType">
      {{ saveMessage }}
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading">Loading...</div>

    <!-- Form (single page, no tabs) -->
    <form v-else @submit.prevent="handleSave" class="admin-form">

      <!-- Section 1: Basic Info -->
      <div class="form-card">
        <h2 class="card-title">Basic Information</h2>
        <div class="form-grid">
          <div class="form-group">
            <label>Product Name *</label>
            <input v-model="form.name" class="form-input" :class="{ 'input-error': errors.name }" placeholder="2'-Azido-dATP" />
            <span v-if="errors.name" class="error-text">{{ errors.name }}</span>
          </div>
          <div class="form-group">
            <label>Catalog No</label>
            <input v-model="form.catalog_no" class="form-input" placeholder="SC8047" />
          </div>
          <div class="form-group">
            <label>CAS Number</label>
            <input v-model="form.cas" class="form-input" placeholder="73449-06-6" />
          </div>
          <div class="form-group">
            <label>Synonyms</label>
            <input v-model="form.synonyms" class="form-input" placeholder="comma-separated" />
          </div>
          <div class="form-group">
            <label>Status</label>
            <select v-model="form.status" class="form-input">
              <option value="draft">Draft</option>
              <option value="published">Published</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          <div class="form-group">
            <label>Slug</label>
            <input v-model="form.slug" class="form-input" placeholder="auto-generated" />
          </div>
        </div>
      </div>

      <!-- Section 2: Chemical Structure -->
      <div class="form-card">
        <h2 class="card-title">Chemical Structure</h2>
        <div class="form-grid">
          <div class="form-group form-full">
            <label>SMILES</label>
            <input v-model="form.smiles" class="form-input" placeholder="C1=NC(=C2C(=N1)N(C=N2)..." />
          </div>
          <div class="form-group form-full">
            <label>InChI</label>
            <input v-model="form.inchi" class="form-input" placeholder="InChI=1S/..." />
          </div>
        </div>
      </div>

      <!-- Section 3: Scientific Parameters -->
      <div class="form-card">
        <h2 class="card-title">Scientific Parameters</h2>
        <div class="form-grid">
          <div class="form-group">
            <label>Formula</label>
            <input v-model="form.formula" class="form-input" placeholder="C10H15N8O12P3" />
          </div>
          <div class="form-group">
            <label>Molecular Weight</label>
            <input v-model="form.molecular_weight" class="form-input" :class="{ 'input-error': errors.molecular_weight }" type="number" step="0.01" placeholder="532.2" />
          </div>
          <div class="form-group">
            <label>Purity</label>
            <input v-model="form.purity" class="form-input" placeholder="≥ 90% (HPLC)" />
          </div>
          <div class="form-group">
            <label>Concentration</label>
            <input v-model="form.concentration" class="form-input" placeholder="100 mM" />
          </div>
          <div class="form-group">
            <label>Storage</label>
            <input v-model="form.storage" class="form-input" placeholder="-20°C" />
          </div>
          <div class="form-group">
            <label>Shipping</label>
            <input v-model="form.shipping" class="form-input" placeholder="Blue Ice" />
          </div>
          <div class="form-group">
            <label>Lead Time</label>
            <input v-model="form.lead_time" class="form-input" placeholder="1-3 days" />
          </div>
          <div class="form-group">
            <label>Shelf Life</label>
            <input v-model="form.shelf_life" class="form-input" placeholder="12 months" />
          </div>
          <div class="form-group form-full">
            <label>Handling Notes</label>
            <textarea v-model="form.handling_notes" class="form-input" rows="2" placeholder="Avoid freeze-thaw cycles"></textarea>
          </div>
        </div>
      </div>

      <!-- Section 4: Category -->
      <div class="form-card">
        <h2 class="card-title">Category</h2>
        <div class="form-grid">
          <div class="form-group">
            <label>Category L1</label>
            <select v-model="form.category_l1" class="form-input" @change="form.category_l2 = ''">
              <option value="">Select...</option>
              <option v-for="c in categoryL1Options" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Category L2</label>
            <select v-model="form.category_l2" class="form-input" :disabled="!form.category_l1">
              <option value="">Select...</option>
              <option v-for="c in categoryL2Options" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>Category L3</label>
            <input v-model="form.category_l3" class="form-input" placeholder="Optional subcategory" />
          </div>
        </div>
      </div>

      <!-- Section 5: Research Knowledge -->
      <div class="form-card">
        <h2 class="card-title">Research Knowledge</h2>
        <p class="card-hint">Link this product to research goals, applications, methods, and protocols.</p>

        <div class="knowledge-section">
          <label class="knowledge-label">Research Goals</label>
          <div class="chips">
            <button v-for="opt in GOAL_OPTIONS" :key="opt.id" type="button"
              class="chip" :class="{ 'chip-on': researchGoalIds.includes(opt.id) }"
              @click="toggleItem(researchGoalIds, opt.id)">{{ opt.name }}</button>
          </div>
        </div>

        <div class="knowledge-section">
          <label class="knowledge-label">Applications</label>
          <div class="chips">
            <button v-for="opt in APP_OPTIONS" :key="opt.id" type="button"
              class="chip" :class="{ 'chip-on': applicationIds.includes(opt.id) }"
              @click="toggleItem(applicationIds, opt.id)">{{ opt.name }}</button>
          </div>
        </div>

        <div class="knowledge-section">
          <label class="knowledge-label">Methods</label>
          <div class="chips">
            <button v-for="opt in METHOD_OPTIONS" :key="opt.id" type="button"
              class="chip" :class="{ 'chip-on': methodIds.includes(opt.id) }"
              @click="toggleItem(methodIds, opt.id)">{{ opt.name }}</button>
          </div>
        </div>

        <div class="knowledge-section">
          <label class="knowledge-label">Protocols</label>
          <div class="chips">
            <button v-for="opt in PROTOCOL_OPTIONS" :key="opt.id" type="button"
              class="chip" :class="{ 'chip-on': protocolIds.includes(opt.id) }"
              @click="toggleItem(protocolIds, opt.id)">{{ opt.name }}</button>
          </div>
        </div>
      </div>

      <!-- Section 6: Description -->
      <div class="form-card">
        <h2 class="card-title">Description</h2>
        <div class="form-group form-full">
          <label>Overview</label>
          <textarea v-model="form.overview" class="form-input" rows="4" placeholder="Product description..."></textarea>
          <span class="char-count">{{ (form.overview || '').length }} / 5000</span>
        </div>
      </div>

      <!-- Section 7: SKUs -->
      <div class="form-card">
        <h2 class="card-title">SKUs</h2>
        <table class="sku-table" v-if="skus.length">
          <thead>
            <tr>
              <th>SKU Code</th><th>Pack Size</th><th>Concentration</th>
              <th>Price</th><th>Currency</th><th>Status</th><th>Lead Time</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(sku, i) in skus" :key="sku._key">
              <td><input v-model="sku.sku_code" class="form-input-sm" placeholder="SC8047-10" /></td>
              <td><input v-model="sku.pack_size" class="form-input-sm" placeholder="10 µL" /></td>
              <td><input v-model="sku.concentration" class="form-input-sm" placeholder="100 mM" /></td>
              <td><input v-model="sku.price" class="form-input-sm" type="number" step="0.01" placeholder="199" /></td>
              <td><input v-model="sku.currency" class="form-input-sm" placeholder="USD" /></td>
              <td>
                <select v-model="sku.inventory_status" class="form-input-sm">
                  <option value="in_stock">In Stock</option>
                  <option value="out_of_stock">Out of Stock</option>
                  <option value="preorder">Pre-order</option>
                </select>
              </td>
              <td><input v-model="sku.lead_time" class="form-input-sm" placeholder="1-3 days" /></td>
              <td><button type="button" class="btn-remove" @click="removeSku(i)">×</button></td>
            </tr>
          </tbody>
        </table>
        <button type="button" class="btn-add-sku" @click="addSku">+ Add SKU</button>
      </div>

      <!-- Section 8: SEO -->
      <div class="form-card">
        <h2 class="card-title">SEO</h2>
        <div class="form-grid">
          <div class="form-group form-full">
            <label>SEO Title</label>
            <input v-model="form.seo_title" class="form-input" placeholder="Auto-generated if empty" />
          </div>
          <div class="form-group form-full">
            <label>SEO Description</label>
            <textarea v-model="form.seo_description" class="form-input" rows="2" placeholder="Auto-generated if empty"></textarea>
          </div>
        </div>
      </div>

      <!-- Bottom Actions -->
      <div class="form-bottom">
        <button type="submit" class="btn-save" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Product' }}
        </button>
        <button type="button" class="btn-cancel" @click="router.push('/products')">Cancel</button>
      </div>
    </form>

    <!-- AI Tools Panel (edit mode only) -->
    <div v-if="isEdit" class="form-card ai-tools-section">
      <AiToolsPanel
        :product-id="route.params.id"
        :product-name="form.name"
        :product-cas="form.cas"
        :product-smiles="form.smiles"
      />
    </div>
  </div>

  <!-- Access Denied -->
  <div v-else class="access-denied">
    <h2>Access Denied</h2>
    <p>You don't have permission to access this page.</p>
    <button @click="router.push('/')">Back to Home</button>
  </div>
</template>

<style scoped>
.admin-edit { max-width: 960px; margin: 0 auto; padding: 24px; }
.admin-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.admin-title { font-size: 24px; font-weight: 800; margin: 0; }
.admin-subtitle { font-size: 14px; color: var(--color-text-secondary); margin: 4px 0 0; }
.admin-actions { display: flex; gap: 8px; }

.toast { padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; font-weight: 500; }
.toast.success { background: #d1fae5; color: #065f46; }
.toast.error { background: #fee2e2; color: #991b1b; }

.admin-form { display: flex; flex-direction: column; gap: 20px; }

.form-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 20px; }
.card-title { font-size: 16px; font-weight: 700; margin: 0 0 16px; color: var(--color-text); border-bottom: 2px solid var(--color-primary); display: inline-block; padding-bottom: 4px; }
.card-hint { font-size: 13px; color: var(--color-text-secondary); margin: -8px 0 16px; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.form-full { grid-column: span 2; }
.form-input { padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 13px; font-family: var(--font-sans); }
.form-input:focus { border-color: var(--color-primary); outline: none; box-shadow: 0 0 0 2px var(--color-primary-light); }
.input-error { border-color: #ef4444; }
.error-text { font-size: 11px; color: #ef4444; }
.char-count { font-size: 11px; color: var(--color-text-tertiary); text-align: right; }

/* Knowledge chips */
.knowledge-section { margin-bottom: 16px; }
.knowledge-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 6px; display: block; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 4px 12px; border: 1px solid var(--color-border); border-radius: 16px; font-size: 12px; cursor: pointer; background: var(--color-surface); color: var(--color-text); font-family: var(--font-sans); transition: all 0.15s; }
.chip:hover { border-color: var(--color-primary); }
.chip-on { background: var(--color-primary); border-color: var(--color-primary); color: white; }

/* SKU table */
.sku-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
.sku-table th { font-size: 11px; font-weight: 600; text-align: left; padding: 6px 8px; border-bottom: 2px solid var(--color-border); color: var(--color-text-secondary); }
.sku-table td { padding: 4px; }
.form-input-sm { width: 100%; padding: 6px 8px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 12px; }
.btn-remove { background: none; border: none; color: #ef4444; cursor: pointer; font-size: 16px; }
.btn-add-sku { background: none; border: 1px dashed var(--color-border); padding: 8px 16px; border-radius: var(--radius-md); cursor: pointer; font-size: 13px; color: var(--color-primary); }
.btn-add-sku:hover { border-color: var(--color-primary); }

/* Buttons */
.btn-save { height: 40px; padding: 0 24px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-save:hover { opacity: 0.9; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-cancel { height: 40px; padding: 0 24px; background: transparent; color: var(--color-text-secondary); border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 14px; cursor: pointer; }
.btn-cancel:hover { border-color: var(--color-text-secondary); }
.form-bottom { display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid var(--color-border); }

.access-denied { text-align: center; padding: 80px 24px; }
.access-denied h2 { font-size: 20px; margin-bottom: 8px; }
.access-denied p { color: var(--color-text-secondary); margin-bottom: 16px; }
.access-denied button { padding: 8px 20px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); cursor: pointer; }

.loading { text-align: center; padding: 40px; color: var(--color-text-secondary); }

@media (max-width: 768px) { .form-grid { grid-template-columns: 1fr; } .form-full { grid-column: span 1; } }

.ai-tools-section {
  margin-top: 20px;
}
</style>
