<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getHomeData } from '@/api/site'
import { getMethods } from '@/api/methods'
import { getProducts } from '@/api/products'
import ApplicationCard from '@/components/cards/ApplicationCard.vue'

const router = useRouter()
const loading = ref(true)
const searchQuery = ref('')
const methods = ref([])
const products = ref([])
const homeData = ref({
  hero: { title: 'SciReagent', subtitle: 'Navigate from research goal to application, method, protocol, and product.' },
  stats: { applications: 0, methods: 0, protocols: 0, products: 0 },
  featured_applications: [],
})

const popularSearches = ['Nucleotide synthesis', 'Click chemistry', 'RNA labeling', 'Cy3 dye']

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

  try {
    const methodRes = await getMethods({ page_size: 4 })
    methods.value = methodRes.data || []
  } catch (e) { /* silent */ }

  try {
    const productRes = await getProducts({ page_size: 5 })
    products.value = productRes.data || []
  } catch (e) { /* silent */ }
})

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/search', query: { q: searchQuery.value } })
  }
}

function handlePopularSearch(term) {
  searchQuery.value = term
  handleSearch()
}

function handleApplicationClick(app) {
  router.push({ name: 'ApplicationDetail', params: { id: app.id } })
}

function formatPrice(price, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(price)
}
</script>

