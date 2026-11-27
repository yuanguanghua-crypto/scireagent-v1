<script setup>
/**
 * ResearchBreadcrumb — Shows research path instead of catalog categories.
 * Replaces the standard catalog breadcrumb with entity-level navigation.
 *
 * Props:
 *   - items: Array of { type, id, name }
 *   - currentName: Name of the current page (last item)
 */
import { computed } from 'vue'
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

/**
 * ★ 2026-11-27（A-117）：去掉**末级重复**。
 * 上级链里最后一个实体常常就是当前页自己（应用页 items 末尾是本应用、
 * 方法页末尾是本方法），于是面包屑出现 "Home / PCR / PCR"、
 * "… / Sequencing Library Preparation / Sequencing Library Preparation"（QA 实测两处）。
 * 处理：从尾部把 `name === currentName` 的条目去掉。
 */
const crumbItems = computed(() => {
  const list = [...(props.items || [])]
  const cur = (props.currentName || '').trim()
  while (list.length && cur && (list[list.length - 1].name || '').trim() === cur) {
    list.pop()
  }
  return list
})

function goTo(item) {
  const routeFn = TYPE_ROUTES[item.type]
  if (routeFn && item.id) router.push(routeFn(item.id))
}
</script>

<template>
  <nav class="rb" aria-label="Research path">
    <router-link to="/" class="rb-home">Home</router-link>
    <template v-for="(item, idx) in crumbItems" :key="item.type + item.id">
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
  height: 36px;
  gap: 4px;
  font-size: 13px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.rb-home {
  color: var(--color-gray-500);
  text-decoration: none;
  font-size: 13px;
}
.rb-home:hover {
  color: var(--color-emerald-600);
  text-decoration: underline;
}
.rb-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--color-gray-500);
  font-size: 13px;
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
}
.rb-link:hover {
  color: var(--color-emerald-600);
  text-decoration: underline;
}
.rb-sep {
  color: var(--color-gray-400);
  margin: 0 2px;
  font-size: 13px;
}
.rb-current {
  color: var(--color-emerald-600);
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 250px;
}
</style>
