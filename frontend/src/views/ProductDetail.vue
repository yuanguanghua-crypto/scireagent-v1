<script setup>
import { onMounted, onUnmounted, ref, reactive, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProductsStore } from '@/stores/products'
import { useBasketStore } from '@/stores/basket'
import { formatCurrency } from '@/utils/helpers'
import { smilesToSvg, rdkitReady, rdkitLoading } from '@/composables/useRdkit'
import ProductLayout from '@/components/layout/ProductLayout.vue'
import ExpandableSection from './admin/components/ExpandableSection.vue'
import UnifiedCTA from '@/components/navigation/UnifiedCTA.vue'
import { useResearchPathStore } from '@/stores/researchPath'
import * as documentsApi from '@/api/documents'
import { openPreview } from '@/utils/previewInject'
import { AppButton, LoadingSpinner, toast } from '@/components/common'

/* ── Collapse state for long sections ── */
const DEFAULT_SHOW = 3
const showAllApps = ref(false)
const showAllMethods = ref(false)
const showAllProtocols = ref(false)
const showAllRefs = ref(false)
const showAllRelated = ref(false)

/* ── InChI collapse state (Fix 6) ── */
const showFullInchi = ref(false)

const route = useRoute()
const router = useRouter()
const store = useProductsStore()
const basketStore = useBasketStore()
const researchCart = useResearchPathStore()

const product = computed(() => store.currentProduct)
const detail = computed(() => store.productDetail)

/* ── V1.2 aggregated data from detail API ── */
const applications = computed(() => detail.value?.applications || [])
const protocols = computed(() => detail.value?.protocols || [])
const references = computed(() => detail.value?.references || [])
const relatedProducts = computed(() => detail.value?.related_products || [])
const faq = computed(() => detail.value?.faq || [])
const compatibility = computed(() => detail.value?.compatibility || {})
const methods = computed(() => compatibility.value.methods || [])

/* ── Related Products — responsive count (Fix 10) ── */
const relatedGridRef = ref(null)
const relatedContainerWidth = ref(0)
const MAX_RELATED_POOL = 10

const relatedDisplayCount = computed(() => {
  const items = relatedProducts.value
  if (!items.length) return 0
  if (!relatedContainerWidth.value) return Math.min(items.length, 6)

  const minCardWidth = 150
  const gap = 8
  // cols = how many 150px+ cards fit in the available width
  const cols = Math.max(1, Math.floor((relatedContainerWidth.value + gap) / (minCardWidth + gap)))
  const pool = Math.min(items.length, MAX_RELATED_POOL)
  // Display in multiples of cols (no orphan last row)
  const displayCount = Math.floor(pool / cols) * cols
  // At least 1 row
  return Math.max(displayCount, Math.min(cols, pool))
})

/* ── Knowledge Tabs ── */
const activeTab = ref('')
const availableTabs = computed(() => {
  const tabs = []
  if (applications.value.length) tabs.push({ key: 'applications', label: 'Applications' })
  if (methods.value.length) tabs.push({ key: 'methods', label: 'Methods' })
  if (protocols.value.length) tabs.push({ key: 'protocols', label: 'Protocols' })
  if (references.value.length) tabs.push({ key: 'references', label: 'References' })
  if (faq.value.length) tabs.push({ key: 'faq', label: 'FAQ' })
  return tabs
})
watch(availableTabs, (tabs) => {
  if (tabs.length && !tabs.some(t => t.key === activeTab.value)) {
    activeTab.value = tabs[0].key
  }
}, { immediate: true })

/* ── Navigation: upstream/downstream ── */
const upstreamEntities = computed(() => {
  const items = []
  for (const app of applications.value) items.push({ type: 'application', id: app.id, name: app.name })
  return items
})
const downstreamEntities = computed(() => {
  return relatedProducts.value.map(p => ({ type: 'product', id: p.id, name: p.name, catalog_no: p.catalog_no }))
})

/* ── Research Path Card ── */
const researchPath = computed(() => {
  const path = []
  // Find the first application that has a research_goal
  const app = applications.value[0]
  if (app?.research_goal_id) {
    path.push({ type: 'research_goal', id: app.research_goal_id, name: app.research_goal_name || 'Research Goal' })
  }
  for (const a of applications.value.slice(0, 1)) {
    path.push({ type: 'application', id: a.id, name: a.name })
  }
  for (const m of methods.value.slice(0, 1)) {
    path.push({ type: 'method', id: m.id, name: m.name })
  }
  for (const p of protocols.value.slice(0, 1)) {
    path.push({ type: 'protocol', id: p.id, name: p.name })
  }
  if (product.value) {
    path.push({ type: 'product', id: product.value.id, name: product.value.name })
  }
  return path
})

/* ── RDKit rendered SVG ── */
const renderedSvg = ref('')
const renderingStructure = ref(false)

