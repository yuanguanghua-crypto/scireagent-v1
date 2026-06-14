<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createProduct, updateProduct, getProduct, getCategories } from '@/api/products'
import { smilesToSvg, rdkitLoading } from '@/composables/useRdkit'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const loading = ref(false)
const saving = ref(false)
const saveMessage = ref('')
const saveMessageType = ref('success')

/* ── Categories ── */
const categories = ref({})
onMounted(async () => {
  try {
    const res = await getCategories()
    categories.value = res.data || res || {}
  } catch { /* ignore */ }
  if (isEdit.value) loadProduct()
})

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

/* ── SKUs ── */
const skus = ref([])
function addSku() {
  skus.value.push({
    _key: Date.now(),
    sku_code: '', pack_size: '', concentration: '', price: '0.00', currency: 'USD',
    inventory_status: 'in_stock', lead_time: '', is_default: false,
  })
}
function removeSku(idx) {
  skus.value.splice(idx, 1)
}

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
    // Split category_l2 into L2 + L3 if concatenated
    if (form.category_l2 && form.category_l2.includes(' | ')) {
      const parts = form.category_l2.split(' | ')
      form.category_l2 = parts[0]
      form.category_l3 = parts.slice(1).join(' | ')
    }
    if (data.skus) {
      skus.value = data.skus.map(s => ({ ...s, _key: s.id }))
    }
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
    // Merge L2 + L3
    if (payload.category_l3) {
      payload.category_l2 = `${payload.category_l2} | ${payload.category_l3}`
    }
    delete payload.category_l3
    // Clean nulls
    if (payload.molecular_weight === '' || payload.molecular_weight === undefined) payload.molecular_weight = null
    if (!payload.product_class_id) delete payload.product_class_id
    // Attach SKUs
    payload.skus = skus.value.map(s => {
      const { _key, ...rest } = s
      return rest
    })

    if (isEdit.value) {
      await updateProduct(route.params.id, payload)
      saveMessage.value = 'Product updated successfully.'
    } else {
      const res = await createProduct(payload)
      saveMessage.value = 'Product created successfully.'
      const newId = res.data?.id || res.id
      if (newId) setTimeout(() => router.push(`/products/${newId}`), 1500)
    }
    saveMessageType.value = 'success'
  } catch (err) {
    saveMessage.value = err?.data?.meta?.error?.message || err?.message || 'Save failed.'
    saveMessageType.value = 'error'
  } finally {
    saving.value = false
  }
}

/* ── SMILES preview with RDKit.js ── */
const smilesPreviewSvg = ref('')
const previewLoading = ref(false)
let previewTimer = null
watch(() => form.smiles, (val) => {
  clearTimeout(previewTimer)
  if (!val) { smilesPreviewSvg.value = ''; return }
  previewTimer = setTimeout(async () => {
    previewLoading.value = true
    try {
      const svg = await smilesToSvg(val, { width: 350, height: 250 })
      smilesPreviewSvg.value = svg || ''
    } catch { smilesPreviewSvg.value = '' }
    finally { previewLoading.value = false }
  }, 500)
})

