<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/api/http'
import * as documentsApi from '@/api/documents'
import { openPreview } from '@/utils/previewInject'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { AppInput, AppSelect, LoadingSpinner } from '@/components/common'

import StructureViewer from './components/StructureViewer.vue'

import JenaMatchSection from './components/JenaMatchSection.vue'
import BiozEvidenceSection from './components/BiozEvidenceSection.vue'

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

// 必填字段标红：collectMissing 计算缺失项，missingFields 保存 key 列表供 isFieldMissing() 使用。
// 告知模式（CLAUDE.md 规则5）：缺失只标红提示，不阻止保存/发布，研究员拥有最终决定权。
const missingFields = ref([])
const REQUIRED_FIELDS = [
  { key: 'name', label: 'Name' },
  { key: 'catalog_no', label: 'Catalog No' },
  { key: 'cas', label: 'CAS' },
  { key: 'smiles', label: 'SMILES' },
  { key: 'product_class_id', label: 'Category' },
]
function collectMissing() {
  const out = []
  if (!form.name) out.push({ key: 'name', label: 'Name' })
  if (!form.catalog_no) out.push({ key: 'catalog_no', label: 'Catalog No' })
  if (!form.cas) out.push({ key: 'cas', label: 'CAS' })
  if (!form.smiles) out.push({ key: 'smiles', label: 'SMILES' })
  if (!form.product_class_id) out.push({ key: 'product_class_id', label: 'Category' })
  if (!skus.value.some(s => s.is_default)) out.push({ key: 'default_sku', label: 'Default SKU' })
  return out
}
function isFieldMissing(key) {
  return missingFields.value.includes(key)
}

// Word import / AI states
const wordImporting = ref(false)
const wordFile = ref(null)
const wordResult = ref(null)


// ── Knowledge inline editor ─────────────────
const showInlineEditor = ref(false)
const inlineEntityType = ref('method')
const inlineForm = reactive({ name: '', summary: '', purpose: '', reagent: '', amount: '', duration: '' })
const inlineSaving = ref(false)
const knowledgeList = ref({ goals: [], apps: [], methods: [], protocols: [] })

// ── Dialog accessibility (ARIA + ESC + focus 管理) ─────────────────
const publishOverlay = ref(null)
const inlineOverlay = ref(null)
const publishAttrs = useDialogA11y(showPublishDialog, publishOverlay, {
  titleId: 'publish-title',
  close: () => { showPublishDialog.value = false },
})
const inlineAttrs = useDialogA11y(showInlineEditor, inlineOverlay, {
  titleId: 'inline-title',
  close: () => { showInlineEditor.value = false },
})

// Form
const form = reactive({
  name: '', slug: '', catalog_no: '', cas: '', smiles: '', synonyms: '',
  inchi: '', formula: '', molecular_weight: null, purity: '', concentration: '',
  storage: '', shipping: '', lead_time: '', handling_notes: '', shelf_life: '',
  research_use_only: true, overview: '', structure_svg: '', structure_image: '',
  seo_title: '', seo_description: '',
  status: 'draft', product_class_id: null,
})

// Cascader value: array of ids [l1_id, l2_id] or [l1_id, l2_id, l3_id]
const categoryCascaderValue = ref([])
// Pending product_class_id to apply after options load (edit mode)
const pendingProductClassId = ref(null)

const skus = ref([])
const methodIds = ref([])
const protocolIds = ref([])

// ── Dropdown options — pulled from Product model Choices ────
const purityOpts = ['≥ 99% (HPLC)', '≥ 98% (HPLC)', '≥ 97% (HPLC)', '≥ 95% (HPLC)', '≥ 90% (HPLC)', '≥ 99% (PAGE)', '≥ 95% (PAGE)', '≥ 98% (TLC)']
const concentrationOpts = ['100 mM', '50 mM', '10 mM', '1 mM', '100 µM', '10 µM', 'solid']
const storageOpts = ['-20°C', '-20°C, protect from light', '-80°C', '4°C', '4°C, protect from light', 'Room temperature', 'Room temperature, dry']
const shippingOpts = ['Dry Ice', 'Blue Ice', 'Ambient', 'Cold Pack']
const leadTimeOpts = ['In stock, ships same day', '1-3 business days', '3-5 business days', '1-2 weeks', '2-4 weeks', '4-6 weeks']
const shelfLifeOpts = [
  { label: '1 year', value: 'P1Y' },
  { label: '2 years', value: 'P2Y' },
  { label: '3 years', value: 'P3Y' },
  { label: '5 years', value: 'P5Y' },
]
const packSizeUnits = ['µg', 'mg', 'g', 'µL', 'mL', 'L']
const concentrationUnits = ['mM', 'µM', 'M', 'mg/mL', 'µg/mL', '%']

// AppSelect options (computed from existing choice arrays)
const statusOptions = [
  { label: 'Draft', value: 'draft' },
  { label: 'Active', value: 'active' },
  { label: 'Deprecated', value: 'deprecated' },
  { label: 'Archived', value: 'archived' },
]
const purityOptions = [{ label: '— Custom —', value: '' }].concat(purityOpts.map(o => ({ label: o, value: o })))
const concentrationSelectOpts = [{ label: '— Custom —', value: '' }].concat(concentrationOpts.map(o => ({ label: o, value: o })))
const storageOptions = [{ label: '— Custom —', value: '' }].concat(storageOpts.map(o => ({ label: o, value: o })))
const shippingOptions = [{ label: '— Custom —', value: '' }].concat(shippingOpts.map(o => ({ label: o, value: o })))
const leadTimeOptions = [{ label: '— Custom —', value: '' }].concat(leadTimeOpts.map(o => ({ label: o, value: o })))
const shelfLifeOptions = [{ label: '— Custom —', value: '' }].concat(shelfLifeOpts)
const packUnitOptions = packSizeUnits.map(u => ({ label: u, value: u }))
const concUnitOptions = concentrationUnits.map(u => ({ label: u, value: u }))
const currencyOptions = [
  { label: 'USD', value: 'USD' },
  { label: 'CNY', value: 'CNY' },
  { label: 'EUR', value: 'EUR' },
]

// Category cascader options — tree built from ProductClass API
const categoryCascaderOptions = ref([])

async function loadCategoryOptions() {
  try {
    const resp = await http.get('/product-classes/', { params: { page_size: 500 } })
    const all = resp.data?.results || resp.data || []
    // Build 3-level tree: L1 → L2 → L3
    categoryCascaderOptions.value = all
      .filter(c => !c.parent_id)
      .map(l1 => {
        const l2s = all.filter(c => c.parent_id === l1.id).map(l2 => {
          const l3s = all.filter(c => c.parent_id === l2.id).map(l3 => ({
            value: l3.id, label: l3.name,
          }))
          const l2node = { value: l2.id, label: l2.name }
          if (l3s.length) l2node.children = l3s
          return l2node
        })
        return { value: l1.id, label: l1.name, slug: l1.slug, children: l2s }
      })
    // Apply pending product_class_id once options are loaded
    if (pendingProductClassId.value) {
      const path = _findIdPath(categoryCascaderOptions.value, pendingProductClassId.value)
      if (path) categoryCascaderValue.value = path
      pendingProductClassId.value = null
    }
  } catch { /* ignore */ }
}

// Find cascader id-path from a product_class_id by walking up parents via flat options
function _findIdPath(options, targetId, path = []) {
  for (const node of options) {
    const next = [...path, node.value]
    if (node.value === targetId) return next
    if (node.children) {
      const found = _findIdPath(node.children, targetId, next)
      if (found) return found
    }
  }
  return null
}

// Apply cascader selection → set product_class_id
function onCategoryChange(val) {
  if (Array.isArray(val) && val.length) {
    form.product_class_id = val[val.length - 1]
  } else {
    form.product_class_id = null
  }
}