async function renderStructure() {
  const p = product.value
  if (!p?.smiles) { renderedSvg.value = ''; return }
  if (p.structure_svg && !p.structure_svg.includes('Structure rendering requires')) {
    renderedSvg.value = p.structure_svg
    return
  }
  renderingStructure.value = true
  try {
    const svg = await smilesToSvg(p.smiles, { width: 350, height: 250 })
    if (svg) renderedSvg.value = svg
    else renderedSvg.value = p.structure_svg || ''
  } catch {
    renderedSvg.value = p.structure_svg || ''
  } finally {
    renderingStructure.value = false
  }
}

/* ── SKU quantities ── */
const skuQuantities = reactive({})
function getSkuQty(id) { return skuQuantities[id] ?? 1 }
function setSkuQty(id, qty) { skuQuantities[id] = Math.max(1, qty) }

/* ── Add to cart ── */
async function addToCart(skuId) {
  try {
    await basketStore.addItem(skuId, getSkuQty(skuId))
    toast.success('Added to cart')
  } catch (e) {
    console.error(e)
    toast.error('Failed to add')
  }
}

/* ── Request Quote ── */
function requestQuote() {
  router.push({ path: '/quote-request', query: { product_id: route.params.id } })
}

/* ── Status badge color ── */
function statusColor(s) {
  if (s === 'active' || s === 'in_stock') return 'badge-green'
  if (s === 'limited' || s === 'draft') return 'badge-amber'
  if (s === 'preorder') return 'badge-blue'
  return 'badge-gray'
}

/* ── Category display ── */
const categoryDisplay = computed(() => {
  const p = product.value
  if (!p) return ''
  const parts = [p.category_l1, p.category_l2].filter(Boolean)
  return parts.join(' › ') || ''
})

/**
 * Strip "In " prefix from category text (Fix 8).
 * Database data may include "In" prefix in product_class_path entries.
 */
function stripCategoryPrefix(text) {
  if (!text) return ''
  const str = Array.isArray(text) ? text.join(' › ') : String(text)
  return str.replace(/^In\s+/, '')
}

/* ── Load product data ── */
async function loadProduct(id) {
  await store.fetchProductDetail(id)
  renderStructure()
  loadCompliance()
  // Track in research path
  if (product.value) {
    researchCart.addStep('product', product.value.id, product.value.name, product.value.slug)
  }
}

/* ── Compliance (COA / SDS) — read-only, public ── */
const sdsList = ref([])
const currentSds = ref(null)
const coaList = ref([])
const complianceLoading = ref(false)

async function loadCompliance() {
  const id = route.params.id
  if (!id) return
  complianceLoading.value = true
  try {
    const [sds, coas] = await Promise.all([
      documentsApi.getSdsList(id),
      documentsApi.getCoaList({ product_id: id, status: 'published' }),
    ])
    sdsList.value = Array.isArray(sds) ? sds : []
    currentSds.value = sdsList.value.find((s) => s.is_current) || null
    coaList.value = Array.isArray(coas) ? coas : []
  } catch (e) {
    console.error('Failed to load compliance documents', e)
    sdsList.value = []
    coaList.value = []
    currentSds.value = null
  } finally {
    complianceLoading.value = false
  }
}

function previewSds() {
  if (currentSds.value) openPreview('sds', currentSds.value)
}
function downloadSds() {
  if (currentSds.value) window.open(documentsApi.downloadSdsUrl(currentSds.value.id), '_blank')
}
function previewCoa(coa) {
  openPreview('coa', coa)
}
function downloadCoa(coa) {
  window.open(documentsApi.downloadCoaUrl(coa.id), '_blank')
}
function confidenceLabel(level) {
  return ({ high: 'High', medium: 'Medium', low: 'Low', very_low: 'Very Low' })[level] || 'Low'
}

function skuHasCoa(skuCode) {
  return coaList.value.some(coa => coa.sku_code === skuCode)
}

function getSkuCoa(skuCode) {
  return coaList.value.find(coa => coa.sku_code === skuCode)
}

onMounted(() => {
  loadProduct(route.params.id)
})

/* ── Watch route params for navigation between products ── */
watch(() => route.params.id, (newId) => {
  if (newId) loadProduct(newId)
  // Reset InChI collapse on navigation
  showFullInchi.value = false
})

/* ── ResizeObserver for Related Products — deferred until grid renders ── */
let relatedObserver = null

function setupRelatedObserver() {
  // Cleanup previous observer
  if (relatedObserver) {
    relatedObserver.disconnect()
    relatedObserver = null
  }
  nextTick(() => {
    const el = relatedGridRef.value
    if (!el) return
    relatedObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        relatedContainerWidth.value = entry.contentRect.width
      }
    })
    relatedObserver.observe(el)
    // Fire once synchronously
    relatedContainerWidth.value = el.offsetWidth
  })
}

watch(relatedProducts, (items) => {
  if (items.length) setupRelatedObserver()
}, { immediate: true })

onUnmounted(() => {
  store.clearCurrent()
  if (relatedObserver) {
    relatedObserver.disconnect()
    relatedObserver = null
  }
})

function onCategoryFilter(filter) {
  const query = {}
  if (filter.productClassId) query.product_class_id = filter.productClassId
  else if (filter.l1) query.category_l1 = filter.l1
  router.push({ path: '/products', query })
}

