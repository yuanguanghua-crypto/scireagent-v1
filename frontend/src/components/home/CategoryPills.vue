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
  position: relative;
  overflow: hidden;
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
  box-shadow: 0 0 6px var(--dot-color);
  animation: dot-pulse 2.6s ease-in-out infinite;
}
.category-pill:nth-child(2n) .dot { animation-delay: -0.6s; }
.category-pill:nth-child(3n) .dot { animation-delay: -1.2s; }
.category-pill::after {
  content: '';
  position: absolute;
  top: 50%;
  left: -16px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #A7FFFF;
  box-shadow: 0 0 10px #A7FFFF, 0 0 18px rgba(167, 255, 255, 0.6);
  opacity: 0;
  transform: translateY(-50%);
  pointer-events: none;
}
.category-pill:hover::after {
  animation: firefly-glide 1.3s ease-in-out;
}
.count {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 400;
}
@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.55; transform: scale(0.82); }
}
@keyframes firefly-glide {
  0%   { left: -16px; opacity: 0; }
  15%  { opacity: 1; }
  85%  { opacity: 1; }
  100% { left: calc(100% + 16px); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .dot { animation: none; }
  .category-pill::after { display: none; }
}
</style>
