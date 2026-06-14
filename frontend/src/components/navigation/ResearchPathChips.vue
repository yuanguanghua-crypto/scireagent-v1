<script setup>
/**
 * ResearchPathChips — Lightweight clickable path indicator.
 * Shows the research path as compact chips at the top of the page.
 * Less prominent than ResearchPathCard (sidebar), more than Breadcrumb.
 *
 * Props:
 *   - path: Array of { type, id, name }
 *   - currentType: Entity type of current page
 */
import { useRouter } from 'vue-router'

const props = defineProps({
  path: { type: Array, default: () => [] },
  currentType: { type: String, default: '' },
})

const router = useRouter()

const TYPE_ROUTES = {
  research_goal: (id) => `/research-goals/${id}`,
  application: (id) => `/applications/${id}`,
  method: (id) => `/methods/${id}`,
  protocol: (id) => `/protocols/${id}`,
  product: (id) => `/products/${id}`,
}

function goTo(item) {
  if (item.type === props.currentType) return
  const routeFn = TYPE_ROUTES[item.type]
  if (routeFn && item.id) router.push(routeFn(item.id))
}
</script>

<template>
  <div class="rpc-bar" v-if="path.length > 1" aria-label="Research path">
    <span class="rpc-label">Path:</span>
    <template v-for="(item, idx) in path" :key="item.type + item.id">
      <button
        class="rpc-chip"
        :class="{ 'rpc-active': item.type === currentType }"
        @click="goTo(item)"
      >
        {{ item.name }}
      </button>
      <span v-if="idx < path.length - 1" class="rpc-sep">&rsaquo;</span>
    </template>
  </div>
</template>

<style scoped>
.rpc-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--color-bg, #f8fafc);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-md, 8px);
}
.rpc-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-tertiary, #94a3b8);
  margin-right: 4px;
}
.rpc-chip {
  padding: 2px 8px;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary, #0f766e);
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
  transition: all 0.15s;
}
.rpc-chip:hover {
  background: var(--color-primary-subtle, #f0fdf4);
  border-color: var(--color-primary, #0f766e);
}
.rpc-active {
  background: var(--color-primary-light, #ecfdf5);
  border-color: var(--color-primary, #0f766e);
  color: var(--color-text, #1e293b);
  font-weight: 600;
  cursor: default;
}
.rpc-sep {
  font-size: 14px;
  color: var(--color-text-tertiary, #94a3b8);
}
</style>