function onSearch(query) {
  if (query) {
    router.push({ path: '/search', query: { q: query } })
  }
}
</script>

<template>
  <div class="pd" v-if="product">
    <ProductLayout
      :page-title="product.name"
      :page-subtitle="product.catalog_no ? `${product.catalog_no} | ${product.cas || ''}` : ''"
      :hide-header="true"
      :hide-search="true"
      @filter="onCategoryFilter"
      @search="onSearch"
    >
    <!-- ============================================================
         FULL-WIDTH HEADER: Breadcrumb + Product Name
         ============================================================ -->
    <!-- Breadcrumb: product class path -->
    <div class="pd-breadcrumb" v-if="product.product_class_path?.length">
      <router-link to="/products" class="pd-bc-link">Products</router-link>
      <span v-for="(cat, i) in product.product_class_path" :key="i">
        <span class="pd-bc-sep">/</span>
        <span class="pd-bc-item">{{ cat }}</span>
      </span>
    </div>

    <!-- Product Name & Tags -->
    <h1 class="pd-name">{{ product.name }}</h1>
    <div class="pd-name-tags" v-if="product.catalog_no || product.cas">
      <span v-if="product.catalog_no" class="pd-chip pd-chip-mono">{{ product.catalog_no }}</span>
      <span v-if="product.cas" class="pd-chip pd-chip-mono">{{ product.cas }}</span>
    </div>

    <!-- ============================================================
         TWO-COLUMN GRID: Structure vs SKU
         ============================================================ -->
    <div class="pd-two-col">

      <!-- ── LEFT COLUMN ── -->
      <div class="pd-left-col">

        <!-- Structure + Description (flex row) -->
        <div class="pd-structure-row">

          <!-- Structure (280x220) -->
          <div class="pd-structure-box">
            <!-- 优先显示 Word 提取的结构图（权威、高于 SMILES 渲染） -->
            <img v-if="product.structure_image" :src="product.structure_image" class="pd-structure-img" alt="Chemical structure" />
            <template v-else>
            <div v-if="renderedSvg" class="pd-svg-wrap" v-html="renderedSvg"></div>
            <div v-else-if="renderingStructure || rdkitLoading" class="pd-svg-placeholder">
              <svg class="spinner" width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="12" stroke="currentColor" stroke-width="2.5" stroke-dasharray="50" stroke-dashoffset="15" stroke-linecap="round"/></svg>
              <span>Loading structure...</span>
            </div>
            <div v-else-if="product.smiles" class="pd-svg-placeholder">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/><circle cx="12" cy="12" r="3"/></svg>
              <span class="pd-mono-sm">{{ product.smiles }}</span>
            </div>
            <div v-else class="pd-svg-placeholder">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6M9 13h4"/></svg>
              <span>No structure</span>
            </div>
            </template>
          </div>

          <!-- Description (right side) -->
          <div class="pd-desc-col">
            <div class="pd-category-tag" v-if="product.product_class_name">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
              <span>{{ stripCategoryPrefix(product.product_class_path || product.product_class_name) }}</span>
            </div>
            <div class="pd-meta-row">
              <span class="pd-badge pd-badge-dot" :class="statusColor(product.status)">{{ product.status }}</span>
              <span v-if="product.research_use_only" class="pd-badge badge-amber">RUO</span>
            </div>
            <p v-if="product.overview" class="pd-overview">{{ product.overview }}</p>
            <p v-if="product.synonyms?.length" class="pd-synonyms">
              <span class="pd-syn-label">Also known as:</span>
              {{ Array.isArray(product.synonyms) ? product.synonyms.join(', ') : product.synonyms }}
            </p>
          </div>

        </div>

        <!-- Unified Property List -->
        <div class="pd-props">
          <!-- Chemical Identity -->
          <div class="pd-prop-group" v-if="product.smiles || product.inchi || product.cas || product.formula || product.molecular_weight">
            <h4 class="pd-prop-group-title">Chemical Identity</h4>
            <dl class="pd-prop-list">
              <div class="pd-prop-item" v-if="product.smiles">
                <dt class="pd-prop-label">SMILES</dt>
                <dd class="pd-prop-val pd-mono">{{ product.smiles }}</dd>
              </div>
              <div class="pd-prop-item" v-if="product.inchi">
                <dt class="pd-prop-label">InChI</dt>
                <dd class="pd-prop-val pd-mono pd-inchi-val">
                  <span v-if="!showFullInchi && product.inchi.length > 100" class="pd-inchi-truncated">
                    {{ product.inchi.slice(0, 100) }}...
                  </span>
                  <span v-else class="pd-inchi-full">{{ product.inchi }}</span>
                  <button
                    v-if="product.inchi.length > 100"
                    class="pd-inchi-toggle"
                    @click="showFullInchi = !showFullInchi"
                  >
                    {{ showFullInchi ? 'Collapse' : 'Show full' }}
                  </button>
                </dd>
              </div>
              <div class="pd-prop-item" v-if="product.cas">
                <dt class="pd-prop-label">CAS</dt>
                <dd class="pd-prop-val pd-mono">{{ product.cas }}</dd>
              </div>
              <div class="pd-prop-item" v-if="product.formula">
                <dt class="pd-prop-label">Formula</dt>
                <dd class="pd-prop-val pd-mono">{{ product.formula }}</dd>
              </div>
              <div class="pd-prop-item" v-if="product.molecular_weight">
                <dt class="pd-prop-label">MW</dt>
                <dd class="pd-prop-val">{{ product.molecular_weight }} g/mol</dd>
              </div>
            </dl>
          </div>

          <!-- Modification Signature (SMARTS) -->
          <div class="pd-prop-group" v-if="product.substructure_tags && product.substructure_tags.parsed && product.substructure_tags.axes">
            <h4 class="pd-prop-group-title">Modification Signature <span class="pd-prop-group-sub">SMARTS</span></h4>
            <dl class="pd-prop-list">
              <div class="pd-prop-item">
                <dt class="pd-prop-label">Base</dt>
                <dd class="pd-prop-val">
                  <span class="ss-chip ss-chip--base">{{ product.substructure_tags.axes.base }}</span>
                  <span v-if="product.substructure_tags.axes.base_mod" class="ss-chip ss-chip--base_mod">{{ product.substructure_tags.axes.base_mod }}</span>
                </dd>
              </div>
              <div class="pd-prop-item">
                <dt class="pd-prop-label">Sugar</dt>
                <dd class="pd-prop-val">
                  <span v-if="product.substructure_tags.axes.sugar_sub" class="ss-chip ss-chip--sugar_sub">{{ product.substructure_tags.axes.sugar_sub }}</span>
                  <span class="ss-chip ss-chip--sugar_type">{{ product.substructure_tags.axes.sugar_type }}</span>
                </dd>
              </div>
              <div class="pd-prop-item" v-if="product.substructure_tags.axes.biotin_label || product.substructure_tags.axes.ntp || product.substructure_tags.axes.propargyl">
                <dt class="pd-prop-label">Labels</dt>
                <dd class="pd-prop-val">
                  <span v-if="product.substructure_tags.axes.biotin_label" class="ss-chip ss-chip--label">Biotin</span>
                  <span v-if="product.substructure_tags.axes.ntp" class="ss-chip ss-chip--label">NTP</span>
                  <span v-if="product.substructure_tags.axes.propargyl" class="ss-chip ss-chip--label">Propargyl</span>
                </dd>
              </div>
            </dl>
          </div>

          <!-- Specifications -->
          <div class="pd-prop-group" v-if="product.purity || product.concentration || product.storage || product.shipping || product.lead_time">
            <h4 class="pd-prop-group-title">Specifications</h4>
            <dl class="pd-prop-list">
              <div class="pd-prop-item" v-if="product.purity">
                <dt class="pd-prop-label">Purity</dt>
                <dd class="pd-prop-val">{{ product.purity }}</dd>
              </div>
              <div class="pd-prop-item" v-if="product.concentration">
                <dt class="pd-prop-label">Conc.</dt>
                <dd class="pd-prop-val">{{ product.concentration }}</dd>
              </div>
              <div class="pd-prop-item" v-if="product.storage">
                <dt class="pd-prop-label">Storage</dt>
                <dd class="pd-prop-val">{{ product.storage }}</dd>
              </div>
              <div class="pd-prop-item" v-if="product.shipping">
                <dt class="pd-prop-label">Shipping</dt>
                <dd class="pd-prop-val">{{ product.shipping }}</dd>
              </div>
              <div class="pd-prop-item" v-if="product.lead_time">
                <dt class="pd-prop-label">Lead Time</dt>
                <dd class="pd-prop-val">{{ product.lead_time }}</dd>
              </div>
            </dl>
          </div>

        </div>
      </div>

      <!-- ── RIGHT COLUMN ── -->
      <div class="pd-right-col">

        <!-- SKU Table (5 columns) -->
        <section class="pd-section" v-if="product.skus?.length">
          <h2 class="pd-section-title">Available SKUs</h2>
          <div class="pd-sku-table">
            <div class="pd-sku-head">
              <span>SKU</span><span>Pack Size</span><span>Price</span><span>Status</span><span class="pd-coa-header">COA</span><span></span>
            </div>
            <div v-for="sku in product.skus" :key="sku.id" class="pd-sku-row">
              <span class="pd-mono-sm">{{ sku.sku_code }}</span>
              <span>{{ sku.pack_size }}</span>
              <span class="pd-price">{{ formatCurrency(sku.price, sku.currency) }}</span>
              <span class="pd-badge-sm pd-badge-dot" :class="statusColor(sku.inventory_status)">{{ sku.inventory_status }}</span>
              <!-- COA column -->
              <div class="pd-coa-cell">
                <button
                  v-if="skuHasCoa(sku.sku_code)"
                  class="pd-coa-icon"
                  :title="`COA: ${getSkuCoa(sku.sku_code)?.lot_number}`"
                  @click="previewCoa(getSkuCoa(sku.sku_code))"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                </button>
                <span v-else class="pd-coa-na">&mdash;</span>
              </div>
              <!-- Actions column (clean: no COA icon) -->
              <div class="pd-sku-actions">
                <div class="pd-qty">
                  <button @click="setSkuQty(sku.id, getSkuQty(sku.id) - 1)">−</button>
                  <span>{{ getSkuQty(sku.id) }}</span>
                  <button @click="setSkuQty(sku.id, getSkuQty(sku.id) + 1)">+</button>
                </div>
                <AppButton variant="primary" size="sm" @click="addToCart(sku.id)">Add to Cart</AppButton>
              </div>
            </div>
          </div>
          <p v-if="product.skus[0]?.lead_time" class="pd-sku-footnote">Lead time: {{ product.skus[0].lead_time }}</p>
          
          <!-- Product-level Documents + Actions (Fix 2) -->
          <div class="pd-sku-bottom">
            <div class="pd-sds-group" v-if="currentSds">
              <button class="pd-doc-link" @click="previewSds">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                SDS
                <span class="pd-sds-conf" v-if="currentSds?.data_confidence">{{ confidenceLabel(currentSds.data_confidence) }}</span>
              </button>
              <button class="pd-doc-link pd-doc-link-alt" @click="downloadSds" title="Download SDS">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </button>
            </div>
            <button class="pd-doc-link pd-doc-link-alt" @click="requestQuote">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Request Quote
            </button>
          </div>
        </section>

        <!-- Related Products (compact grid) -->
        <section class="pd-section" v-if="relatedProducts.length">
          <h2 class="pd-section-title">Related Products</h2>
          <div class="pd-related-mini-grid" ref="relatedGridRef">
            <router-link
              v-for="rp in relatedProducts.slice(0, relatedDisplayCount)"
              :key="rp.id"
              :to="`/products/${rp.id}`"
              class="pd-related-mini-card"
            >
              <h4 class="pd-related-mini-name">{{ rp.name }}</h4>
              <span v-if="rp.catalog_no" class="pd-related-mini-cat">{{ rp.catalog_no }}</span>
              <span v-if="rp.match_reason && rp.match_reason !== 'related'" class="pd-related-mini-reason">{{ rp.match_reason }}</span>
            </router-link>
          </div>
        </section>

      </div><!-- /.pd-right-col -->
    </div><!-- /.pd-two-col -->

    <!-- ============================================================
         SECOND SCREEN: Knowledge Tabs
         ============================================================ -->
    <div class="pd-tabs-section" v-if="availableTabs.length">
      <div class="pd-tab-bar">
        <button
          v-for="tab in availableTabs"
          :key="tab.key"
          class="pd-tab-btn"
          :class="{ 'pd-tab-active': activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="pd-tab-content">
        <!-- Applications (Fix 7: removed redundant title) -->
        <ExpandableSection
          v-if="activeTab === 'applications'"
          title=""
          :items="applications"
          :default-show="DEFAULT_SHOW"
          item-type="application"
          fallback-msg="Application data is being curated for this product."
          fallback-link="/applications"
          fallback-link-text="Browse all applications"
        >
          <template #item="{ item }">
            <router-link :to="`/applications/${item.id}`" class="pd-card">
              <div class="pd-card-icon pd-icon-app">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              </div>
              <div class="pd-card-body">
                <h3 class="pd-card-title">{{ item.name }}</h3>
                <p v-if="item.summary" class="pd-card-desc">{{ item.summary }}</p>
              </div>
              <span class="pd-card-arrow">&rarr;</span>
            </router-link>
          </template>
        </ExpandableSection>

        <!-- Methods (Fix 7: removed redundant title) -->
        <ExpandableSection
          v-if="activeTab === 'methods'"
          title=""
          :items="methods"
          :default-show="DEFAULT_SHOW"
          item-type="method"
          fallback-msg="Method associations are being mapped for this product."
          fallback-link="/methods"
          fallback-link-text="Browse all methods"
        >
          <template #item="{ item }">
            <router-link :to="`/methods/${item.id}`" class="pd-card">
              <div class="pd-card-icon pd-icon-method">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>
              </div>
              <div class="pd-card-body">
                <h3 class="pd-card-title">{{ item.name }}</h3>
                <p v-if="item.purpose" class="pd-card-desc">{{ item.purpose }}</p>
              </div>
              <span class="pd-card-arrow">&rarr;</span>
            </router-link>
          </template>
        </ExpandableSection>

        <!-- Protocols (Fix 7: removed redundant title) -->
        <ExpandableSection
          v-if="activeTab === 'protocols'"
          title=""
          :items="protocols"
          :default-show="DEFAULT_SHOW"
          item-type="protocol"
          fallback-msg="Validated protocols are being documented for this product."
          fallback-link="/protocols"
          fallback-link-text="Browse all protocols"
        >
          <template #item="{ item }">
            <router-link :to="`/protocols/${item.id}`" class="pd-card">
              <div class="pd-card-icon pd-icon-protocol">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              </div>
              <div class="pd-card-body">
                <h3 class="pd-card-title">{{ item.name }}</h3>
                <p v-if="item.objective" class="pd-card-desc">{{ item.objective }}</p>
                <span v-if="item.estimated_time_minutes" class="pd-card-meta">{{ item.estimated_time_minutes }} min</span>
              </div>
              <span class="pd-card-arrow">&rarr;</span>
            </router-link>
          </template>
        </ExpandableSection>

        <!-- References (Fix 7: removed redundant title) -->
        <ExpandableSection
          v-if="activeTab === 'references'"
          title=""
          :items="references"
          :default-show="DEFAULT_SHOW"
          item-type="reference"
        >
          <template #item="{ item }">
            <div class="pd-ref-item">
              <div class="pd-ref-body">
                <h4 class="pd-ref-title">{{ item.title }}</h4>
                <div class="pd-ref-meta">
                  <span v-if="item.journal" class="pd-ref-journal">{{ item.journal }}</span>
                  <span v-if="item.year" class="pd-ref-year">{{ item.year }}</span>
                </div>
              </div>
              <a v-if="item.doi" :href="`https://doi.org/${item.doi}`" target="_blank" rel="noopener" class="pd-ref-doi">
                DOI &rarr;
              </a>
            </div>
          </template>
        </ExpandableSection>

        <!-- FAQ -->
        <section v-if="activeTab === 'faq'" class="pd-section">
          <div class="pd-faq-list">
            <div v-for="(item, i) in faq" :key="i" class="pd-card pd-faq-card">
              <div class="pd-card-icon pd-icon-faq">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><circle cx="12" cy="8" r="1" fill="currentColor" stroke="none"/></svg>
              </div>
              <div class="pd-card-body">
                <h3 class="pd-card-title pd-faq-q-text" @click="item._expanded = !item._expanded" style="cursor:pointer">{{ item.question }}</h3>
                <p v-if="item._expanded" class="pd-faq-a-card">{{ item.answer }}</p>
              </div>
              <span class="pd-card-arrow" @click="item._expanded = !item._expanded" style="cursor:pointer">{{ item._expanded ? '−' : '+' }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- ============================================================
         BOTTOM SECTION
         ============================================================ -->

    <!-- Handling Notes -->
    <section class="pd-section" v-if="product.handling_notes">
      <h2 class="pd-section-title">Handling Notes</h2>
      <p class="pd-text">{{ product.handling_notes }}</p>
    </section>

    <!-- Unified CTA -->
    <UnifiedCTA
      title="Request this Product"
      subtitle="Add items to cart or submit a quote request for bulk orders."
      :show-cart="!!product.skus?.length"
      :show-rfq="true"
      :show-explore="true"
      :product-id="product.id"
      @add-to-cart="product.skus?.length && addToCart(product.skus[0].id)"
    />

    </ProductLayout>
  </div>

  <!-- Loading -->
  <LoadingSpinner v-else-if="store.loading" text="Loading..." />
  <div v-else class="pd-empty">Product not found</div>
</template>

<style scoped>
.pd { padding-bottom: 40px; }

/* ── Two-column layout ── */
.pd-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  align-items: start;
  margin-bottom: 40px;
}
.pd-left-col { min-width: 0; }
.pd-right-col { min-width: 0; }

