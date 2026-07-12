<script setup>
import { useRouter } from 'vue-router'

defineProps({
  goals: { type: Array, default: () => [] },
})

const router = useRouter()

function handleClick(goal) {
  router.push({ path: '/products', query: { research_goal: goal.id } })
}
</script>

<template>
  <section v-if="goals.length" class="section" aria-label="Research Goals">
    <div class="section-header">
      <h2 class="section-title">Research Goals</h2>
      <router-link to="/research-goals" class="section-link">View all →</router-link>
    </div>
    <div class="goals-grid">
      <button
        v-for="goal in goals"
        :key="goal.id"
        class="goal-card"
        @click="handleClick(goal)"
      >
        <div class="goal-icon">🎯</div>
        <h3 class="goal-name">{{ goal.name }}</h3>
        <div class="goal-stats">
          <span class="goal-stat">
            <strong>{{ goal.applications_count }}</strong> applications
          </span>
          <span class="goal-stat">
            <strong>{{ goal.products_count }}</strong> products
          </span>
        </div>
        <span class="goal-explore">Explore &rarr;</span>
      </button>
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
.section-link {
  font-size: 14px;
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}
.section-link:hover { text-decoration: underline; }
.goals-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.goal-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font-sans);
}
.goal-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.goal-icon { font-size: 28px; }
.goal-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  text-align: center;
}
.goal-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.goal-stat strong {
  font-weight: 700;
  color: var(--color-primary);
}
.goal-explore {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary);
  margin-top: 2px;
}
</style>
