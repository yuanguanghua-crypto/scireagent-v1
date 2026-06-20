<script setup>
import { onMounted, onUnmounted, ref, reactive, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProductsStore } from '@/stores/products'
import { useBasketStore } from '@/stores/basket'
import { formatCurrency } from '@/utils/helpers'
import { smilesToSvg, rdkitReady, rdkitLoading } from '@/composables/useRdkit'
import { useGraph } from '@/composables/useGraph'
import ProductLayout from '@/components/layout/ProductLayout.vue'
import KnowledgeGraph from '@/components/graph/KnowledgeGraph.vue'
import ContextCards from '@/components/navigation/ContextCards.vue'
import ExpandableSection from './admin/components/ExpandableSection.vue'
import ResearchPathCard from '@/components/navigation/ResearchPathCard.vue'
import UnifiedCTA from '@/components/navigation/UnifiedCTA.vue'
import ResearchBreadcrumb from '@/components/navigation/ResearchBreadcrumb.vue'
import ResearchPathChips from '@/components/navigation/ResearchPathChips.vue'
import RelationshipWidget from '@/components/navigation/RelationshipWidget.vue'
import { useResearchPathStore } from '@/stores/researchPath'

/* ── Collapse state for long sections ── */
const DEFAULT_SHOW = 3
const showAllApps = ref(false)
const showAllMethods = ref(false)
const showAllProtocols = ref(false)
const showAllRefs = ref(false)
const showAllRelated = ref(false)

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
  for (const m of (compatibility.value.methods || []).slice(0, 1)) {
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

/* ── Relationship Widget groups ── */
const relationshipGroups = computed(() => {
  const groups = []
  if (applications.value.length) {
    groups.push({ type: 'application', label: 'Applications', items: applications.value.slice(0, 4) })
  }
  if (compatibility.value.methods?.length) {
    groups.push({ type: 'method', label: 'Methods', items: compatibility.value.methods.slice(0, 4) })
  }
  if (protocols.value.length) {
    groups.push({ type: 'protocol', label: 'Protocols', items: protocols.value.slice(0, 4) })
  }
  if (relatedProducts.value.length) {
    groups.push({ type: 'product', label: 'Related Products', items: relatedProducts.value.slice(0, 4) })
  }
  return groups
})

/* ── Knowledge Graph ── */
const { nodes: graphNodes, edges: graphEdges, loading: graphLoading, fetch: fetchGraph } = useGraph('product', computed(() => route.params.id), { depth: 2, maxNodes: 30, maxEdges: 50 })

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

/* ── Toast ── */
const toastMsg = ref('')
const toastShow = ref(false)
function showToast(msg) { toastMsg.value = msg; toastShow.value = true; setTimeout(() => toastShow.value = false, 2500) }

/* ── Add to cart ── */
async function addToCart(skuId) {
  try {
    await basketStore.addItem(skuId, getSkuQty(skuId))
    showToast('Added to cart')
  } catch (e) {
    console.error(e)
    showToast('Failed to add')
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

/* ── Load product data ── */
async function loadProduct(id) {
  await store.fetchProductDetail(id)
  renderStructure()
  fetchGraph()
  // Track in research path
  if (product.value) {
    researchCart.addStep('product', product.value.id, product.value.name, product.value.slug)
  }
}

onMounted(() => loadProduct(route.params.id))

/* ── Watch route params for navigation between products ── */
watch(() => route.params.id, (newId) => {
  if (newId) loadProduct(newId)
})

onUnmounted(() => store.clearCurrent())

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
      @filter="onCategoryFilter"
      @search="onSearch"
    >
    <!-- Research Breadcrumb (P1) -->
    <ResearchBreadcrumb
      :items="researchPath.slice(0, -1)"
      :current-name="product.name"
    />

    <!-- Research Path Chips (P1) -->
    <ResearchPathChips :path="researchPath" current-type="product" />

    <!-- Context Cards: upstream/downstream navigation -->
    <ContextCards
      :upstream="upstreamEntities"
      :downstream="downstreamEntities"
      downstream-label="Related Products"
      fallback-message="Knowledge links are being built for this product."
      :request-support-link="!upstreamEntities.length"
    />

    <!-- Hero: Structure + Title + Key Info -->
    <div class="pd-hero">
      <div class="pd-hero-img">
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
      </div>

      <div class="pd-hero-info">
        <h1 class="pd-name">{{ product.name }}</h1>
        <div v-if="product.product_class_name" class="pd-category-tag">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
          <span>{{ product.product_class_path?.join(' › ') || product.product_class_name }}</span>
        </div>
        <div class="pd-meta-row">
          <span v-if="product.catalog_no" class="pd-chip pd-chip-primary">{{ product.catalog_no }}</span>
          <span v-if="product.cas" class="pd-chip pd-chip-mono">{{ product.cas }}</span>
          <span class="pd-badge" :class="statusColor(product.status)">{{ product.status }}</span>
          <span v-if="product.research_use_only" class="pd-badge badge-amber">RUO</span>
        </div>
        <p v-if="product.overview" class="pd-overview">{{ product.overview }}</p>
        <p v-if="product.synonyms?.length" class="pd-synonyms">
          <span class="pd-syn-label">Also known as:</span>
          {{ Array.isArray(product.synonyms) ? product.synonyms.join(', ') : product.synonyms }}
        </p>

        <div class="pd-specs">
          <div class="pd-spec" v-if="product.formula">
            <span class="pd-spec-label">Formula</span>
            <span class="pd-spec-val pd-mono">{{ product.formula }}</span>
          </div>
          <div class="pd-spec" v-if="product.molecular_weight">
            <span class="pd-spec-label">MW</span>
            <span class="pd-spec-val">{{ product.molecular_weight }} g/mol</span>
          </div>
          <div class="pd-spec" v-if="product.purity">
            <span class="pd-spec-label">Purity</span>
            <span class="pd-spec-val">{{ product.purity }}</span>
          </div>
          <div class="pd-spec" v-if="product.concentration">
            <span class="pd-spec-label">Conc.</span>
            <span class="pd-spec-val">{{ product.concentration }}</span>
          </div>
          <div class="pd-spec" v-if="product.storage">
            <span class="pd-spec-label">Storage</span>
            <span class="pd-spec-val">{{ product.storage }}</span>
          </div>
          <div class="pd-spec" v-if="product.shipping">
            <span class="pd-spec-label">Shipping</span>
            <span class="pd-spec-val">{{ product.shipping }}</span>
          </div>
          <div class="pd-spec" v-if="product.lead_time">
            <span class="pd-spec-label">Lead Time</span>
            <span class="pd-spec-val">{{ product.lead_time }}</span>
          </div>
        </div>

        <!-- Quick CTA -->
        <div class="pd-hero-cta">
          <button class="pd-rfq-btn" @click="requestQuote">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Request Quote
          </button>
        </div>
      </div>
    </div>

    <!-- SKU Table -->
    <section class="pd-section" v-if="product.skus?.length">
      <h2 class="pd-section-title">Available SKUs</h2>
      <div class="pd-sku-table">
        <div class="pd-sku-head">
          <span>SKU</span><span>Pack Size</span><span>Conc.</span><span>Price</span><span>Status</span><span>Lead Time</span><span></span>
        </div>
        <div v-for="sku in product.skus" :key="sku.id" class="pd-sku-row">
          <span class="pd-mono-sm">{{ sku.sku_code }}</span>
          <span>{{ sku.pack_size }}</span>
          <span>{{ sku.concentration || '—' }}</span>
          <span class="pd-price">{{ formatCurrency(sku.price, sku.currency) }}</span>
          <span class="pd-badge-sm" :class="statusColor(sku.inventory_status)">{{ sku.inventory_status }}</span>
          <span class="pd-text-sm">{{ sku.lead_time || '—' }}</span>
          <div class="pd-sku-actions">
            <div class="pd-qty">
              <button @click="setSkuQty(sku.id, getSkuQty(sku.id) - 1)">−</button>
              <span>{{ getSkuQty(sku.id) }}</span>
              <button @click="setSkuQty(sku.id, getSkuQty(sku.id) + 1)">+</button>
            </div>
            <button class="pd-cart-btn" @click="addToCart(sku.id)">Add to Cart</button>
          </div>
        </div>
      </div>
    </section>

    <!-- Used In Applications (V1.2) -->
    <ExpandableSection
      title="Used In Applications"
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

    <!-- Methods (V1.2) -->
    <ExpandableSection
      title="Compatible Methods"
      :items="compatibility.methods || []"
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

    <!-- Protocols (V1.2) -->
    <ExpandableSection
      title="Protocols"
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

    <!-- References (V1.2) -->
    <ExpandableSection
      v-if="references.length"
      title="References"
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

    <!-- FAQ (V1.2) -->
    <section class="pd-section" v-if="faq.length">
      <h2 class="pd-section-title">Frequently Asked Questions</h2>
      <div class="pd-faq-list">
        <details v-for="(item, i) in faq" :key="i" class="pd-faq-item">
          <summary class="pd-faq-q">{{ item.question }}</summary>
          <p class="pd-faq-a">{{ item.answer }}</p>
        </details>
      </div>
    </section>

    <!-- Related Products (V1.2) -->
    <section class="pd-section" v-if="relatedProducts.length">
      <h2 class="pd-section-title">Related Products</h2>
      <div class="pd-related-grid">
        <router-link v-for="rp in relatedProducts" :key="rp.id" :to="`/products/${rp.id}`" class="pd-related-card">
          <h4 class="pd-related-name">{{ rp.name }}</h4>
          <span v-if="rp.catalog_no" class="pd-related-cat">{{ rp.catalog_no }}</span>
          <span v-if="rp.cas" class="pd-related-cas">{{ rp.cas }}</span>
          <span v-if="rp.match_reason" class="pd-related-reason">{{ rp.match_reason }}</span>
        </router-link>
      </div>
    </section>

    <!-- Handling Notes -->
    <section class="pd-section" v-if="product.handling_notes">
      <h2 class="pd-section-title">Handling Notes</h2>
      <p class="pd-text">{{ product.handling_notes }}</p>
    </section>

    <!-- Classification -->
    <section class="pd-section" v-if="categoryDisplay">
      <h2 class="pd-section-title">Classification</h2>
      <div class="pd-class-grid">
        <div class="pd-class-item" v-if="product.category_l1">
          <span class="pd-class-label">Category L1</span>
          <span class="pd-class-val">{{ product.category_l1 }}</span>
        </div>
        <div class="pd-class-item" v-if="product.category_l2">
          <span class="pd-class-label">Category L2</span>
          <span class="pd-class-val">{{ product.category_l2 }}</span>
        </div>
      </div>
    </section>

    <!-- Documents -->
    <section class="pd-section" v-if="product.documents?.length">
      <h2 class="pd-section-title">Documents</h2>
      <div class="pd-docs">
        <a v-for="doc in product.documents" :key="doc.id" :href="doc.file" target="_blank" class="pd-doc-item">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 2h6l4 4v8a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" stroke-width="1.5"/><path d="M10 2v4h4" stroke="currentColor" stroke-width="1.5"/></svg>
          <span>{{ doc.document_type }} — {{ doc.original_filename }}</span>
        </a>
      </div>
    </section>

    <!-- Chemical Identifiers -->
    <section class="pd-section" v-if="product.smiles || product.inchi">
      <h2 class="pd-section-title">Chemical Identifiers</h2>
      <div class="pd-id-grid">
        <div class="pd-id-item" v-if="product.smiles">
          <span class="pd-id-label">SMILES</span>
          <code class="pd-id-val">{{ product.smiles }}</code>
        </div>
        <div class="pd-id-item" v-if="product.inchi">
          <span class="pd-id-label">InChI</span>
          <code class="pd-id-val">{{ product.inchi }}</code>
        </div>
      </div>
    </section>

    <!-- Relationship Widget (P1) -->
    <RelationshipWidget
      title="Related by Research"
      :groups="relationshipGroups"
    />

    <!-- Research Path Card -->
    <ResearchPathCard v-if="researchPath.length" :path="researchPath" current-type="product" />

    <!-- Unified CTA -->
    <UnifiedCTA
      title="Need this product?"
      subtitle="Add to cart or request a quote for bulk and custom orders."
      :show-cart="!!product.skus?.length"
      :show-rfq="true"
      :show-explore="true"
      :product-id="product.id"
      @add-to-cart="product.skus?.length && addToCart(product.skus[0].id)"
    />

    </ProductLayout>
  </div>

  <!-- Loading -->
  <div v-else-if="store.loading" class="pd-loading">Loading...</div>
  <div v-else class="pd-empty">Product not found</div>

  <!-- Toast -->
  <Transition name="pd-t">
    <div v-if="toastShow" class="pd-toast">{{ toastMsg }}</div>
  </Transition>
</template>

<style scoped>
.pd { padding-bottom: 40px; }

/* Breadcrumb */
.pd-breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 16px; }
.pd-breadcrumb a { color: var(--color-primary); text-decoration: none; }
.pd-breadcrumb a:hover { text-decoration: underline; }
.pd-breadcrumb span { color: var(--color-text-tertiary); }
.pd-breadcrumb-cur { color: var(--color-text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; }
.pd-breadcrumb-sep { color: var(--color-text-tertiary); margin: 0 2px; }
.pd-breadcrumb-link { color: var(--color-primary); text-decoration: none; }
.pd-breadcrumb-link:hover { text-decoration: underline; }

/* Hero */
.pd-hero { display: flex; gap: 24px; margin-bottom: 28px; align-items: flex-start; }
.pd-hero-img { width: 200px; height: 200px; flex-shrink: 0; border: 1px solid var(--color-border); border-radius: var(--radius-lg); overflow: hidden; display: flex; align-items: center; justify-content: center; background: var(--color-surface); }
.pd-svg-wrap { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 8px; }
.pd-svg-wrap :deep(svg) { max-width: 100%; max-height: 100%; height: auto; }
.pd-svg-placeholder { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--color-text-tertiary); font-size: 12px; padding: 16px; text-align: center; }
.spinner { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.pd-hero-info { flex: 1; min-width: 0; }
.pd-name { font-size: 26px; font-weight: 800; color: var(--color-text); margin: 0 0 6px; letter-spacing: -0.01em; line-height: 1.2; }
.pd-category-tag { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; color: var(--color-primary); background: var(--color-primary-light); padding: 3px 10px; border-radius: var(--radius-sm); margin-bottom: 8px; }
.pd-meta-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 12px; }
.pd-chip { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: var(--radius-sm); }
.pd-chip-primary { background: var(--color-primary-light); color: var(--color-primary); }
.pd-chip-mono { font-family: var(--font-mono); background: var(--color-bg); color: var(--color-text-secondary); }
.pd-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; text-transform: capitalize; }
.pd-badge-sm { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 8px; text-transform: capitalize; }
.badge-green { background: var(--color-success-light); color: var(--color-success); }
.badge-amber { background: var(--color-warning-light); color: var(--color-warning); }
.badge-blue { background: var(--color-info-light); color: var(--color-info); }
.badge-gray { background: var(--color-bg); color: var(--color-text-secondary); }
.pd-overview { font-size: 14px; line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 8px; }
.pd-synonyms { font-size: 12px; line-height: 1.5; color: var(--color-text-tertiary); margin: 0 0 12px; }
.pd-syn-label { font-weight: 600; color: var(--color-text-secondary); }
.pd-text-sm { font-size: 12px; color: var(--color-text-secondary); }

/* Specs */
.pd-specs { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }
.pd-spec { display: flex; flex-direction: column; gap: 1px; }
.pd-spec-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-tertiary); }
.pd-spec-val { font-size: 13px; font-weight: 500; color: var(--color-text); }
.pd-mono { font-family: var(--font-mono); font-size: 12px; }
.pd-mono-sm { font-family: var(--font-mono); font-size: 11px; color: var(--color-text-secondary); }