/* ── Product Name (Left Column) ── */
.pd-name {
  font-size: 32px;
  font-weight: 800;
  color: var(--color-text);
  margin: 0 0 6px;
  letter-spacing: -0.01em;
  line-height: 1.15;
}
.pd-name-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

/* ── Structure + Description flex row ── */
.pd-structure-row {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 20px;
}
.pd-structure-box {
  width: 280px;
  height: 220px;
  flex-shrink: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-surface);
}
.pd-desc-col {
  flex: 1;
  min-width: 0;
}

/* ── SVG inside structure box ── */
.pd-svg-wrap { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 8px; }
.pd-svg-wrap :deep(svg) { max-width: 100%; max-height: 100%; height: auto; }
/* Word 提取的结构图（权威）优先显示 */
.pd-structure-img { max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; padding: 8px; }
.pd-svg-placeholder { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--color-text-tertiary); font-size: 12px; padding: 16px; text-align: center; }
.spinner { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Unified Property List (grid: label | value) ── */
.pd-props { margin-bottom: 16px; }
.pd-prop-group { margin-bottom: 16px; }
.pd-prop-group-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-tertiary);
  margin: 0 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--color-border-light);
}
.pd-prop-group-sub {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-text-tertiary);
  background: var(--color-border-light);
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 6px;
  vertical-align: middle;
}
/* S6 四轴修饰标签 chips（与卡片共用配色语义） */
.ss-chip {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.5;
  padding: 1px 7px;
  border-radius: 4px;
  margin: 1px 4px 1px 0;
  white-space: nowrap;
}
.ss-chip--base { color: #1d4ed8; background: #dbeafe; }
.ss-chip--base_mod { color: #7c3aed; background: #ede9fe; }
.ss-chip--sugar_sub { color: #047857; background: #d1fae5; }
.ss-chip--sugar_type { color: #b45309; background: #fef3c7; }
.ss-chip--label { color: #be123c; background: #ffe4e6; }
.pd-prop-list {
  margin: 0;
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 3px 8px;
}
.pd-prop-item {
  display: contents;
}
.pd-prop-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-tertiary);
  padding: 2px 0;
}
.pd-prop-val {
  font-size: 13px;
  color: var(--color-text);
  word-break: break-all;
  padding: 2px 0;
}
.pd-mono { font-family: var(--font-mono); font-size: 12px; }
.pd-mono-sm { font-family: var(--font-mono); font-size: 11px; color: var(--color-text-secondary); }

/* ── InChI collapse (Fix 6) ── */
.pd-inchi-val {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px;
}
.pd-inchi-truncated,
.pd-inchi-full {
  font-family: var(--font-mono);
  font-size: 12px;
  word-break: break-all;
  line-height: 1.4;
  max-width: 100%;
}
.pd-inchi-toggle {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary);
  background: none;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s;
}
.pd-inchi-toggle:hover {
  background: var(--color-primary-subtle);
  border-color: var(--color-primary);
}

/* ── Left column meta ── */
.pd-left-meta { margin-top: 16px; }
.pd-category-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  border: 1px solid var(--color-border-light);
}
.pd-meta-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 8px; }
.pd-chip { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: var(--radius-sm); }
.pd-chip-mono { font-family: var(--font-mono); background: var(--color-bg); color: var(--color-text-secondary); border: 1px solid var(--color-border-light); }
.pd-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: capitalize;
  /* All status badges neutral gray */
  background: var(--color-bg);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-light);
}
.pd-badge-sm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  text-transform: capitalize;
  /* All status badges neutral gray */
  background: var(--color-bg);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-light);
}
.badge-green, .badge-amber, .badge-blue, .badge-gray {
  background: var(--color-bg);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-light);
}

