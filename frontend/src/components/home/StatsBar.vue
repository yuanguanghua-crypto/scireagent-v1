<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCountUp } from '@/composables/useCountUp'
import StarDot from '@/components/common/StarDot.vue'

const props = defineProps({
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
const rootEl = ref(null)
const display = reactive({ products: 0, skus: 0, methods: 0, protocols: 0, areas: 0 })
const counter = useCountUp(1400, 120)

onMounted(() => {
  counter.watch(rootEl.value, [
    { setter: v => (display.products = v), value: props.stats.products || 0 },
    { setter: v => (display.skus = v), value: props.stats.skus || 0 },
    { setter: v => (display.methods = v), value: props.stats.methods || 0 },
    { setter: v => (display.protocols = v), value: props.stats.protocols || 0 },
    { setter: v => (display.areas = v), value: props.stats.areas || 0 },
  ])
})
</script>

<template>
  <section ref="rootEl" class="stats-section" aria-label="Platform statistics">
    <div class="stats-grid">
      <button class="stat-item" @click="router.push('/products')">
        <StarDot class="stat-star" :size="4" color="#5EEAD4" pulse />
        <div class="stat-number">{{ display.products }}</div>
        <div class="stat-label">Products</div>
      </button>
      <button class="stat-item" @click="router.push('/products')">
        <StarDot class="stat-star" :size="4" color="#38BDF8" pulse />
        <div class="stat-number">{{ display.skus }}</div>
        <div class="stat-label">SKUs</div>
      </button>
      <button class="stat-item" @click="router.push('/methods')">
        <StarDot class="stat-star" :size="4" color="#8FE8FF" pulse />
        <div class="stat-number">{{ display.methods }}</div>
        <div class="stat-label">Methods</div>
      </button>
      <button class="stat-item" @click="router.push('/protocols')">
        <StarDot class="stat-star" :size="4" color="#A6D7FF" pulse />
        <div class="stat-number">{{ display.protocols }}</div>
        <div class="stat-label">Protocols</div>
      </button>
      <button class="stat-item" @click="router.push('/research-goals')">
        <StarDot class="stat-star" :size="4" color="#B2B0FF" pulse />
        <div class="stat-number">{{ display.areas }}</div>
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
  position: relative;
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
.stat-star {
  position: absolute;
  top: 10px;
  right: 12px;
  opacity: 0.55;
  transition: opacity 0.2s;
}
.stat-item:hover .stat-star {
  opacity: 1;
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