/* Hero CTA */
.pd-hero-cta { margin-top: 12px; }
.pd-rfq-btn { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 18px; background: transparent; color: var(--color-primary); border: 2px solid var(--color-primary); border-radius: var(--radius-md); font-size: 13px; font-weight: 700; cursor: pointer; font-family: var(--font-sans); transition: all 0.15s; }
.pd-rfq-btn:hover { background: var(--color-primary); color: white; }

/* Sections */
.pd-section { margin-bottom: 24px; }
.pd-section-title { font-size: 16px; font-weight: 700; color: var(--color-text); margin: 0 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--color-primary); display: inline-block; }

/* SKU Table */
.pd-sku-table { border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; }
.pd-sku-head { display: grid; grid-template-columns: 130px 110px 80px 90px 90px 100px 1fr; gap: 8px; padding: 8px 14px; background: var(--color-bg); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-tertiary); }
.pd-sku-row { display: grid; grid-template-columns: 130px 110px 80px 90px 90px 100px 1fr; gap: 8px; padding: 10px 14px; align-items: center; border-top: 1px solid var(--color-border-light); font-size: 13px; }
.pd-sku-row:hover { background: var(--color-primary-subtle); }
.pd-price { font-weight: 700; font-variant-numeric: tabular-nums; }
.pd-sku-actions { display: flex; align-items: center; gap: 8px; justify-content: flex-end; }
.pd-qty { display: flex; align-items: center; border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; height: 32px; }
.pd-qty button { width: 28px; height: 32px; border: none; background: var(--color-bg); cursor: pointer; font-size: 14px; font-weight: 600; color: var(--color-text-secondary); font-family: var(--font-sans); }
.pd-qty button:hover { background: var(--color-primary); color: white; }
.pd-qty span { min-width: 28px; text-align: center; font-size: 13px; font-weight: 600; border-left: 1px solid var(--color-border); border-right: 1px solid var(--color-border); height: 100%; display: flex; align-items: center; justify-content: center; font-variant-numeric: tabular-nums; }
.pd-cart-btn { height: 36px; padding: 0 18px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); font-size: 13px; font-weight: 700; cursor: pointer; font-family: var(--font-sans); white-space: nowrap; transition: background 0.15s; }
.pd-cart-btn:hover { background: var(--color-primary-hover); }

