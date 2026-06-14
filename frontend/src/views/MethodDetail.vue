<script setup>
import { onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMethodsStore } from '@/stores/methods'
import { useGraph } from '@/composables/useGraph'
import KnowledgeGraph from '@/components/graph/KnowledgeGraph.vue'

const route = useRoute()
const router = useRouter()
const store = useMethodsStore()

const method = computed(() => store.currentMethod)
const methodId = computed(() => route.params.id)

const { nodes: graphNodes, edges: graphEdges, fetch: fetchGraph } = useGraph('method', methodId, { depth: 2, maxNodes: 25, maxEdges: 40 })

async function loadMethod(id) {
  await store.fetchMethod(id)
  fetchGraph()
}

onMounted(() => loadMethod(route.params.id))
watch(() => route.params.id, (newId) => { if (newId) loadMethod(newId) })
onUnmounted(() => { store.clearCurrent() })
</script>

<template>
  <div class="detail-page" v-if="method">
    <nav class="breadcrumb">
      <router-link to="/methods">Methods</router-link>
      <span class="sep">/</span>
      <span class="cur">{{ method.name }}</span>
    </nav>

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
    <section class="detail-section" v-if="method.protocols?.length">
      <h2 class="section-title">Protocols</h2>
      <div class="card-grid">
        <router-link v-for="p in method.protocols" :key="p.id" :to="`/protocols/${p.id}`" class="link-card">
          <div class="card-icon icon-protocol">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div class="card-body">
            <h3 class="card-name">{{ p.name }}</h3>
            <span v-if="p.version" class="card-meta">v{{ p.version }}</span>
          </div>
          <span class="card-arrow">&rarr;</span>
        </router-link>
      </div>
    </section>

    <!-- Products -->
    <section class="detail-section" v-if="method.products?.length">
      <h2 class="section-title">Products</h2>
      <div class="card-grid">
        <router-link v-for="p in method.products" :key="p.id" :to="`/products/${p.id}`" class="link-card">
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
    </section>

    <!-- Knowledge Graph -->
    <section class="detail-section" v-if="graphNodes.length">
      <h2 class="section-title">Knowledge Graph</h2>
      <div class="kg-wrap">
        <KnowledgeGraph :nodes="graphNodes" :edges="graphEdges" height="320px" />
      </div>
    </section>
  </div>

  <div v-else-if="store.loading" class="loading">Loading...</div>
  <div v-else class="empty">Method not found</div>
</template>

<style scoped>
.detail-page { max-width: 1200px; margin: 0 auto; padding: 24px; }
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 16px; }
.breadcrumb a { color: var(--color-primary); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.sep { color: var(--color-text-tertiary); }
.cur { color: var(--color-text-secondary); }
.detail-hero { margin-bottom: 24px; }
.detail-title { font-size: 28px; font-weight: 800; color: var(--color-text); margin: 0 0 8px; }
.detail-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; text-transform: capitalize; }
.badge-active { background: #ecfdf5; color: #059669; }
.badge-draft { background: #fffbeb; color: #d97706; }
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
.icon-protocol { background: #fffbeb; color: #d97706; }
.icon-product { background: #fef2f2; color: #dc2626; }
.card-body { flex: 1; min-width: 0; }
.card-name { font-size: 14px; font-weight: 600; margin: 0; }
.card-meta { font-size: 12px; color: var(--color-text-secondary); font-family: var(--font-mono); }
.card-arrow { font-size: 16px; color: var(--color-text-tertiary); }
.kg-wrap { border: 1px solid var(--color-border); border-radius: var(--radius-lg); overflow: hidden; }
.loading, .empty { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }

@media (max-width: 768px) { .detail-columns { grid-template-columns: 1fr; } }
</style>