/* ── Sections ── */
const activeSection = ref('basic')
const sections = [
  { id: 'basic', label: 'Basic Info', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z' },
  { id: 'structure', label: 'Structure', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5' },
  { id: 'science', label: 'Parameters', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2' },
  { id: 'category', label: 'Category', icon: 'M4 6h16M4 12h16M4 18h16' },
  { id: 'description', label: 'Description', icon: 'M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z' },
  { id: 'skus', label: 'SKUs', icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' },
  { id: 'seo', label: 'SEO', icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
]
</script>

<template>
  <div class="product-edit">
    <!-- Header -->
    <div class="edit-header">
      <div class="edit-header__left">
        <button class="btn-back" @click="router.back()">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 4l-4 4 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <h1 class="edit-title">{{ isEdit ? 'Edit Product' : 'New Product' }}</h1>
      </div>
      <button class="btn-save" :disabled="saving" @click="handleSave">
        <svg v-if="saving" class="spinner" width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="2" stroke-dasharray="25" stroke-dashoffset="8" stroke-linecap="round"/></svg>
        <span v-else>{{ isEdit ? 'Save Changes' : 'Create Product' }}</span>
      </button>
    </div>

    <!-- Save message -->
    <div v-if="saveMessage" class="save-msg" :class="`save-msg--${saveMessageType}`">
      {{ saveMessage }}
    </div>

    <!-- Layout: sidebar + content -->
    <div class="edit-layout">
      <!-- Section nav -->
      <aside class="edit-sidebar">
        <button v-for="s in sections" :key="s.id" class="section-btn" :class="{ active: activeSection === s.id }" @click="activeSection = s.id">
          <svg class="section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path :d="s.icon"/></svg>
          <span>{{ s.label }}</span>
        </button>
      </aside>

      <!-- Form content -->
      <div class="edit-content">
        <!-- Basic Info -->
        <section v-if="activeSection === 'basic'" class="form-section">
          <h2 class="section-title">Basic Information</h2>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Product Name <span class="required">*</span></label>
              <input v-model="form.name" class="form-input" :class="{ 'input-error': errors.name }" placeholder="e.g. 3'-Amino-ddATP" />
              <span v-if="errors.name" class="form-error">{{ errors.name }}</span>
            </div>
            <div class="form-group">
              <label class="form-label">Catalog No.</label>
              <input v-model="form.catalog_no" class="form-input" placeholder="e.g. SC8111" />
            </div>
            <div class="form-group">
              <label class="form-label">CAS Number</label>
              <input v-model="form.cas" class="form-input" :class="{ 'input-error': errors.cas }" placeholder="e.g. 1234567-89-0" />
              <span v-if="errors.cas" class="form-error">{{ errors.cas }}</span>
            </div>
            <div class="form-group">
              <label class="form-label">Synonyms</label>
              <input v-model="form.synonyms" class="form-input" placeholder="Comma separated" />
            </div>
            <div class="form-group">
              <label class="form-label">Slug</label>
              <input v-model="form.slug" class="form-input" placeholder="auto-generated if empty" />
            </div>
            <div class="form-group">
              <label class="form-label">Status</label>
              <select v-model="form.status" class="form-input form-select">
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <div class="form-group form-group--toggle">
              <label class="form-label">Research Use Only</label>
              <label class="toggle">
                <input type="checkbox" v-model="form.research_use_only" />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
        </section>

        <!-- Chemical Structure -->
        <section v-if="activeSection === 'structure'" class="form-section">
          <h2 class="section-title">Chemical Structure</h2>
          <div class="form-grid">
            <div class="form-group form-group--full">
              <label class="form-label">SMILES</label>
              <input v-model="form.smiles" class="form-input" placeholder="e.g. O=C(ON1C(=O)CCC1=O)c2ccc(N(C)C)cc2" />
            </div>
            <div class="form-group form-group--full">
              <label class="form-label">InChI</label>
              <input v-model="form.inchi" class="form-input" placeholder="InChI=1S/..." />
            </div>
            <div class="form-group form-group--full">
              <label class="form-label">SVG Structure</label>
              <textarea v-model="form.structure_svg" class="form-input form-textarea" rows="3" placeholder="Paste SVG XML or auto-generated from SMILES"></textarea>
            </div>
          </div>
          <div v-if="form.smiles" class="structure-preview">
            <div class="preview-label">Structure Preview</div>
            <div v-if="previewLoading || rdkitLoading" class="preview-loading">
              <svg class="spinner" width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" stroke-dasharray="40" stroke-dashoffset="12" stroke-linecap="round"/></svg>
              <span>Rendering structure...</span>
            </div>
            <div v-else-if="smilesPreviewSvg" class="svg-preview" v-html="smilesPreviewSvg"></div>
            <div v-else class="smiles-text">SMILES: {{ form.smiles }}</div>
          </div>
        </section>

        <!-- Scientific Parameters -->
        <section v-if="activeSection === 'science'" class="form-section">
          <h2 class="section-title">Scientific Parameters</h2>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Molecular Formula</label>
              <input v-model="form.formula" class="form-input" placeholder="e.g. C11H12N2O5" />
            </div>
            <div class="form-group">
              <label class="form-label">Molecular Weight (g/mol)</label>
              <input v-model="form.molecular_weight" class="form-input" :class="{ 'input-error': errors.molecular_weight }" type="number" step="0.01" placeholder="e.g. 283.24" />
              <span v-if="errors.molecular_weight" class="form-error">{{ errors.molecular_weight }}</span>
            </div>
            <div class="form-group">
              <label class="form-label">Purity</label>
              <input v-model="form.purity" class="form-input" placeholder="e.g. >=98%" />
            </div>
            <div class="form-group">
              <label class="form-label">Concentration</label>
              <input v-model="form.concentration" class="form-input" placeholder="e.g. 100 mM" />
            </div>
            <div class="form-group">
              <label class="form-label">Storage</label>
              <input v-model="form.storage" class="form-input" placeholder="e.g. -20C, protect from light" />
            </div>
            <div class="form-group">
              <label class="form-label">Shipping</label>
              <input v-model="form.shipping" class="form-input" placeholder="e.g. Dry Ice" />
            </div>
            <div class="form-group">
              <label class="form-label">Lead Time</label>
              <input v-model="form.lead_time" class="form-input" placeholder="e.g. 1-3 business days" />
            </div>
            <div class="form-group">
              <label class="form-label">Shelf Life</label>
              <input v-model="form.shelf_life" class="form-input" placeholder="e.g. 365 days" />
            </div>
            <div class="form-group form-group--full">
              <label class="form-label">Handling Notes</label>
              <textarea v-model="form.handling_notes" class="form-input form-textarea" rows="3" placeholder="Safety and handling instructions"></textarea>
            </div>
          </div>
        </section>

        <!-- Category -->
        <section v-if="activeSection === 'category'" class="form-section">
          <h2 class="section-title">Product Category</h2>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">L1 Category</label>
              <select v-model="form.category_l1" class="form-input form-select">
                <option value="">-- Select --</option>
                <option v-for="opt in categoryL1Options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">L2 Category</label>
              <select v-model="form.category_l2" class="form-input form-select" :disabled="!form.category_l1">
                <option value="">-- Select --</option>
                <option v-for="opt in categoryL2Options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">L3 (free text)</label>
              <input v-model="form.category_l3" class="form-input" placeholder="e.g. 5-Formyl, 2'-Fluoro" />
            </div>
          </div>
        </section>

        <!-- Description -->
        <section v-if="activeSection === 'description'" class="form-section">
          <h2 class="section-title">Product Description</h2>
          <div class="form-group form-group--full">
            <label class="form-label">Overview</label>
            <textarea v-model="form.overview" class="form-input form-textarea" rows="12" maxlength="5000" placeholder="Detailed product description (max 5000 characters)"></textarea>
            <span class="char-count">{{ (form.overview || '').length }} / 5000</span>
          </div>
        </section>

        <!-- SKUs -->
        <section v-if="activeSection === 'skus'" class="form-section">
          <h2 class="section-title">SKU / Packaging</h2>
          <div class="sku-table">
            <div class="sku-header">
              <span>Code</span><span>Pack Size</span><span>Conc.</span><span>Price</span><span>Currency</span><span>Status</span><span>Lead Time</span><span>Default</span><span></span>
            </div>
            <div v-for="(sku, idx) in skus" :key="sku._key" class="sku-row">
              <input v-model="sku.sku_code" class="form-input sku-input" placeholder="SKU code" />
              <input v-model="sku.pack_size" class="form-input sku-input" placeholder="e.g. 1mg" />
              <input v-model="sku.concentration" class="form-input sku-input" placeholder="e.g. 100 mM" />
              <input v-model="sku.price" class="form-input sku-input" type="number" step="0.01" placeholder="0.00" />
              <select v-model="sku.currency" class="form-input form-select sku-input"><option>USD</option><option>CNY</option><option>EUR</option></select>
              <select v-model="sku.inventory_status" class="form-input form-select sku-input">
                <option value="in_stock">In Stock</option><option value="limited">Limited</option>
                <option value="preorder">Pre-order</option><option value="out_of_stock">Out of Stock</option>
              </select>
              <input v-model="sku.lead_time" class="form-input sku-input" placeholder="e.g. 1-3 days" />
              <label class="sku-default"><input type="radio" :value="true" v-model="sku.is_default" name="sku-default" /></label>
              <button class="btn-remove-sku" @click="removeSku(idx)">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
              </button>
            </div>
          </div>
          <button class="btn-add-sku" @click="addSku">+ Add SKU</button>
        </section>

        <!-- SEO -->
        <section v-if="activeSection === 'seo'" class="form-section">
          <h2 class="section-title">SEO Information</h2>
          <p class="section-hint">Auto-generated from product name and category. Edit if needed.</p>
          <div class="form-grid">
            <div class="form-group form-group--full">
              <label class="form-label">SEO Title</label>
              <input v-model="form.seo_title" class="form-input" placeholder="Auto-generated if empty" />
            </div>
            <div class="form-group form-group--full">
              <label class="form-label">SEO Description</label>
              <textarea v-model="form.seo_description" class="form-input form-textarea" rows="3" placeholder="Auto-generated if empty"></textarea>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.product-edit { max-width: 1200px; margin: 0 auto; }
.edit-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.edit-header__left { display: flex; align-items: center; gap: 12px; }
.edit-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0; }
.btn-back { background: none; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 8px; cursor: pointer; color: var(--color-text-secondary); display: flex; }
.btn-back:hover { background: var(--color-bg); }
.btn-save { height: 40px; padding: 0 24px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); font-weight: 600; cursor: pointer; font-family: var(--font-sans); font-size: 14px; display: flex; align-items: center; gap: 8px; }
.btn-save:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }

.save-msg { padding: 10px 16px; border-radius: var(--radius-md); font-size: 14px; margin-bottom: 16px; }
.save-msg--success { background: var(--color-success-light); color: var(--color-success); }
.save-msg--error { background: var(--color-danger-light); color: var(--color-danger); }

.edit-layout { display: flex; gap: 20px; }
.edit-sidebar { width: 180px; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px; }
.section-btn { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: none; border: none; border-radius: var(--radius-md); cursor: pointer; font-size: 13px; font-weight: 500; color: var(--color-text-secondary); text-align: left; font-family: var(--font-sans); }
.section-btn:hover { background: var(--color-bg); color: var(--color-text); }
.section-btn.active { background: var(--color-primary); color: white; }
.section-icon { width: 16px; height: 16px; flex-shrink: 0; }

.edit-content { flex: 1; min-width: 0; }
.form-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: 24px; }
.section-title { font-size: 18px; font-weight: 700; color: var(--color-text); margin: 0 0 20px; }
.section-hint { font-size: 13px; color: var(--color-text-tertiary); margin: -12px 0 16px; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group--full { grid-column: 1 / -1; }
.form-group--toggle { flex-direction: row; align-items: center; justify-content: space-between; }
.form-label { font-size: 13px; font-weight: 500; color: var(--color-text); }
.required { color: var(--color-danger); }
.form-input { height: 40px; padding: 0 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-family: var(--font-sans); font-size: 14px; color: var(--color-text); background: var(--color-surface); outline: none; transition: border-color 0.15s; }
.form-input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-light); }
.input-error { border-color: var(--color-danger); }
.form-select { appearance: none; background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%2364748B' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; padding-right: 32px; cursor: pointer; }
.form-textarea { height: auto; padding: 10px 12px; resize: vertical; }
.form-error { font-size: 12px; color: var(--color-danger); }
.char-count { font-size: 12px; color: var(--color-text-tertiary); text-align: right; }

.toggle { position: relative; display: inline-block; width: 44px; height: 24px; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: var(--color-border); border-radius: 12px; transition: 0.2s; }
.toggle-slider::before { content: ''; position: absolute; height: 18px; width: 18px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: 0.2s; }
.toggle input:checked + .toggle-slider { background: var(--color-primary); }
.toggle input:checked + .toggle-slider::before { transform: translateX(20px); }

.structure-preview { margin-top: 16px; padding: 16px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.preview-label { font-size: 12px; font-weight: 600; color: var(--color-text-tertiary); margin-bottom: 8px; text-transform: uppercase; }
.svg-preview { text-align: center; }
.svg-preview :deep(svg) { max-width: 100%; height: auto; }
.preview-loading { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 20px; color: var(--color-text-tertiary); font-size: 13px; }
.spinner { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.smiles-text { font-family: var(--font-mono); font-size: 13px; color: var(--color-text-secondary); }

.sku-table { margin-bottom: 12px; }
.sku-header { display: grid; grid-template-columns: 1fr 1fr 100px 90px 80px 110px 100px 60px 40px; gap: 8px; padding: 8px 0; font-size: 12px; font-weight: 600; color: var(--color-text-tertiary); text-transform: uppercase; border-bottom: 1px solid var(--color-border); }
.sku-row { display: grid; grid-template-columns: 1fr 1fr 100px 90px 80px 110px 100px 60px 40px; gap: 8px; padding: 8px 0; align-items: center; border-bottom: 1px solid var(--color-border-light); }
.sku-input { height: 36px; font-size: 13px; }
.sku-default { display: flex; justify-content: center; }
.btn-remove-sku { background: none; border: none; cursor: pointer; color: var(--color-text-tertiary); padding: 4px; border-radius: 4px; display: flex; }
.btn-remove-sku:hover { color: var(--color-danger); background: var(--color-danger-light); }
.btn-add-sku { background: none; border: 1px dashed var(--color-border); border-radius: var(--radius-md); padding: 10px; width: 100%; cursor: pointer; color: var(--color-primary); font-weight: 500; font-family: var(--font-sans); }
.btn-add-sku:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }

.spinner { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .edit-layout { flex-direction: column; }
  .edit-sidebar { width: 100%; flex-direction: row; overflow-x: auto; }
  .form-grid { grid-template-columns: 1fr; }
  .sku-header, .sku-row { grid-template-columns: 1fr 1fr 1fr; }
}
</style>