/* Card grid (Applications, Methods, Protocols) */
.pd-card-grid { display: flex; flex-direction: column; gap: 8px; }
.pd-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); text-decoration: none; color: var(--color-text); transition: all 0.15s; }
.pd-card:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }
.pd-card-icon { width: 36px; height: 36px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.pd-icon-app { background: #ecfdf5; color: #059669; }
.pd-icon-method { background: #eff6ff; color: #2563eb; }
.pd-icon-protocol { background: #fffbeb; color: #d97706; }
.pd-card-body { flex: 1; min-width: 0; }
.pd-card-title { font-size: 14px; font-weight: 600; margin: 0; color: var(--color-text); }
.pd-card-desc { font-size: 12px; color: var(--color-text-secondary); margin: 2px 0 0; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pd-card-meta { font-size: 11px; color: var(--color-text-tertiary); }
.pd-card-arrow { font-size: 16px; color: var(--color-text-tertiary); flex-shrink: 0; }

/* References */
.pd-refs-list { display: flex; flex-direction: column; gap: 8px; }
.pd-ref-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 10px 14px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.pd-ref-body { flex: 1; min-width: 0; }
.pd-ref-title { font-size: 13px; font-weight: 600; margin: 0 0 4px; color: var(--color-text); line-height: 1.4; }
.pd-ref-meta { display: flex; gap: 8px; font-size: 12px; color: var(--color-text-secondary); }
.pd-ref-journal { font-style: italic; }
.pd-ref-doi { font-size: 12px; color: var(--color-primary); text-decoration: none; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.pd-ref-doi:hover { text-decoration: underline; }

/* FAQ */
.pd-faq-list { display: flex; flex-direction: column; gap: 6px; }
.pd-faq-item { border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; }
.pd-faq-q { padding: 12px 16px; font-size: 14px; font-weight: 600; color: var(--color-text); cursor: pointer; list-style: none; display: flex; align-items: center; gap: 8px; }
.pd-faq-q::before { content: 'Q'; width: 22px; height: 22px; background: var(--color-primary-light); color: var(--color-primary); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; flex-shrink: 0; }
.pd-faq-a { padding: 0 16px 12px 46px; font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; margin: 0; }

/* Related Products */
.pd-related-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.pd-related-card { padding: 12px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); text-decoration: none; color: var(--color-text); transition: all 0.15s; }
.pd-related-card:hover { border-color: var(--color-primary); }
.pd-related-name { font-size: 13px; font-weight: 600; margin: 0 0 4px; color: var(--color-primary); }
.pd-related-cat { font-family: var(--font-mono); font-size: 11px; color: var(--color-text-secondary); display: block; }
.pd-related-cas { font-size: 11px; color: var(--color-text-tertiary); display: block; margin-top: 2px; }
.pd-related-reason { font-size: 10px; color: var(--color-primary); background: var(--color-primary-light); padding: 1px 6px; border-radius: 8px; display: inline-block; margin-top: 4px; }

/* Handling notes */
.pd-text { font-size: 14px; line-height: 1.6; color: var(--color-text); margin: 0; }

/* Category */
.pd-class-grid { display: flex; gap: 16px; }
.pd-class-item { display: flex; flex-direction: column; gap: 2px; }
.pd-class-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-tertiary); }
.pd-class-val { font-size: 13px; color: var(--color-text); text-transform: capitalize; }

/* Documents */
.pd-docs { display: flex; flex-direction: column; gap: 6px; }
.pd-doc-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 13px; color: var(--color-primary); text-decoration: none; }
.pd-doc-item:hover { background: var(--color-primary-subtle); border-color: var(--color-primary); }

/* Graceful Degradation Fallback */
.pd-fallback {
  padding: 16px;
  background: var(--color-bg);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  text-align: center;
}
.pd-fallback p { font-size: 13px; color: var(--color-text-secondary); margin: 0 0 6px; }
.pd-fallback-link { font-size: 13px; color: var(--color-primary); text-decoration: none; font-weight: 500; }
.pd-fallback-link:hover { text-decoration: underline; }

/* Knowledge Graph */
.pd-graph-wrap { border: 1px solid var(--color-border); border-radius: var(--radius-lg); overflow: hidden; }

/* Chemical IDs */
.pd-id-grid { display: flex; flex-direction: column; gap: 8px; }
.pd-id-item { display: flex; flex-direction: column; gap: 2px; }
.pd-id-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-tertiary); }
.pd-id-val { font-family: var(--font-mono); font-size: 12px; color: var(--color-text-secondary); background: var(--color-bg); padding: 6px 10px; border-radius: var(--radius-sm); word-break: break-all; margin: 0; }