// Completeness — 5 conditions matching backend _is_product_complete
const isComplete = computed(() => {
  return !!(form.name && form.catalog_no && form.cas && form.smiles && form.product_class_id &&
    skus.value.some(s => s.is_default))
})
const incompleteItems = computed(() => {
  const items = []
  if (!(form.name && form.catalog_no)) items.push('Name/Catalog No')
  if (!form.cas) items.push('CAS')
  if (!form.smiles) items.push('SMILES')
  if (!form.product_class_id) items.push('Category')
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
  if (data.storage) form.storage = normalizeStorage(data.storage)
  if (data.shipping) form.shipping = normalizeShipping(data.shipping)
  if (data.synonyms) form.synonyms = data.synonyms
  if (data.description) form.overview = data.description
  // 文档原样字段：SMILES / 结构图 必须保持原样，不做任何加工（用户要求）
  if (data.smiles) form.smiles = data.smiles
  if (data.structure_image_base64) form.structure_image = data.structure_image_base64
  // Pre-fill SKUs from word import
  if (data.skus && data.skus.length) {
    const importCatNo = (data.catalog_number || form.catalog_no || 'SKU').trim()
    skus.value = data.skus.map((s, i) => ({
      _key: Date.now() + i,
      sku_code: s.sku_code || `${importCatNo}-${i + 1}`,
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
    const seoData = resp?.data || resp
    if (seoData) {
      if (seoData.seo_title) form.seo_title = seoData.seo_title
      if (seoData.seo_description) form.seo_description = seoData.seo_description
      // ④ 生成后明确引导
      setFeedback('success', 'SEO generated. It is auto-applied on publish if title/description are left empty.')
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
function addSelectedMethod(val) {
  const raw = (val != null && val !== '') ? val : linkMethodSelect.value
  if (raw) { toggleMethodId(Number(raw)); linkMethodSelect.value = '' }
}
function addSelectedProtocol(val) {
  const raw = (val != null && val !== '') ? val : linkProtocolSelect.value
  if (raw) { toggleProtocolId(Number(raw)); linkProtocolSelect.value = '' }
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
    setFeedback('error', 'Save failed: ' + formatSaveError(e))
  } finally {
    inlineSaving.value = false
  }
}

// ── One-stop Enrich (PubChem + ChEMBL + Literature + Protocols) ──
import {
  enrichProduct,
  importProtocol,
  adoptBiozRefs,
} from '@/api/aiTools'
const pubchemEnriching = ref(false)
const pubchemEnrichResult = ref(null)
const protocolExpanded = ref({})
const protocolImported = ref({})
const protocolImportingId = ref(null)
const adoptedRefs = ref(new Set())  // 本地标记已 adopt 的 ref index（bioz）

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
      product_id: isEdit.value ? productId.value : null,  // 关联当前产品（编辑页有 id；新建成品为 null，保存时按数组重建）
    })
    if (resp.success) {
      protocolImported.value[idx] = true
      // 写入 method_id 与 protocol_id 到当前产品（修复此前 Protocols: None）
      const newMethodId = resp.data.method_id
      if (newMethodId && !methodIds.value.includes(newMethodId)) {
        methodIds.value.push(newMethodId)
      }
      const newProtocolId = resp.data.protocol_id
      if (newProtocolId && !protocolIds.value.includes(newProtocolId)) {
        protocolIds.value.push(newProtocolId)
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
const enrichJena = computed(() => pubchemEnrichResult.value?.jena || null)
const enrichBioz = computed(() => pubchemEnrichResult.value?.bioz || null)
// 化学属性是否「已验证、可安全自动套用」（修复 1/3）：
// 仅当后端 identity_verified 且非待复核、无候选、无 Formula/MW 不一致时才自动套用；
// 否则必须用户从候选中显式选用，杜绝未经验证即写入表单。
const chemAutoVerified = computed(() => {
  const c = enrichChemical.value
  if (!c || !c.found) return false
  if (c.candidates && c.candidates.length) return false
  if (c.requires_review) return false
  if (c.formula_mismatch || c.mw_mismatch) return false
  return !!c.identity_verified
})
// CAS 冲突检测（P3-2）— 表单 / PubChem / jena 三源非空且去 dash 互不相同 → 警示
const casSources = computed(() => {
  const out = []
  if (form.cas) out.push({ src: 'Form', val: form.cas })
  if (enrichChemical.value?.cas_resolved) out.push({ src: 'PubChem', val: enrichChemical.value.cas_resolved })
  if (enrichJena.value?.cas_number) out.push({ src: 'jena', val: enrichJena.value.cas_number })
  return out
})
const casConflict = computed(() => {
  const sources = casSources.value
  if (sources.length < 2) return null
  const distinct = [...new Set(sources.map(s => s.val.replace(/-/g, '')))]
  return distinct.length > 1 ? sources : null
})
// BiozEvidenceSection ref（用于 expose 调用 markAdopted / setAdoptingAll）
// BiozEvidenceSection ref（用于 expose 调用 markAdopted / setAdoptingAll）
const wrapRef = ref(null)
// 切换产品/enrich 结果时重置 Adopt 状态
watch(enrichBioz, () => {
  adoptedRefs.value = new Set()
})
// Knowledge chain match computed (from literature data)
const enrichMatchedMethods = computed(() => enrichLiterature.value?.matched_methods || [])
const enrichMatchedApps = computed(() => enrichLiterature.value?.matched_apps || [])
const enrichUnmatchedKeywords = computed(() => [
  ...(enrichLiterature.value?.unmatched_method_keywords || []),
  ...(enrichLiterature.value?.unmatched_app_keywords || []),
])
const hasKnowledgeMatches = computed(() =>
  enrichMatchedMethods.value.length > 0 || enrichMatchedApps.value.length > 0 || enrichUnmatchedKeywords.value.length > 0
)

async function runPubchemEnrich() {
  const ids = {
    name: (form.name || '').trim(),
    cas: (form.cas || '').trim(),
    smiles: (form.smiles || '').trim(),
    inchi: (form.inchi || '').trim(),
    // 文档已提供的 Formula/MW，传给后端做交叉校验（修复 3）
    formula: (form.formula || '').trim(),
    molecular_weight: form.molecular_weight ?? null,
    productId: isEdit.value ? productId.value : null,
  }
  if (!ids.name && !ids.cas && !ids.smiles && !ids.inchi) return
  pubchemEnriching.value = true
  pubchemEnrichResult.value = null
  try {
    const resp = await enrichProduct(ids)
    pubchemEnrichResult.value = resp.data
    // 自动预填 Category（若表单尚未选择）：enrich 返回的 jena.normalized.category_l1
    if (!form.product_class_id && resp.data?.jena?.matched && resp.data?.jena?.normalized?.category_l1) {
      applyJenaCategoryL1(resp.data.jena.normalized.category_l1)
    }
  } catch (e) {
    pubchemEnrichResult.value = { error: e?.response?.data?.meta?.error?.message || 'Enrich failed' }
  } finally {
    pubchemEnriching.value = false
  }
}

// Link all methods under an Application (cascade from knowledge chain)
async function linkAppMethods(appData) {
  const aId = appData.id
  if (!aId) return
  try {
    const resp = await http.get(`/applications/${aId}/`)
    const methods = resp.data?.methods || []
    let added = 0
    for (const m of methods) {
      if (!methodIds.value.includes(m.id)) {
        methodIds.value.push(m.id)
        added++
      }
    }
    setFeedback('success', `Linked Application: ${appData.name} (+${added} methods)`)
  } catch {
    setFeedback('error', 'Failed to link application')
  }
}

// Apply jena 归一化规格（仅填空字段）
function applyJenaNormalized() {
  const jena = enrichJena.value
  if (!jena?.matched || !jena.normalized) return
  const n = jena.normalized
  // jena 是最终权威：匹配到则把其 CAS 回填（修复 CAS 字段为空）
  if (jena.cas_number && !form.cas) form.cas = jena.cas_number
  if (n.purity && !form.purity) form.purity = n.purity
  if (n.storage_condition && !form.storage) form.storage = normalizeStorage(n.storage_condition)
  if (n.shipping_condition && !form.shipping) form.shipping = normalizeShipping(n.shipping_condition)
  if (n.shelf_life && !form.shelf_life) form.shelf_life = n.shelf_life
  if (n.category_l1 && !form.product_class_id) applyJenaCategoryL1(n.category_l1)
  setFeedback('success', 'Jena specs filled into form')
}

// Map jena category_l1 slug → cascader L1 selection
function applyJenaCategoryL1(l1Slug) {
  const l1 = categoryCascaderOptions.value.find(o => o.slug === l1Slug)
  if (l1) {
    categoryCascaderValue.value = [l1.value]
    form.product_class_id = l1.value
  }
}

// 显式选用一个候选化合物（用户主动确认，允许套用未自动验证的结果）
function applyCandidate(c) {
  if (!c) return
  // 任务2(b)：分子式/MW 与文档(权威)不符 → 这是错误化合物，禁止套用其 SMILES/属性
  if (c.formula_mismatch || c.mw_mismatch || c.confidence === 'rejected') {
    setFeedback('warn', '⚠ 该候选分子式/分子量与文档不一致，疑似错误化合物，未套用。请人工核实或手动录入。')
    return
  }
  if (c.canonical_smiles && !form.smiles) form.smiles = c.canonical_smiles
  if (c.molecular_formula && !form.formula) form.formula = c.molecular_formula
  if (c.molecular_weight) form.molecular_weight = Number(c.molecular_weight) || null
  if (c.cas && !form.cas) form.cas = c.cas
  if (c.inchi && !form.inchi) form.inchi = c.inchi
  setFeedback('success', 'Candidate applied — please verify before saving')
}

function applyPubchemProperties() {
  if (!chemAutoVerified.value) {
    setFeedback('warn', '化学属性未经验证，请先从候选中选择正确化合物')
    return
  }
  const data = pubchemEnrichResult.value
  const chem = data?.chemical || data
  if (!chem || !chem.properties) return
  const p = chem.properties
  if (p.canonical_smiles && !form.smiles) form.smiles = p.canonical_smiles
  if (p.inchi && !form.inchi) form.inchi = p.inchi
  if (p.molecular_formula && !form.formula) form.formula = p.molecular_formula
  if (p.molecular_weight) form.molecular_weight = Number(p.molecular_weight) || null
  // jena 是最终权威：匹配到则优先用其 CAS，否则用 PubChem 解析的 CAS
  const jena = enrichJena.value
  const casToUse = (jena?.matched && jena.cas_number) ? jena.cas_number : (chem.cas_resolved || '')
  if (casToUse && !form.cas) form.cas = casToUse
  pubchemEnrichResult.value = { ...data, applied: true }
  setFeedback('success', 'Chemical properties applied to form')
}

// #170B: 保存前若化学身份已 verified 而表单 cas/smiles 仍空，自动套用（verified=后端已校验，安全），
// 避免研究员点 Save Draft 后化学属性「凭空消失」造成不完整。unverified/候选分支不自动套用（须人工选候选）。
function applyVerifiedChemicalToForm() {
  if (!chemAutoVerified.value) return
  const data = pubchemEnrichResult.value
  const chem = data?.chemical || data
  if (!chem?.properties) return
  const p = chem.properties
  if (p.canonical_smiles && !form.smiles) form.smiles = p.canonical_smiles
  if (p.inchi && !form.inchi) form.inchi = p.inchi
  if (p.molecular_formula && !form.formula) form.formula = p.molecular_formula
  if (p.molecular_weight) form.molecular_weight = Number(p.molecular_weight) || null
  // jena 是最终权威：匹配到则优先用其 CAS，否则用 PubChem 解析的 CAS
  const jena = enrichJena.value
  const casToUse = (jena?.matched && jena.cas_number) ? jena.cas_number : (chem.cas_resolved || '')
  if (casToUse && !form.cas) form.cas = casToUse
}

// Lipinski badge class helper
function lipinskiClass(val) {
  if (val === true) return 'lipinski-ok'
  if (val === false) return 'lipinski-ng'
  return 'lipinski-unknown'
}

// #172: 抽出 Knowledge Chain 关联逻辑（methods / apps 级联 / protocols），
// 供 Apply All 与 Save Draft 自动套用共用（与 Apply All 行为一致）。
async function applyEnrichKnowledgeLinks() {
  const data = pubchemEnrichResult.value
  if (!data || data.error) return { methodCount: 0, protoCount: 0 }
  let methodCount = 0
  let protoCount = 0

  // 2. Knowledge chain — matched methods
  const matchedMethods = enrichMatchedMethods.value
  for (const mm of matchedMethods) {
    for (const m of mm.matches) {
      if (!methodIds.value.includes(m.id)) {
        methodIds.value.push(m.id)
        methodCount++
      }
    }
  }

  // 3. Knowledge chain — matched apps (cascade to their methods)
  const matchedApps = enrichMatchedApps.value
  for (const ma of matchedApps) {
    for (const a of ma.matches) {
      const appMethods = knowledgeList.value.methods.filter(m => m.application_id === a.id)
      for (const m of appMethods) {
        if (!methodIds.value.includes(m.id)) {
          methodIds.value.push(m.id)
          methodCount++
        }
      }
    }
  }

  // 4. Protocols — 数字 DB id 直接链；BioProCorpus 字符串 id 先导入知识库再链
  const protos = enrichProtocols.value || []
  for (const p of protos) {
    if (Number.isInteger(p.id)) {
      if (!protocolIds.value.includes(p.id)) { protocolIds.value.push(p.id); protoCount++ }
      continue
    }
    try {
      const r = await importProtocol({
        method_name: p.method_hint || p.title || '',
        protocol_title: p.title || '',
        protocol_url: p.url || '',
        objective: p.abstract || '',
        reagents: p.reagents || '',
        equipment: p.equipment || '',
        materials: p.materials || '',
        steps: p.steps || [],
        product_id: isEdit.value ? productId.value : null,
      })
      if (r.success && r.data?.protocol_id && !protocolIds.value.includes(r.data.protocol_id)) {
        protocolIds.value.push(r.data.protocol_id)
        if (r.data.method_id && !methodIds.value.includes(r.data.method_id)) methodIds.value.push(r.data.method_id)
        protoCount++
      }
    } catch { /* 单个协议导入失败不影响其余 */ }
  }

  return { methodCount, protoCount }
}

// Apply All: chemical properties + knowledge links + protocols + jena
async function applyAllEnrichResults() {
  const data = pubchemEnrichResult.value
  if (!data) return
  const chem = data?.chemical || data

  // 1. Chemical properties — 仅当后端已验证才自动套用；否则跳过并提示人工确认
  if (chem?.properties && chemAutoVerified.value) {
    const p = chem.properties
    if (p.canonical_smiles && !form.smiles) form.smiles = p.canonical_smiles
    if (p.inchi && !form.inchi) form.inchi = p.inchi
    if (p.molecular_formula && !form.formula) form.formula = p.molecular_formula
    if (p.molecular_weight) form.molecular_weight = Number(p.molecular_weight) || null
    if (chem.cas_resolved && !form.cas) form.cas = chem.cas_resolved
  } else if (chem?.found && !chemAutoVerified.value) {
    setFeedback('warn', '化学属性未经验证，未自动套用 — 请从候选中选择或手动填写')
  }

  // 2-4. Knowledge chain（methods / apps / protocols）— 共用抽取函数
  const { methodCount, protoCount } = await applyEnrichKnowledgeLinks()

  // 5. Jena 归一化规格（仅填空字段，不覆盖已填）
  let jenaCount = 0
  const jena = enrichJena.value
  if (jena?.matched && jena.normalized) {
    const n = jena.normalized
    if (n.purity && !form.purity) { form.purity = n.purity; jenaCount++ }
    if (n.storage_condition && !form.storage) { form.storage = normalizeStorage(n.storage_condition); jenaCount++ }
    if (n.shipping_condition && !form.shipping) { form.shipping = normalizeShipping(n.shipping_condition); jenaCount++ }
    if (n.shelf_life && !form.shelf_life) { form.shelf_life = n.shelf_life; jenaCount++ }
    if (n.category_l1 && !form.product_class_id) { applyJenaCategoryL1(n.category_l1); jenaCount++ }
  }

  pubchemEnrichResult.value = { ...data, applied: true }
  const parts = []
  if (chem?.found) parts.push('properties')
  if (methodCount) parts.push(`${methodCount} methods`)
  if (protoCount) parts.push(`${protoCount} protocols`)
  if (jenaCount) parts.push(`${jenaCount} jena specs`)
  setFeedback('success', `Applied: ${parts.join(', ')}`)
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

// ── Bioz Adopt ──────────────────────────────────────
// 适配后端 API 的字段命名：前端 camelCase → 后端 snake_case
function _toSnakeRef(r) {
  return {
    article_title: r.article_title || r.title || '',
    authors: r.authors || '',
    journal: r.journal || '',
    pub_date: r.pub_date || r.date || '',
    doi: r.doi || '',
    pmid: r.pmid || '',
    pmcid: r.pmcid || '',
    impact_factor: r.impact_factor || null,
    techniques: r.techniques || '',
    long: r.long || r.techniques || '',
    medium: r.medium || '',
    short: r.short || '',
    catalog_group: r.catalog_group || '',
    catalog_number: r.catalog_number || '',
  }
}

async function handleAdoptBiozRef({ ref, index }) {
  if (!isEdit.value) return
  wrapRef.value?.setAdoptingAll?.(true)
  try {
    const resp = await adoptBiozRefs(productId.value, [_toSnakeRef(ref)])
    const d = resp.data
    if (d?.adopted >= 1) {
      wrapRef.value?.markAdopted?.([index])
      setFeedback('success', 'Reference stored')
    } else {
      setFeedback('success', `Skipped / already exists (skipped=${d?.skipped || 0})`)
      wrapRef.value?.markAdopted?.([index])
    }
  } catch (e) {
    setFeedback('error', `Store failed: ${e?.response?.data?.meta?.error?.message || e.message}`)
  } finally {
    wrapRef.value?.setAdoptingAll?.(false)
  }
}

async function handleAdoptAllBioz({ refs }) {
  if (!isEdit.value || !refs?.length) return
  wrapRef.value?.setAdoptingAll?.(true)
  try {
    const resp = await adoptBiozRefs(productId.value, refs.map(_toSnakeRef))
    const d = resp.data
    if (d) {
      // 全部标记为已落库（前 5 条都是可见卡片，全部标记）
      const allIndices = refs.map((_, i) => i)
      wrapRef.value?.markAdopted?.(allIndices)
      setFeedback('success', `Adopt complete: ${d.adopted} created / ${d.skipped} existing`)
    }
  } catch (e) {
    setFeedback('error', `Batch store failed: ${e?.response?.data?.meta?.error?.message || e.message}`)
  } finally {
    wrapRef.value?.setAdoptingAll?.(false)
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
      // 回填 cascader 选中路径（从 product_class_id 反查 options 树）
      if (d.product_class_id) {
        // options 可能尚未加载，延迟到 loadCategoryOptions 后处理
        pendingProductClassId.value = d.product_class_id
      }
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
    if (productId.value) loadCompliance()
  } catch (e) {
    loadError.value = 'Failed to load product'
  } finally {
    loading.value = false
  }
}

// ── 合规文档（COA / SDS）────────────────────────────
// 仅 is_staff 工作台页可见（本页已要求 is_staff）；匿名不可见（按钮本就在工作台）。
const sdsList = ref([])
const skuCompliance = ref([]) // [{ sku:{id,sku_code}, batches:[{ batch, coa }] }]
const complianceLoading = ref(false)
const qcEditingId = ref(null)
const qcForms = reactive({})
const newBatchForms = ref({}) // { [skuId]: { lot_number, produced_at, retest_at } }

// 无 CAS / SMILES / InChI → 禁用 SDS 生成（P1-4）
const sdsGenerateDisabled = computed(() => !form.cas && !form.smiles && !form.inchi)
// 当前已发布（is_current）的 SDS
const currentSds = computed(() => sdsList.value.find(s => s.is_current) || null)
// ③ 文档生命周期状态（None → Draft → Published），供状态步进器使用
const sdsState = computed(() => {
  if (!sdsList.value.length) return 'none'
  if (sdsList.value.some(s => s.is_current)) return 'published'
  return 'draft'
})
const coaState = computed(() => {
  const coas = skuCompliance.value.flatMap(sc => sc.batches.map(b => b.coa).filter(Boolean))
  if (!coas.length) return 'none'
  return coas.some(c => c.status === 'published') ? 'published' : 'draft'
})
function docStepClass(state, step) {
  const idx = { none: 0, draft: 1, published: 2 }[state] ?? 0
  if (idx > step) return 'step-done'
  if (idx === step) return 'step-current'
  return 'step-todo'
}

async function loadCompliance() {
  if (!isEdit.value) return
  complianceLoading.value = true
  try {
    const [sds, batches, coas] = await Promise.all([
      documentsApi.getSdsList(productId.value),
      documentsApi.getBatches({ product_id: productId.value }),
      documentsApi.getCoaList({ product_id: productId.value }),
    ])
    sdsList.value = Array.isArray(sds) ? sds : []
    const coaByBatch = {}
    ;(coas || []).forEach(c => { if (c.batch) coaByBatch[c.batch] = c })
    const bySku = {}
    skus.value.filter(s => s.id).forEach(s => {
      bySku[s.id] = { sku: { id: s.id, sku_code: s.sku_code }, batches: [] }
    })
    ;(batches || []).forEach(b => {
      const skuCode = b.sku_code || (skus.value.find(s => s.id === b.sku)?.sku_code) || `SKU #${b.sku}`
      if (!bySku[b.sku]) bySku[b.sku] = { sku: { id: b.sku, sku_code: skuCode }, batches: [] }
      bySku[b.sku].batches.push({ batch: b, coa: coaByBatch[b.id] || null })
    })
    skuCompliance.value = Object.values(bySku)
    // 为每个 SKU 初始化新建批次的表单
    const init = {}
    skuCompliance.value.forEach(sc => {
      init[sc.sku.id] = { lot_number: sc.sku.sku_code || '', produced_at: '', retest_at: '' }
    })
    newBatchForms.value = init
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'Compliance data failed to load')
  } finally {
    complianceLoading.value = false
  }
}

// 确保每个 SKU 在 newBatchForms 中都有对应的表单数据
watch(skuCompliance, (list) => {
  const init = { ...newBatchForms.value }
  let changed = false
    list.forEach(sc => {
      if (!init[sc.sku.id]) {
        init[sc.sku.id] = { lot_number: sc.sku.sku_code || '', produced_at: '', retest_at: '' }
        changed = true
      }
    })
  if (changed) newBatchForms.value = init
}, { deep: true })

// ── COA: 为无批次的 SKU 新建批次 → 生成 COA ──────────
const creatingBatch = ref(false)
async function createBatchAndCoa(skuId) {
  const form = newBatchForms.value[skuId]
  if (!form || !form.lot_number) {
    setFeedback('error', 'Enter a lot number')
    return
  }
  if (!form.produced_at) {
    setFeedback('error', 'Select a production date')
    return
  }
  creatingBatch.value = true
  try {
    await documentsApi.createCoa({
      sku_id: skuId,
      lot_number: form.lot_number,
      produced_at: form.produced_at,
      retest_at: form.retest_at || undefined,
    })
    // ④ 生成后明确引导：下一步是批准并公开
    setFeedback('success', 'Batch + COA draft created. Click “Approve & Publish COA” to make it public.')
    // 刷新合规数据
    await loadCompliance()
    // 清空当前表单
    if (newBatchForms.value[skuId]) {
      newBatchForms.value[skuId] = { lot_number: '', produced_at: '', retest_at: '' }
    }
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'Creation failed')
  } finally {
    creatingBatch.value = false
  }
}

// ── SDS actions ──
async function generateProductSds() {
  // ② 缺化学标识时不静默禁用，而是点击后给出明确引导（不引入新错误）
  if (sdsGenerateDisabled.value) {
    setFeedback('warn', 'SDS needs a chemical identifier (CAS, SMILES, or InChI). Add one in section 2 “Chemical Structure” first.')
    return
  }
  try {
    await documentsApi.generateSds(productId.value)
    // ④ 生成后明确引导：下一步是批准并公开
    setFeedback('success', 'SDS draft generated. Click “Approve & Publish SDS” to make it public.')
    await loadCompliance()
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'SDS generation failed')
  }
}
async function approveSdsRev(id) {
  try {
    await documentsApi.approveSds(id)
    setFeedback('success', 'SDS approved and published')
    await loadCompliance()
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'SDS approval failed')
  }
}
async function withdrawSdsRev(id) {
  try {
    await documentsApi.withdrawSds(id)
    setFeedback('success', 'SDS withdrawn')
    await loadCompliance()
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'SDS withdrawal failed')
  }
}
function previewSds(sds) { openPreview('sds', sds) }
function downloadSds(id) { window.open(documentsApi.downloadSdsUrl(id), '_blank') }

// ── COA actions ──
async function approveCoaRev(coa) {
  try {
    await documentsApi.approveCoa(coa.id)
    setFeedback('success', 'COA approved and published')
    await loadCompliance()
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'COA approval failed')
  }
}
async function withdrawCoaRev(coa) {
  try {
    await documentsApi.withdrawCoa(coa.id)
    setFeedback('success', 'COA withdrawn (back to draft)')
    await loadCompliance()
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'COA withdrawal failed')
  }
}
function previewCoa(coa) { openPreview('coa', coa) }
function downloadCoa(id) { window.open(documentsApi.downloadCoaUrl(id), '_blank') }