/* ── Status badge semantic dot (Fix 5) ── */
.pd-badge-dot::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #9CA3AF; /* default gray */
}
.badge-green.pd-badge-dot::before { background: #22C55E; }
.badge-amber.pd-badge-dot::before { background: #F59E0B; }
.badge-blue.pd-badge-dot::before { background: #3B82F6; }
.badge-gray.pd-badge-dot::before { background: #9CA3AF; }

.pd-overview { font-size: 14px; line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 8px; }
.pd-synonyms { font-size: 12px; line-height: 1.5; color: var(--color-text-tertiary); margin: 0; }
.pd-syn-label { font-weight: 600; color: var(--color-text-secondary); }

/* ── Sections ── */
.pd-section { margin-bottom: 24px; }
.pd-section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--color-border);
  display: inline-block;
}

/* ── SKU Table (5 columns) ── */
.pd-sku-table { border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; }
.pd-sku-head {
  display: grid;
  grid-template-columns: 120px 80px 75px 65px 55px 1fr;
  gap: 8px;
  padding: 10px 16px;
  background: var(--color-bg);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-tertiary);
  border-bottom: 2px solid var(--color-border);
}
.pd-sku-row {
  display: grid;
  grid-template-columns: 120px 80px 75px 65px 55px 1fr;
  gap: 8px;
  padding: 12px 16px;
  align-items: center;
  border-top: 1px solid var(--color-border-light);
  font-size: 13px;
  transition: background 0.1s;
}
.pd-sku-row:hover { background: var(--color-primary-subtle); }
.pd-price {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  font-size: 16px;
}
.pd-sku-actions { display: flex; align-items: center; gap: 6px; justify-content: flex-end; }
.pd-qty { display: flex; align-items: center; border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; height: 32px; }
.pd-qty button { width: 28px; height: 32px; border: none; background: var(--color-bg); cursor: pointer; font-size: 14px; font-weight: 600; color: var(--color-text-secondary); font-family: var(--font-sans); }
.pd-qty button:hover { background: var(--color-primary); color: white; }
.pd-qty span { min-width: 28px; text-align: center; font-size: 13px; font-weight: 600; border-left: 1px solid var(--color-border); border-right: 1px solid var(--color-border); height: 100%; display: flex; align-items: center; justify-content: center; font-variant-numeric: tabular-nums; }
.pd-sku-footnote { font-size: 11px; color: var(--color-text-tertiary); margin: 6px 0 0; }

/* ── COA column header center-aligned ── */
.pd-coa-header { text-align: center; }

/* ── COA column per SKU row ── */
.pd-coa-cell { display: flex; align-items: center; justify-content: center; }
.pd-coa-icon {
  width: 28px;
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-tertiary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.pd-coa-icon:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-subtle);
}
.pd-coa-na { font-size: 11px; color: var(--color-text-tertiary); line-height: 28px; }

