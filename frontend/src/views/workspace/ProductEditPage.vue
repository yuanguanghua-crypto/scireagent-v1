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
const saveFeedback = ref({ type: '', message: '' })   // toast instead of alert
const showPublishDialog = ref(false)
const loading = ref(false)
const loadError = ref('')
const publishedButIncomplete = ref(false)  // 2.11 — 已发布但不够完整

// Word import / AI states
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

// ── Dropdown options — pulled from Product model Choices ────
const purityOpts = ['≥ 99% (HPLC)', '≥ 98% (HPLC)', '≥ 97% (HPLC)', '≥ 95% (HPLC)', '≥ 90% (HPLC)', '≥ 99% (PAGE)', '≥ 95% (PAGE)', '≥ 98% (TLC)']
const concentrationOpts = ['100 mM', '50 mM', '10 mM', '1 mM', '100 µM', '10 µM', 'solid']
const storageOpts = ['-20°C', '-20°C, protect from light', '-80°C', '4°C', '4°C, protect from light', 'Room temperature', 'Room temperature, dry']
const shippingOpts = ['Dry Ice', 'Blue Ice', 'Ambient', 'Cold Pack']
const leadTimeOpts = ['In stock, ships same day', '1-3 business days', '3-5 business days', '1-2 weeks', '2-4 weeks', '4-6 weeks']
const shelfLifeOpts = ['12 months', '24 months', '6 months']
const packSizeUnits = ['µg', 'mg', 'g', 'µL', 'mL', 'L']
const concentrationUnits = ['mM', 'µM', 'M', 'mg/mL', 'µg/mL', '%']

// L1/L2 category options — loaded from ProductClass API
const categoryL1Options = ref([])
const categoryL2Options = ref([])

async function loadCategoryOptions() {
  try {
    const resp = await http.get('/product-classes/', { params: { page_size: 500 } })
    const all = resp.data?.results || resp.data || []
    categoryL1Options.value = all.filter(c => !c.parent_id).map(c => ({ value: c.slug, label: c.name }))
    categoryL2Options.value = all.filter(c => c.parent_id).map(c => ({ value: c.name, label: c.name, parent_slug: c.parent_id }))
  } catch { /* ignore */ }
}