// ── COA 实测录入 ──
function openQcForm(coa) {
  qcEditingId.value = coa.id
  qcForms[coa.id] = {
    appearance_result: coa.appearance_result || '',
    purity_result: coa.purity_result || '',
    water_content_result: coa.water_content_result || '',
    melting_point: coa.melting_point || '',
    specific_rotation: coa.specific_rotation || '',
    residual_solvents: coa.residual_solvents || '',
    heavy_metals: coa.heavy_metals || '',
    nmr_result: coa.nmr_result || '',
    lcms_result: coa.lcms_result || '',
  }
}
function closeQcForm() { qcEditingId.value = null }
async function saveQc(coa) {
  const payload = qcForms[coa.id] || {}
  try {
    await documentsApi.updateCoaQc(coa.id, payload)
    setFeedback('success', 'COA measurements saved')
    qcEditingId.value = null
    await loadCompliance()
  } catch (e) {
    setFeedback('error', e.response?.data?.error || 'Measurement save failed')
  }
}

function confidenceLabel(v) {
  return { high: 'High', medium: 'Medium', low: 'Low', very_low: 'Very low' }[v] || v || '—'
}
function formatPictograms(p) {
  if (!p) return '—'
  try {
    const arr = typeof p === 'string' ? JSON.parse(p) : p
    return Array.isArray(arr) && arr.length ? arr.join(', ') : '—'
  } catch {
    return '—'
  }
}

