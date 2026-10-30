<script setup>
/**
 * FeaturedEntities — 首页的「精选应用 / 精选方法」卡片区（通用）。
 *
 * ★ 2026-10-30 C 批新建：`/api/v1/site/home` 一直在算 featured_applications（6 条）
 *   和 featured_methods（6 条），但首页**从来没有渲染过**它们 —— 数据白算、
 *   知识实体在首页只有一个折叠的四卡片入口。本组件把这两块接上。
 *
 * 两种 kind 的字段差异：
 * - application: name / summary / methods_count / products_count
 * - method:      name / purpose   / products_count
 * 所以描述取 `summary || purpose`，计数按 kind 拼。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  kind: { type: String, default: 'application' }, // application | method
  items: { type: Array, default: () => [] },
  linkTo: { type: String, required: true },
  linkText: { type: String, default: 'Browse all' },
  limit: { type: Number, default: 6 },
})

const router = useRouter()

const shown = computed(() => (props.items || []).slice(0, props.limit))

function pathOf(item) {
  return props.kind === 'method' ? `/methods/${item.id}` : `/applications/${item.id}`
}

function descOf(item) {
  return item.summary || item.purpose || ''
}

/** 单复数：卡片上出现过 "1 methods · 2 products" —— 明显英文错误。 */
function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`
}

function metaOf(item) {
  if (props.kind === 'method') {
    return item.products_count ? plural(item.products_count, 'product', 'products') : ''
  }
  const bits = []
  if (item.methods_count) bits.push(plural(item.methods_count, 'method', 'methods'))
  if (item.products_count) bits.push(plural(item.products_count, 'product', 'products'))
  return bits.join(' · ')
}
</script>

<template>
  <section v-if="shown.length" class="section" :aria-label="title">
    <div class="section-header">
      <div class="header-text">
        <h2 class="section-title">{{ title }}</h2>
        <p v-if="subtitle" class="section-subtitle">{{ subtitle }}</p>
      </div>
      <router-link :to="linkTo" class="section-link">{{ linkText }} &rarr;</router-link>
    </div>

    <div class="entity-grid">
      <button
        v-for="item in shown"
        :key="item.id"
        class="entity-card"
        @click="router.push(pathOf(item))"
      >
        <div class="card-name">{{ item.name }}</div>
        <p v-if="descOf(item)" class="card-desc">{{ descOf(item) }}</p>
        <div v-if="metaOf(item)" class="card-meta">{{ metaOf(item) }}</div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.section { margin-bottom: 40px; }

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.header-text { min-width: 0; }
.section-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}
.section-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.section-link {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  text-decoration: none;
  white-space: nowrap;
  padding-top: 4px;
}
.section-link:hover { text-decoration: underline; }

.entity-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.entity-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  text-align: left;
  font-family: var(--font-sans);
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;
  overflow: hidden;
}
.entity-card::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--color-primary);
  opacity: 0;
  transition: opacity 0.18s;
}
.entity-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}
.entity-card:hover::after { opacity: 1; }

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  margin-top: auto;
  padding-top: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  opacity: 0.85;
}

@media (max-width: 900px) {
  .entity-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 560px) {
  .entity-grid { grid-template-columns: 1fr; }
  .section-header { flex-direction: column; gap: 6px; }
}
</style>
