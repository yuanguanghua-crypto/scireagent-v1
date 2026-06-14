<script setup>
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProtocolsStore } from '@/stores/protocols'
import { formatDate, getStatusType } from '@/utils/helpers'
import ContextCards from '@/components/navigation/ContextCards.vue'
import ResearchPathCard from '@/components/navigation/ResearchPathCard.vue'
import UnifiedCTA from '@/components/navigation/UnifiedCTA.vue'
import ResearchBreadcrumb from '@/components/navigation/ResearchBreadcrumb.vue'
import ResearchPathChips from '@/components/navigation/ResearchPathChips.vue'

const route = useRoute()
const router = useRouter()
const store = useProtocolsStore()
const activeTab = ref('steps')

const protocol = computed(() => store.currentProtocol)

/* ── Navigation data ── */
const upstreamEntities = computed(() => {
  const items = []
  if (protocol.value?.method_id) {
    items.push({ type: 'method', id: protocol.value.method_id, name: protocol.value.method_name || 'Method' })
  }
  return items
})
const downstreamEntities = computed(() => {
  return (protocol.value?.products || []).map(p => ({ type: 'product', id: p.id, name: p.name, catalog_no: p.catalog_no }))
})
const researchPath = computed(() => {
  const path = []
  if (protocol.value?.research_goal_id) {
    path.push({ type: 'research_goal', id: protocol.value.research_goal_id, name: 'Research Goal' })
  }
  if (protocol.value?.application_id) {
    path.push({ type: 'application', id: protocol.value.application_id, name: protocol.value.application_name || 'Application' })
  }
  if (protocol.value?.method_id) {
    path.push({ type: 'method', id: protocol.value.method_id, name: protocol.value.method_name || 'Method' })
  }
  if (protocol.value) path.push({ type: 'protocol', id: protocol.value.id, name: protocol.value.name })
  return path
})

async function loadProtocol(id) {
  await store.fetchProtocol(id)
}

onMounted(() => loadProtocol(route.params.id))
watch(() => route.params.id, (newId) => { if (newId) loadProtocol(newId) })
onUnmounted(() => { store.clearCurrent() })

/**
 * Format duration in seconds to a human-readable string.
 * @param {number} seconds - Duration in seconds.
 * @returns {string} Formatted duration string.
 */
function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}
</script>

<template>
  <div class="protocol-detail">
    <div v-if="store.loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <template v-else-if="store.currentProtocol">
      <!-- Research Breadcrumb + Path Chips (P1) -->
      <ResearchBreadcrumb :items="researchPath.slice(0, -1)" :current-name="protocol.name" />
      <ResearchPathChips :path="researchPath" current-type="protocol" />

      <!-- Context Cards -->
      <ContextCards
        :upstream="upstreamEntities"
        :downstream="downstreamEntities"
        downstream-label="Required Products"
        fallback-message="Product requirements are being documented."
        :request-support-link="!downstreamEntities.length"
      />

      <!-- Header -->
      <div class="detail-header">
        <div class="header-left">
          <h1 class="detail-title">{{ store.currentProtocol.name }}</h1>
          <el-tag size="small" class="version-tag">v{{ store.currentProtocol.version }}</el-tag>
          <el-tag :type="getStatusType(store.currentProtocol.status)" size="small">
            {{ store.currentProtocol.status }}
          </el-tag>
        </div>
        <span class="detail-meta">Method ID: {{ store.currentProtocol.method_id }}</span>
      </div>

      <!-- Objective & Principle -->
      <section class="detail-section">
        <h2 class="section-title">Objective</h2>
        <p class="section-content">{{ store.currentProtocol.objective || 'No objective specified.' }}</p>
      </section>

      <section v-if="store.currentProtocol.principle" class="detail-section">
        <h2 class="section-title">Principle</h2>
        <p class="section-content">{{ store.currentProtocol.principle }}</p>
      </section>

      <!-- Tabs -->
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- Steps Tab -->
        <el-tab-pane label="Steps" name="steps">
          <div v-if="store.currentProtocol.steps?.length" class="steps-container">
            <el-timeline>
              <el-timeline-item
                v-for="step in store.currentProtocol.steps"
                :key="step.id"
                :timestamp="`Step ${step.step_no}`"
                placement="top"
                :type="step.warnings ? 'warning' : 'primary'"
              >
                <el-card shadow="never" class="step-card">
                  <div class="step-header">
                    <h3 class="step-title">{{ step.title }}</h3>
                    <el-tag v-if="step.duration_seconds" size="small" type="info">
                      {{ formatDuration(step.duration_seconds) }}
                    </el-tag>
                  </div>
                  <p class="step-body">{{ step.body }}</p>
                  <el-alert
                    v-if="step.warnings"
                    :title="step.warnings"
                    type="warning"
                    :closable="false"
                    show-icon
                    class="step-warning"
                  />
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
          <el-empty v-else description="No steps defined yet" />
        </el-tab-pane>

        <!-- Materials Tab -->
        <el-tab-pane label="Materials" name="materials">
          <div class="two-column">
            <section class="detail-section">
              <h2 class="section-title">Materials</h2>
              <p class="section-content pre-wrap">{{ store.currentProtocol.materials || 'N/A' }}</p>
            </section>
            <section class="detail-section">
              <h2 class="section-title">Equipment</h2>
              <p class="section-content pre-wrap">{{ store.currentProtocol.equipment || 'N/A' }}</p>
            </section>
          </div>
          <section class="detail-section">
            <h2 class="section-title">Reagents</h2>
            <p class="section-content pre-wrap">{{ store.currentProtocol.reagents || 'N/A' }}</p>
          </section>
        </el-tab-pane>

        <!-- Troubleshooting Tab -->
        <el-tab-pane label="Troubleshooting" name="troubleshooting">
          <section v-if="store.currentProtocol.troubleshooting" class="detail-section">
            <p class="section-content pre-wrap">{{ store.currentProtocol.troubleshooting }}</p>
          </section>
          <el-empty v-else description="No troubleshooting information" />
        </el-tab-pane>

        <!-- Expected Results Tab -->
        <el-tab-pane label="Expected Results" name="results">
          <section v-if="store.currentProtocol.expected_results" class="detail-section">
            <p class="section-content pre-wrap">{{ store.currentProtocol.expected_results }}</p>
          </section>
          <el-empty v-else description="No expected results specified" />
        </el-tab-pane>

        <!-- References Tab -->
        <el-tab-pane label="References" name="references">
          <div v-if="store.currentProtocol.references?.length" class="refs-list">
            <div v-for="ref in store.currentProtocol.references" :key="ref.id" class="ref-item">
              <div class="ref-body">
                <h4 class="ref-title">{{ ref.title }}</h4>
                <div class="ref-meta">
                  <span v-if="ref.journal" class="ref-journal">{{ ref.journal }}</span>
                  <span v-if="ref.year">{{ ref.year }}</span>
                </div>
              </div>
              <a v-if="ref.doi" :href="`https://doi.org/${ref.doi}`" target="_blank" rel="noopener" class="ref-doi">DOI &rarr;</a>
            </div>
          </div>
          <el-empty v-else description="No references linked" />
        </el-tab-pane>

        <!-- Products Tab -->
        <el-tab-pane label="Products" name="products">
          <div v-if="store.currentProtocol.products?.length" class="card-grid">
            <router-link v-for="p in store.currentProtocol.products" :key="p.id" :to="`/products/${p.id}`" class="link-card">
              <div class="card-icon icon-product">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
              </div>
              <div class="card-body">
                <h3 class="card-name">{{ p.name }}</h3>
                <span v-if="p.catalog_no" class="card-meta">{{ p.catalog_no }}</span>
              </div>
              <span class="card-arrow">&rarr;</span>
            </router-link>
          </div>
          <el-empty v-else description="No products linked" />
        </el-tab-pane>
      </el-tabs>

      <!-- Research Path Card -->
      <ResearchPathCard v-if="researchPath.length > 1" :path="researchPath" current-type="protocol" />

      <!-- Unified CTA -->
      <UnifiedCTA
        title="Ready to run this protocol?"
        subtitle="Get all required reagents or request a custom quote."
        :show-rfq="true"
        :show-explore="true"
      />
    </template>

    <div v-else class="empty-container">
      <el-empty description="Protocol not found">
        <el-button @click="router.push('/protocols')">Back to Protocols</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.detail-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin: 20px 0 24px 0;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.detail-title { font-size: 28px; font-weight: 700; color: var(--color-text); margin: 0; }