// Completeness — 5 conditions matching backend _is_product_complete
const isComplete = computed(() => {
  return !!(form.name && form.catalog_no && form.cas && form.smiles && form.category_l1 &&
    skus.value.some(s => s.is_default))
})
const incompleteItems = computed(() => {
  const items = []
  if (!(form.name && form.catalog_no)) items.push('Name/Catalog No')
  if (!form.cas) items.push('CAS')
  if (!form.smiles) items.push('SMILES')
  if (!form.category_l1) items.push('Category L1')
  if (!skus.value.some(s => s.is_default)) items.push('Default SKU')
  return items
})
const suggestionsMissing = computed(() => {
  const missing = []
  if (!form.cas) missing.push('CAS')
  if (!form.smiles) missing.push('SMILES')
  if (!form.formula) missing.push('Formula')
  if (!form.molecular_weight) missing.push('Molecular Weight')
  if (!methodIds.value.length && !protocolIds.value.length) missing.push('Knowledge Links')
  if (!form.seo_title && !form.seo_description) missing.push('SEO metadata')
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

function addSku() {
  skus.value.push({
    _key: Date.now() + Math.random(),
    sku_code: '', pack_size: '', pack_unit: 'mg', concentration: form.concentration || '',
    conc_unit: 'mM', price: '0.00', currency: 'USD', inventory_status: 'in_stock',
    lead_time: '', is_default: skus.value.length === 0,
  })
}
function removeSku(idx) { skus.value.splice(idx, 1) }

// 拆分存储的 "10 µL" 字符串 → {value, unit}，用于回填 SKU 表格的分离输入
// 非数字开头（如 "solid"）整体作为 value，无单位
function splitValueUnit(str, defaultUnit) {
  if (!str) return { value: '', unit: defaultUnit }
  const m = String(str).match(/^(\d+(?:\.\d+)?)\s*(.*)$/)
  if (m) return { value: m[1], unit: m[2] || defaultUnit }
  return { value: String(str), unit: '' }
}
// 合并 value+unit → "10 µL"，unit 为空时只返回 value
function joinValueUnit(value, unit) {
  if (!value) return ''
  return unit ? `${value} ${unit}`.trim() : String(value)
}

// ── Word Import ─────────────────────────────────────
async function handleWordFile(e) {
  wordFile.value = e.target.files?.[0]
  if (!wordFile.value) return
  wordImporting.value = true
  wordResult.value = null
  try {
    const fd = new FormData()
    fd.append('file', wordFile.value)
    const resp = await http.post('/products/parse-word/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    wordResult.value = resp.data
    if (wordResult.value && !wordResult.value.error) {
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
  // Pre-fill SKUs from word import
  if (data.skus && data.skus.length) {
    skus.value = data.skus.map((s, i) => ({
      _key: Date.now() + i,
      sku_code: s.sku_code || '',
      pack_size: s.pack_size || '',
      pack_unit: s.pack_unit || 'mg',
      concentration: s.concentration || form.concentration || '',
      conc_unit: s.conc_unit || 'mM',
      price: s.price || '0.00',
      currency: s.currency || 'USD',
      inventory_status: s.inventory_status || 'in_stock',
      lead_time: '',
      is_default: i === 0,
    }))
  }
  // Clear the completeness flag after prefill to avoid misleading ✓
  wordResult.value.prefilled = true
}

// ── SEO Auto-Generate ───────────────────────────────
const seoGenerating = ref(false)
async function autoGenerateSeo() {
  if (!isEdit.value) return
  seoGenerating.value = true
  try {
    const resp = await http.post(`/products/${productId.value}/generate-seo/`)
    if (resp.data) {
      if (resp.data.seo_title) form.seo_title = resp.data.seo_title
      if (resp.data.seo_description) form.seo_description = resp.data.seo_description
      setFeedback('success', 'SEO generated successfully')
    }
  } catch (e) {
    setFeedback('error', 'SEO generation failed')
  } finally {
    seoGenerating.value = false
  }
}

// ── Feedback toast (replaces alert) ──────────────────
function setFeedback(type, message) {
  saveFeedback.value = { type, message }
  setTimeout(() => { saveFeedback.value = { type: '', message: '' } }, 4000)
}

// ── Input validation ─────────────────────────────────
function validateField(fieldName) {
  const val = form[fieldName]
  if (!val && typeof val === 'string') return null
  // Detect obviously invalid CAS/SMILES patterns
  if (fieldName === 'cas' && val) {
    // CAS format: digits-digits-digits (last digit is checksum)
    if (!/^\d{1,7}-\d{2}-\d$/.test(val)) return 'Invalid CAS format (e.g. 1927-31-7)'
  }
  if (fieldName === 'smiles' && val) {
    // Basic SMILES check — no unescaped special chars
    if (/[<>{}|\\]/.test(val)) return 'SMILES contains invalid characters'
  }
  if (fieldName === 'formula' && val) {
    if (/[^A-Za-z0-9\s().,+\-*/[\]]/.test(val)) return 'Formula contains invalid characters'
  }
  if (fieldName === 'molecular_weight' && val !== null) {
    if (isNaN(val) || val <= 0) return 'Molecular weight must be a positive number'
  }
  return null
}

// ── Knowledge inline ────────────────────────────────
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
    knowledgeList.value.goals = (Array.isArray(g.data) ? g.data : (g.data?.results || []))
    knowledgeList.value.apps = (Array.isArray(a.data) ? a.data : (a.data?.results || []))
    knowledgeList.value.methods = (Array.isArray(m.data) ? m.data : (m.data?.results || []))
    knowledgeList.value.protocols = (Array.isArray(p.data) ? p.data : (p.data?.results || []))
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

// Combined add-existing toggle — replaces two separate select+button blocks
const linkMethodSelect = ref('')
const linkProtocolSelect = ref('')
function addSelectedMethod() {
  if (linkMethodSelect.value) { toggleMethodId(Number(linkMethodSelect.value)); linkMethodSelect.value = '' }
}
function addSelectedProtocol() {
  if (linkProtocolSelect.value) { toggleProtocolId(Number(linkProtocolSelect.value)); linkProtocolSelect.value = '' }
}

async function saveInlineEntity() {
  inlineSaving.value = true
  const type = inlineEntityType.value
  const payload = { name: inlineForm.name }
  if (type === 'goal' || type === 'app') payload.summary = inlineForm.summary
  if (type === 'method') payload.purpose = inlineForm.purpose
  try {
    const resp = await http.post(apiEndpoints[type], payload)
    const newId = resp.data?.id
    if (newId) {
      if (type === 'method') methodIds.value.push(newId)
      if (type === 'protocol') protocolIds.value.push(newId)
    }
    showInlineEditor.value = false
    await loadKnowledge()
    setFeedback('success', `${type} created and linked`)
  } catch (e) {
    setFeedback('error', 'Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    inlineSaving.value = false
  }
}

// ── AI adopt handlers ───────────────────────────────
// P0-1: link-method / link-app from AiToolsPanel matched results
async function handleLinkMethod(methodData) {
  const mId = methodData.id
  if (!mId) return
  toggleMethodId(mId)
  if (!knowledgeList.value.methods.find(m => m.id === mId)) {
    await loadKnowledge()
  }
  setFeedback('success', `Linked Method: ${methodData.name}`)
}

async function handleLinkApp(appData) {
  const aId = appData.id
  if (!aId) return
  // Load the app's methods and link them all
  try {
    const resp = await http.get(`/applications/${aId}/`)
    const methods = resp.data?.methods || []
    for (const m of methods) {
      toggleMethodId(m.id)
    }
    setFeedback('success', `Linked Application "${appData.name}" → ${methods.length} methods`)
  } catch {
    setFeedback('error', 'Failed to load application methods')
  }
}

// ── One-stop Enrich (PubChem + ChEMBL + Literature + Protocols) ──
import { enrichProduct, importProtocol } from '@/api/aiTools'
const pubchemEnriching = ref(false)
const pubchemEnrichResult = ref(null)
const protocolExpanded = ref({})
const protocolImported = ref({})
const protocolImportingId = ref(null)

function toggleProtocolExpand(i) {
  protocolExpanded.value[i] = !protocolExpanded.value[i]
}

async function importSingleProtocol(idx) {
  const p = enrichProtocols.value[idx]
  if (!p) return
  protocolImportingId.value = idx
  try {
    const resp = await importProtocol({
      method_name: p.method_hint || p.title || '',
      protocol_title: p.title || '',
      protocol_url: p.url || '',
      objective: p.abstract || '',
      reagents: p.reagents || '',
      equipment: p.equipment || '',
      materials: p.materials || '',
      steps: p.steps || [],
      method_ids: methodIds.value,  // link to current product
    })
    if (resp.success) {
      protocolImported.value[idx] = true
      // Add new method_id to current product
      const newMethodId = resp.data.method_id
      if (newMethodId && !methodIds.value.includes(newMethodId)) {
        methodIds.value.push(newMethodId)
      }
      await loadKnowledge()
      setFeedback('success', 'Protocol imported to knowledge base')
    }
  } catch (e) {
    setFeedback('error', 'Import failed: ' + (e?.response?.data?.meta?.error?.message || e.message))
  } finally {
    protocolImportingId.value = null
  }
}

// Computed: extract sections from new enrich format { chemical, literature, protocols }
const enrichChemical = computed(() => pubchemEnrichResult.value?.chemical || pubchemEnrichResult.value)
const enrichLiterature = computed(() => pubchemEnrichResult.value?.literature || null)
const enrichProtocols = computed(() => pubchemEnrichResult.value?.protocols || null)

async function runPubchemEnrich() {
  const ids = {
    name: (form.name || '').trim(),
    cas: (form.cas || '').trim(),
    smiles: (form.smiles || '').trim(),
    inchi: (form.inchi || '').trim(),
  }
  if (!ids.name && !ids.cas && !ids.smiles && !ids.inchi) return
  pubchemEnriching.value = true
  pubchemEnrichResult.value = null
  try {
    const resp = await enrichProduct(ids)
    pubchemEnrichResult.value = resp.data
  } catch (e) {
    pubchemEnrichResult.value = { error: e?.response?.data?.meta?.error?.message || 'Enrich failed' }
  } finally {
    pubchemEnriching.value = false
  }
}

function applyPubchemProperties() {
  const data = pubchemEnrichResult.value
  // New enrich format: { chemical: {...}, literature: {...}, protocols: [...] }
  const chem = data?.chemical || data
  if (!chem || !chem.properties) return
  const p = chem.properties
  if (p.canonical_smiles && !form.smiles) form.smiles = p.canonical_smiles
  if (p.inchi && !form.inchi) form.inchi = p.inchi
  if (p.molecular_formula && !form.formula) form.formula = p.molecular_formula
  if (p.molecular_weight) form.molecular_weight = Number(p.molecular_weight) || null
  if (chem.cas_resolved && !form.cas) form.cas = chem.cas_resolved
  pubchemEnrichResult.value = { ...data, applied: true }
  setFeedback('success', 'Chemical properties applied to form')
}

async function adoptProtocol(protocolData) {
  try {
    const resp = await http.post('/protocols/', { name: protocolData.title })
    const newId = resp.data?.id
    if (newId) { protocolIds.value.push(newId); await loadKnowledge(); setFeedback('success', 'Protocol adopted') }
  } catch (e) {
    setFeedback('error', 'Failed to adopt protocol')
  }
}

async function adoptReference(refData) {
  try {
    const resp = await http.post('/references/', {
      title: refData.citation || refData.doi || 'Untitled',
      doi: refData.doi || '',
      citation: refData.citation || '',
      source_type: 'journal',
    })
    if (resp.data?.id) { setFeedback('success', 'Reference adopted') }
  } catch (e) {
    setFeedback('error', 'Failed to adopt reference')
  }
}

// ── Load / Save / Publish ───────────────────────────
async function loadProduct() {
  if (!productId.value) { loadCategoryOptions(); loadKnowledge(); return }  // load knowledge list for new products too
  loading.value = true
  try {
    const resp = await http.get(`/products/${productId.value}/`)
    if (resp.data) {
      const d = resp.data
      Object.keys(form).forEach(k => { if (k in d) form[k] = d[k] ?? form[k] })
      if (d.skus) skus.value = d.skus.map(s => {
        const ps = splitValueUnit(s.pack_size, 'mg')
        const cs = splitValueUnit(s.concentration, 'mM')
        return {
          ...s,
          _key: s.id || Date.now() + Math.random(),
          pack_size: ps.value, pack_unit: ps.unit,
          concentration: cs.value, conc_unit: cs.unit,
        }
      })
      methodIds.value = d.method_ids || []
      protocolIds.value = d.protocol_ids || []
      // 2.11 — check if published but missing suggested fields
      if (d.status === 'active') {
        const missing = []
        if (!d.cas) missing.push('CAS')
        if (!d.smiles) missing.push('SMILES')
        if (!d.formula) missing.push('Formula')
        if (!d.molecular_weight) missing.push('Molecular Weight')
        if (!(d.method_ids || []).length && !(d.protocol_ids || []).length) missing.push('Knowledge Links')
        if (!d.seo_title && !d.seo_description) missing.push('SEO')
        if (missing.length) {
          publishedButIncomplete.value = true
        }
      }
    }
    loadKnowledge()
    loadCategoryOptions()
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
    skus: skus.value.map(({ _key, pack_unit, conc_unit, ...s }) => ({
      ...s,
      pack_size: joinValueUnit(s.pack_size, pack_unit),
      concentration: joinValueUnit(s.concentration, conc_unit),
    })),
    method_ids: methodIds.value,
    protocol_ids: protocolIds.value,
  }
  try {
    if (isEdit.value) {
      await http.put(`/products/${productId.value}/`, payload)
      setFeedback('success', 'Draft saved')
    } else {
      const resp = await http.post('/products/', payload)
      const newId = resp.data?.id
      if (newId) {
        router.replace(`/workspace/products/${newId}/edit`)
        setFeedback('success', 'Product created. Edit details and publish when ready.')
      }
    }
  } catch (e) {
    setFeedback('error', 'Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
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

onMounted(() => {
  loadProduct()
  if (!isEdit.value) loadCategoryOptions()
})
</script>

<template>
  <div class="product-edit" v-if="!loading">
    <div v-if="loadError" class="error">{{ loadError }}</div>

    <!-- Published incomplete warning (2.11) -->
    <div v-if="publishedButIncomplete && form.status === 'active'" class="incomplete-banner">
      ⚠ This product is published but is missing some recommended fields
      ({{ suggestionsMissing.join(', ') }}).
      Consider completing them for better quality.
    </div>

    <!-- Completeness bar -->
    <div class="completeness-bar" :class="isComplete ? 'completeness-ok' : 'completeness-warn'">
      <span v-if="isComplete">✓ Complete</span>
      <span v-else>✗ Incomplete — missing: {{ incompleteItems.join(', ') }}</span>
    </div>

    <!-- Feedback toast -->
    <div v-if="saveFeedback.message" class="toast" :class="'toast-' + saveFeedback.type">
      {{ saveFeedback.message }}
    </div>

    <!-- Word Import Panel — 3.9 clearer button -->
    <section class="form-section word-import-section">
      <h3>📄 Word Import (optional)</h3>
      <div class="word-import-row">
        <label class="file-upload-btn">
          Choose .docx File
          <input type="file" accept=".docx" @change="handleWordFile" hidden />
        </label>
        <span v-if="wordFile" class="file-name">{{ wordFile.name }}</span>
        <span v-if="wordImporting" class="word-status">Parsing…</span>
        <span v-else-if="wordResult && wordResult.prefilled" class="word-status word-ok">
          ✓ {{ wordResult.fields_found || '' }} fields extracted — review before publishing
        </span>
        <span v-else-if="wordResult && !wordResult.error" class="word-status word-ok">
          {{ wordResult.fields_found }} fields extracted
        </span>
        <span v-else-if="wordResult && wordResult.error" class="word-status word-err">
          {{ wordResult.error }}
        </span>
      </div>
      <p class="form-hint">Upload a .docx product specification to pre-fill the form. All pre-filled values must be reviewed before publishing.</p>
    </section>

    <!-- PubChem Auto-fill Panel -->
    <section v-if="form.name || form.cas || form.smiles || form.inchi" class="form-section pubchem-enrich-section">
      <h3>🔍 Auto-fill from PubChem</h3>
      <div class="word-import-row">
        <button type="button" class="file-upload-btn" @click="runPubchemEnrich" :disabled="pubchemEnriching || (!form.name && !form.cas && !form.smiles && !form.inchi)">
          {{ pubchemEnriching ? 'Searching PubChem…' : `Look up "${form.name || form.cas || form.smiles || form.inchi}" in PubChem` }}
        </button>
        <span v-if="pubchemEnrichResult && enrichChemical?.found && !pubchemEnrichResult.applied" class="word-status word-ok">
          ✓ Found: {{ enrichChemical.source === 'chembl' ? 'ChEMBL' : 'PubChem' }} CID {{ enrichChemical.cid }} <template v-if="enrichChemical.fallback_used">(via fragment search)</template>
        </span>
        <span v-else-if="pubchemEnrichResult && pubchemEnrichResult.applied" class="word-status word-ok">
          ✓ Properties applied to form
        </span>
        <span v-else-if="pubchemEnrichResult && pubchemEnrichResult.error" class="word-status word-err">
          {{ pubchemEnrichResult.error }}
        </span>
        <span v-else-if="pubchemEnrichResult && !enrichChemical?.found && !pubchemEnrichResult.error" class="word-status word-warn">
          ✗ Not found in PubChem or ChEMBL
        </span>
      </div>
      <!-- Preview -->
      <!-- New enrich format: { chemical: {...}, literature: {...}, protocols: [...] } -->
      <div v-if="enrichChemical && enrichChemical.found && !pubchemEnrichResult.applied" class="pubchem-preview">
        <template v-if="enrichChemical.source">
          <p class="source-badge" :class="'source-' + enrichChemical.source">
            {{ enrichChemical.source === 'chembl' ? 'ChEMBL' : 'PubChem' }}
            <template v-if="enrichChemical.search_note"> — {{ enrichChemical.search_note }}</template>
          </p>
        </template>
        <table>
          <tr><td>Resolved Name:</td><td>{{ enrichChemical.resolved_name || '—' }}</td></tr>
          <tr><td>CID:</td><td>{{ enrichChemical.cid }}</td></tr>
          <tr v-if="enrichChemical.cas_resolved"><td>CAS:</td><td class="prop-highlight">{{ enrichChemical.cas_resolved }}</td></tr>
          <tr v-else><td>CAS:</td><td class="prop-missing">— (not indexed)</td></tr>
          <tr v-if="enrichChemical.properties.canonical_smiles"><td>SMILES:</td><td class="prop-highlight mono-wrap">{{ enrichChemical.properties.canonical_smiles }}</td></tr>
          <tr v-if="enrichChemical.properties.molecular_formula"><td>Formula:</td><td class="prop-highlight">{{ enrichChemical.properties.molecular_formula }}</td></tr>
          <tr v-if="enrichChemical.properties.molecular_weight"><td>MW:</td><td class="prop-highlight">{{ enrichChemical.properties.molecular_weight }} Da</td></tr>
          <tr v-if="enrichChemical.properties.inchi"><td>InChI:</td><td class="mono-wrap">{{ enrichChemical.properties.inchi }}</td></tr>
          <tr v-if="enrichChemical.properties.inchikey"><td>InChIKey:</td><td class="mono-wrap">{{ enrichChemical.properties.inchikey }}</td></tr>
          <tr v-if="enrichChemical.properties.iupac_name"><td>IUPAC:</td><td>{{ enrichChemical.properties.iupac_name }}</td></tr>
          <tr v-if="enrichChemical.properties.xlogp != null"><td>LogP:</td><td>{{ enrichChemical.properties.xlogp }}</td></tr>
          <tr v-if="enrichChemical.properties.tpsa != null"><td>TPSA:</td><td>{{ enrichChemical.properties.tpsa }} Å²</td></tr>
          <tr v-if="enrichChemical.properties.exact_mass != null"><td>Exact Mass:</td><td>{{ enrichChemical.properties.exact_mass }}</td></tr>
          <tr v-if="enrichChemical.properties.h_bond_donor_count != null"><td>HBD:</td><td>{{ enrichChemical.properties.h_bond_donor_count }}</td></tr>
          <tr v-if="enrichChemical.properties.h_bond_acceptor_count != null"><td>HBA:</td><td>{{ enrichChemical.properties.h_bond_acceptor_count }}</td></tr>
          <tr v-if="enrichChemical.properties.rotatable_bond_count != null"><td>RotB:</td><td>{{ enrichChemical.properties.rotatable_bond_count }}</td></tr>
        </table>
        <button type="button" class="btn btn-primary btn-sm" style="margin-top:8px" @click="applyPubchemProperties">
          Apply All to Form
        </button>
      </div>
      <!-- Literature & Protocols from enrich -->
      <div v-if="enrichLiterature && enrichLiterature.references?.length > 0 && !pubchemEnrichResult.applied" class="pubchem-preview" style="margin-top: 8px">
        <h4 style="margin:0 0 4px 0;font-size:13px">📚 Literature ({{ enrichLiterature.references.length }} references)</h4>
        <div v-for="(ref, i) in enrichLiterature.references.slice(0, 3)" :key="i" style="font-size:11px;margin-bottom:4px;color:var(--color-text-secondary)">
          {{ ref.citation?.substring(0, 120) }}{{ ref.citation?.length > 120 ? '...' : '' }}
        </div>
      </div>
      <div v-if="enrichProtocols && enrichProtocols.length > 0 && !pubchemEnrichResult.applied" class="pubchem-preview" style="margin-top: 8px">
        <h4 style="margin:0 0 8px 0;font-size:13px">🧪 Protocols ({{ enrichProtocols.length }} found)</h4>
        <div v-for="(p, i) in enrichProtocols.slice(0, 5)" :key="i" class="protocol-card">
          <div class="protocol-card-header" @click="toggleProtocolExpand(i)">
            <span style="font-weight:600;font-size:12px">{{ p.title || 'Untitled' }}</span>
            <span style="font-size:11px;color:var(--color-text-secondary)">[{{ p.source }}]</span>
            <span v-if="p.steps?.length" style="font-size:11px;color:var(--color-text-secondary)">{{ p.steps.length }} steps</span>
            <span style="margin-left:auto;font-size:11px">{{ protocolExpanded[i] ? '▲' : '▼' }}</span>
          </div>
          <div v-if="protocolExpanded[i]" class="protocol-card-body">
            <div v-if="p.abstract" style="font-size:11px;margin-bottom:4px;color:var(--color-text-secondary)">{{ p.abstract.substring(0, 200) }}</div>
            <div v-if="p.reagents" style="font-size:11px;margin-bottom:4px"><strong>Reagents:</strong><pre style="white-space:pre-wrap;font-size:10px;margin:2px 0">{{ p.reagents.substring(0, 300) }}</pre></div>
            <div v-if="p.equipment" style="font-size:11px;margin-bottom:4px"><strong>Equipment:</strong><pre style="white-space:pre-wrap;font-size:10px;margin:2px 0">{{ p.equipment.substring(0, 200) }}</pre></div>
            <div v-if="p.steps?.length" style="font-size:11px;margin-bottom:4px">
              <strong>Steps:</strong>
              <div v-for="s in p.steps.slice(0, 10)" :key="s.step_no" style="margin-left:8px;font-size:10px;color:var(--color-text-secondary)">{{ s.step_no }} — {{ s.body.substring(0, 80) }}</div>
              <div v-if="p.steps.length > 10" style="font-size:10px;color:var(--color-text-secondary)">... and {{ p.steps.length - 10 }} more steps</div>
            </div>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              style="margin-top:4px;font-size:11px"
              :disabled="protocolImportingId === i"
              @click="importSingleProtocol(i)"
            >{{ protocolImportingId === i ? 'Importing...' : '🔽 Import to Knowledge Base' }}</button>
            <span v-if="protocolImported[i]" style="font-size:11px;color:#059669;margin-left:8px">✓ Imported</span>
          </div>
        </div>
      </div>
      <!-- Ambiguous candidates -->
      <div v-if="pubchemEnrichResult && pubchemEnrichResult.candidates?.length > 0 && !pubchemEnrichResult.applied" class="pubchem-preview">
        <p class="form-hint">Multiple candidates found. Select the correct one or try with a CAS number.</p>
        <div v-for="c in pubchemEnrichResult.candidates" :key="c.cid" class="candidate-item">
          <strong>{{ c.iupac_name || '—' }}</strong>
          <span>CID: {{ c.cid }}, MW: {{ c.molecular_weight }}</span>
          <span v-if="c.cas">, CAS: {{ c.cas }}</span>
        </div>
      </div>
      <!-- Not found guidance -->
      <div v-if="pubchemEnrichResult && !pubchemEnrichResult.found && !pubchemEnrichResult.error && !pubchemEnriching" class="pubchem-notfound">
        <p class="form-hint">{{ pubchemEnrichResult.search_hint || 'Not found in PubChem. Try using a CAS number or entering SMILES/FW manually.' }}</p>
      </div>
      <p class="form-hint">One-click search across PubChem + ChEMBL + PubMed + BioProCorpus.</p>
    </section>

    <form @submit.prevent="saveDraft" class="edit-form">
      <!-- 1. Basic Info -->
      <section class="form-section">
        <h3>1. Basic Information</h3>
        <div class="field-grid">
          <label>Name *
            <input v-model="form.name" required placeholder="e.g. 2'-Amino-ATP" />
          </label>
          <label>Catalog No *
            <input v-model="form.catalog_no" required placeholder="e.g. SC8043" />
          </label>
          <label>CAS
            <input v-model="form.cas" placeholder="e.g. 1927-31-7" />
            <span v-if="validateField('cas')" class="field-error">{{ validateField('cas') }}</span>
          </label>
          <label>Synonyms
            <input v-model="form.synonyms" placeholder="comma separated" />
          </label>
          <label>Slug <input v-model="form.slug" placeholder="auto-generated-if-empty" /></label>
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
            <label>SMILES
              <textarea v-model="form.smiles" rows="2" placeholder="e.g. C1=CC=C(C=C1)N"></textarea>
              <span v-if="validateField('smiles')" class="field-error">{{ validateField('smiles') }}</span>
            </label>
            <label>InChI <textarea v-model="form.inchi" rows="2" placeholder="Standard InChI"></textarea></label>
            <label>Formula
              <input v-model="form.formula" placeholder="e.g. C10H17N6O13P3" />
              <span v-if="validateField('formula')" class="field-error">{{ validateField('formula') }}</span>
            </label>
            <label>Molecular Weight
              <input v-model.number="form.molecular_weight" type="number" step="0.01" placeholder="e.g. 522.2" />
              <span v-if="validateField('molecular_weight')" class="field-error">{{ validateField('molecular_weight') }}</span>
            </label>
            <button type="button" class="btn btn-ghost btn-sm" @click="showAiPanel = !showAiPanel">
              {{ showAiPanel ? 'Hide AI Tools' : 'AI Tools' }}
            </button>
          </div>
          <div class="chem-preview">
            <StructureViewer :smiles="form.smiles" :pubchem-cid="pubchemEnrichResult?.found ? pubchemEnrichResult.cid : null" />
          </div>
        </div>
        <!-- AI Tools Panel -->
        <div v-if="showAiPanel" class="ai-panel-wrapper">
          <AiToolsPanel
            :product-id="productId"
            :product-name="form.name"
            :product-cas="form.cas"
            :product-smiles="form.smiles"
            @adopt-smiles="(s) => form.smiles = s"
            @adopt-formula-weight="({ formula, weight }) => { if (formula) form.formula = formula; if (weight) form.molecular_weight = weight }"
            @adopt-protocol="adoptProtocol"
            @adopt-reference="adoptReference"
            @link-method="handleLinkMethod"
            @link-app="handleLinkApp"
          />
        </div>
      </section>

      <!-- 3. Scientific Parameters — real select dropdowns -->
      <section class="form-section">
        <h3>3. Scientific Parameters</h3>
        <div class="field-grid">
          <label>Purity
            <select v-model="form.purity">
              <option value="">— Custom —</option>
              <option v-for="o in purityOpts" :key="o" :value="o">{{ o }}</option>
            </select>
            <input v-if="form.purity === ''" v-model="form.purity" placeholder="Or enter custom" class="custom-under" />
          </label>
          <label>Concentration
            <select v-model="form.concentration">
              <option value="">— Custom —</option>
              <option v-for="o in concentrationOpts" :key="o" :value="o">{{ o }}</option>
            </select>
          </label>
          <label>Storage
            <select v-model="form.storage">
              <option value="">— Custom —</option>
              <option v-for="o in storageOpts" :key="o" :value="o">{{ o }}</option>
            </select>
          </label>
          <label>Shipping
            <select v-model="form.shipping">
              <option value="">— Custom —</option>
              <option v-for="o in shippingOpts" :key="o" :value="o">{{ o }}</option>
            </select>
          </label>
          <label>Lead Time
            <select v-model="form.lead_time">
              <option value="">— Custom —</option>
              <option v-for="o in leadTimeOpts" :key="o" :value="o">{{ o }}</option>
            </select>
          </label>
          <label>Shelf Life
            <select v-model="form.shelf_life">
              <option value="">— Custom —</option>
              <option v-for="o in shelfLifeOpts" :key="o" :value="o">{{ o }}</option>
            </select>
          </label>
          <label class="full-width">Handling Notes <textarea v-model="form.handling_notes" rows="2"></textarea></label>
        </div>
      </section>

      <!-- 4. Category — real L1/L2 dropdowns from DB -->
      <section class="form-section">
        <h3>4. Category</h3>
        <div class="field-grid">
          <label>L1 *
            <select v-model="form.category_l1">
              <option value="">— Select L1 category —</option>
              <option v-for="o in categoryL1Options" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>
          <label>L2
            <select v-model="form.category_l2">
              <option value="">— Optional —</option>
              <option v-for="o in categoryL2Options.filter(x => x.parent_slug === form.category_l1 || !form.category_l1)" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>
        </div>
      </section>

      <!-- 5. Knowledge Links — chips with click-to-view, single add buttons -->
      <section class="form-section">
        <h3>5. Knowledge Links</h3>

        <!-- Methods chips -->
        <div class="chip-group">
          <span class="chip-label">Methods:</span>
          <span v-for="mid in methodIds" :key="mid" class="chip">
            <a :href="`/methods/${mid}`" target="_blank" class="chip-link">{{ knowledgeList.methods.find(m => m.id === mid)?.name || `#${mid}` }}</a>
            <button type="button" class="chip-remove" @click="toggleMethodId(mid)" title="Unlink">✕</button>
          </span>
          <span v-if="!methodIds.length" class="chip-none">None</span>
        </div>

        <!-- Protocols chips -->
        <div class="chip-group">
          <span class="chip-label">Protocols:</span>
          <span v-for="pid in protocolIds" :key="pid" class="chip">
            <a :href="`/protocols/${pid}`" target="_blank" class="chip-link">{{ knowledgeList.protocols.find(p => p.id === pid)?.name || `#${pid}` }}</a>
            <button type="button" class="chip-remove" @click="toggleProtocolId(pid)" title="Unlink">✕</button>
          </span>
          <span v-if="!protocolIds.length" class="chip-none">None</span>
        </div>

        <!-- Add existing (single select + add button) -->
        <div class="entity-select-row">
          <select v-model="linkMethodSelect" class="filter-select">
            <option value="">— Link existing Method —</option>
            <option v-for="m in knowledgeList.methods" :key="m.id" :value="String(m.id)" :disabled="methodIds.includes(m.id)">{{ m.name }}</option>
          </select>
          <button type="button" class="btn btn-ghost btn-sm" @click="addSelectedMethod" :disabled="!linkMethodSelect">Link</button>

          <select v-model="linkProtocolSelect" class="filter-select" style="margin-left:16px">
            <option value="">— Link existing Protocol —</option>
            <option v-for="p in knowledgeList.protocols" :key="p.id" :value="String(p.id)" :disabled="protocolIds.includes(p.id)">{{ p.name }}</option>
          </select>
          <button type="button" class="btn btn-ghost btn-sm" @click="addSelectedProtocol" :disabled="!linkProtocolSelect">Link</button>
        </div>

        <!-- Quick-create inline (single button, dropdown type) -->
        <div class="inline-buttons">
          <span class="inline-label">Quick create:</span>
          <button type="button" class="btn btn-ghost btn-sm" @click="openInlineNew('method')">+ New Method</button>
          <button type="button" class="btn btn-ghost btn-sm" @click="openInlineNew('protocol')">+ New Protocol</button>
        </div>
      </section>

      <!-- 6. Description — wide input -->
      <section class="form-section">
        <h3>6. Description</h3>
        <label class="full-width-label">Overview
          <textarea v-model="form.overview" rows="8" maxlength="5000" class="desc-textarea" placeholder="Describe the product, its applications, and key features…"></textarea>
        </label>
        <span class="char-count">{{ (form.overview || '').length }} / 5000</span>
      </section>

      <!-- 7. SKUs — pack unit + conc unit as dropdowns -->
      <section class="form-section">
        <h3>7. SKUs</h3>
        <table class="sku-table" v-if="skus.length">
          <thead>
            <tr><th>Code</th><th>Pack Size</th><th>Unit</th><th>Concn</th><th>Unit</th><th>Price</th><th>Curr</th><th>Default</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in skus" :key="s._key" :class="{ 'sku-duplicate': skuDuplicate.has(i) }">
              <td><input v-model="s.sku_code" style="width:90px" /></td>
              <td><input v-model="s.pack_size" style="width:60px" type="number" step="any" min="0" /></td>
              <td>
                <select v-model="s.pack_unit"><option v-for="u in packSizeUnits" :key="u" :value="u">{{ u }}</option></select>
              </td>
              <td><input v-model="s.concentration" style="width:60px" /></td>
              <td>
                <select v-model="s.conc_unit"><option v-for="u in concentrationUnits" :key="u" :value="u">{{ u }}</option></select>
              </td>
              <td><input v-model="s.price" style="width:70px" type="number" step="0.01" min="0" /></td>
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
        <p v-if="skuDuplicate.size" class="sku-warning">⚠ Duplicate pack size + concentration combination detected</p>
        <p class="form-hint">Each SKU represents a purchasable variant. Set one as Default.</p>
      </section>

      <!-- 8. SEO -->
      <section class="form-section">
        <h3>8. SEO (auto-generated on publish)</h3>
        <div class="field-grid">
          <label>SEO Title <input v-model="form.seo_title" placeholder="Auto-generated if left empty" /></label>
          <label>SEO Description <input v-model="form.seo_description" placeholder="Auto-generated if left empty" /></label>
        </div>
        <button v-if="isEdit" type="button" class="btn btn-ghost btn-sm" style="margin-top:8px" @click="autoGenerateSeo" :disabled="seoGenerating">
          {{ seoGenerating ? 'Generating...' : 'Auto-generate SEO' }}
        </button>
        <p class="form-hint">SEO fields are auto-generated when publishing from draft → active if left empty.</p>
      </section>

      <!-- Actions -->
      <div class="form-actions">
        <button type="button" @click="saveDraft" class="btn btn-secondary" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Draft' }}
        </button>
        <button type="button" @click="handlePublish" class="btn btn-primary" :disabled="saving || !isComplete">
          {{ isComplete ? 'Publish' : 'Incomplete — fill required fields first' }}
        </button>
      </div>
    </form>

    <!-- Publish confirm dialog -->
    <div v-if="showPublishDialog" class="dialog-overlay" @click.self="showPublishDialog = false">
      <div class="dialog">
        <h3>Confirm Publish</h3>
        <div v-if="!isComplete" class="dialog-warn">
          <p>Product is incomplete — required fields missing:</p>
          <ul>
            <li v-for="item in incompleteItems" :key="item">✗ {{ item }}</li>
          </ul>
        </div>
        <div v-if="suggestionsMissing.length" class="dialog-suggest">
          <p>Recommended improvements:</p>
          <ul>
            <li v-for="s in suggestionsMissing" :key="s">◯ {{ s }}</li>
          </ul>
        </div>
        <p>Confirm publishing this product?</p>
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
.incomplete-banner { padding: 10px 16px; background: #d1ecf1; color: #0c5460; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
.edit-form { display: flex; flex-direction: column; gap: 0; }
.form-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 20px; margin-bottom: 16px; }
.form-section h3 { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--color-text); }
.field-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.field-grid label { display: flex; flex-direction: column; font-size: 13px; color: var(--color-text-secondary); gap: 4px; }
.field-grid input, .field-grid select, .field-grid textarea { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); font-family: var(--font-sans); }
.field-grid textarea { resize: vertical; }
.full-width { grid-column: span 2; }
.full-width-label { display: flex; flex-direction: column; font-size: 13px; color: var(--color-text-secondary); gap: 4px; }
.desc-textarea { width: 100%; padding: 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); font-family: var(--font-sans); resize: vertical; min-height: 120px; }
.char-count { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.chem-row { display: flex; gap: 20px; }
.chem-inputs { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.chem-inputs label { font-size: 13px; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 4px; }
.chem-inputs input, .chem-inputs textarea { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); resize: vertical; }
.ai-panel-wrapper { margin-top: 16px; border-top: 1px solid var(--color-border); padding-top: 16px; }
.form-hint { font-size: 12px; color: var(--color-text-secondary); margin-top: 8px; }
.field-error { font-size: 12px; color: #dc3545; }
.custom-under { margin-top: 4px; }
.toast { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; z-index: 2000; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.toast-success { background: #dcf7e8; color: #176b3a; }
.toast-error { background: #f8d7da; color: #721c24; }

/* Word Import */
.word-import-section { background: var(--color-bg); border-style: dashed; }
.word-import-row { display: flex; align-items: center; gap: 12px; }
.file-upload-btn { display: inline-block; padding: 8px 16px; border: 1.5px solid var(--color-primary); border-radius: 6px; color: var(--color-primary); font-size: 13px; font-weight: 500; cursor: pointer; background: white; }
.file-upload-btn:hover { background: var(--color-primary-light); }
.file-name { font-size: 13px; color: var(--color-text-secondary); }
.word-status { font-size: 13px; }
.word-ok { color: #176b3a; font-weight: 500; }
.word-err { color: #dc3545; }
.word-warn { color: #856404; font-weight: 500; }

/* PubChem Enrich */
.pubchem-enrich-section { background: var(--color-bg); border-style: dashed; }
.pubchem-preview { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 13px; }
.pubchem-preview table { width: 100%; border-collapse: collapse; }
.pubchem-preview td { padding: 4px 8px; border-bottom: 1px solid #dcfce7; font-size: 12px; }
.pubchem-preview td:first-child { color: var(--color-text-secondary); width: 120px; }
.prop-highlight { color: #059669; font-weight: 600; font-family: var(--font-mono); }
.prop-missing { color: var(--color-text-secondary); font-style: italic; }
.mono-wrap { font-family: var(--font-mono); font-size: 11px; word-break: break-all; }
.candidate-item { padding: 6px 8px; margin: 4px 0; background: #fff; border: 1px solid var(--color-border); border-radius: 6px; }
.candidate-item span { font-size: 11px; color: var(--color-text-secondary); margin-left: 8px; }
.source-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; display: inline-block; margin-bottom: 6px; }
.source-pubchem { background: #dbeafe; color: #1e40af; }
.source-chembl { background: #fef3c7; color: #92400e; }
.pubchem-notfound { background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
.pubchem-notfound .form-hint { margin-top: 0; color: #92400e; }

/* Protocol cards */
.protocol-card { border: 1px solid var(--color-border); border-radius: 6px; margin-bottom: 6px; overflow: hidden; }
.protocol-card-header { display: flex; gap: 8px; align-items: center; padding: 6px 10px; background: #f8fafc; cursor: pointer; user-select: none; }
.protocol-card-header:hover { background: #f1f5f9; }
.protocol-card-body { padding: 8px 10px; font-size: 11px; max-height: 400px; overflow-y: auto; }
.protocol-card-body pre { font-family: var(--font-mono); background: #f8fafc; padding: 4px 8px; border-radius: 4px; }


/* SKU table */
.sku-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
.sku-table th, .sku-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: 13px; }
.sku-table th { color: var(--color-text-secondary); font-weight: 600; }
.sku-table input, .sku-table select { padding: 4px 6px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; background: var(--color-bg); color: var(--color-text); }
.sku-duplicate td { background: #fff3cd; }
.col-default { text-align: center; }
.sku-warning { font-size: 12px; color: #856404; margin: 4px 0; }

/* Knowledge inline */
.chip-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.chip-label { font-size: 13px; color: var(--color-text-secondary); font-weight: 600; margin-right: 4px; }
.chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; background: var(--color-primary-light); color: var(--color-primary); border-radius: 6px; font-size: 12px; font-weight: 500; }
.chip-link { color: var(--color-primary); text-decoration: none; }
.chip-link:hover { text-decoration: underline; }
.chip-remove { background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; color: var(--color-primary); opacity: 0.6; }
.chip-remove:hover { opacity: 1; }
.chip-none { font-size: 12px; color: var(--color-text-secondary); font-style: italic; }
.entity-select-row { display: flex; gap: 8px; margin-bottom: 6px; align-items: center; flex-wrap: wrap; }
.entity-select-row select { flex: 1; min-width: 180px; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 13px; background: var(--color-bg); color: var(--color-text); }
.inline-buttons { display: flex; gap: 8px; margin-top: 8px; align-items: center; }
.inline-label { font-size: 13px; color: var(--color-text-secondary); }
.input-full { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); font-family: var(--font-sans); resize: vertical; }

.form-actions { display: flex; gap: 12px; justify-content: flex-end; padding: 16px 0; }

.dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--color-surface); border-radius: 12px; padding: 24px; max-width: 480px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.dialog h3 { margin-bottom: 16px; color: var(--color-text); }
.dialog-warn ul, .dialog-suggest ul { margin: 8px 0 0 16px; font-size: 14px; color: var(--color-text-secondary); }
.dialog-warn ul li { color: #856404; }
.dialog p { margin: 8px 0; font-size: 14px; color: var(--color-text); }
.dialog-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.loading, .error { text-align: center; padding: 40px; color: var(--color-text-secondary); }
</style>