<template>
  <div class="home-page">
    <!-- Loading -->
    <template v-if="loading">
      <div class="hero-skeleton">
        <el-skeleton :rows="4" animated />
      </div>
    </template>

    <template v-else>
      <!-- Hero Section -->
      <section class="hero-section" aria-label="Platform introduction">
        <div class="hero-pattern" aria-hidden="true">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="hex-pattern" width="60" height="52" patternUnits="userSpaceOnUse" patternTransform="scale(1.2)">
                <polygon points="30,2 54,15 54,37 30,50 6,37 6,15" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#hex-pattern)"/>
          </svg>
        </div>
        <div class="hero-glow" aria-hidden="true"></div>

        <div class="hero-content">
          <div class="hero-badge">
            <span class="hero-badge-dot" aria-hidden="true"></span>
            AI-Native Scientific Platform
          </div>
          <h1 class="hero-title">{{ homeData.hero.title }}</h1>
          <p class="hero-subtitle">{{ homeData.hero.subtitle }}</p>

          <div class="hero-search-wrapper">
            <el-input
              v-model="searchQuery"
              placeholder="Search products, methods, protocols, applications..."
              size="large"
              prefix-icon="Search"
              clearable
              aria-label="Search the platform"
              @keyup.enter="handleSearch"
              class="hero-search-input"
            />
            <el-button type="primary" size="large" class="hero-search-btn" @click="handleSearch">
              Search
            </el-button>
          </div>

          <div class="hero-popular" aria-label="Popular searches">
            <span class="hero-popular-label">Trending:</span>
            <button
              v-for="term in popularSearches"
              :key="term"
              class="hero-popular-chip"
              @click="handlePopularSearch(term)"
            >
              {{ term }}
            </button>
          </div>
        </div>
      </section>

      <!-- Stats Strip -->
      <section class="stats-strip" aria-label="Platform statistics">
        <button class="stat-chip" @click="router.push('/applications')">
          <span class="stat-chip-icon stat-icon-apps" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
          </span>
          <span class="stat-chip-value">{{ homeData.stats.applications }}</span>
          <span class="stat-chip-label">Applications</span>
        </button>
        <button class="stat-chip" @click="router.push('/methods')">
          <span class="stat-chip-icon stat-icon-methods" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>
          </span>
          <span class="stat-chip-value">{{ homeData.stats.methods }}</span>
          <span class="stat-chip-label">Methods</span>
        </button>
        <button class="stat-chip" @click="router.push('/protocols')">
          <span class="stat-chip-icon stat-icon-protocols" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </span>
          <span class="stat-chip-value">{{ homeData.stats.protocols }}</span>
          <span class="stat-chip-label">Protocols</span>
        </button>
        <button class="stat-chip" @click="router.push('/products')">
          <span class="stat-chip-icon stat-icon-products" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>
          </span>
          <span class="stat-chip-value">{{ homeData.stats.products }}</span>
          <span class="stat-chip-label">Products</span>
        </button>
      </section>

      <!-- Featured Applications -->
      <section class="content-section" aria-label="Featured applications">
        <div class="section-header">
          <div class="section-header-left">
            <span class="section-indicator" aria-hidden="true"></span>
            <h2 class="section-title">Featured Applications</h2>
          </div>
          <el-button text type="primary" size="small" @click="router.push('/applications')">
            View all <el-icon class="section-arrow"><ArrowRight /></el-icon>
          </el-button>
        </div>
        <div v-if="homeData.featured_applications.length" class="card-grid-3">
          <ApplicationCard
            v-for="app in homeData.featured_applications.slice(0, 6)"
            :key="app.id"
            :application="app"
            @click="handleApplicationClick"
          />
        </div>
        <div v-else class="empty-state-compact">
          <p>No applications yet</p>
        </div>
      </section>

      <!-- Two-column: Methods + Products -->
      <div class="split-grid">
        <!-- Methods -->
        <section class="content-section" aria-label="Featured methods">
          <div class="section-header">
            <div class="section-header-left">
              <span class="section-indicator indicator-secondary" aria-hidden="true"></span>
              <h2 class="section-title">Methods</h2>
            </div>
            <el-button text type="primary" size="small" @click="router.push('/methods')">
              View all
            </el-button>
          </div>
          <div v-if="methods.length" class="compact-list">
            <router-link
              v-for="m in methods.slice(0, 4)"
              :key="m.id"
              :to="`/methods/${m.id}`"
              class="compact-item"
            >
              <div class="compact-item-main">
                <h4 class="compact-item-title">{{ m.name }}</h4>
                <p class="compact-item-desc">{{ m.summary || m.purpose || 'No description' }}</p>
              </div>
              <div class="compact-item-meta">
                <span class="compact-item-count">{{ m.protocol_count || 0 }}</span>
                <span class="compact-item-count-label">protocols</span>
              </div>
            </router-link>
          </div>
          <div v-else class="empty-state-compact">
            <p>No methods yet</p>
          </div>
        </section>

        <!-- Products -->
        <section class="content-section" aria-label="Featured products">
          <div class="section-header">
            <div class="section-header-left">
              <span class="section-indicator indicator-warning" aria-hidden="true"></span>
              <h2 class="section-title">Products</h2>
            </div>
            <el-button text type="primary" size="small" @click="router.push('/products')">
              View all
            </el-button>
          </div>
          <div v-if="products.length" class="compact-list">
            <router-link
              v-for="p in products.slice(0, 5)"
              :key="p.id"
              :to="`/products/${p.id}`"
              class="compact-item"
            >
              <div class="compact-item-main">
                <div class="compact-item-top">
                  <h4 class="compact-item-title">{{ p.name }}</h4>
                  <span v-if="p.price" class="compact-item-price">{{ formatPrice(p.price, p.currency) }}</span>
                </div>
                <div class="compact-item-tags">
                  <span v-if="p.cas" class="chem-id-sm">{{ p.cas }}</span>
                  <span v-if="p.purity" class="compact-item-purity">{{ p.purity }}</span>
                </div>
              </div>
              <el-tag :type="p.inventory_status === 'in_stock' ? 'success' : 'warning'" size="small" effect="light">
                {{ p.inventory_status || 'available' }}
              </el-tag>
            </router-link>
          </div>
          <div v-else class="empty-state-compact">
            <p>No products yet</p>
          </div>
        </section>
      </div>

      <!-- Value Proposition -->
      <section class="values-section" aria-label="Platform advantages">
        <div class="values-grid">
          <div class="value-item">
            <div class="value-icon value-icon-search" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
            </div>
            <div class="value-text">
              <h3 class="value-title">Search by Intent</h3>
              <p class="value-desc">Find reagents by research goal, not just product name.</p>
            </div>
          </div>
          <div class="value-item">
            <div class="value-icon value-icon-graph" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
            </div>
            <div class="value-text">
              <h3 class="value-title">Knowledge Graph</h3>
              <p class="value-desc">Application → Method → Protocol → Product, every connection explicit.</p>
            </div>
          </div>
          <div class="value-item">
            <div class="value-icon value-icon-ai" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
            </div>
            <div class="value-text">
              <h3 class="value-title">AI-Ready Data</h3>
              <p class="value-desc">Structured JSON-LD for agents, citations, and retrieval.</p>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

/* ========== Hero Section ========== */
.hero-section {
  background: linear-gradient(135deg, #0F766E 0%, #134E4A 50%, #1E3A5F 100%);
  border-radius: var(--radius-lg);
  padding: 40px 36px;
  color: white;
  position: relative;
  overflow: hidden;
}

.hero-pattern {
  position: absolute;
  inset: 0;
  opacity: 0.5;
  pointer-events: none;
}

.hero-glow {
  position: absolute;
  width: 300px;
  height: 300px;
  right: -80px;
  top: -60px;
  background: radial-gradient(circle, rgba(217, 119, 6, 0.2) 0%, transparent 70%);
  pointer-events: none;
}

.hero-content {
  position: relative;
  max-width: 600px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-full);
  padding: 4px 12px;
  font-size: 12px;
  margin-bottom: 14px;
  font-weight: 500;
  backdrop-filter: blur(8px);
}

