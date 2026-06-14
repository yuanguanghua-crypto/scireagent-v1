<script setup>
/**
 * ResearchBreadcrumb — Shows research path instead of catalog categories.
 * Replaces the standard catalog breadcrumb with entity-level navigation.
 *
 * Props:
 *   - items: Array of { type, id, name }
 *   - currentName: Name of the current page (last item)
 */
import { useRouter } from 'vue-router'

const props = defineProps({
  items: { type: Array, default: () => [] },
  currentName: { type: String, default: '' },
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
  const routeFn = TYPE_ROUTES[item.type]
  if (routeFn && item.id) router.push(routeFn(item.id))
}
</script>

<template>
  <nav class="rb" aria-label="Research path">
    <router-link to="/" class="rb-home">Home</router-link>
    <template v-for="(item, idx) in items" :key="item.type + item.id">
      <span class="rb-sep">/</span>
      <button class="rb-link" @click="goTo(item)">{{ item.name }}</button>
    </template>
    <span v-if="currentName" class="rb-sep">/</span>
    <span v-if="currentName" class="rb-current">{{ currentName }}</span>
  </nav>
</template>

<style scoped>
.rb {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.rb-home {
  color: var(--color-primary, #0f766e);
  text-decoration: none;
}
.rb-home:hover { text-decoration: underline; }
.rb-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--color-primary, #0f766e);
  font-size: 13px;
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
}
.rb-link:hover { text-decoration: underline; }
.rb-sep { color: var(--color-text-tertiary, #94a3b8); margin: 0 2px; }
.rb-current {
  color: var(--color-text-secondary, #64748b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 250px;
}
</style>
