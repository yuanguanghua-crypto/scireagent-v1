<script setup>
/**
 * ResearchPathCard — Shows the full research path from Research Goal to SKU.
 * Used as a sidebar component on product and protocol detail pages.
 *
 * Props:
 *   - path: Array of { type, id, name, slug, count? }
 *   - currentType: The entity type of the current page
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  path: { type: Array, default: () => [] },
  currentType: { type: String, default: '' },
})

const router = useRouter()

const TYPE_LABELS = {
  research_goal: 'Research Goal',
  application: 'Application',
  method: 'Method',
  protocol: 'Protocol',
  product: 'Product',
  sku: 'SKU',
}

const TYPE_COLORS = {
  research_goal: '#db2777',
  application: '#059669',
  method: '#2563eb',
  protocol: '#d97706',
  product: '#dc2626',
  sku: '#78716c',
}

const TYPE_ROUTES = {
  research_goal: (id) => `/research-goals/${id}`,
  application: (id) => `/applications/${id}`,
  method: (id) => `/methods/${id}`,
  protocol: (id) => `/protocols/${id}`,
  product: (id) => `/products/${id}`,
  sku: null,
}

function goTo(item) {
  if (item.type === props.currentType) return
  const routeFn = TYPE_ROUTES[item.type]
  if (routeFn && item.id) router.push(routeFn(item.id))
}

const hasPath = computed(() => props.path.length > 0)
</script>

<template>
  <aside class="rpc" v-if="hasPath" aria-label="Research Path">
    <h3 class="rpc-title">Research Context</h3>
    <div class="rpc-chain">
      <template v-for="(item, idx) in path" :key="item.type + item.id">
        <div
          class="rpc-node"
          :class="{ 'rpc-current': item.type === currentType, 'rpc-clickable': item.type !== currentType }"
          :style="{ '--node-color': TYPE_COLORS[item.type] || '#64748b' }"
          @click="goTo(item)"
        >
          <span class="rpc-dot"></span>
          <div class="rpc-info">
            <span class="rpc-type">{{ TYPE_LABELS[item.type] || item.type }}</span>
            <span class="rpc-name">{{ item.name }}</span>
            <span v-if="item.count !== undefined" class="rpc-count">{{ item.count }} linked</span>
          </div>
          <span v-if="item.type !== currentType" class="rpc-arrow">&rarr;</span>
        </div>
        <div v-if="idx < path.length - 1" class="rpc-connector"></div>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.rpc {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-lg, 12px);
  padding: 16px;
}
.rpc-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-secondary, #64748b);
  margin: 0 0 12px;
}
.rpc-chain { display: flex; flex-direction: column; }
.rpc-node {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-md, 8px);
  transition: all 0.15s;
}
.rpc-clickable { cursor: pointer; }
.rpc-clickable:hover { background: var(--color-primary-subtle, #f0fdf4); }
.rpc-current {
  background: var(--color-primary-light, #ecfdf5);
  border-left: 3px solid var(--node-color);
}
.rpc-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--node-color);
  flex-shrink: 0;
}
.rpc-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.rpc-type { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-tertiary, #94a3b8); }
.rpc-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text, #1e293b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rpc-count { font-size: 11px; color: var(--color-text-secondary, #64748b); }
.rpc-arrow { font-size: 14px; color: var(--color-text-tertiary, #94a3b8); flex-shrink: 0; }
.rpc-connector {
  width: 2px;
  height: 12px;
  background: var(--color-border, #e2e8f0);
  margin-left: 14px;
}
</style>
