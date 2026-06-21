<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/api/http'
import AiToolsPanel from '@/views/admin/components/AiToolsPanel.vue'
import StructureViewer from './components/StructureViewer.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

if (!auth.isStaff) { router.replace('/') }

const isEdit = computed(() => !!route.params.id)
const productId = computed(() => route.params.id)
const saving = ref(false)
const showPublishDialog = ref(false)
const loading = ref(false)
const loadError = ref('')

// Word import / AI / inline-entity states
const wordImporting = ref(false)
const wordFile = ref(null)
const wordResult = ref(null)
const showAiPanel = ref(false)

// ── Knowledge inline editor ─────────────────
const showInlineEditor = ref(false)
const inlineEntityType = ref('method')
const inlineForm = reactive({ name: '', summary: '', purpose: '', reagent: '', amount: '', duration: '' })
const inlineSaving = ref(false)
const knowledgeList = ref({ goals: [], apps: [], methods: [], protocols: [] })

// Form
const form = reactive({
  name: '', slug: '', catalog_no: '', cas: '', smiles: '', synonyms: '',
  inchi: '', formula: '', molecular_weight: null, purity: '', concentration: '',
  storage: '', shipping: '', lead_time: '', handling_notes: '', shelf_life: '',
  research_use_only: true, overview: '', structure_svg: '',
  seo_title: '', seo_description: '',
  category_l1: '', category_l2: '',
  status: 'draft', product_class_id: null,
})

const skus = ref([])
const methodIds = ref([])
const protocolIds = ref([])
const researchGoalIds = ref([])
const applicationIds = ref([])

// Completeness
const isComplete = computed(() => {
  return !!(form.name && form.catalog_no && form.category_l1 &&
    skus.value.some(s => s.is_default))
})
const incompleteItems = computed(() => {
  const items = []
  if (!(form.name && form.catalog_no)) items.push('基本信息')
  if (!form.category_l1) items.push('分类')
  if (!skus.value.some(s => s.is_default)) items.push('默认SKU')
  return items
})
const suggestionsMissing = computed(() => {
  const missing = []
  if (!form.cas) missing.push('CAS')
  if (!form.smiles) missing.push('SMILES')
  if (!form.formula) missing.push('分子式')
  if (!methodIds.value.length && !protocolIds.value.length) missing.push('知识关联')
  if (!form.seo_title && !form.seo_description) missing.push('SEO')
  return missing
})

// SKU duplicate check
const skuDuplicate = computed(() => {
  const seen = new Map()
  const dupes = new Set()
  skus.value.forEach((s, i) => {
    const key = `${s.pack_size || ''}::${s.concentration || ''}`
    if (key === '::') return
    if (seen.has(key)) dupes.add(i)
    else seen.set(key, i)
  })
  return dupes
})

// Dropdown presets
const purityOpts = ['≥ 99% (HPLC)', '≥ 98% (HPLC)', '≥ 97% (HPLC)', '≥ 95% (HPLC)', '≥ 90% (HPLC)']
const concentrationOpts = ['100 mM', '50 mM', '10 mM', '1 mM']
const storageOpts = ['-20°C', '-80°C', '4°C', 'Room temperature']
const shippingOpts = ['Blue Ice', 'Dry Ice', 'Ambient', 'Cold Pack']
const leadTimeOpts = ['In stock', '1-3 days', '3-5 days', '1-2 weeks', '2-4 weeks']
const shelfLifeOpts = ['12 months', '24 months', '6 months']
const categoryL1Opts = ['Nucleotides', 'Click Chemistry', 'Fluorescent Labels', 'Biotin Labels', 'Modified Bases']

function addSku() {
  skus.value.push({
    _key: Date.now(), sku_code: '', pack_size: '', concentration: form.concentration || '',
    price: '0.00', currency: 'USD', inventory_status: 'in_stock',
    lead_time: '', is_default: skus.value.length === 0,
  })
}
function removeSku(idx) { skus.value.splice(idx, 1) }