/* Bottom CTA — handled by UnifiedCTA component */

/* Loading / Empty */
.pd-loading, .pd-empty { text-align: center; padding: 60px 0; color: var(--color-text-secondary); font-size: 15px; }

/* Toast */
.pd-toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); background: var(--color-text); color: white; padding: 10px 24px; border-radius: var(--radius-md); font-size: 14px; font-weight: 500; z-index: 9999; box-shadow: 0 4px 12px rgba(0,0,0,.15); }
.pd-t-enter-active, .pd-t-leave-active { transition: opacity .3s, transform .3s; }
.pd-t-enter-from, .pd-t-leave-to { opacity: 0; transform: translateX(-50%) translateY(12px); }

@media (max-width: 768px) {
  .pd-hero { flex-direction: column; align-items: center; text-align: center; }
  .pd-hero-img { width: 160px; height: 160px; }
  .pd-specs { justify-content: center; }
  .pd-sku-head, .pd-sku-row { grid-template-columns: 1fr; font-size: 12px; }
  .pd-sku-head { display: none; }
  .pd-sku-row { display: flex; flex-wrap: wrap; gap: 4px 12px; }
  .pd-related-grid { grid-template-columns: 1fr 1fr; }
  .pd-cta-actions { flex-direction: column; align-items: center; }
}
</style>