// ── 字段归一化（enrich/Word 导入的原始值 → choices 枚举值）─────────
// 与后端 jena_index.normalize_storage / normalize_shipping 保持一致语义
function normalizeStorage(raw) {
  if (!raw) return ''
  const s = String(raw).toLowerCase().trim()
  if (!s) return ''
  // 已是合法 choices 值，原样返回
  if (storageOpts.includes(raw)) return raw
  if (s.includes('-80')) return '-80°C'
  if (s.includes('-20') && (s.includes('light') || s.includes('避光'))) return '-20°C, protect from light'
  if (s.includes('-20')) return '-20°C'
  if (s.includes('4') && (s.includes('light') || s.includes('避光'))) return '4°C, protect from light'
  if (s.includes('4')) return '4°C'
  if (s.includes('room') || s.includes('室温')) {
    if (s.includes('dry') || s.includes('干燥')) return 'Room temperature, dry'
    return 'Room temperature'
  }
  return ''  // 匹配不上置空（model 允许 blank）
}
function normalizeShipping(raw) {
  if (!raw) return ''
  const s = String(raw).toLowerCase().trim()
  if (!s) return ''
  if (shippingOpts.includes(raw)) return raw
  if (s.includes('dry ice') || s.includes('干冰')) return 'Dry Ice'
  if (s.includes('blue ice') || s.includes('蓝冰')) return 'Blue Ice'
  if (s.includes('cold pack') || s.includes('gel pack') || s.includes('冷')) return 'Cold Pack'
  if (s.includes('ambient') || s.includes('常温') || s.includes('room')) return 'Ambient'
  return ''
}
// 通用 choices 校验：非法值置空（purity/concentration/storage/shipping/lead_time/shelf_life）
function sanitizeChoiceFields(payload) {
  const checks = {
    purity: purityOpts,
    concentration: concentrationOpts,
    storage: storageOpts,
    shipping: shippingOpts,
    lead_time: leadTimeOpts,
  }
  for (const [field, opts] of Object.entries(checks)) {
    if (payload[field] && !opts.includes(payload[field])) payload[field] = ''
  }
  return payload
}
// slug 兜底：空时从 catalog_no 或 name 生成
function slugify(str) {
  return String(str || '')
    .toLowerCase().trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 200)
}
function ensureSlug(payload) {
  if (!payload.slug) {
    payload.slug = slugify(payload.catalog_no) || slugify(payload.name) || `product-${Date.now()}`
  }
  return payload
}

