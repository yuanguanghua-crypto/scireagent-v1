<script setup>
import { defineAsyncComponent, onMounted, ref } from 'vue'
import { getHomeData } from '@/api/site'

/* Public navigation */
import PublicNav from '@/components/layout/PublicNav.vue'

/* Blocking components */
import HeroSearch from '@/components/home/HeroSearch.vue'
import CategoryPills from '@/components/home/CategoryPills.vue'
import FeaturedProducts from '@/components/home/FeaturedProducts.vue'

/* Lazy-loaded components (below fold) */
const StatsBar = defineAsyncComponent(() => import('@/components/home/StatsBar.vue'))
const KnowledgeSection = defineAsyncComponent(() => import('@/components/home/KnowledgeSection.vue'))

const loading = ref(true)
const homeData = ref({
  hero: { title: 'SciReagent', subtitle: '', suggested_searches: [] },
  stats: { applications: 0, methods: 0, protocols: 0, products: 0 },
  featured_products: [],
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
  <div class="home">
    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <div class="loading-skeleton" style="height: 400px;"></div>
    </div>

    <template v-else>
      <!-- Public Navigation -->
      <PublicNav />

      <!-- 1. Hero Search (full-width dark section) -->
      <HeroSearch
        :title="homeData.hero?.title"
        :subtitle="homeData.hero?.subtitle"
        :suggested-searches="homeData.hero?.suggested_searches"
      />

      <!-- Content area (contained width) -->
      <div class="content-area">
        <!-- 2. Category Pills -->
        <CategoryPills />

        <!-- 3. Featured Products Grid -->
        <FeaturedProducts :products="homeData.featured_products" />

        <!-- 4. Stats Bar -->
        <Suspense>
          <StatsBar :stats="homeData.stats" />
          <template #fallback>
            <div class="loading-skeleton" style="height: 120px; margin: 32px 0;"></div>
          </template>
        </Suspense>

        <!-- 5. Knowledge Section (collapsible) -->
        <Suspense>
          <KnowledgeSection />
          <template #fallback>
            <div class="loading-skeleton" style="height: 80px;"></div>
          </template>
        </Suspense>
      </div>
    </template>
  </div>
</template>

<style scoped>
.home {
  min-height: 100vh;
}
.content-area {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 32px;
}

/* Loading */
.loading-state {
  max-width: 1280px;
  margin: 0 auto;
  padding: 100px 32px;
}
.loading-skeleton {
  background: var(--color-gray-100);
  border-radius: 12px;
  animation: pulse 1.5s ease-in-out infinite;
  width: 100%;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@media (max-width: 768px) {
  .content-area {
    padding: 0 20px;
  }
}
</style>