.hero-badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #34D399;
  box-shadow: 0 0 6px #34D399;
}

.hero-title {
  font-size: 34px;
  font-weight: 800;
  margin: 0 0 8px;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.hero-subtitle {
  font-size: 15px;
  margin: 0 0 24px;
  opacity: 0.8;
  line-height: 1.55;
  max-width: 460px;
}

/* Hero Search */
.hero-search-wrapper {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  max-width: 520px;
}

.hero-search-input {
  flex: 1;
}

.hero-search-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.95);
  border-radius: var(--radius-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.hero-search-btn {
  border-radius: var(--radius-md);
  background: var(--color-warning);
  color: #1a1a1a;
  border: none;
  font-weight: 700;
  padding: 0 24px;
}

.hero-search-btn:hover {
  background: #EAB308;
}

/* Popular searches */
.hero-popular {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-popular-label {
  font-size: 12px;
  font-weight: 500;
  opacity: 0.6;
}

.hero-popular-chip {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: white;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s ease;
}

.hero-popular-chip:hover {
  background: rgba(255, 255, 255, 0.16);
}

.hero-popular-chip:focus-visible {
  outline: 2px solid white;
  outline-offset: 2px;
}

/* ========== Stats Strip ========== */
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.stat-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  font-family: inherit;
  text-align: left;
}

.stat-chip:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-card);
}

.stat-chip:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.stat-chip-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-apps { background: var(--color-primary-soft); color: var(--color-primary); }
.stat-icon-methods { background: var(--color-secondary-soft); color: var(--color-secondary); }
.stat-icon-protocols { background: #DBEAFE; color: #3B82F6; }
.stat-icon-products { background: var(--color-warning-soft); color: var(--color-warning); }

.stat-chip-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.stat-chip-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* ========== Content Sections ========== */
.content-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-indicator {
  width: 3px;
  height: 18px;
  border-radius: 2px;
  background: var(--color-primary);
}

.indicator-secondary { background: var(--color-secondary); }
.indicator-warning { background: var(--color-warning); }

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}

.section-arrow {
  margin-left: 2px;
}

.card-grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

/* ========== Two-column grid ========== */
.split-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

/* ========== Compact list ========== */
.compact-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.compact-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  text-decoration: none;
  color: inherit;
  transition: background 0.1s ease;
  border-bottom: 1px solid var(--color-border-light);
}

.compact-item:last-child {
  border-bottom: none;
}

.compact-item:hover {
  background: var(--color-bg);
}

.compact-item-main {
  flex: 1;
  min-width: 0;
}

.compact-item-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 3px;
}

.compact-item-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.compact-item-price {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.compact-item-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 2px 0 0;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.compact-item-tags {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 3px;
}

.chem-id-sm {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 0 5px;
  border-radius: var(--radius-sm);
}

.compact-item-purity {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.compact-item-meta {
  text-align: right;
  flex-shrink: 0;
}

.compact-item-count {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
  display: block;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.compact-item-count-label {
  font-size: 10px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* ========== Value Proposition ========== */
.values-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 24px 28px;
}

.values-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.value-item {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.value-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.value-icon-search { background: var(--color-primary-soft); color: var(--color-primary); }
.value-icon-graph { background: var(--color-secondary-soft); color: var(--color-secondary); }
.value-icon-ai { background: var(--color-warning-soft); color: var(--color-warning); }

.value-text {
  min-width: 0;
}

.value-title {
  font-size: 14px;
  font-weight: 700;
  margin: 0 0 4px;
  color: var(--color-text);
}

.value-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.45;
}

/* ========== Empty state ========== */
.empty-state-compact {
  text-align: center;
  padding: 32px;
  color: var(--color-text-secondary);
  font-size: 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

/* ========== Skeleton ========== */
.hero-skeleton {
  background: linear-gradient(135deg, var(--color-primary) 0%, #1E3A8A 40%, var(--color-secondary) 100%);
  border-radius: var(--radius-lg);
  padding: 48px 40px;
}

/* ========== Responsive ========== */
@media (max-width: 1024px) {
  .split-grid {
    grid-template-columns: 1fr;
  }
  .card-grid-3 {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .hero-section {
    padding: 28px 20px;
  }
  .hero-title {
    font-size: 26px;
  }
  .hero-search-wrapper {
    flex-direction: column;
  }
  .stats-strip {
    grid-template-columns: repeat(2, 1fr);
  }
  .card-grid-3 {
    grid-template-columns: 1fr;
  }
  .values-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}
</style>