function formatSaveError(e) {
  // 兼容后端两种错误信封：
  // 1) 业务错误（EnvelopeMixin）：{success:false, data:null, meta:{error:{message}}}
  // 2) DRF 校验错误（默认异常处理器）：{detail:'...'} 或 {field:['msg',...]}
  const resp = e?.response
  if (!resp) return e?.message || 'Unknown error'
  const status = resp.status
  const bd = resp.data || {}
  const envMsg = bd?.meta?.error?.message
  if (envMsg) return `HTTP ${status} — ${envMsg}`
  if (bd?.detail) return `HTTP ${status} — ${bd.detail}`
  const fieldParts = Object.entries(bd)
    .filter(([k]) => k !== 'success' && k !== 'data' && k !== 'meta')
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : (typeof v === 'object' ? JSON.stringify(v) : v)}`)
  if (fieldParts.length) return `HTTP ${status} — ${fieldParts.join('; ')}`
  return `HTTP ${status} — ${e.message}`
}

async function saveDraft(isPublish = false) {
  // 告知模式（CLAUDE.md 规则5：研究员是最终权威，发布检查是告知不是硬阻断）：
  // 缺失必填字段仅标红提示，不阻止保存/发布。后端草稿允许不完整。
  // #170B: 保存前若已 verified 化学身份，先把化学属性套入表单（仅填空字段，不覆盖人工录入）
  applyVerifiedChemicalToForm()
  // #172: 已有 enrich 结果则自动关联 Knowledge Links（与 Apply All 行为一致），
  // 使「AI AUTO MATCH → Save Draft」无需手动点 Apply All 也能自动关联方法/协议。
  if (pubchemEnrichResult.value && !pubchemEnrichResult.value.error) {
    await applyEnrichKnowledgeLinks()
  }
  const missing = collectMissing()
  missingFields.value = missing.map(m => m.key)
  if (missing.length) {
    setFeedback('warn', `${missing.length} required fields unfilled (marked red); save/publish kept available`)
  }
  saving.value = true
  // 派生 sku_code：Word 导入/AI 不生成，按 catalog_no + 序号兜底
  const catNo = (form.catalog_no || 'SKU').trim()
  const skusPayload = skus.value.map(({ _key, pack_unit, conc_unit, ...s }, i) => ({
    ...s,
    sku_code: s.sku_code || `${catNo}-${i + 1}`,
    pack_size: joinValueUnit(s.pack_size, pack_unit),
    concentration: joinValueUnit(s.concentration, conc_unit),
  }))
  const payload = {
    ...form,
    skus: skusPayload,
    method_ids: methodIds.value,
    protocol_ids: protocolIds.value,
  }
  ensureSlug(payload)
  sanitizeChoiceFields(payload)
  try {
    if (isEdit.value) {
      const resp = await http.put(`/products/${productId.value}/`, payload)
      // 回填后端派生字段：publish 时 _auto_seo_on_publish 生成的 SEO、兜底的 slug
      const d = resp?.data
      if (d) {
        if (d.seo_title) form.seo_title = d.seo_title
        if (d.seo_description) form.seo_description = d.seo_description
        if (d.slug) form.slug = d.slug
      }
      // ⑤ 编辑态保存后重新同步 SKU / 合规数据：新加的 SKU 立即可生成 COA，
      // 避免操作员加了 SKU 却看不到生成入口（与新建分支一致，不丢已保存数据）。
      await loadProduct()
      setFeedback('success', isPublish ? 'Product published' : 'Draft saved')
    } else {
      const resp = await http.post('/products/', payload)
      // 新建保存后同样回填后端派生字段（POST 路径也会触发 _auto_seo_on_publish）
      const d = resp?.data
      // #170A: 健壮提取 newId（兼容 envelope.data.id / 直接 id / pk）
      const newId = d?.id || resp?.id || d?.pk || (resp?.data && resp.data.id)
      if (d) {
        if (d.seo_title) form.seo_title = d.seo_title
        if (d.seo_description) form.seo_description = d.seo_description
        if (d.slug) form.slug = d.slug
      }
      if (newId) {
        await router.replace(`/workspace/products/${newId}/edit`)
        await nextTick()        // 确保 route.params.id 已刷新为 newId，再重载产品
        await loadProduct()     // 从服务端重新同步带 id 的 SKU 并触发 loadCompliance（修复新建后 Batch COA 为空 #3）
        // ⑥ 首次保存后不跳离（router.replace 保持本页）+ 解锁提示
        setFeedback('success', isPublish ? 'Product created and published' : 'Product saved. You can now generate SDS, COA, and SEO in section 9.')
      }
    }
  } catch (e) {
    // #170A: 显式抛出后端真实错误（唯一约束/字段校验等），不再吞掉原因
    setFeedback('error', 'Save failed: ' + formatSaveError(e))
  } finally {
    saving.value = false
  }
}

async function publish() {
  showPublishDialog.value = false
  form.status = 'active'
  await saveDraft(true)
}

function handlePublish() {
  showPublishDialog.value = true
}

onMounted(() => {
  loadProduct()
  if (!isEdit.value) loadCategoryOptions()
})

// 用户补填字段后，实时清除该字段的"必填未填"标红——避免填好后红框和提示还挂着。
// 放在 form/skus 定义之后，watch 回调里通过闭包引用它们。
watch(
  () => [form.name, form.catalog_no, form.product_class_id, skus.value.some(s => s.is_default)],
  () => {
    if (!missingFields.value.length) return
    missingFields.value = missingFields.value.filter(key => {
      if (key === 'default_sku') return !skus.value.some(s => s.is_default)
      return !form[key]
    })
  }
)
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

    <!-- ③ 生命周期状态步进器：厘清「产品发布」与「文档发布」两个概念 -->
    <div class="lifecycle-stepper" v-if="isEdit">
      <div class="stepper-track">
        <span class="stepper-label">Product</span>
        <span class="step" :class="form.status === 'active' ? 'step-done' : 'step-current'">Draft</span>
        <span class="step-arrow">→</span>
        <span class="step" :class="form.status === 'active' ? 'step-done' : 'step-todo'">Published</span>
      </div>
      <div class="stepper-track">
        <span class="stepper-label">SDS</span>
        <span v-for="(label, i) in ['None','Draft','Published']" :key="label" class="step" :class="docStepClass(sdsState, i)">{{ label }}</span>
      </div>
      <div class="stepper-track">
        <span class="stepper-label">COA</span>
        <span v-for="(label, i) in ['None','Draft','Published']" :key="label" class="step" :class="docStepClass(coaState, i)">{{ label }}</span>
      </div>
    </div>
    <p v-if="isEdit" class="form-hint stepper-hint">“Publish” makes the product visible to the public. “Approve &amp; Publish SDS / COA” makes the compliance document public.</p>

    <!-- Feedback toast -->
    <div v-if="saveFeedback.message" class="toast" :class="'toast-' + saveFeedback.type">
      {{ saveFeedback.message }}
    </div>

    <!-- ④ 页面身份行：保存后显示 catalog_no · status，不依赖路由 meta 时机 -->
    <div v-if="isEdit || form.name || form.catalog_no" class="page-identity">
      <strong>{{ isEdit ? 'Editing ' + (form.catalog_no || form.name || '…') : 'New Product' }}</strong>
      <span class="page-identity-status" :class="'status-' + (form.status || 'draft')">{{ form.status || 'draft' }}</span>
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

    <!-- AI AUTO MATCH Panel -->
    <section v-if="form.name || form.cas || form.smiles || form.inchi" class="form-section pubchem-enrich-section">
      <h3>🤖 AI AUTO MATCH</h3>
      <!-- ① 未验证警告横条：化学属性不会自动写入，提示核对后 Apply All 或手填 -->
      <div v-if="enrichChemical?.found && !chemAutoVerified && !enrichChemical.candidates?.length" class="ai-warn-banner">
        ⚠ 化学身份未验证，化学属性不会自动写入表单。请核对 CAS / 分子式无误后点 “Apply All”，或手动填写下方字段。
      </div>
      <div class="word-import-row">
        <button type="button" class="file-upload-btn" @click="runPubchemEnrich" :disabled="pubchemEnriching || (!form.name && !form.cas && !form.smiles && !form.inchi)">
          {{ pubchemEnriching ? 'Searching & matching…' : `AI AUTO MATCH "${form.name || form.cas || form.smiles || form.inchi}"` }}
        </button>
        <!-- ② Apply All 移到顶部，删除底部重复块 -->
        <button
          v-if="enrichChemical?.found && !pubchemEnrichResult?.applied && !enrichChemical.candidates?.length"
          type="button"
          class="btn btn-primary btn-sm"
          style="margin-left:8px"
          @click="applyAllEnrichResults"
        >Apply All to Form</button>
        <span v-if="pubchemEnriching" class="ai-loading-spinner" aria-label="loading">
          <span class="spinner-ring"></span>
        </span>
        <span v-if="pubchemEnrichResult && enrichChemical?.found && !pubchemEnrichResult.applied && !enrichChemical.candidates?.length" class="word-status word-ok">
          ✓ Found: {{ enrichChemical.source === 'chembl' ? 'ChEMBL' : 'PubChem' }} CID {{ enrichChemical.cid }} <template v-if="enrichChemical.fallback_used">(via fragment search)</template>
        </span>
        <span v-if="enrichChemical?.confidence" class="word-status" :class="enrichChemical.identity_verified ? 'word-ok' : 'word-warn'">
          {{ enrichChemical.identity_verified ? '✓ 身份已验证' : '⚠ 未验证' }} ({{ enrichChemical.confidence }})
        </span>
        <span v-if="enrichChemical?.doc_value_mismatch" class="word-status word-warn">
          ⚠ 文档 Formula/MW 与库值不一致，请核对文档是否有误
        </span>
        <span v-else-if="pubchemEnrichResult && enrichChemical?.candidates?.length && !pubchemEnrichResult.applied" class="word-status word-warn">
          ⚠ Multiple candidates ({{ enrichChemical.candidates.length }}) — select correct one
        </span>
        <span v-else-if="pubchemEnrichResult && pubchemEnrichResult.applied" class="word-status word-ok">
          ✓ All results applied to form
        </span>
        <span v-else-if="pubchemEnrichResult && pubchemEnrichResult.error" class="word-status word-err">
          {{ pubchemEnrichResult.error }}
        </span>
        <span v-else-if="pubchemEnrichResult && !enrichChemical?.found && !pubchemEnrichResult.error" class="word-status word-warn">
          ✗ Not found in PubChem or ChEMBL
        </span>
      </div>
      <!-- Preview -->
      <!-- Enrich format: { chemical: {...}, literature: {...}, protocols: [...] } -->
      <div v-if="enrichChemical && enrichChemical.found && !pubchemEnrichResult.applied && !enrichChemical.candidates?.length" class="pubchem-preview">
        <!-- Fallback warning (Bug 1 fix) -->
        <div v-if="enrichChemical.fallback_used" class="fallback-warning">
          ⚠️ Matched via partial name search — please verify this is the correct compound.
        </div>
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
          <tr v-if="enrichChemical.properties?.canonical_smiles"><td>SMILES:</td><td class="prop-highlight mono-wrap">{{ enrichChemical.properties.canonical_smiles }}</td></tr>
          <tr v-if="enrichChemical.properties?.molecular_formula"><td>Formula:</td><td class="prop-highlight">{{ enrichChemical.properties.molecular_formula }}</td></tr>
          <tr v-if="enrichChemical.properties?.molecular_weight"><td>MW:</td><td class="prop-highlight">{{ enrichChemical.properties.molecular_weight }} Da</td></tr>
          <tr v-if="enrichChemical.properties?.inchi"><td>InChI:</td><td class="mono-wrap">{{ enrichChemical.properties.inchi }}</td></tr>
          <tr v-if="enrichChemical.properties?.inchikey"><td>InChIKey:</td><td class="mono-wrap">{{ enrichChemical.properties.inchikey }}</td></tr>
          <tr v-if="enrichChemical.properties?.iupac_name"><td>IUPAC:</td><td>{{ enrichChemical.properties.iupac_name }}</td></tr>
          <tr v-if="enrichChemical.properties?.xlogp != null"><td>LogP:</td><td>{{ enrichChemical.properties.xlogp }}</td></tr>
          <tr v-if="enrichChemical.properties?.tpsa != null"><td>TPSA:</td><td>{{ enrichChemical.properties.tpsa }} Å²</td></tr>
          <tr v-if="enrichChemical.properties?.exact_mass != null"><td>Exact Mass:</td><td>{{ enrichChemical.properties.exact_mass }}</td></tr>
          <tr v-if="enrichChemical.properties?.h_bond_donor_count != null"><td>HBD:</td><td>{{ enrichChemical.properties.h_bond_donor_count }}</td></tr>
          <tr v-if="enrichChemical.properties?.h_bond_acceptor_count != null"><td>HBA:</td><td>{{ enrichChemical.properties.h_bond_acceptor_count }}</td></tr>
          <tr v-if="enrichChemical.properties?.rotatable_bond_count != null"><td>RotB:</td><td>{{ enrichChemical.properties.rotatable_bond_count }}</td></tr>
        </table>
        <!-- CAS 冲突警示条（P3-2）— 表单/PubChem/jena 三源不一致 -->
        <div v-if="casConflict" class="cas-conflict">
          <div class="cas-conflict-title">⚠ CAS sources inconsistent, please verify</div>
          <div class="cas-conflict-body">
            <span v-for="s in casConflict" :key="s.src" class="cas-conflict-src">
              {{ s.src }}: <strong>{{ s.val }}</strong>
            </span>
          </div>
        </div>
      </div>
      <!-- ⑥ 高级匹配区默认折叠，核心化学预览表常显 -->
      <details class="ai-advanced">
        <summary>高级匹配详情（Lipinski / Jena / 文献 / 协议）</summary>
      <!-- Lipinski rules (from Validate integration) -->
      <div v-if="enrichChemical?.lipinski && !pubchemEnrichResult.applied" class="pubchem-preview" style="margin-top: 8px">
        <h4 style="margin:0 0 6px 0;font-size:13px">💊 Lipinski Rule of Five</h4>
        <p class="lipinski-help">Rule of Five predicts oral-drug-likeness of small molecules (MW≤500, LogP≤5, HBD≤5, HBA≤10, RotB≤10). Bioreagents/oligonucleotides (e.g. Jena SC8001) typically fail — this is expected.</p>
        <span :class="enrichChemical.lipinski.passed ? 'lipinski-pass' : 'lipinski-fail'" style="font-size:12px;font-weight:600">
          {{ enrichChemical.lipinski.passed ? '✓ PASS' : '✗ FAIL' }}
        </span>
        <div v-if="enrichChemical.lipinski.violations?.length" style="font-size:11px;color:var(--color-danger);margin-top:4px">
          {{ enrichChemical.lipinski.violations.join('; ') }}
        </div>
        <div class="lipinski-grid">
          <span :class="lipinskiClass(enrichChemical.lipinski.details?.mw_ok)">MW ≤ 500</span>
          <span :class="lipinskiClass(enrichChemical.lipinski.details?.logp_ok)">LogP ≤ 5</span>
          <span :class="lipinskiClass(enrichChemical.lipinski.details?.hbd_ok)">HBD ≤ 5</span>
          <span :class="lipinskiClass(enrichChemical.lipinski.details?.hba_ok)">HBA ≤ 10</span>
          <span :class="lipinskiClass(enrichChemical.lipinski.details?.rot_ok)">RotB ≤ 10</span>
        </div>
      </div>

      <!-- Jena 规格匹配 -->
      <!-- 跨字段一致性校验（原 AI Tools Validate 已合并进 AUTO MATCH） -->
      <div v-if="enrichChemical?.mismatches?.length && !pubchemEnrichResult.applied" class="pubchem-preview" style="margin-top:8px">
        <h4 style="margin:0 0 6px 0;font-size:13px">⚠ Cross-field Mismatches ({{ enrichChemical.mismatches.length }})</h4>
        <div v-for="(m, i) in enrichChemical.mismatches" :key="i" class="ai-mismatch-item">
          <strong v-if="m.field">{{ m.field }}</strong>
          <span v-if="m.expected !== undefined"> expected: <code>{{ m.expected }}</code></span>
          <span v-if="m.actual !== undefined"> actual: <code>{{ m.actual }}</code></span>
          <span v-if="m.message"> — {{ m.message }}</span>
        </div>
      </div>
      <!-- 相似化合物（原 AI Tools Validate 已合并进 AUTO MATCH） -->
      <div v-if="enrichChemical?.similar_compounds?.length && !pubchemEnrichResult.applied" class="pubchem-preview" style="margin-top:8px">
        <h4 style="margin:0 0 6px 0;font-size:13px">🔗 Similar Compounds ({{ enrichChemical.similar_compounds.length }})</h4>
        <div v-for="(s, i) in enrichChemical.similar_compounds" :key="i" class="ai-rec-item">
          <div class="ai-rec-title">{{ s.name || ('CID ' + s.cid) || 'Untitled' }}</div>
          <div class="ai-rec-meta" v-if="s.cid">CID: {{ s.cid }}</div>
        </div>
      </div>
      <JenaMatchSection
        v-if="pubchemEnrichResult && !pubchemEnrichResult.applied"
        :jena="enrichJena"
        style="margin-top: 8px"
        @apply="applyJenaNormalized"
      />
      <!-- Bioz 文献证据（依赖 jena 命中） -->
      <BiozEvidenceSection
        v-if="pubchemEnrichResult && !pubchemEnrichResult.applied"
        ref="wrapRef"
        :bioz="enrichBioz"
        :can-adopt="isEdit"
        style="margin-top: 8px"
        @adopt="handleAdoptBiozRef"
        @adopt-all="handleAdoptAllBioz"
      />


      <!-- Knowledge chain matches from literature -->
      <div v-if="hasKnowledgeMatches && !pubchemEnrichResult.applied" class="pubchem-preview" style="margin-top: 8px">
        <h4 style="margin:0 0 8px 0;font-size:13px">🧬 Knowledge Chain Matches</h4>
        <!-- Matched Methods -->
        <div v-if="enrichMatchedMethods.length > 0" class="knowledge-match-group">
          <div class="km-section-title">🔬 Methods ({{ enrichMatchedMethods.length }})</div>
          <div v-for="mm in enrichMatchedMethods" :key="mm.keyword" class="km-keyword-group">
            <span class="km-keyword">"{{ mm.keyword }}" →</span>
            <span v-for="m in mm.matches" :key="m.id" class="km-match-item">
              <a :href="`/methods/${m.id}`" target="_blank" class="km-link">{{ m.name }}</a>
              <button type="button" class="km-link-btn" @click="toggleMethodId(m.id)" :title="methodIds.includes(m.id) ? 'Unlink' : 'Link'">{{ methodIds.includes(m.id) ? '✕' : '✓' }}</button>
            </span>
          </div>
        </div>
        <!-- Matched Applications (cascade to Methods) -->
        <div v-if="enrichMatchedApps.length > 0" class="knowledge-match-group">
          <div class="km-section-title">🎯 Applications ({{ enrichMatchedApps.length }})</div>
          <div v-for="ma in enrichMatchedApps" :key="ma.keyword" class="km-keyword-group">
            <span class="km-keyword">"{{ ma.keyword }}" →</span>
            <span v-for="a in ma.matches" :key="a.id" class="km-match-item">
              <a :href="`/applications/${a.id}`" target="_blank" class="km-link">{{ a.name }}</a>
              <button type="button" class="km-link-btn" @click="linkAppMethods(a)" :title="'Link app & cascade methods'">🔗 Link</button>
            </span>
          </div>
        </div>
        <!-- Unmatched keywords -->
        <div v-if="enrichUnmatchedKeywords.length > 0" class="km-unmatched">
          <span class="km-section-title dim">💡 Unmatched keywords — may need new entities</span>
          <span v-for="kw in enrichUnmatchedKeywords" :key="kw" class="km-chip">{{ kw }}</span>
        </div>
      </div>
      <!-- Literature & Protocols from enrich -->
      <div v-if="enrichLiterature && enrichLiterature.references?.length > 0 && !pubchemEnrichResult.applied" class="pubchem-preview" style="margin-top: 8px">
        <h4 style="margin:0 0 4px 0;font-size:13px">📚 Literature ({{ enrichLiterature.references.length }} references)</h4>
        <div v-for="(ref, i) in enrichLiterature.references.slice(0, 3)" :key="i" style="font-size:11px;margin-bottom:4px;color:var(--color-text-secondary)">
          <a v-if="ref.ref_id" :href="`/references/${ref.ref_id}`" target="_blank" style="color:var(--color-info);text-decoration:none;font-weight:600">✓ #{{ ref.ref_id }}</a>
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
            <span v-if="protocolImported[i]" style="font-size:11px;color:var(--color-success);margin-left:8px">✓ Imported</span>
          </div>
        </div>
      </div>
      </details>
      <!-- Apply All button moved to top action row (see AI AUTO MATCH panel header) -->
      <!-- Ambiguous candidates (require explicit user choice — 修复 1/4) -->
      <div v-if="enrichChemical?.candidates?.length > 0 && !pubchemEnrichResult.applied" class="pubchem-preview">
        <p class="form-hint">⚠ 自动匹配未经验证（{{ enrichChemical.confidence }}）— 必须手动选择正确的化合物，请勿直接 Apply All。</p>
        <div v-for="c in enrichChemical.candidates" :key="c.cid" class="candidate-item">
          <div style="flex:1;min-width:0">
            <strong>{{ c.iupac_name || '—' }}</strong>
            <span>CID: {{ c.cid }}, MW: {{ c.molecular_weight }}</span>
            <span v-if="c.cas">, CAS: {{ c.cas }}</span>
            <span v-if="c.canonical_smiles" class="mono-wrap" style="display:block;font-size:10px;color:var(--color-text-secondary);word-break:break-all">{{ c.canonical_smiles }}</span>
            <span class="mono-wrap" style="display:block;font-size:10px;color:var(--color-text-secondary)">文档 Formula: {{ form.formula || '—' }} ｜ PubChem: {{ c.molecular_formula || '—' }}</span>
            <span v-if="c.formula_mismatch || c.mw_mismatch" class="field-error" style="display:block">⚠ 与文档 Formula/MW 不一致</span>
          </div>
          <button type="button" class="btn btn-sm btn-primary" style="font-size:11px;white-space:nowrap"
            :disabled="c.formula_mismatch || c.mw_mismatch || c.confidence === 'rejected'"
            :title="(c.formula_mismatch || c.mw_mismatch) ? '分子式/分子量与文档不符，疑似错误化合物，已禁用' : ''"
            @click="applyCandidate(c)">Use this</button>
        </div>
      </div>
      <!-- Not found guidance (Bug 2 fix: check enrichChemical instead of top-level) -->
      <div v-if="pubchemEnrichResult && !enrichChemical?.found && !pubchemEnrichResult.error && !pubchemEnriching" class="pubchem-notfound">
        <p class="form-hint">{{ pubchemEnrichResult.search_hint || 'Not found in PubChem. Try using a CAS number or entering SMILES/FW manually.' }}</p>
      </div>
      <p class="form-hint">One-click search across PubChem + ChEMBL + PubMed + BioProCorpus, with knowledge chain matching.</p>
    </section>

    <!-- AI Tools: Validate / Recommend Protocols / Recommend Literature (gap ④) -->

    <form @submit.prevent="saveDraft" class="edit-form">
      <!-- 1. Basic Info -->
      <section class="form-section">
        <h3>1. Basic Information</h3>
        <div class="field-grid">
          <label>Name *
            <AppInput v-model="form.name" placeholder="e.g. 2'-Amino-ATP" />
            <span v-if="isFieldMissing('name')" class="field-error">⚠ Required field unfilled</span>
          </label>
          <label>Catalog No *
            <AppInput v-model="form.catalog_no" placeholder="e.g. SC8043" />
            <span v-if="isFieldMissing('catalog_no')" class="field-error">⚠ Required field unfilled</span>
          </label>
          <label>CAS
            <AppInput v-model="form.cas" placeholder="e.g. 1927-31-7" />
            <span v-if="validateField('cas')" class="field-error">{{ validateField('cas') }}</span>
          </label>
          <label>Synonyms
            <AppInput v-model="form.synonyms" placeholder="comma separated" />
          </label>
          <label>Slug <AppInput v-model="form.slug" placeholder="auto-generated-if-empty" /></label>
          <label>Status
            <AppSelect v-model="form.status" :options="statusOptions" />
          </label>
        </div>
      </section>

      <!-- 2. Chemical Structure -->
      <section class="form-section">
        <h3>2. Chemical Structure</h3>
        <div class="chem-row">
          <div class="chem-inputs">
            <label>SMILES
              <AppInput v-model="form.smiles" type="textarea" rows="2" placeholder="e.g. C1=CC=C(C=C1)N" />
              <span v-if="isFieldMissing('smiles')" id="smiles-missing" class="field-error">⚠ Required field unfilled</span>
              <span v-if="validateField('smiles')" class="field-error">{{ validateField('smiles') }}</span>
            </label>
            <label>InChI <AppInput v-model="form.inchi" type="textarea" rows="2" placeholder="Standard InChI" /></label>
            <label>Formula
              <AppInput v-model="form.formula" placeholder="e.g. C10H17N6O13P3" />
              <span v-if="validateField('formula')" class="field-error">{{ validateField('formula') }}</span>
            </label>
            <label>Molecular Weight
              <AppInput v-model.number="form.molecular_weight" type="number" step="0.01" placeholder="e.g. 522.2" />
              <span v-if="validateField('molecular_weight')" class="field-error">{{ validateField('molecular_weight') }}</span>
            </label>
          </div>
          <div class="chem-preview">
            <StructureViewer :smiles="form.smiles" :pubchem-cid="pubchemEnrichResult?.found ? pubchemEnrichResult.cid : null" :structure-image="form.structure_image" />
          </div>
        </div>
      </section>

      <!-- 3. Scientific Parameters — real select dropdowns -->
      <section class="form-section">
        <h3>3. Scientific Parameters</h3>
        <div class="field-grid">
          <label>Purity
            <AppSelect v-model="form.purity" :options="purityOptions" />
            <AppInput v-if="form.purity === ''" v-model="form.purity" placeholder="Or enter custom" />
          </label>
          <label>Concentration
            <AppSelect v-model="form.concentration" :options="concentrationSelectOpts" />
          </label>
          <label>Storage
            <AppSelect v-model="form.storage" :options="storageOptions" />
          </label>
          <label>Shipping
            <AppSelect v-model="form.shipping" :options="shippingOptions" />
          </label>
          <label>Lead Time
            <AppSelect v-model="form.lead_time" :options="leadTimeOptions" />
          </label>
          <label>Shelf Life
            <AppSelect v-model="form.shelf_life" :options="shelfLifeOptions" />
          </label>
          <label class="full-width">Handling Notes <AppInput v-model="form.handling_notes" type="textarea" rows="2" /></label>
        </div>
      </section>

      <!-- 4. Category — cascader selector writing product_class_id -->
      <section class="form-section">
        <h3>4. Category</h3>
        <div class="field-grid">
          <label class="full-width">Category *
            <el-cascader
              v-model="categoryCascaderValue"
              :options="categoryCascaderOptions"
              :props="{ expandTrigger: 'hover', emitPath: true, checkStrictly: true }"
              placeholder="Select category"
              clearable
              style="width: 100%"
              :class="{ 'field-missing': isFieldMissing('product_class_id') }"
              :aria-invalid="isFieldMissing('product_class_id')"
              @change="onCategoryChange"
            />
            <span v-if="isFieldMissing('product_class_id')" class="field-error">⚠ 请选择 Category（需选到三级分类{{ categoryCascaderValue.length ? '，当前仅选到 L' + categoryCascaderValue.length : '' }}）</span>
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
          <AppSelect v-model="linkMethodSelect" :options="[{label:'— Link existing Method —',value:''},...knowledgeList.methods.filter(m => !methodIds.includes(m.id)).map(m => ({label:m.name,value:String(m.id)}))]" @change="addSelectedMethod" />
          <button type="button" class="btn btn-ghost btn-sm" @click="addSelectedMethod" :disabled="!linkMethodSelect">Link</button>

          <AppSelect v-model="linkProtocolSelect" :options="[{label:'— Link existing Protocol —',value:''},...knowledgeList.protocols.filter(p => !protocolIds.includes(p.id)).map(p => ({label:p.name,value:String(p.id)}))]" style="margin-left:16px" @change="addSelectedProtocol" />
          <button type="button" class="btn btn-ghost btn-sm" @click="addSelectedProtocol" :disabled="!linkProtocolSelect">Link</button>
        </div>

        <p class="form-hint" style="margin:2px 0 0">Select a knowledge entity above and it links to this product immediately; the “Link” button is an explicit alternative.</p>

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
          <AppInput v-model="form.overview" type="textarea" rows="8" maxlength="5000" placeholder="Describe the product, its applications, and key features…" />
        </label>
        <span class="char-count">{{ (form.overview || '').length }} / 5000</span>
      </section>

      <!-- 7. SKUs — pack unit + conc unit as dropdowns -->
      <section class="form-section">
        <h3>7. SKUs</h3>
        <table class="sku-table" v-if="skus.length">
          <thead>
            <tr><th>Code</th><th>Pack Size</th><th>Pack Unit</th><th>Concn</th><th>Conc Unit</th><th>Price</th><th>Curr</th><th>Default</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in skus" :key="s._key" :class="{ 'sku-duplicate': skuDuplicate.has(i) }">
              <td><AppInput v-model="s.sku_code" style="width:140px;margin-bottom:0" /></td>
              <td><AppInput v-model="s.pack_size" type="number" step="any" min="0" style="width:80px;margin-bottom:0" /></td>
              <td>
                <AppSelect v-model="s.pack_unit" :options="packUnitOptions" style="width:90px;margin-bottom:0" />
              </td>
              <td><AppInput v-model="s.concentration" style="width:80px;margin-bottom:0" /></td>
              <td>
                <AppSelect v-model="s.conc_unit" :options="concUnitOptions" style="width:90px;margin-bottom:0" />
              </td>
              <td><AppInput v-model="s.price" type="number" step="0.01" min="0" style="width:100px;margin-bottom:0" /></td>
              <td>
                <AppSelect v-model="s.currency" :options="currencyOptions" style="margin-bottom:0" />
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
        <p v-if="isFieldMissing('default_sku')" class="field-error">⚠ Add at least one SKU and tick Default</p>
        <p v-if="skuDuplicate.size" class="sku-warning">⚠ Duplicate pack size + concentration combination detected</p>
        <p class="form-hint">Each SKU represents a purchasable variant. Set one as Default.</p>
      </section>

      <!-- 8. SEO -->
      <section class="form-section">
        <h3>8. SEO</h3>
        <div class="field-grid">
          <label>SEO Title <AppInput v-model="form.seo_title" placeholder="Auto-generated if left empty" /></label>
          <label>SEO Description <AppInput v-model="form.seo_description" placeholder="Auto-generated if left empty" /></label>
        </div>
        <button type="button" class="btn btn-ghost btn-sm" style="margin-top:8px" @click="autoGenerateSeo" :disabled="seoGenerating || !isEdit">
          {{ !isEdit ? 'Save product first to enable SEO auto-gen' : (seoGenerating ? 'Generating...' : 'Auto-generate SEO') }}
        </button>
        <p class="form-hint">SEO 在发布时自动生成；也可点上方按钮立即生成。</p>
      </section>

      <!-- 9. Compliance — COA & SDS -->
      <section class="form-section">
        <h3>9. Compliance — COA &amp; SDS</h3>
        <!-- ① 未保存时常显占位横幅，给出原因而非隐藏整段 -->
        <div v-if="!isEdit" class="compliance-placeholder">
          💡 Save the product first to enable SDS / COA generation. After saving, return here to generate compliance documents.
        </div>
        <template v-else>
        <p class="form-hint">Generate / approve SDS and COA for this product. Anonymous visitors can view published documents on the product detail page.</p>

        <!-- SDS 卡 -->
        <div class="compliance-block">
          <div class="compliance-block-title">
            <span>SDS (Safety Data Sheet)</span>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="complianceLoading"
              :title="sdsGenerateDisabled ? 'SDS needs a chemical identifier (CAS / SMILES / InChI). Click to see what is missing.' : 'Generate SDS draft'"
              @click="generateProductSds"
            >Generate SDS</button>
            <!-- ② 缺标识时按钮不静默禁用，常显引导文案 -->
            <p v-if="sdsGenerateDisabled" class="form-hint sds-hint">⚠ Add a chemical identifier (CAS, SMILES, or InChI) in section 2 “Chemical Structure” before generating SDS.</p>
          </div>

          <LoadingSpinner v-if="complianceLoading" size="small" text="Loading…" />
          <div v-else-if="!sdsList.length" class="compliance-empty">No SDS versions yet.</div>
          <div v-else class="sds-rev-list">
            <div v-for="sds in sdsList" :key="sds.id" class="sds-rev-card">
              <div class="sds-rev-head">
                <span class="sds-rev-no">v{{ sds.revision_no }}</span>
                <span v-if="sds.is_current" class="tag tag-sds">Currently published</span>
                <span v-else class="tag tag-incomplete">Draft</span>
                <span class="sds-confidence" :title="sds.data_source_detail">
                  Confidence: {{ confidenceLabel(sds.data_confidence) }}
                </span>
              </div>
              <div class="sds-rev-meta">
                <span>Signal word: {{ sds.signal_word || '—' }}</span>
                <span>GHS: {{ formatPictograms(sds.pictograms) }}</span>
              </div>
              <div v-if="sds.data_source_detail" class="sds-source">{{ sds.data_source_detail }}</div>
              <div class="sds-rev-actions">
                <button v-if="!sds.is_current" type="button" class="btn btn-ghost btn-sm" @click="approveSdsRev(sds.id)">Approve &amp; Publish SDS</button>
                <button v-if="sds.is_current" type="button" class="btn btn-ghost btn-sm" @click="withdrawSdsRev(sds.id)">Withdraw</button>
                <button type="button" class="btn btn-ghost btn-sm" @click="previewSds(sds)">Preview</button>
                <button v-if="sds.pdf_path" type="button" class="btn btn-ghost btn-sm" @click="downloadSds(sds.id)">Download</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 每 SKU 的批次 + COA -->
        <div class="compliance-block" v-if="!complianceLoading">
          <div class="compliance-block-title"><span>Batch COA</span></div>
          <div v-if="!skuCompliance.length" class="compliance-empty">This product has no batches yet.</div>
          <div v-for="sc in skuCompliance" :key="sc.sku.id" class="sku-coa-group">
            <div class="sku-coa-title">SKU: {{ sc.sku.sku_code || ('#' + sc.sku.id) }}</div>
            <div v-for="item in sc.batches" :key="item.batch.id" class="coa-card">
              <div class="coa-card-head">
                <span>Batch {{ item.batch.lot_number }}</span>
                <span v-if="item.coa" class="tag" :class="item.coa.status === 'published' ? 'tag-sds' : 'tag-incomplete'">
                  {{ item.coa.status === 'published' ? 'Published' : 'Draft' }}
                </span>
                <span v-else class="tag tag-incomplete">No COA</span>
              </div>

              <template v-if="item.coa">
                <div class="coa-card-meta">
                  <span>Doc: {{ item.coa.doc_id }}</span>
                  <span>Produced: {{ item.coa.produced_at }}</span>
                </div>

                <div v-if="qcEditingId === item.coa.id" class="qc-form">
                  <label>Appearance <AppInput v-model="qcForms[item.coa.id].appearance_result" style="margin-bottom:0" /></label>
                  <label>Purity <AppInput v-model="qcForms[item.coa.id].purity_result" style="margin-bottom:0" /></label>
                  <label>Water content <AppInput v-model="qcForms[item.coa.id].water_content_result" style="margin-bottom:0" /></label>
                  <label>Melting point <AppInput v-model="qcForms[item.coa.id].melting_point" style="margin-bottom:0" /></label>
                  <label>Specific rotation <AppInput v-model="qcForms[item.coa.id].specific_rotation" style="margin-bottom:0" /></label>
                  <label>Residual solvents <AppInput v-model="qcForms[item.coa.id].residual_solvents" style="margin-bottom:0" /></label>
                  <label>Heavy metals <AppInput v-model="qcForms[item.coa.id].heavy_metals" style="margin-bottom:0" /></label>
                  <label>NMR <AppInput v-model="qcForms[item.coa.id].nmr_result" style="margin-bottom:0" /></label>
                  <label>LC-MS <AppInput v-model="qcForms[item.coa.id].lcms_result" style="margin-bottom:0" /></label>
                  <div class="qc-form-actions">
                    <button type="button" class="btn btn-primary btn-sm" @click="saveQc(item.coa)">Save measurements</button>
                    <button type="button" class="btn btn-ghost btn-sm" @click="closeQcForm">Cancel</button>
                  </div>
                </div>

                <div class="coa-card-actions">
                  <button v-if="item.coa.status === 'draft'" type="button" class="btn btn-ghost btn-sm" @click="openQcForm(item.coa)">Enter measurements</button>
                  <button v-if="item.coa.status === 'draft'" type="button" class="btn btn-ghost btn-sm" @click="approveCoaRev(item.coa)">Approve &amp; Publish COA</button>
                  <button v-if="item.coa.status === 'published'" type="button" class="btn btn-ghost btn-sm" @click="withdrawCoaRev(item.coa)">Withdraw</button>
                  <button type="button" class="btn btn-ghost btn-sm" @click="previewCoa(item.coa)">Preview</button>
                  <button v-if="item.coa.pdf_path" type="button" class="btn btn-ghost btn-sm" @click="downloadCoa(item.coa.id)">Download</button>
                </div>
              </template>

              <template v-else>
                <div class="coa-card-actions">
                  <span class="coa-note">No COA yet — COA is generated together when you create the batch above.</span>
                </div>
              </template>
            </div>
          <!-- 无批次时显示新建入口 -->
          <div v-if="!sc.batches.length" class="batch-create-form">
            <label>Lot number
              <AppInput v-model="newBatchForms[sc.sku.id].lot_number" placeholder="默认带入 SKU code，可修改" style="margin-bottom:0" />
            </label>
            <label>Production date
              <input v-model="newBatchForms[sc.sku.id].produced_at" type="date" />
            </label>
            <label>Retest date
              <input v-model="newBatchForms[sc.sku.id].retest_at" type="date" />
            </label>
            <button type="button" class="btn btn-primary btn-sm" :disabled="creatingBatch" @click="createBatchAndCoa(sc.sku.id)">
              {{ creatingBatch ? 'Creating…' : 'Generate COA' }}
            </button>
            <span class="sku-code-hint">（已默认带入 SKU code，可修改）</span>
          </div>
        </div>
        </div>
        </template>
      </section>

      <!-- Actions -->
      <div class="form-actions">
        <button type="button" @click="saveDraft()" class="btn btn-outline btn-md" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Draft' }}
        </button>
        <button type="button" @click="handlePublish" class="btn btn-primary btn-md" :disabled="saving">
          Publish
        </button>
      </div>
    </form>

    <!-- (必填字段缺失不再弹独立弹窗：Save Draft 直接标红提示，Publish 走发布确认框，研究员拥有最终决定权) -->

    <!-- Publish confirm dialog -->
    <div v-if="showPublishDialog" ref="publishOverlay" class="dialog-overlay" v-bind="publishAttrs" @click.self="showPublishDialog = false">
      <div class="dialog">
        <h3 id="publish-title">Confirm Publish</h3>
        <div v-if="!isComplete" class="dialog-warn" role="alert" aria-live="assertive">
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
    <div v-if="showInlineEditor" ref="inlineOverlay" class="dialog-overlay" v-bind="inlineAttrs" @click.self="showInlineEditor = false">
      <div class="dialog">
        <h3 id="inline-title">New {{ {goal:'Research Goal',app:'Application',method:'Method',protocol:'Protocol'}[inlineEntityType] }}</h3>
        <label>Name <AppInput v-model="inlineForm.name" style="margin-bottom:0" /></label>
        <label v-if="inlineEntityType==='goal'||inlineEntityType==='app'">Summary <AppInput v-model="inlineForm.summary" type="textarea" rows="3" style="margin-bottom:0" /></label>
        <label v-if="inlineEntityType==='method'">Purpose <AppInput v-model="inlineForm.purpose" type="textarea" rows="3" style="margin-bottom:0" /></label>
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
.product-edit { max-width: var(--content-max-width, 1200px); margin: 0 auto; padding: 0 32px; }
.completeness-bar { padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; font-weight: 500; }
.completeness-ok { background: var(--color-success-bg); color: var(--color-primary-active); }
.completeness-warn { background: var(--color-warning-bg); color: var(--color-warning); }
.incomplete-banner { padding: 10px 16px; background: var(--color-info-bg); color: var(--color-emerald-800); border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
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
.field-error { font-size: 12px; color: var(--color-red-500); }
.custom-under { margin-top: 4px; }
.toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); max-width: calc(100vw - 32px); padding: 12px 20px; border-radius: 8px; font-size: 14px; font-weight: 500; z-index: 2000; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.toast-success { background: var(--color-success-light); color: var(--color-primary-active); }
.toast-error { background: var(--color-danger-light); color: var(--color-red-700); }
.toast-warn { background: var(--color-warning-light); color: var(--color-warning); }

/* Word Import */
.word-import-section { background: var(--color-bg); border-style: dashed; }
.word-import-row { display: flex; align-items: center; gap: 12px; }
.file-upload-btn { display: inline-block; padding: 8px 16px; border: 1.5px solid var(--color-primary); border-radius: 6px; color: var(--color-primary); font-size: 13px; font-weight: 500; cursor: pointer; background: white; }
.file-upload-btn:hover { background: var(--color-primary-light); }
.file-name { font-size: 13px; color: var(--color-text-secondary); }
.word-status { font-size: 13px; }
.word-ok { color: var(--color-success); font-weight: 500; }
.word-err { color: var(--color-danger); }
.word-warn { color: var(--color-warning); font-weight: 500; }

/* PubChem Enrich */
.pubchem-enrich-section { background: var(--color-bg); border-style: dashed; }
.pubchem-preview { background: var(--color-success-bg); border: 1px solid var(--color-success-light); border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 13px; }
.pubchem-preview table { width: 100%; border-collapse: collapse; }
.pubchem-preview td { padding: 4px 8px; border-bottom: 1px solid var(--color-success-light); font-size: 12px; }
.pubchem-preview td:first-child { color: var(--color-text-secondary); width: 120px; }
.prop-highlight { color: var(--color-success); font-weight: 600; font-family: var(--font-mono); }
.prop-missing { color: var(--color-text-secondary); font-style: italic; }
.mono-wrap { font-family: var(--font-mono); font-size: 11px; word-break: break-all; }
.candidate-item { padding: 6px 8px; margin: 4px 0; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; }
.candidate-item span { font-size: 11px; color: var(--color-text-secondary); margin-left: 8px; }
.source-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; display: inline-block; margin-bottom: 6px; }
.source-pubchem { background: var(--color-info-light); color: var(--color-blue-700); }
html.dark .source-pubchem { color: #fff; }
/* #172: 深色模式下 Toast / Completeness 条文字改浅色，避免深绿底+中绿字糊在一起 */
html.dark .toast-success, html.dark .completeness-ok { color: #D1FAE5; }
html.dark .toast-warn { color: #FDE68A; }
html.dark .toast-error { color: #FECACA; }
.source-chembl { background: var(--color-warning-light); color: var(--color-warning); }
.pubchem-notfound { background: var(--color-warning-bg); border: 1px solid var(--color-amber-200); border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
.pubchem-notfound .form-hint { margin-top: 0; color: var(--color-amber-800); }

/* Fallback warning */
.fallback-warning { background: var(--color-warning-bg); border: 1px solid var(--color-amber-400); border-radius: 6px; padding: 8px 12px; margin-bottom: 8px; font-size: 12px; color: var(--color-amber-800); }

/* CAS 冲突警示（P3-2） */
.cas-conflict { margin-top: 8px; background: var(--color-warning-light); border: 1px solid var(--color-amber-500); border-radius: 6px; padding: 6px 10px; }
.cas-conflict-title { font-size: 12px; font-weight: 600; color: var(--color-amber-800); margin-bottom: 3px; }
.cas-conflict-body { display: flex; flex-wrap: wrap; gap: 10px; }
.cas-conflict-src { font-size: 11px; color: var(--color-amber-800); }

/* Knowledge chain match styles */
.knowledge-match-group { margin-bottom: 8px; }
.km-section-title { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; }
.km-keyword-group { margin: 4px 0; padding-left: 8px; }
.km-keyword { font-size: 11px; color: var(--color-text-tertiary); font-style: italic; }
.km-match-item { display: inline-flex; align-items: center; gap: 4px; margin: 2px 6px 2px 0; }
.km-link { font-size: 12px; color: var(--color-info); text-decoration: none; }
.km-link:hover { text-decoration: underline; }
.km-link-btn { font-size: 11px; background: none; border: 1px solid var(--color-border); border-radius: 4px; padding: 1px 6px; cursor: pointer; color: var(--color-success); }
.km-link-btn:hover { background: var(--color-success-bg); }
.km-unmatched { margin-top: 6px; }
.km-unmatched .dim { font-size: 11px; color: var(--color-text-tertiary); }
.km-chip { display: inline-block; font-size: 11px; background: var(--color-warning-light); color: var(--color-amber-800); border: 1px solid var(--color-amber-200); border-radius: 12px; padding: 2px 10px; margin: 2px 4px; }

/* Lipinski rules */
.lipinski-pass { color: var(--color-success); }
.lipinski-fail { color: var(--color-danger); }
.lipinski-grid { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
.lipinski-help { font-size: 11px; line-height: 1.4; color: var(--color-text-tertiary); margin: 0 0 6px 0; }
.lipinski-ok { font-size: 11px; background: var(--color-success-light); color: var(--color-emerald-800); border: 1px solid var(--color-success-light); border-radius: 4px; padding: 2px 8px; }
.lipinski-ng { font-size: 11px; background: var(--color-danger-light); color: var(--color-red-700); border: 1px solid var(--color-danger-light); border-radius: 4px; padding: 2px 8px; }
.lipinski-unknown { font-size: 11px; background: var(--color-bg-alt); color: var(--color-text-tertiary); border: 1px solid var(--color-border-hover); border-radius: 4px; padding: 2px 8px; }



/* Protocol cards */
.protocol-card { border: 1px solid var(--color-border); border-radius: 6px; margin-bottom: 6px; overflow: hidden; }
.protocol-card-header { display: flex; gap: 8px; align-items: center; padding: 6px 10px; background: var(--color-bg); cursor: pointer; user-select: none; }
.protocol-card-header:hover { background: var(--color-bg-alt); }
.protocol-card-body { padding: 8px 10px; font-size: 11px; max-height: 400px; overflow-y: auto; }
.protocol-card-body pre { font-family: var(--font-mono); background: var(--color-bg); padding: 4px 8px; border-radius: 4px; }


/* SKU table */
.sku-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
.sku-table th, .sku-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--color-border); font-size: 13px; }
.sku-table th { color: var(--color-text-secondary); font-weight: 600; }
.sku-table input, .sku-table select { padding: 4px 6px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; background: var(--color-bg); color: var(--color-text); }
.sku-duplicate td { background: var(--color-warning-bg); }
.col-default { text-align: center; }
/* 将 SKU 三对字段视觉分组：Pack Size+Pack Unit / Concn+Conc Unit / Price+Curr
   每对首列前加分隔线 + 留白，使「一对」作为一个单元靠在一起（#7）。 */
.sku-table th:nth-child(2),
.sku-table td:nth-child(2),
.sku-table th:nth-child(4),
.sku-table td:nth-child(4),
.sku-table th:nth-child(6),
.sku-table td:nth-child(6) {
  border-left: 2px solid var(--color-border);
  padding-left: 14px;
}
.sku-warning { font-size: 12px; color: var(--color-warning); margin: 4px 0; }

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
.entity-select-row .app-select { flex: 1 1 240px; min-width: 240px; margin-bottom: 0; }
.entity-select-row .el-select { width: 100%; }
.entity-select-row select { flex: 1; min-width: 180px; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 13px; background: var(--color-bg); color: var(--color-text); }
.inline-buttons { display: flex; gap: 8px; margin-top: 8px; align-items: center; }
.inline-label { font-size: 13px; color: var(--color-text-secondary); }

.form-actions { display: flex; gap: 12px; justify-content: flex-end; padding: 16px 0; }

.ai-loading-spinner { display: inline-flex; align-items: center; margin-left: 10px; }
.spinner-ring { width: 18px; height: 18px; border: 2px solid var(--color-border); border-top-color: var(--color-primary, var(--color-info)); border-radius: 50%; display: inline-block; animation: ai-spin 0.7s linear infinite; }
@keyframes ai-spin { to { transform: rotate(360deg); } }
.loading, .error { text-align: center; padding: 40px; color: var(--color-text-secondary); }

/* AI Tools (gap ④) */
.ai-tools-section { background: var(--color-bg); border-style: dashed; }
.ai-tools-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ai-result-block { margin-top: 12px; border-top: 1px solid var(--color-border); padding-top: 8px; }
.ai-validate-summary { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.ai-badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 4px; background: var(--color-info-bg); color: #3730a3; }
.ai-badge-ok { background: var(--color-success-light); color: var(--color-primary-active); }
.ai-badge-ng { background: var(--color-danger-light); color: var(--color-red-700); }
.ai-badge-muted { background: var(--color-bg-alt); color: var(--color-text-tertiary); }
.ai-sub-block { margin: 6px 0; }
.ai-sub-title { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; }
.ai-mismatch-item { font-size: 12px; margin: 2px 0; color: var(--color-amber-800); }
.ai-mismatch-item code { font-family: var(--font-mono); background: var(--color-warning-light); padding: 0 4px; border-radius: 3px; }
.ai-hit-item { font-size: 12px; margin: 2px 0; color: var(--color-text-secondary); }
.ai-rec-item { border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; }
.ai-rec-title { font-size: 13px; font-weight: 600; color: var(--color-text); }
.ai-rec-meta { font-size: 11px; color: var(--color-text-secondary); margin: 2px 0; }
.ai-rec-reason { font-size: 11px; color: var(--color-text-secondary); }

/* Compliance — COA & SDS */
.compliance-block { margin-top: 16px; border: 1px solid var(--color-border); border-radius: 10px; padding: 14px 16px; background: var(--color-bg); }
.compliance-block-title { display: flex; align-items: center; justify-content: space-between; font-weight: 600; font-size: 14px; margin-bottom: 10px; }
.compliance-empty { font-size: 13px; color: var(--color-text-secondary); padding: 8px 0; }
.sds-rev-list { display: flex; flex-direction: column; gap: 10px; }
.sds-rev-card { border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 12px; background: var(--color-surface); }
.sds-rev-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sds-rev-no { font-weight: 700; color: var(--color-text); }
.sds-confidence { font-size: 11px; color: var(--color-text-secondary); margin-left: auto; }
.sds-rev-meta { display: flex; gap: 16px; font-size: 12px; color: var(--color-text-secondary); margin: 6px 0; }
.sds-source { font-size: 11px; color: var(--color-text-secondary); margin-bottom: 6px; }
.sds-rev-actions, .coa-card-actions, .qc-form-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.sku-coa-group { margin-top: 12px; border-top: 1px dashed var(--color-border); padding-top: 10px; }
.sku-coa-title { font-size: 13px; font-weight: 600; color: var(--color-text); margin-bottom: 8px; }
.coa-card { border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 12px; background: var(--color-surface); margin-bottom: 8px; }
.coa-card-head { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.coa-card-meta { display: flex; gap: 16px; font-size: 12px; color: var(--color-text-secondary); margin: 6px 0; }
.qc-form { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; }
.qc-form label { display: flex; flex-direction: column; font-size: 12px; color: var(--color-text-secondary); gap: 2px; }
.qc-form input { padding: 6px 8px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 13px; background: var(--color-bg); color: var(--color-text); }

/* 合规徽章（沿用 ProductsPage 体系） */
.tag-sds { background: #d1fae5; color: #065f46; }
.tag-coa { background: var(--color-info-bg); color: var(--color-info); }

/* 无批次 SKU 的新建入口 */
.batch-create-form { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 12px; border: 1px dashed var(--color-border); border-radius: 8px; margin-top: 8px; background: var(--color-surface); }
.batch-create-form label { font-size: 13px; display: flex; flex-direction: column; gap: 4px; color: var(--color-text-secondary); }
.batch-create-form input { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 13px; background: var(--color-bg); color: var(--color-text); min-width: 140px; }
.sku-code-hint { font-size: 12px; color: var(--color-text-secondary); font-weight: 500; }

/* ① Compliance 占位横幅 */
.compliance-placeholder { padding: 16px; border: 1px dashed var(--color-border); border-radius: 8px; background: var(--color-bg); font-size: 13px; color: var(--color-text-secondary); }

/* ② SDS 缺失标识引导 */
.sds-hint { margin-top: 6px; }

/* ⑤ 批次无 COA 注释 */
.coa-note { font-size: 12px; color: var(--color-text-secondary); }

/* ③ 生命周期状态步进器 */
.lifecycle-stepper { display: flex; gap: 20px; flex-wrap: wrap; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; background: var(--color-bg-alt); border: 1px solid var(--color-border); }
.stepper-track { display: flex; align-items: center; gap: 6px; }
.stepper-label { font-size: 12px; font-weight: 700; color: var(--color-text-secondary); margin-right: 4px; }
.step { font-size: 12px; padding: 3px 10px; border-radius: 12px; border: 1px solid var(--color-border); color: var(--color-text-tertiary); background: var(--color-surface); }
.step-done { background: var(--color-success-light); color: var(--color-primary-active); border-color: var(--color-success-light); }
.step-current { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.step-todo { opacity: 0.55; }
.step-arrow { color: var(--color-text-tertiary); }
.stepper-hint { margin-bottom: 16px; }

/* ④ 页面身份行 */
.page-identity { display: flex; align-items: center; gap: 10px; margin: 4px 0 2px; font-size: 15px; }
.page-identity strong { font-weight: 600; color: var(--color-text); }
.page-identity-status { font-size: 11px; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; letter-spacing: .03em; }
.page-identity-status.status-draft { background: #fef3c7; color: #92400e; }
.page-identity-status.status-active { background: #d1fae5; color: #065f46; }

/* ① 未验证警告横条 */
.ai-warn-banner { margin: 0 0 10px; padding: 10px 12px; border-radius: 8px; background: #fff7ed; border: 1px solid #fdba74; color: #9a3412; font-size: 13px; line-height: 1.5; }

/* ⑥ AI 高级区折叠 */
details.ai-advanced { margin: 10px 0; border: 1px solid #e5e7eb; border-radius: 8px; padding: 6px 10px; background: #fff; }
details.ai-advanced > summary { cursor: pointer; font-size: 13px; font-weight: 600; color: var(--color-text-secondary); user-select: none; }
details.ai-advanced[open] > summary { margin-bottom: 8px; }

/* 深色模式对比度修复：Knowledge Chain 关键词/标签在深色容器上对比度不足
   .km-keyword 原用 --color-text-tertiary(#64748B) 在深绿底上约 2.8:1；
   .km-chip 原用 --color-amber-800(#92400E) 在深棕底上同色不可见。深色模式改浅色。 */
html.dark .km-keyword { color: var(--color-text-secondary); }
html.dark .km-chip { color: var(--color-amber-200); }
</style>
