<script setup>
/**
 * KnowledgeGraphPreview — Homepage interactive graph.
 * Uses graph_preview data from the homepage API (pre-loaded by HomePage.vue).
 * Falls back to static SVG if no graph data available.
 */
import { ref, onMounted, computed, defineAsyncComponent } from 'vue'

const KnowledgeGraph = defineAsyncComponent(() =>
  import('@/components/graph/KnowledgeGraph.vue')
)

const props = defineProps({
  graphData: { type: Object, default: null },
})

const hasGraph = computed(() =>
  props.graphData && props.graphData.nodes && props.graphData.nodes.length > 0
)
</script>

<template>
  <section class="section" aria-label="Knowledge Graph Preview">
    <div class="section-header">
      <h2 class="section-title">Knowledge Graph</h2>
      <router-link to="/applications" class="section-link">Explore &rarr;</router-link>
    </div>

    <!-- Interactive graph from API -->
    <div v-if="hasGraph" class="graph-container">
      <Suspense>
        <KnowledgeGraph
          :nodes="graphData.nodes"
          :edges="graphData.edges"
          height="350px"
          layout="cose"
        />
        <template #fallback>
          <div class="graph-loading">Loading graph...</div>
        </template>
      </Suspense>
      <p class="graph-caption">Interactive knowledge graph — click nodes to explore</p>
    </div>

    <!-- Fallback: static SVG when no API data -->
    <div v-else class="graph-container">
      <svg viewBox="0 0 680 200" width="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Knowledge graph showing entity relationships">
        <g>
          <rect x="20" y="70" width="120" height="60" rx="8" fill="#e1f5ee" stroke="#0f766e" stroke-width="1.5"/>
          <text x="80" y="95" text-anchor="middle" font-family="Inter, sans-serif" font-size="13" font-weight="600" fill="#0f766e">Application</text>
          <text x="80" y="115" text-anchor="middle" font-family="Inter, sans-serif" font-size="11" fill="#64748b">RNA Labeling</text>
        </g>
        <line x1="140" y1="100" x2="190" y2="100" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrowhead)"/>
        <g>
          <rect x="190" y="70" width="120" height="60" rx="8" fill="#e6f1fb" stroke="#185fa5" stroke-width="1.5"/>
          <text x="250" y="95" text-anchor="middle" font-family="Inter, sans-serif" font-size="13" font-weight="600" fill="#185fa5">Method</text>
          <text x="250" y="115" text-anchor="middle" font-family="Inter, sans-serif" font-size="11" fill="#64748b">CuAAC</text>
        </g>
        <line x1="310" y1="100" x2="360" y2="100" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrowhead)"/>
        <g>
          <rect x="360" y="70" width="120" height="60" rx="8" fill="#faeeda" stroke="#854f0b" stroke-width="1.5"/>
          <text x="420" y="95" text-anchor="middle" font-family="Inter, sans-serif" font-size="13" font-weight="600" fill="#854f0b">Protocol</text>
          <text x="420" y="115" text-anchor="middle" font-family="Inter, sans-serif" font-size="11" fill="#64748b">Click Labeling</text>
        </g>
        <line x1="480" y1="100" x2="530" y2="100" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrowhead)"/>
        <g>
          <rect x="530" y="70" width="130" height="60" rx="8" fill="#fcebeb" stroke="#993c1d" stroke-width="1.5"/>
          <text x="595" y="95" text-anchor="middle" font-family="Inter, sans-serif" font-size="13" font-weight="600" fill="#993c1d">Product</text>
          <text x="595" y="115" text-anchor="middle" font-family="Inter, sans-serif" font-size="11" fill="#64748b">2'-Azido-dATP</text>
        </g>
        <line x1="595" y1="130" x2="595" y2="160" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrowhead)"/>
        <g>
          <rect x="535" y="160" width="120" height="35" rx="6" fill="#f1efe8" stroke="#5f5e5a" stroke-width="1"/>
          <text x="595" y="182" text-anchor="middle" font-family="Inter, sans-serif" font-size="12" font-weight="500" fill="#444441">SKU: SC8047-1</text>
        </g>
        <defs>
          <marker id="arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M2 1L8 5L2 9" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </marker>
        </defs>
      </svg>
      <p class="graph-caption">Research Intent &rarr; Application &rarr; Method &rarr; Protocol &rarr; Product &rarr; SKU</p>
    </div>
  </section>
</template>

<style scoped>
.section { margin-bottom: 32px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}
.section-link {
  font-size: 14px;
  color: var(--color-primary, #0f766e);
  text-decoration: none;
  font-weight: 500;
}
.section-link:hover { text-decoration: underline; }
.graph-container {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 24px;
  text-align: center;
}
.graph-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: var(--color-text-secondary);
  font-size: 14px;
}
.graph-caption {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 12px 0 0;
}

@media (max-width: 768px) {
  .graph-container { overflow-x: auto; }
}
</style>