/* ── SKU table bottom: SDS + Quote ── */
.pd-sku-bottom {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0 0;
  margin-top: 10px;
  border-top: 1px solid var(--color-border-light);
}
.pd-sds-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.pd-sds-conf {
  font-size: 10px;
  font-weight: 500;
  color: var(--color-text-tertiary);
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  padding: 0 6px;
  line-height: 16px;
  margin-left: 2px;
}
.pd-doc-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-sans);
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.12s;
}
.pd-doc-link:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-subtle);
}
.pd-doc-link-alt { color: var(--color-text-secondary); }
.pd-doc-link-alt:hover { color: var(--color-primary); }
.pd-sds-meta { font-size: 11px; color: var(--color-text-tertiary); }

/* ── Breadcrumb (product class path) ── */
.pd-breadcrumb { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; font-size: 12px; }
.pd-bc-link { color: var(--color-primary); text-decoration: none; font-weight: 500; }
.pd-bc-link:hover { text-decoration: underline; }
.pd-bc-sep { color: var(--color-text-tertiary); margin: 0 2px; }
.pd-bc-item { color: var(--color-text-secondary); }

/* ── Related Products (mini grid for right column) ── */
.pd-related-mini-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}
.pd-related-mini-card {
  padding: 8px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  text-decoration: none;
  color: var(--color-text);
  transition: all 0.15s;
}
.pd-related-mini-card:hover { border-color: var(--color-primary); }
.pd-related-mini-name { font-size: 11px; font-weight: 600; margin: 0 0 2px; color: var(--color-primary); line-height: 1.3; }
.pd-related-mini-cat { font-family: var(--font-mono); font-size: 9px; color: var(--color-text-secondary); display: block; }
.pd-related-mini-reason { font-size: 10px; color: var(--color-text-tertiary); background: var(--color-bg); padding: 1px 6px; border-radius: 8px; display: inline-block; margin-top: 3px; }

