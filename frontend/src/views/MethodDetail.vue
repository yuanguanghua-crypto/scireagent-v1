<script setup>
import { onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMethodsStore } from '@/stores/methods'
import ContextCards from '@/components/navigation/ContextCards.vue'
import ResearchPathCard from '@/components/navigation/ResearchPathCard.vue'
import UnifiedCTA from '@/components/navigation/UnifiedCTA.vue'
import ResearchBreadcrumb from '@/components/navigation/ResearchBreadcrumb.vue'
import ResearchPathChips from '@/components/navigation/ResearchPathChips.vue'
import { useResearchPathStore } from '@/stores/researchPath'
import { LoadingSpinner } from '@/components/common'
import ExpandableSection from './admin/components/ExpandableSection.vue'

const route = useRoute()
const router = useRouter()
const store = useMethodsStore()
const researchCart = useResearchPathStore()

const method = computed(() => store.currentMethod)
const methodId = computed(() => route.params.id)

/* ── Navigation data ── */
const upstreamEntities = computed(() => {
  const items = []
  if (method.value?.application_id) {
    items.push({ type: 'application', id: method.value.application_id, name: method.value.application_name || 'Application' })
  }
  return items
})
const downstreamEntities = computed(() => {
  return (method.value?.protocols || []).map(p => ({ type: 'protocol', id: p.id, name: p.name }))
})
const researchPath = computed(() => {
  const path = []
  if (method.value?.research_goal_id) {
    path.push({ type: 'research_goal', id: method.value.research_goal_id, name: method.value.research_goal_name || 'Research Goal' })
  }
  if (method.value?.application_id) {
    path.push({ type: 'application', id: method.value.application_id, name: method.value.application_name || 'Application' })
  }
  if (method.value) path.push({ type: 'method', id: method.value.id, name: method.value.name })
  for (const p of (method.value?.protocols || []).slice(0, 1)) {
    path.push({ type: 'protocol', id: p.id, name: p.name })
  }
  return path
})

async function loadMethod(id) {
  await store.fetchMethod(id)
  if (method.value) researchCart.addStep('method', method.value.id, method.value.name, method.value.slug)
}

onMounted(() => loadMethod(route.params.id))
watch(() => route.params.id, (newId) => { if (newId) loadMethod(newId) })
onUnmounted(() => { store.clearCurrent() })
</script>

<template>
  <div class="detail-page" v-if="method">
    <ResearchBreadcrumb :items="researchPath.slice(0, -1)" :current-name="method.name" />
    <ResearchPathChips :path="researchPath" current-type="method" />

    <!-- Context Cards -->
    <ContextCards
      :upstream="upstreamEntities"
      :downstream="downstreamEntities"
      downstream-label="Protocols"
      fallback-message="Protocol data is being curated for this method."
    />

    <div class="detail-hero">
      <h1 class="detail-title">{{ method.name }}</h1>
      <span class="detail-badge" :class="`badge-${method.status}`">{{ method.status }}</span>
      <p v-if="method.summary" class="detail-summary">{{ method.summary }}</p>
      <p v-if="method.purpose" class="detail-purpose"><strong>Purpose:</strong> {{ method.purpose }}</p>
    </div>

    <!-- Specs -->
    <div class="specs-row" v-if="method.cost_band || method.timeline">
      <div class="spec" v-if="method.cost_band">
        <span class="spec-label">Cost Band</span>
        <span class="spec-val">{{ method.cost_band }}</span>
      </div>
      <div class="spec" v-if="method.timeline">
        <span class="spec-label">Timeline</span>
        <span class="spec-val">{{ method.timeline }}</span>
      </div>
    </div>

    <!-- Advantages / Limitations -->
    <div class="detail-columns" v-if="method.advantages || method.limitations">
      <section class="detail-col" v-if="method.advantages">
        <h3 class="col-title">Advantages</h3>
        <p class="col-text">{{ method.advantages }}</p>
      </section>
      <section class="detail-col" v-if="method.limitations">
        <h3 class="col-title">Limitations</h3>
        <p class="col-text">{{ method.limitations }}</p>
      </section>
    </div>

    <!-- Protocols -->
    <section class="detail-section">
      <h2 class="section-title">Protocols</h2>
      <ExpandableSection
        title=""
        :items="method.protocols || []"
        :default-show="3"
        item-type="protocol"
        fallback-msg="Protocols are being documented for this method."
        fallback-link="/protocols"
        fallback-link-text="Browse all protocols"
      >
        <template #item="{ item }">
          <router-link :to="`/protocols/${item.id}`" class="link-card">
            <div class="card-icon icon-protocol">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <div class="card-body">
              <h3 class="card-name">{{ item.name }}</h3>
              <span v-if="item.version" class="card-meta">v{{ item.version }}</span>
            </div>
            <span class="card-arrow">&rarr;</span>
          </router-link>
        </template>
      </ExpandableSection>
    </section>

    <!-- Products -->
    <section class="detail-section">
      <h2 class="section-title">Products</h2>
      <ExpandableSection
        title=""
        :items="method.products || []"
        :default-show="3"
        item-type="product"
        fallback-msg="Product associations are being mapped for this method."
        fallback-link="/products"
        fallback-link-text="Browse all products"
      >
        <template #item="{ item }">
          <router-link :to="`/products/${item.id}`" class="link-card">
            <div class="card-icon icon-product">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
            </div>
            <div class="card-body">
              <h3 class="card-name">{{ item.name }}</h3>
              <span v-if="item.catalog_no" class="card-meta">{{ item.catalog_no }}</span>
            </div>
            <span class="card-arrow">&rarr;</span>
          </router-link>
        </template>
      </ExpandableSection>
    </section>

    <!-- Research Path Card -->
    <ResearchPathCard v-if="researchPath.length > 1" :path="researchPath" current-type="method" />

    <!-- Unified CTA -->
    <UnifiedCTA
      title="Ready to use this method?"
      subtitle="Find protocols and reagents, or request a custom quote."
      :show-rfq="true"
      :show-explore="true"
    />
  </div>

  <LoadingSpinner v-else-if="store.loading" text="Loading..." />
  <div v-else class="empty">Method not found</div>
