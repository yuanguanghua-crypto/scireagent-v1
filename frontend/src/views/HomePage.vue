<script setup>
import { defineAsyncComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getHomeData } from '@/api/site'

/* Blocking components (loaded immediately) */
import HeroSearch from '@/components/home/HeroSearch.vue'
import FeaturedProducts from '@/components/home/FeaturedProducts.vue'
import ResearchGoals from '@/components/home/ResearchGoals.vue'

/* Lazy-loaded components (below fold) */
const FeaturedSolutions = defineAsyncComponent(() => import('@/components/home/FeaturedSolutions.vue'))
const KnowledgeGraphPreview = defineAsyncComponent(() => import('@/components/home/KnowledgeGraphPreview.vue'))
const ReferencesSection = defineAsyncComponent(() => import('@/components/home/ReferencesSection.vue'))
const CustomSynthesisCTA = defineAsyncComponent(() => import('@/components/home/CustomSynthesisCTA.vue'))

const router = useRouter()
const loading = ref(true)
const homeData = ref({
  hero: { title: 'SciReagent', subtitle: '', suggested_searches: [] },
  stats: { applications: 0, methods: 0, protocols: 0, products: 0 },
  featured_applications: [],
  featured_methods: [],
  featured_products: [],
  featured_solutions: [],
  research_goals: [],
  references: [],
  graph_preview: null,
})

onMounted(async () => {
  try {
    const result = await getHomeData()
    if (result.data) {
      homeData.value = { ...homeData.value, ...result.data }
    }
  } catch (err) {
    console.error('Failed to load home data:', err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="home-page">
    <!-- Loading -->
    <template v-if="loading">
      <div class="hero-skeleton">
        <div class="skeleton-block" style="height: 300px; border-radius: 12px;"></div>
        <div class="skeleton-row">
          <div class="skeleton-block" v-for="i in 4" :key="i" style="height: 120px;"></div>
        </div>
      </div>
    </template>

    <template v-else>
      <!-- Hero Search (Blocking) -->
      <HeroSearch
        :title="homeData.hero.title"
        :subtitle="homeData.hero.subtitle"
        :suggested-searches="homeData.hero.suggested_searches"
      />

      <!-- Stats Strip -->
      <section class="stats-strip" aria-label="Platform statistics">
        <button class="stat-chip" @click="router.push('/applications')">
          <span class="stat-value">{{ homeData.stats.applications }}</span>
          <span class="stat-label">Applications</span>
        </button>
        <button class="stat-chip" @click="router.push('/methods')">
          <span class="stat-value">{{ homeData.stats.methods }}</span>
          <span class="stat-label">Methods</span>
        </button>
        <button class="stat-chip" @click="router.push('/protocols')">
          <span class="stat-value">{{ homeData.stats.protocols }}</span>
          <span class="stat-label">Protocols</span>
        </button>
        <button class="stat-chip" @click="router.push('/products')">
          <span class="stat-value">{{ homeData.stats.products }}</span>
          <span class="stat-label">Products</span>
        </button>
      </section>

      <!-- Research Goals (Blocking) -->
      <ResearchGoals :goals="homeData.research_goals" />

      <!-- Featured Solutions (Lazy) -->
      <Suspense>
        <FeaturedSolutions :solutions="homeData.featured_solutions" />
        <template #fallback>
          <div class="skeleton-block" style="height: 200px;"></div>
        </template>
      </Suspense>

      <!-- Featured Products (Blocking) -->
      <FeaturedProducts :products="homeData.featured_products" />

      <!-- Knowledge Graph Preview (Lazy) -->
      <Suspense>
        <KnowledgeGraphPreview :graph-data="homeData.graph_preview" />
        <template #fallback>
          <div class="skeleton-block" style="height: 200px;"></div>
        </template>
      </Suspense>

      <!-- References (Lazy) -->
      <Suspense>
        <ReferencesSection :references="homeData.references" />
        <template #fallback>
          <div class="skeleton-block" style="height: 150px;"></div>
        </template>
      </Suspense>

      <!-- Custom Synthesis CTA (Lazy) -->
      <Suspense>
        <CustomSynthesisCTA />
        <template #fallback>
          <div class="skeleton-block" style="height: 120px;"></div>
        </template>
      </Suspense>
    </template>
  </div>
</template>

<style scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Stats Strip */
.stats-strip {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}
.stat-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font-sans);
}
.stat-chip:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.stat-value {
  font-size: 20px;
  font-weight: 800;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}
.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

/* Skeleton */
.hero-skeleton { display: flex; flex-direction: column; gap: 16px; }
.skeleton-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.skeleton-block {
  background: var(--color-bg);
  border-radius: var(--radius-md);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@media (max-width: 768px) {
  .home-page { padding: 16px; }
  .stats-strip { gap: 8px; }
  .stat-chip { padding: 8px 14px; }
  .skeleton-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