// ── Word Import ─────────────────────────────────────
async function handleWordFile(e) {
  wordFile.value = e.target.files[0]
  if (!wordFile.value) return
  wordImporting.value = true
  wordResult.value = null
  try {
    const fd = new FormData()
    fd.append('file', wordFile.value)
    const resp = await http.post('/products/parse-word/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    wordResult.value = resp.data?.data
    if (wordResult.value) {
      prefillFromWord(wordResult.value)
    }
  } catch (e) {
    wordResult.value = { error: e.response?.data?.meta?.error?.message || 'Parse failed' }
  } finally {
    wordImporting.value = false
  }
}

function prefillFromWord(data) {
  if (data.product_name) form.name = data.product_name
  if (data.catalog_number) form.catalog_no = data.catalog_number
  if (data.cas) form.cas = data.cas
  if (data.formula) form.formula = data.formula
  if (data.molecular_weight) form.molecular_weight = parseFloat(data.molecular_weight) || null
  if (data.purity) form.purity = data.purity
  if (data.concentration) form.concentration = data.concentration
  if (data.storage) form.storage = data.storage
  if (data.shipping) form.shipping = data.shipping
  if (data.synonyms) form.synonyms = data.synonyms
  if (data.description) form.overview = data.description
  // Prefill SKUs from word import
  if (data.skus && data.skus.length) {
    skus.value = data.skus.map((s, i) => ({
      _key: Date.now() + i,
      sku_code: '',
      pack_size: s.pack_size || '',
      concentration: data.concentration || form.concentration || '',
      price: s.price || '0.00',
      currency: 'USD',
      inventory_status: 'in_stock',
      lead_time: '',
      is_default: i === 0,
    }))
  }
}

// ── SEO Auto-Generate ───────────────────────────────
const seoGenerating = ref(false)
async function autoGenerateSeo() {
  if (!isEdit.value) return
  seoGenerating.value = true
  try {
    const resp = await http.post(`/products/${productId.value}/generate-seo/`)
    if (resp.data?.data) {
      if (resp.data.data.seo_title) form.seo_title = resp.data.data.seo_title
      if (resp.data.data.seo_description) form.seo_description = resp.data.data.seo_description
    }
  } catch (e) {
    alert('SEO generation failed')
  } finally {
    seoGenerating.value = false
  }
}

// ── Knowledge inline editor ───────────────────────
const apiEndpoints = {
  goal: '/research-goals/', app: '/applications/', method: '/methods/',
  protocol: '/protocols/', reference: '/references/',
}

async function loadKnowledge() {
  try {
    const [g, a, m, p] = await Promise.all([
      http.get('/research-goals/', { params: { page_size: 200 } }),
      http.get('/applications/', { params: { page_size: 200 } }),
      http.get('/methods/', { params: { page_size: 200 } }),
      http.get('/protocols/', { params: { page_size: 500 } }),
    ])
    knowledgeList.value.goals = (g.data?.data?.results || g.data?.data || [])
    knowledgeList.value.apps = (a.data?.data?.results || a.data?.data || [])
    knowledgeList.value.methods = (m.data?.data?.results || m.data?.data || [])
    knowledgeList.value.protocols = (p.data?.data?.results || p.data?.data || [])
  } catch { /* ignore */ }
}

function openInlineNew(type) {
  inlineEntityType.value = type
  Object.assign(inlineForm, { name: '', summary: '', purpose: '', reagent: '', amount: '', duration: '' })
  showInlineEditor.value = true
}

function toggleMethodId(id) {
  const idx = methodIds.value.indexOf(id)
  if (idx === -1) methodIds.value.push(id)
  else methodIds.value.splice(idx, 1)
}

function toggleProtocolId(id) {
  const idx = protocolIds.value.indexOf(id)
  if (idx === -1) protocolIds.value.push(id)
  else protocolIds.value.splice(idx, 1)
}

async function saveInlineEntity() {
  inlineSaving.value = true
  const type = inlineEntityType.value
  const payload = { name: inlineForm.name }
  if (type === 'goal' || type === 'app') payload.summary = inlineForm.summary
  if (type === 'method') payload.purpose = inlineForm.purpose
  try {
    const resp = await http.post(apiEndpoints[type], payload)
    const newId = resp.data?.data?.id
    if (newId) {
      if (type === 'method') methodIds.value.push(newId)
      if (type === 'protocol') protocolIds.value.push(newId)
    }
    showInlineEditor.value = false
    await loadKnowledge()
  } catch (e) {
    alert('Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    inlineSaving.value = false
  }
}

// ── AI adopt handlers ───────────────────────────────
async function adoptProtocol(protocolData) {
  // Create protocol entity + link to product
  try {
    const resp = await http.post('/protocols/', { name: protocolData.title })
    const newId = resp.data?.data?.id
    if (newId) { protocolIds.value.push(newId); await loadKnowledge() }
  } catch (e) {
    alert('Failed to adopt protocol: ' + (e.response?.data?.meta?.error?.message || e.message))
  }
}

async function adoptReference(refData) {
  // Create reference entity
  try {
    const resp = await http.post('/references/', {
      title: refData.citation || refData.doi || 'Untitled',
      doi: refData.doi || '',
      citation: refData.citation || '',
      source_type: 'journal',
    })
    const newId = resp.data?.data?.id
    if (newId) { /* linked on next product load */ }
  } catch (e) {
    alert('Failed to adopt reference: ' + (e.response?.data?.meta?.error?.message || e.message))
  }
}

// ── Load / Save / Publish ───────────────────────────
async function loadProduct() {
  if (!productId.value) return
  loading.value = true
  try {
    const resp = await http.get(`/products/${productId.value}/`)
    if (resp.data?.data) {
      const d = resp.data.data
      Object.keys(form).forEach(k => { if (k in d) form[k] = d[k] ?? form[k] })
      if (d.skus) skus.value = d.skus.map(s => ({ ...s, _key: s.id || Date.now() }))
      methodIds.value = d.method_ids || []
      protocolIds.value = d.protocol_ids || []
      researchGoalIds.value = d.research_goal_ids || []
      applicationIds.value = d.application_ids || []
    }
    loadKnowledge()
  } catch (e) {
    loadError.value = 'Failed to load product'
  } finally {
    loading.value = false
  }
}

async function saveDraft() {
  saving.value = true
  const payload = {
    ...form,
    skus: skus.value.map(({ _key, ...s }) => s),
    method_ids: methodIds.value,
    protocol_ids: protocolIds.value,
    research_goal_ids: researchGoalIds.value,
    application_ids: applicationIds.value,
  }
  try {
    if (isEdit.value) {
      await http.put(`/products/${productId.value}/`, payload)
    } else {
      const resp = await http.post('/products/', payload)
      const newId = resp.data?.data?.id
      if (newId) router.replace(`/workspace/products/${newId}/edit`)
    }
    alert('Saved!')
  } catch (e) {
    alert('Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    saving.value = false
  }
}

async function publish() {
  showPublishDialog.value = false
  form.status = 'active'
  await saveDraft()
}

function handlePublish() {
  showPublishDialog.value = true
}

onMounted(loadProduct)
</script>

<template>
  <div class="product-edit" v-if="!loading">
    <div v-if="loadError" class="error">{{ loadError }}</div>

    <!-- Completeness bar -->
    <div class="completeness-bar" :class="isComplete ? 'completeness-ok' : 'completeness-warn'">
      <span v-if="isComplete">✓ Complete</span>
      <span v-else>✗ Incomplete — missing: {{ incompleteItems.join(', ') }}</span>
    </div>

    <!-- Word Import Panel -->
    <section class="form-section word-import-section">
      <h3>📄 Word Import</h3>
      <div class="word-import-row">
        <input type="file" accept=".docx" @change="handleWordFile" />
        <span v-if="wordImporting" class="word-status">Parsing...</span>
        <span v-else-if="wordResult && !wordResult.error" class="word-status word-ok">
          {{ wordResult.fields_found }} fields extracted
        </span>
        <span v-else-if="wordResult && wordResult.error" class="word-status word-err">
          {{ wordResult.error }}
        </span>
      </div>
      <p class="form-hint">Upload a .docx product specification to pre-fill the form. All pre-filled values must be reviewed before publishing.</p>
    </section>

    <form @submit.prevent="saveDraft" class="edit-form">
      <!-- 1. Basic Info -->
      <section class="form-section">
        <h3>1. Basic Information</h3>
        <div class="field-grid">
          <label>Name * <input v-model="form.name" /></label>
          <label>Catalog No * <input v-model="form.catalog_no" /></label>
          <label>CAS <input v-model="form.cas" placeholder="e.g. 1927-31-7" /></label>
          <label>Synonyms <input v-model="form.synonyms" placeholder="comma separated" /></label>
          <label>Slug <input v-model="form.slug" /></label>
          <label>Status
            <select v-model="form.status">
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="deprecated">Deprecated</option>
            </select>
          </label>
        </div>
      </section>

      <!-- 2. Chemical Structure -->
      <section class="form-section">
        <h3>2. Chemical Structure</h3>
        <div class="chem-row">
          <div class="chem-inputs">
            <label>SMILES <textarea v-model="form.smiles" rows="2"></textarea></label>
            <label>InChI <textarea v-model="form.inchi" rows="2"></textarea></label>
            <label>Formula <input v-model="form.formula" /></label>
            <label>Molecular Weight <input v-model.number="form.molecular_weight" type="number" step="0.01" /></label>
            <button type="button" class="btn btn-ghost btn-sm" @click="showAiPanel = !showAiPanel">
              {{ showAiPanel ? 'Hide AI Tools' : 'AI Tools' }}
            </button>
          </div>
          <div class="chem-preview">
            <StructureViewer :smiles="form.smiles" />
          </div>
        </div>
        <!-- AI Tools Panel -->
        <div v-if="showAiPanel && isEdit" class="ai-panel-wrapper">
          <AiToolsPanel
            :product-id="productId"
            :product-name="productName"
            :product-cas="productCas"
            :product-smiles="productSmiles"
            @adopt-smiles="(s) => form.smiles = s"
            @adopt-formula-weight="({ formula, weight }) => { if (formula) form.formula = formula; if (weight) form.molecular_weight = weight }"
            @adopt-protocol="adoptProtocol"
            @adopt-reference="adoptReference"
          />
        </div>
      </section>

      <!-- 3. Scientific Parameters -->
      <section class="form-section">
        <h3>3. Scientific Parameters</h3>
        <div class="field-grid">
          <label>Purity
            <input v-model="form.purity" list="purity-list" />
            <datalist id="purity-list"><option v-for="o in purityOpts" :key="o" :value="o" /></datalist>
          </label>
          <label>Concentration
            <input v-model="form.concentration" list="conc-list" />
            <datalist id="conc-list"><option v-for="o in concentrationOpts" :key="o" :value="o" /></datalist>
          </label>
          <label>Storage
            <input v-model="form.storage" list="storage-list" />
            <datalist id="storage-list"><option v-for="o in storageOpts" :key="o" :value="o" /></datalist>
          </label>
          <label>Shipping
            <input v-model="form.shipping" list="shipping-list" />
            <datalist id="shipping-list"><option v-for="o in shippingOpts" :key="o" :value="o" /></datalist>
          </label>
          <label>Lead Time
            <input v-model="form.lead_time" list="lead-list" />
            <datalist id="lead-list"><option v-for="o in leadTimeOpts" :key="o" :value="o" /></datalist>
          </label>
          <label>Shelf Life
            <input v-model="form.shelf_life" list="shelf-list" />
            <datalist id="shelf-list"><option v-for="o in shelfLifeOpts" :key="o" :value="o" /></datalist>
          </label>
          <label class="full-width">Handling Notes <textarea v-model="form.handling_notes" rows="2"></textarea></label>
        </div>
      </section>

      <!-- 4. Category -->
      <section class="form-section">
        <h3>4. Category</h3>
        <div class="field-grid">
          <label>L1 *
            <input v-model="form.category_l1" list="catl1-list" />
            <datalist id="catl1-list"><option v-for="o in categoryL1Opts" :key="o" :value="o" /></datalist>
          </label>
          <label>L2 <input v-model="form.category_l2" placeholder="e.g. Modified dNTPs" /></label>
        </div>
      </section>

      <!-- 5. Knowledge Links -->
      <section class="form-section">
        <h3>5. Knowledge Links</h3>

        <!-- Methods -->
        <div class="chip-group">
          <span class="chip-label">Methods:</span>
          <span v-for="mid in methodIds" :key="mid" class="chip">
            {{ knowledgeList.methods.find(m => m.id === mid)?.name || `#${mid}` }}
            <button type="button" class="chip-remove" @click="toggleMethodId(mid)">✕</button>
          </span>
        </div>

        <!-- Protocols -->
        <div class="chip-group">
          <span class="chip-label">Protocols:</span>
          <span v-for="pid in protocolIds" :key="pid" class="chip">
            {{ knowledgeList.protocols.find(p => p.id === pid)?.name || `#${pid}` }}
            <button type="button" class="chip-remove" @click="toggleProtocolId(pid)">✕</button>
          </span>
        </div>

        <!-- Search & select existing -->
        <div class="entity-select-row">
          <select class="filter-select" v-model="batchLinkMethodId">
            <option value="">— Add Method —</option>
            <option v-for="m in knowledgeList.methods" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
          <button type="button" class="btn btn-ghost btn-sm"
            @click="if(batchLinkMethodId){ toggleMethodId(Number(batchLinkMethodId)); batchLinkMethodId='' }">Add</button>
        </div>

        <div class="entity-select-row">
          <select class="filter-select" v-model="batchLinkProtocolId">
            <option value="">— Add Protocol —</option>
            <option v-for="p in knowledgeList.protocols" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <button type="button" class="btn btn-ghost btn-sm"
            @click="if(batchLinkProtocolId){ toggleProtocolId(Number(batchLinkProtocolId)); batchLinkProtocolId='' }">Add</button>
        </div>

        <!-- Quick-create inline -->
        <div class="inline-buttons">
          <button type="button" class="btn btn-ghost btn-sm" @click="openInlineNew('method')">+ New Method</button>
          <button type="button" class="btn btn-ghost btn-sm" @click="openInlineNew('protocol')">+ New Protocol</button>
        </div>
      </section>

      <!-- 6. Description -->
      <section class="form-section">
        <h3>6. Description</h3>
        <label class="full-width">Overview <textarea v-model="form.overview" rows="6" maxlength="5000"></textarea></label>
      </section>

      <!-- 7. SKUs -->
      <section class="form-section">
        <h3>7. SKUs</h3>
        <table class="sku-table" v-if="skus.length">
          <thead>
            <tr><th>Code</th><th>Pack Size</th><th>Concn</th><th>Price</th><th>Curr</th><th>Default</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in skus" :key="s._key" :class="{ 'sku-duplicate': skuDuplicate.has(i) }">
              <td><input v-model="s.sku_code" style="width:90px" /></td>
              <td><input v-model="s.pack_size" style="width:70px" /></td>
              <td><input v-model="s.concentration" style="width:70px" /></td>
              <td><input v-model="s.price" style="width:70px" type="number" step="0.01" /></td>
              <td>
                <select v-model="s.currency"><option>USD</option><option>CNY</option><option>EUR</option></select>
              </td>
              <td class="col-default">
                <input type="radio" name="default-sku" :checked="s.is_default"
                  @change="skus.forEach((sk, j) => sk.is_default = (j === i))" />
              </td>
              <td><button type="button" @click="removeSku(i)" class="btn btn-ghost btn-sm">✕</button></td>
            </tr>
          </tbody>
        </table>
        <button type="button" @click="addSku" class="btn btn-ghost btn-sm">+ Add SKU</button>
        <p v-if="skuDuplicate.size" class="sku-warning">⚠ Duplicate pack_size + concentration detected (rows highlighted)</p>
        <p class="form-hint">Duplicate pack_size + concentration will be flagged in yellow.</p>
      </section>

      <!-- 8. SEO -->
      <section class="form-section">
        <h3>8. SEO (optional)</h3>
        <div class="field-grid">
          <label>SEO Title <input v-model="form.seo_title" /></label>
          <label>SEO Description <input v-model="form.seo_description" /></label>
        </div>
        <button v-if="isEdit" type="button" class="btn btn-ghost btn-sm" style="margin-top:8px" @click="autoGenerateSeo" :disabled="seoGenerating">
          {{ seoGenerating ? 'Generating...' : 'Auto-generate SEO' }}
        </button>
      </section>

      <!-- Actions -->
      <div class="form-actions">
        <button type="button" @click="saveDraft" class="btn btn-secondary" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Draft' }}
        </button>
        <button type="button" @click="handlePublish" class="btn btn-primary" :disabled="saving">Publish</button>
      </div>
    </form>

    <!-- Publish confirm dialog -->
    <div v-if="showPublishDialog" class="dialog-overlay" @click.self="showPublishDialog = false">
      <div class="dialog">
        <h3>Confirm Publish</h3>
        <div v-if="!isComplete" class="dialog-warn">
          <p>Product is incomplete:</p>
          <ul>
            <li v-for="item in incompleteItems" :key="item">✗ {{ item }}</li>
          </ul>
        </div>
        <div v-if="suggestionsMissing.length" class="dialog-suggest">
          <p>Suggest completing:</p>
          <ul>
            <li v-for="s in suggestionsMissing" :key="s">{{ s }}</li>
          </ul>
        </div>
        <p>The product can still be published. Confirm?</p>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="showPublishDialog = false">Cancel</button>
          <button class="btn btn-primary" @click="publish">Confirm Publish</button>
        </div>
      </div>
    </div>
    <!-- Inline entity editor dialog -->
    <div v-if="showInlineEditor" class="dialog-overlay" @click.self="showInlineEditor = false">
      <div class="dialog">
        <h3>New {{ {goal:'Research Goal',app:'Application',method:'Method',protocol:'Protocol'}[inlineEntityType] }}</h3>
        <label>Name <input v-model="inlineForm.name" class="input-full" /></label>
        <label v-if="inlineEntityType==='goal'||inlineEntityType==='app'">Summary <textarea v-model="inlineForm.summary" rows="3" class="input-full"></textarea></label>
        <label v-if="inlineEntityType==='method'">Purpose <textarea v-model="inlineForm.purpose" rows="3" class="input-full"></textarea></label>
        <div class="dialog-actions">
          <button class="btn btn-ghost btn-sm" @click="showInlineEditor = false">Cancel</button>
          <button class="btn btn-primary btn-sm" @click="saveInlineEntity" :disabled="inlineSaving">
            {{ inlineSaving ? 'Saving...' : 'Save & Link' }}
          </button>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="loading">Loading product...</div>
</template>

<style scoped>
.product-edit { max-width: 1000px; }
.completeness-bar { padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; font-weight: 500; }
.completeness-ok { background: #dcf7e8; color: #176b3a; }
.completeness-warn { background: #ffeeba; color: #856404; }
.edit-form { display: flex; flex-direction: column; gap: 0; }
.form-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 20px; margin-bottom: 16px; }
.form-section h3 { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--color-text); }
.field-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.field-grid label { display: flex; flex-direction: column; font-size: 13px; color: var(--color-text-secondary); gap: 4px; }
.field-grid input, .field-grid select, .field-grid textarea { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); font-family: var(--font-sans); }
.field-grid textarea { resize: vertical; }
.full-width { grid-column: span 2; }
.chem-row { display: flex; gap: 20px; }
.chem-inputs { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.chem-inputs label { font-size: 13px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 4px; }
.chem-inputs input, .chem-inputs textarea { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); resize: vertical; }
.ai-panel-wrapper { margin-top: 16px; border-top: 1px solid var(--color-border); padding-top: 16px; }
.form-hint { font-size: 12px; color: var(--color-text-secondary); margin-top: 8px; }
.form-hint input { padding: 4px 8px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; background: var(--color-bg); color: var(--color-text); width: 300px; margin-left: 8px; }
.sku-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
.sku-table th, .sku-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: 13px; }
.sku-table th { color: var(--color-text-secondary); font-weight: 600; }
.sku-table input, .sku-table select { padding: 4px 6px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; background: var(--color-bg); color: var(--color-text); }
.sku-duplicate td { background: #fff3cd; }
.col-default { text-align: center; }
.sku-warning { font-size: 12px; color: #856404; margin: 4px 0; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; padding: 16px 0; }
.dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--color-surface); border-radius: 12px; padding: 24px; max-width: 420px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.dialog h3 { margin-bottom: 16px; color: var(--color-text); }
.dialog-warn ul, .dialog-suggest ul { margin: 8px 0 0 16px; font-size: 14px; color: var(--color-text-secondary); }
.dialog-warn ul li { color: #856404; }
.dialog p { margin: 8px 0; font-size: 14px; color: var(--color-text); }
.dialog-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.loading, .error { text-align: center; padding: 40px; color: var(--color-text-secondary); }

/* Word Import */
.word-import-section { background: var(--color-bg); border-style: dashed; }
.word-import-row { display: flex; align-items: center; gap: 12px; }
.word-status { font-size: 13px; }
.word-ok { color: #176b3a; font-weight: 500; }
.word-err { color: #dc3545; }

/* Knowledge inline */
.chip-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.chip-label { font-size: 13px; color: var(--color-text-secondary); font-weight: 600; margin-right: 4px; }
.chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; background: var(--color-primary-light); color: var(--color-primary); border-radius: 6px; font-size: 12px; font-weight: 500; }
.chip-remove { background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; color: var(--color-primary); opacity: 0.6; }
.chip-remove:hover { opacity: 1; }
.entity-select-row { display: flex; gap: 8px; margin-bottom: 6px; align-items: center; }
.entity-select-row select { flex: 1; }
.inline-buttons { display: flex; gap: 8px; margin-top: 8px; }
.input-full { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); font-family: var(--font-sans); resize: vertical; }
</style>
