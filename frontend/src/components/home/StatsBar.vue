<script setup>
import { useRouter } from 'vue-router'

defineProps({
  stats: {
    type: Object,
    default: () => ({
      products: 118,
      skus: 293,
      methods: 10,
      protocols: 88,
      areas: 8,
    }),
  },
})

const router = useRouter()
</script>

<template>
  <section class="stats-section" aria-label="Platform statistics">
    <div class="stats-grid">
      <button class="stat-item" @click="router.push('/products')">
        <div class="stat-number">{{ stats.products || 0 }}</div>
        <div class="stat-label">Products</div>
      </button>
      <button class="stat-item" @click="router.push('/products')">
        <div class="stat-number">{{ stats.skus || 0 }}</div>
        <div class="stat-label">SKUs</div>
      </button>
      <button class="stat-item" @click="router.push('/methods')">
        <div class="stat-number">{{ stats.methods || 0 }}</div>
        <div class="stat-label">Methods</div>
      </button>
      <button class="stat-item" @click="router.push('/protocols')">
        <div class="stat-number">{{ stats.protocols || 0 }}</div>
        <div class="stat-label">Protocols</div>
      </button>
      <button class="stat-item" @click="router.push('/research-goals')">
        <div class="stat-number">{{ stats.areas || 0 }}</div>
        <div class="stat-label">Research Areas</div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.stats-section {
  padding: 32px 0 48px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: var(--color-border);
  border-radius: 10px;
  overflow: hidden;
  border: 1.5px solid var(--color-border);
}
.stat-item {
  background: var(--color-surface);
  padding: 28px 20px;
  text-align: center;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
  font-family: var(--font-sans);
}
.stat-item:hover {
  background: var(--color-gray-50);
}
.stat-number {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1;
  margin-bottom: 4px;
}
.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 480px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .stat-item:nth-child(5) { grid-column: span 2; }
}
</style>
