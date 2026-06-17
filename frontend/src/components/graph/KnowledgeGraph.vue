<script setup>
/**
 * KnowledgeGraph.vue — Interactive Cytoscape.js graph component.
 *
 * Props:
 *   - nodes: Array of { id, type, label, slug }
 *   - edges: Array of { id, source, target, relationship }
 *   - height: Container height (default '400px')
 *   - layout: Cytoscape layout name (default 'cose')
 */
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'

// Lazy load Cytoscape to reduce main bundle size
let cytoscape = null
async function loadCytoscape() {
  if (!cytoscape) {
    const mod = await import('cytoscape')
    cytoscape = mod.default || mod
  }
  return cytoscape
}

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  height: { type: String, default: '400px' },
  layout: { type: String, default: 'cose' },
})

const router = useRouter()
const containerRef = ref(null)
let cyInstance = null

// Color scheme per entity type
const TYPE_COLORS = {
  product: { bg: '#fef2f2', border: '#dc2626', text: '#991b1b' },
  application: { bg: '#ecfdf5', border: '#059669', text: '#065f46' },
  method: { bg: '#eff6ff', border: '#2563eb', text: '#1e40af' },
  protocol: { bg: '#fffbeb', border: '#d97706', text: '#92400e' },
  reference: { bg: '#f5f3ff', border: '#7c3aed', text: '#5b21b6' },
  research_goal: { bg: '#fdf2f8', border: '#db2777', text: '#9d174d' },
  sku: { bg: '#f5f5f4', border: '#78716c', text: '#44403c' },
}

// Route map for click navigation
const TYPE_ROUTES = {
  product: (id) => `/products/${id}`,
  application: (id) => `/applications/${id}`,
  method: (id) => `/methods/${id}`,
  protocol: (id) => `/protocols/${id}`,
  reference: null,
  research_goal: (id) => `/research-goals/${id}`,
}

function getNodeIdParts(nodeId) {
  // nodeId format: "type_id" e.g. "product_42"
  const idx = nodeId.indexOf('_')
  if (idx === -1) return { type: nodeId, id: null }
  return { type: nodeId.substring(0, idx), id: nodeId.substring(idx + 1) }
}

function buildCytoscapeElements() {
  const elements = []

  for (const node of props.nodes) {
    const colors = TYPE_COLORS[node.type] || TYPE_COLORS.product
    elements.push({
      group: 'nodes',
      data: {
        id: node.id,
        label: node.label,
        type: node.type,
        slug: node.slug || '',
        nodeColor: colors.bg,
        borderColor: colors.border,
        textColor: colors.text,
      },
    })
  }

  for (const edge of props.edges) {
    elements.push({
      group: 'edges',
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        relationship: edge.relationship,
      },
    })
  }

  return elements
}

function runLayout() {
  if (!cyInstance) return
  const layoutConfig = {
    name: props.layout,
    animate: true,
    animationDuration: 600,
    padding: 30,
    nodeRepulsion: () => 4000,
    idealEdgeLength: () => 100,
    edgeElasticity: () => 100,
    gravity: 0.25,
    numIter: 500,
    randomize: false,
  }
  cyInstance.layout(layoutConfig).run()
}

async function initCytoscape() {
  if (!containerRef.value) return
  if (cyInstance) {
    cyInstance.destroy()
    cyInstance = null
  }

  if (!props.nodes.length) return

  const cy = await loadCytoscape()
  cyInstance = cy({
    container: containerRef.value,
    elements: buildCytoscapeElements(),
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(nodeColor)',
          'border-color': 'data(borderColor)',
          'border-width': 2,
          'label': 'data(label)',
          'text-wrap': 'ellipsis',
          'text-max-width': '100px',
          'font-size': '11px',
          'font-family': 'Inter, system-ui, sans-serif',
          'color': 'data(textColor)',
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'width': 36,
          'height': 36,
          'cursor': 'pointer',
        },
      },
      {
        selector: 'node[type="product"]',
        style: { 'shape': 'round-rectangle' },
      },
      {
        selector: 'node[type="application"]',
        style: { 'shape': 'round-hexagon' },
      },
      {
        selector: 'node[type="method"]',
        style: { 'shape': 'round-diamond' },
      },
      {
        selector: 'node[type="protocol"]',
        style: { 'shape': 'round-triangle' },
      },
      {
        selector: 'node[type="reference"]',
        style: { 'shape': 'round-tag' },
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': '#cbd5e1',
          'target-arrow-color': '#cbd5e1',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(relationship)',
          'font-size': '9px',
          'color': '#94a3b8',
          'text-rotation': 'autorotate',
          'text-margin-y': -8,
        },
      },
    ],
    layout: { name: 'preset' }, // We'll run layout after
    userZoomingEnabled: true,
    userPanningEnabledEnabled: true,
    boxSelectionEnabled: false,
  })

  // Click handler — navigate to entity page
  cyInstance.on('tap', 'node', (evt) => {
    const data = evt.target.data()
    const parts = getNodeIdParts(data.id)
    const routeFn = TYPE_ROUTES[parts.type]
    if (routeFn && parts.id) {
      router.push(routeFn(parts.id))
    }
  })

  // Hover effect
  cyInstance.on('mouseover', 'node', (evt) => {
    evt.target.style('border-width', 3)
    containerRef.value.style.cursor = 'pointer'
  })
  cyInstance.on('mouseout', 'node', (evt) => {
    evt.target.style('border-width', 2)
    containerRef.value.style.cursor = 'default'
  })

  runLayout()
}

watch(() => [props.nodes, props.edges], () => {
  nextTick(() => initCytoscape())
}, { deep: true })

onMounted(() => {
  nextTick(() => initCytoscape())
})

onBeforeUnmount(() => {
  if (cyInstance) {
    cyInstance.destroy()
    cyInstance = null
  }
})

function fitGraph() {
  if (cyInstance) cyInstance.fit(undefined, 30)
}

function resetZoom() {
  if (cyInstance) {
    cyInstance.zoom(1)
    cyInstance.center()
  }
}
</script>

<template>
  <div class="kg-wrapper">
    <div v-if="!nodes.length" class="kg-empty">
      <p>No graph data available.</p>
    </div>
    <div v-else class="kg-inner">
      <div class="kg-toolbar">
        <button class="kg-btn" @click="fitGraph" title="Fit to screen">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="kg-btn" @click="resetZoom" title="Reset zoom">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="5.5" stroke="currentColor" stroke-width="1.5"/><path d="M8 5v6M5 8h6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
      </div>
      <div ref="containerRef" class="kg-canvas" :style="{ height }" />
      <div class="kg-legend">
        <span v-for="(colors, type) in TYPE_COLORS" :key="type" class="kg-legend-item">
          <span class="kg-legend-dot" :style="{ background: colors.border }" />
          {{ type.replace('_', ' ') }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kg-wrapper {
  position: relative;
}
.kg-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: var(--color-text-secondary, #94a3b8);
  font-size: 14px;
}
.kg-inner {
  position: relative;
}
.kg-toolbar {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
  display: flex;
  gap: 4px;
}
.kg-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  cursor: pointer;
  color: var(--color-text-secondary, #64748b);
  transition: all 0.15s;
}
.kg-btn:hover {
  background: var(--color-primary, #0f766e);
  color: #fff;
  border-color: var(--color-primary, #0f766e);
}
.kg-canvas {
  width: 100%;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-lg, 12px);
  background: var(--color-surface, #fff);
}
.kg-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  padding: 0 4px;
}
.kg-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-text-secondary, #64748b);
  text-transform: capitalize;
}
.kg-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>
