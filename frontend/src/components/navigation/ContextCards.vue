<script setup>
/**
 * ContextCards — Upstream and downstream entity links.
 * Shown at the top of each detail page.
 *
 * Props:
 *   - upstream: Array of { type, id, name, slug }
 *   - downstream: Array of { type, id, name, slug, catalog_no? }
 *   - fallbackMessage: Message when downstream is empty
 */
import { useRouter } from 'vue-router'

const props = defineProps({
  upstream: { type: Array, default: () => [] },
  downstream: { type: Array, default: () => [] },
  downstreamLabel: { type: String, default: 'Explore Next' },
  fallbackMessage: { type: String, default: '' },
  requestSupportLink: { type: Boolean, default: false },
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

function goTo(item) {
  const routeFn = TYPE_ROUTES[item.type]
  if (routeFn && item.id) router.push(routeFn(item.id))
}

function requestSupport() {
  router.push({ path: '/quote-request', query: { note: 'Protocol support requested' } })
}
</script>

<template>
  <div class="ctx">
    <!-- Upstream -->
    <div class="ctx-section" v-if="upstream.length">
      <span class="ctx-label">Part of</span>
      <div class="ctx-chips">
        <button
          v-for="item in upstream"
          :key="item.type + item.id"
          class="ctx-chip"
          :style="{ '--chip-color': TYPE_COLORS[item.type] || '#64748b' }"
          @click="goTo(item)"
        >
          <span class="ctx-chip-dot"></span>
          {{ item.name }}
        </button>
      </div>
    </div>

    <!-- Downstream -->
    <div class="ctx-section" v-if="downstream.length">
      <span class="ctx-label">{{ downstreamLabel }}</span>
      <div class="ctx-chips">
        <button
          v-for="item in downstream"
          :key="item.type + item.id"
          class="ctx-chip"
          :style="{ '--chip-color': TYPE_COLORS[item.type] || '#64748b' }"
          @click="goTo(item)"
        >
          <span class="ctx-chip-dot"></span>
          {{ item.name }}
          <span v-if="item.catalog_no" class="ctx-chip-meta">{{ item.catalog_no }}</span>
        </button>
      </div>
    </div>

    <!-- Fallback when downstream is empty -->
    <div class="ctx-section" v-else-if="fallbackMessage || requestSupportLink">
      <span class="ctx-label">{{ downstreamLabel }}</span>
      <div class="ctx-fallback">
        <p v-if="fallbackMessage" class="ctx-fallback-text">{{ fallbackMessage }}</p>
        <button v-if="requestSupportLink" class="ctx-support-btn" @click="requestSupport">
          Request protocol support &rarr;
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ctx {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
}
.ctx-section { display: flex; flex-direction: column; gap: 6px; }
.ctx-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-tertiary, #94a3b8);
}
.ctx-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ctx-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text, #1e293b);
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
  transition: all 0.15s;
}
.ctx-chip:hover {
  border-color: var(--chip-color);
  background: var(--color-primary-subtle, #f0fdf4);
}
.ctx-chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--chip-color);
}
.ctx-chip-meta {
  font-size: 10px;
  color: var(--color-text-secondary, #64748b);
  font-family: var(--font-mono, monospace);
}
.ctx-fallback {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ctx-fallback-text {
  font-size: 13px;
  color: var(--color-text-secondary, #64748b);
  margin: 0;
}
.ctx-support-btn {
  padding: 4px 12px;
  background: transparent;
  border: 1px dashed var(--color-primary, #0f766e);
  border-radius: var(--radius-md, 8px);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary, #0f766e);
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
}
.ctx-support-btn:hover { background: var(--color-primary-subtle, #f0fdf4); }
</style>
