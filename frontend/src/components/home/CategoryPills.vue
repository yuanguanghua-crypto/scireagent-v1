<script setup>
import { useRouter } from 'vue-router'

defineProps({
  categories: {
    type: Array,
    default: () => [
      { name: 'Nucleotides', slug: 'nucleotides', count: 28, color: '#7C3AED', bg: '#EDE9FE' },
      { name: 'Click Chemistry', slug: 'click-chemistry', count: 22, color: '#0F766E', bg: '#F0FDFA' },
      { name: 'Fluorescent Probes', slug: 'fluorescent-probes', count: 31, color: '#0EA5E9', bg: '#E0F2FE' },
      { name: 'Bioconjugation', slug: 'bioconjugation', count: 18, color: '#CA8A04', bg: '#FEF3C7' },
      { name: 'Modifiers', slug: 'modifiers', count: 15, color: '#E11D48', bg: '#FCE7F3' },
      { name: 'Molecular Biology', slug: 'molecular-biology', count: 24, color: '#64748B', bg: '#F1F5F9' },
    ],
  },
})

const router = useRouter()
</script>

<template>
  <section class="categories" aria-label="Product categories">
    <div class="categories-scroll">
      <button
        v-for="cat in categories"
        :key="cat.slug"
        class="category-pill"
        :style="{ '--dot-color': cat.color, '--dot-bg': cat.bg }"
        @click="router.push(`/products?category=${cat.slug}`)"
      >
        <span class="dot"></span>
        {{ cat.name }}
        <span class="count">{{ cat.count }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.categories {
  padding: 8px 0 40px;
}
.categories-scroll {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.category-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  border: 1.5px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-family: var(--font-sans);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.category-pill:hover {
  border-color: var(--color-border-hover);
  color: var(--color-text);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--dot-color);
}
.count {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 400;
}
</style>