/* ── Knowledge Tabs ── */
.pd-tabs-section { margin-bottom: 32px; }
.pd-tab-bar {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 20px;
  overflow-x: auto;
}
.pd-tab-btn {
  padding: 9px 20px;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-secondary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
  font-family: var(--font-sans);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
}
.pd-tab-btn:hover { color: var(--color-text); background: var(--color-bg); }

/* Fix 4: Tab active state → underline style instead of filled */
.pd-tab-active {
  color: var(--color-primary);
  background: transparent;
  border-bottom-color: var(--color-primary);
  border-bottom-width: 2px;
}

/* ── Card grid (Applications, Methods, Protocols) ── */
.pd-card-grid { display: flex; flex-direction: column; gap: 8px; }
.pd-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); text-decoration: none; color: var(--color-text); transition: all 0.15s; }
.pd-card:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }
.pd-card-icon { width: 36px; height: 36px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.pd-icon-app { background: var(--color-emerald-50); color: var(--color-emerald-600); }
.pd-icon-method { background: #E8F0FE; color: #7AAEDB; }
.pd-icon-protocol { background: #F5F0E0; color: #C9A34E; }
.pd-card-body { flex: 1; min-width: 0; }
.pd-card-title { font-size: 14px; font-weight: 600; margin: 0; color: var(--color-text); }
.pd-card-desc { font-size: 12px; color: var(--color-text-secondary); margin: 2px 0 0; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pd-card-meta { font-size: 11px; color: var(--color-text-tertiary); }
.pd-card-arrow { font-size: 16px; color: var(--color-text-tertiary); flex-shrink: 0; }

/* ── References ── */
.pd-refs-list { display: flex; flex-direction: column; gap: 8px; }
.pd-ref-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 10px 14px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.pd-ref-body { flex: 1; min-width: 0; }
.pd-ref-title { font-size: 13px; font-weight: 600; margin: 0 0 4px; color: var(--color-text); line-height: 1.4; }
.pd-ref-meta { display: flex; gap: 8px; font-size: 12px; color: var(--color-text-secondary); }
.pd-ref-journal { font-style: italic; }
.pd-ref-doi { font-size: 12px; color: var(--color-primary); text-decoration: none; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.pd-ref-doi:hover { text-decoration: underline; }

/* ── FAQ ── */
.pd-faq-list { display: flex; flex-direction: column; gap: 8px; }
.pd-faq-card { cursor: pointer; }
.pd-faq-q-text { font-size: 14px; font-weight: 600; margin: 0; color: var(--color-text); }
.pd-faq-a-card { font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; margin: 8px 0 0; padding-top: 8px; border-top: 1px solid var(--color-border-light); }
.pd-icon-faq { background: #F0E8FF; color: #A78BEF; }

/* Handling notes */
.pd-text { font-size: 14px; line-height: 1.6; color: var(--color-text); margin: 0; }

/* ── Not found ── */
.pd-empty { text-align: center; padding: 60px 0; color: var(--color-text-secondary); font-size: 15px; }

/* ── Responsive: single column at 768px ── */
@media (max-width: 768px) {
  .pd-two-col { grid-template-columns: 1fr; gap: 24px; }
  .pd-structure-row { flex-direction: column; }
  .pd-structure-box { width: 100%; max-width: 280px; }
  .pd-sku-head, .pd-sku-row { grid-template-columns: 1fr 1fr; font-size: 12px; }
  .pd-sku-head { display: none; }
  .pd-sku-row { display: flex; flex-wrap: wrap; gap: 4px 12px; }
  .pd-related-mini-grid { grid-template-columns: 1fr 1fr; }
  .pd-tab-bar { gap: 0; }
  .pd-tab-btn { flex: 1; text-align: center; padding: 8px 10px; font-size: 12px; }
}
</style>
