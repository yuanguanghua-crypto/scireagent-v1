<script setup>
/**
 * RelationshipWidget — Shows related entities grouped by type.
 * "People researching X also viewed" style component.
 *
 * Props:
 *   - title: Widget heading
 *   - groups: Array of { type, label, items: [{ id, name, slug?, catalog_no? }] }
 */
import { useRouter } from 'vue-router'

const props = defineProps({
  title: { type: String, default: 'Related by Research' },
  groups: { type: Array, default: () => [] },
})

const router = useRouter()

const TYPE_ROUTES = {
  research_goal: (id) => `/research-goals/${id}`,
  application: (id) => `/applications/${id}`,
  method: (id) => `/methods/${id}`,
  protocol: (id) => `/protocols/${id}`,
  product: (id) => `/products/${id}`,
}

const TYPE_COLORS = {
  research_goal: '#db2777',
  application: '#059669',
  method: '#2563eb',
  protocol: '#d97706',
  product: '#dc2626',
}

function goTo(type, id) {
  const routeFn = TYPE_ROUTES[type]
  if (routeFn && id) router.push(routeFn(id))
}

const hasContent = props.groups.some(g => g.items?.length > 0)
</script>

<template>
  <section class="rw" v-if="hasContent" :aria-label="title">
    <h3 class="rw-title">{{ title }}</h3>
    <div class="rw-grid">
      <div v-for="group in groups" :key="group.type" class="rw-group" v-show="group.items?.length">
        <span class="rw-group-label" :style="{ color: TYPE_COLORS[group.type] || '#64748b' }">
          {{ group.label }}
        </span>
        <div class="rw-items">
          <button
            v-for="item in group.items"
            :key="item.id"
            class="rw-item"
            @click="goTo(group.type, item.id)"
          >
            <span class="rw-dot" :style="{ background: TYPE_COLORS[group.type] || '#64748b' }"></span>
            <span class="rw-name">{{ item.name }}</span>
            <span v-if="item.catalog_no" class="rw-meta">{{ item.catalog_no }}</span>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.rw {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: var(--radius-lg, 12px);
  padding: 16px;
  margin-bottom: 24px;
}
.rw-title {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary, #64748b);
  margin: 0 0 12px;
}
.rw-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}
.rw-group { display: flex; flex-direction: column; gap: 6px; }
.rw-group-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.rw-items { display: flex; flex-direction: column; gap: 4px; }
.rw-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: none;
  border: none;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
  transition: background 0.15s;
  text-align: left;
}
.rw-item:hover { background: var(--color-primary-subtle, #f0fdf4); }
.rw-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.rw-name { font-size: 13px; color: var(--color-text, #1e293b); font-weight: 500; }
.rw-meta { font-size: 10px; color: var(--color-text-secondary, #64748b); font-family: var(--font-mono, monospace); }
</style>
