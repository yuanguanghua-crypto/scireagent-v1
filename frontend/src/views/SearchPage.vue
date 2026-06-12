<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { search } from '@/api/search'
import { truncate } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const searchQuery = ref('')
const results = ref([])
const loading = ref(false)
const resultCount = ref(0)
const activeTypeFilter = ref('all')

const typeFilters = [
  { key: 'all', label: 'All', icon: '☰' },
  { key: 'product', label: 'Products', icon: '📦' },
  { key: 'method', label: 'Methods', icon: '📋' },
  { key: 'application', label: 'Applications', icon: '🧪' },
  { key: 'protocol', label: 'Protocols', icon: '📄' },
]

const filteredResults = computed(() => {
  if (activeTypeFilter.value === 'all') return results.value
  return results.value.filter(r => r.type === activeTypeFilter.value)
})

const typeCounts = computed(() => {
  const counts = { all: results.value.length }
  for (const r of results.value) {
    counts[r.type] = (counts[r.type] || 0) + 1
  }
  return counts
})

onMounted(() => {
  searchQuery.value = route.query.q || ''
  if (searchQuery.value) doSearch()
})

watch(() => route.query.q, (val) => {
  if (val && val !== searchQuery.value) {
    searchQuery.value = val
    doSearch()
  }
})

async function doSearch() {
  if (!searchQuery.value.trim()) return
  loading.value = true
  try {
    const res = await search(searchQuery.value)
    results.value = res.data || []
    resultCount.value = res.meta?.count || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function goToResult(item) {
  const typeMap = {
    product: '/products/',
    application: '/applications/',
    method: '/methods/',
    protocol: '/protocols/',
    reference: '/references/',
  }
  const path = typeMap[item.type] || '/'
  router.push(`${path}${item.id}`)
}

function getTypeTag(type) {
  const map = { product: 'success', application: 'primary', method: 'warning', protocol: 'info', reference: '' }
  return map[type] || ''
}

function getTypeLabel(type) {
  const map = { product: 'Product', application: 'Application', method: 'Method', protocol: 'Protocol', reference: 'Reference' }
  return map[type] || type
}
</script>

<template>
  <div class="search-page">
    <!-- Search header -->
    <div class="search-header">
      <h1 class="page-title">Search</h1>
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          placeholder="Search products, methods, protocols, references..."
          size="large"
          prefix-icon="Search"
          clearable
          @keyup.enter="doSearch"
          class="search-input"
        />
        <el-button type="primary" size="large" @click="doSearch">Search</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-container">
      <el-skeleton v-for="i in 5" :key="i" :rows="2" animated class="skeleton-item" />
    </div>

    <!-- Results area -->
    <div v-else-if="results.length > 0" class="results-layout">
      <!-- Sidebar filters -->
      <aside class="results-sidebar">
        <div class="sidebar-section">
          <h3 class="sidebar-title">Result Types</h3>
          <div class="type-filters">
            <button
              v-for="f in typeFilters"
              :key="f.key"
              class="type-filter-btn"
              :class="{ active: activeTypeFilter === f.key }"
              @click="activeTypeFilter = f.key"
            >
              <span class="type-filter-label">{{ f.label }}</span>
              <span class="type-filter-count">{{ typeCounts[f.key] || 0 }}</span>
            </button>
          </div>
        </div>
      </aside>

      <!-- Results list -->
      <div class="results-main">
        <p class="result-summary">
          <strong>{{ filteredResults.length }}</strong> result(s) for "<em>{{ searchQuery }}</em>"
        </p>

        <div class="result-list">
          <article
            v-for="item in filteredResults"
            :key="`${item.type}-${item.id}`"
            class="result-item"
            @click="goToResult(item)"
          >
            <div class="result-type-bar" :class="`type-${item.type}`" aria-hidden="true"></div>
            <div class="result-body">
              <div class="result-header">
                <el-tag :type="getTypeTag(item.type)" size="small" effect="light">
                  {{ getTypeLabel(item.type) }}
                </el-tag>
                <span class="result-name">{{ item.name || item.title }}</span>
              </div>
              <p v-if="item.summary || item.description" class="result-summary-text">
                {{ truncate(item.summary || item.description, 150) }}
              </p>
              <div class="result-meta">
                <span v-if="item.cas" class="chem-id-sm">CAS: {{ item.cas }}</span>
                <span v-if="item.slug" class="result-slug">/{{ item.slug }}</span>
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="searchQuery" class="empty-container">
      <el-empty :description="`No results for &quot;${searchQuery}&quot;`" />
    </div>
  </div>
</template>

<style scoped>
.search-page {
  max-width: 1200px;
  margin: 0 auto;
}

.page-title {
  font-size: 22px;
  font-weight: 800;
  color: var(--color-text);
  margin: 0 0 14px;
  letter-spacing: -0.01em;
}

.search-bar {
  display: flex;
  gap: 8px;
}

.search-input {
  flex: 1;
  max-width: 600px;
}

.search-header {
  margin-bottom: 20px;
}

/* Results layout */
.results-layout {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 20px;
}

/* Sidebar */
.results-sidebar {
  position: sticky;
  top: 80px;
  align-self: start;
}

.sidebar-section {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 12px;
}

.sidebar-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-secondary);
  margin: 0 0 8px;
}

.type-filters {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.type-filter-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  font-family: inherit;
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.1s ease;
  text-align: left;
}

.type-filter-btn:hover {
  background: var(--color-bg);
}

.type-filter-btn.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 600;
}

.type-filter-count {
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  min-width: 18px;
  text-align: right;
}

/* Results main */
.result-summary {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0 0 12px;
}

.result-summary strong {
  color: var(--color-text);
}

.result-summary em {
  font-style: normal;
  color: var(--color-primary);
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Result item */
.result-item {
  display: flex;
  cursor: pointer;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.result-item:hover {
  border-color: var(--color-border-hover);
  box-shadow: var(--shadow-card);
}

.result-type-bar {
  width: 3px;
  flex-shrink: 0;
}

.type-product { background: var(--color-primary); }
.type-method { background: var(--color-secondary); }
.type-application { background: #8B5CF6; }
.type-protocol { background: #3B82F6; }
.type-reference { background: var(--color-text-secondary); }

.result-body {
  flex: 1;
  padding: 14px 16px;
  min-width: 0;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.result-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.result-summary-text {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.45;
  margin: 4px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 6px;
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

.result-slug {
  color: var(--color-primary);
  font-size: 12px;
  opacity: 0.7;
}

/* Loading & empty */
.skeleton-item {
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
}

.loading-container, .empty-container {
  padding: 60px 0;
  text-align: center;
}

@media (max-width: 768px) {
  .results-layout {
    grid-template-columns: 1fr;
  }
}
</style>
