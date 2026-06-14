<script setup>
import { useRouter } from 'vue-router'

defineProps({
  solutions: { type: Array, default: () => [] },
})

const router = useRouter()

function handleExplore(solution) {
  router.push(`/applications/${solution.application_id}`)
}
</script>

<template>
  <section v-if="solutions.length" class="section" aria-label="Featured Solutions">
    <div class="section-header">
      <h2 class="section-title">Featured Solutions</h2>
    </div>
    <div class="solutions-grid">
      <div
        v-for="sol in solutions"
        :key="sol.application_id"
        class="solution-card"
      >
        <h3 class="solution-name">{{ sol.name }}</h3>
        <div class="solution-stats">
          <span class="stat">{{ sol.methods_count }} Methods</span>
          <span class="stat">{{ sol.protocols_count }} Protocols</span>
          <span class="stat">{{ sol.products_count }} Products</span>
        </div>
        <button class="btn-explore" @click="handleExplore(sol)">Explore Workflow →</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.section { margin-bottom: 32px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}
.solutions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.solution-card {
  padding: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: all 0.15s;
}
.solution-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.solution-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 12px;
}
.solution-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.stat {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.btn-explore {
  padding: 8px 16px;
  background: var(--color-primary-light);
  color: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: background 0.15s;
}
.btn-explore:hover { background: var(--color-primary); color: white; }
</style>
