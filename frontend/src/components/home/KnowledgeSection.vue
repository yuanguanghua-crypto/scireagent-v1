<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  knowledge: {
    type: Object,
    default: () => ({ goals: 8, applications: 8, methods: 10, protocols: 88 }),
  },
})

const open = ref(false)
const router = useRouter()

const knowledgeItems = [
  {
    icon: '🎯',
    title: 'Research Goals',
    desc: 'Explore research directions — from cellular metabolism to gene expression.',
    count: props.knowledge.goals,
    link: '/research-goals',
    bg: '#EDE9FE',
    color: '#7C3AED',
  },
  {
    icon: '🧪',
    title: 'Applications',
    desc: 'qPCR, Western Blot, flow cytometry — standard experimental applications.',
    count: props.knowledge.applications,
    link: '/applications',
    bg: '#F0FDFA',
    color: '#0F766E',
  },
  {
    icon: '🔬',
    title: 'Methods',
    desc: 'Detailed principles, protocols, advantages for core experimental methods.',
    count: props.knowledge.methods,
    link: '/methods',
    bg: '#E0F2FE',
    color: '#0EA5E9',
  },
  {
    icon: '📋',
    title: 'Protocols',
    desc: 'Step-by-step guides with reagent preparation, timing, and troubleshooting.',
    count: props.knowledge.protocols,
    link: '/protocols',
    bg: '#FEF3C7',
    color: '#CA8A04',
  },
]

function toggle() {
  open.value = !open.value
}
</script>

<template>
  <section class="knowledge-section" aria-label="Knowledge graph">
    <button class="knowledge-toggle" :class="{ open }" @click="toggle">
      <span>
        Explore Knowledge Graph
        <span class="pill-count">6 domains</span>
      </span>
      <span class="chevron" :class="{ open }">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
      </span>
    </button>
    <div class="knowledge-body" :class="{ open }">
      <div class="knowledge-grid">
        <button
          v-for="item in knowledgeItems"
          :key="item.title"
          class="knowledge-card"
          @click="router.push(item.link)"
        >
          <div class="k-icon" :style="{ background: item.bg, color: item.color }">{{ item.icon }}</div>
          <h4>{{ item.title }}</h4>
          <p>{{ item.desc }}</p>
          <span class="k-link">Browse {{ item.count }} →</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.knowledge-section {
  padding: 8px 0 80px;
}
.knowledge-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 18px 24px;
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface);
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  transition: all 0.15s;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.knowledge-toggle:hover {
  border-color: var(--color-teal-100);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
}
.chevron {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  color: var(--color-text-tertiary);
}
.chevron.open {
  transform: rotate(180deg);
}
.pill-count {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 9999px;
  background: var(--color-gray-100);
  color: var(--color-text-tertiary);
  margin-left: 8px;
}
.knowledge-body {
  overflow: hidden;
  max-height: 0;
  opacity: 0;
  transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.knowledge-body.open {
  max-height: 600px;
  opacity: 1;
}
.knowledge-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  padding: 28px 0 12px;
}
.knowledge-card {
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  padding: 24px;
  text-decoration: none;
  color: inherit;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.knowledge-card:hover {
  border-color: var(--color-border-hover);
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.10);
}
.k-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  font-size: 18px;
}
.knowledge-card h4 {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-text);
}
.knowledge-card p {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 0;
}
.k-link {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary);
  margin-top: 14px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: gap 0.15s;
}
.knowledge-card:hover .k-link {
  gap: 8px;
}

@media (max-width: 768px) {
  .knowledge-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .knowledge-grid { grid-template-columns: 1fr; }
}
</style>