.version-tag { font-family: var(--font-mono); }
.detail-meta { font-size: 13px; color: var(--color-text-secondary); }
.detail-tabs { margin-top: 8px; }
.detail-section { margin-bottom: 24px; }
.section-title { font-size: 18px; font-weight: 600; color: var(--color-text); margin: 0 0 8px 0; border-bottom: 1px solid var(--color-border); padding-bottom: 6px; }
.section-content { font-size: 15px; line-height: 1.6; color: var(--color-text); }
.pre-wrap { white-space: pre-wrap; }
.two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.steps-container { padding: 8px 0; }
.step-card { margin-bottom: 0; }
.step-header { display: flex; justify-content: space-between; align-items: center; }
.step-title { font-size: 16px; font-weight: 600; color: var(--color-text); margin: 0; }
.step-body { font-size: 14px; line-height: 1.6; color: var(--color-text); margin: 8px 0; }
.step-warning { margin-top: 8px; }
.info-text { color: var(--color-text-secondary); font-size: 14px; margin-bottom: 12px; }

/* References */
.refs-list { display: flex; flex-direction: column; gap: 8px; }
.ref-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 10px 14px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.ref-body { flex: 1; min-width: 0; }
.ref-title { font-size: 13px; font-weight: 600; margin: 0 0 4px; color: var(--color-text); line-height: 1.4; }
.ref-meta { display: flex; gap: 8px; font-size: 12px; color: var(--color-text-secondary); }
.ref-journal { font-style: italic; }
.ref-doi { font-size: 12px; color: var(--color-primary); text-decoration: none; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.ref-doi:hover { text-decoration: underline; }

/* Card grid */
.card-grid { display: flex; flex-direction: column; gap: 8px; }
.link-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); text-decoration: none; color: var(--color-text); transition: all 0.15s; }
.link-card:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }
.card-icon { width: 36px; height: 36px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.icon-product { background: #fef2f2; color: #dc2626; }
.card-body { flex: 1; min-width: 0; }
.card-name { font-size: 14px; font-weight: 600; margin: 0; }
.card-meta { font-size: 12px; color: var(--color-text-secondary); font-family: var(--font-mono); }
.card-arrow { font-size: 16px; color: var(--color-text-tertiary); }
.loading-container, .empty-container { padding: 60px 0; text-align: center; }
</style>