</template>

<style scoped>
.detail-page { max-width: var(--content-max-width); margin: 0 auto; padding: 24px; }
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 16px; }
.breadcrumb a { color: var(--color-primary); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.sep { color: var(--color-text-tertiary); }
.cur { color: var(--color-text-secondary); }
.detail-hero { margin-bottom: 24px; }
.detail-title { font-size: 28px; font-weight: 800; color: var(--color-text); margin: 0 0 8px; }
.detail-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; text-transform: capitalize; background: var(--color-bg); color: var(--color-text-secondary); border: 1px solid var(--color-border-light); }
.detail-badge::before { content: ''; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: #9CA3AF; }
.badge-active::before { background: #22C55E; }
.badge-draft::before { background: #F59E0B; }
.detail-summary { font-size: 15px; color: var(--color-text-secondary); line-height: 1.6; margin: 10px 0 0; }
.detail-purpose { font-size: 14px; color: var(--color-text); margin: 8px 0 0; }
.specs-row { display: flex; gap: 24px; margin-bottom: 24px; }
.spec { display: flex; flex-direction: column; gap: 2px; }
.spec-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-tertiary); }
.spec-val { font-size: 14px; font-weight: 500; color: var(--color-text); }
.detail-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
.detail-col { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 16px; }
.col-title { font-size: 14px; font-weight: 700; margin: 0 0 8px; color: var(--color-text); }
.col-text { font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; margin: 0; }
.detail-section { margin-bottom: 28px; }
.section-title { font-size: 16px; font-weight: 700; color: var(--color-text); margin: 0 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--color-primary); display: inline-block; }
.card-grid { display: flex; flex-direction: column; gap: 8px; }
.link-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); text-decoration: none; color: var(--color-text); transition: all 0.15s; }
.link-card:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }
.card-icon { width: 36px; height: 36px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.icon-protocol { background: #F5F0E0; color: #C9A34E; }
.icon-product { background: #F5E8E8; color: #D47C7C; }
.card-body { flex: 1; min-width: 0; }
.card-name { font-size: 14px; font-weight: 600; margin: 0; }
.card-meta { font-size: 12px; color: var(--color-text-secondary); font-family: var(--font-mono); }
.card-arrow { font-size: 16px; color: var(--color-text-tertiary); }
.fallback { padding: 16px; background: var(--color-bg); border: 1px dashed var(--color-border); border-radius: var(--radius-md); text-align: center; }
.fallback p { font-size: 13px; color: var(--color-text-secondary); margin: 0 0 6px; }
.fallback-link { font-size: 13px; color: var(--color-primary); text-decoration: none; font-weight: 500; }
.fallback-link:hover { text-decoration: underline; }
.loading, .empty { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
@media (max-width: 768px) { .detail-columns { grid-template-columns: 1fr; } }
</style>
