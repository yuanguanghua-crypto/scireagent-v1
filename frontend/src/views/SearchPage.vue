<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { searchGrouped } from '@/api/search'

const route = useRoute()
const router = useRouter()
const searchQuery = ref('')
const loading = ref(false)
const grouped = ref({ products: [], applications: [], methods: [], protocols: [], references: [] })
const totalCount = ref(0)
const activeTab = ref('all')

const tabs = [
  { key: 'all', label: 'All' },
  { key: 'products', label: 'Products' },
  { key: 'applications', label: 'Applications' },
  { key: 'methods', label: 'Methods' },
  { key: 'protocols', label: 'Protocols' },
  { key: 'references', label: 'References' },
]

const tabCounts = computed(() => {
  const counts = {}
  let total = 0
  for (const key of Object.keys(grouped.value)) {
    counts[key] = grouped.value[key]?.length || 0
    total += counts[key]
  }
  counts.all = total
  return counts
})

const displayResults = computed(() => {
  if (activeTab.value === 'all') {
    // Flatten all groups for "All" tab
    const all = []
    for (const [type, items] of Object.entries(grouped.value)) {
      for (const item of (items || [])) {
        all.push({ ...item, _type: type })
      }
    }
    return all
  }
  return (grouped.value[activeTab.value] || []).map(i => ({ ...i, _type: activeTab.value }))
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
    const res = await searchGrouped(searchQuery.value)
    grouped.value = res.data || { products: [], applications: [], methods: [], protocols: [], references: [] }
    totalCount.value = res.meta?.count || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function goToResult(item) {
  const type = item._type || ''
  const typeMap = {
    products: '/products/',
    applications: '/applications/',
    methods: '/methods/',
    protocols: '/protocols/',
    references: null, // no reference detail page
  }
  const path = typeMap[type]
  if (path && item.id) {
    router.push(`${path}${item.id}`)
  }
}

function getTypeColor(type) {
  const map = { products: '#059669', applications: '#8B5CF6', methods: '#2563eb', protocols: '#d97706', references: '#64748b' }
  return map[type] || '#64748b'
}

function getTypeLabel(type) {
  const map = { products: 'Product', applications: 'Application', methods: 'Method', protocols: 'Protocol', references: 'Reference' }
  return map[type] || type
}

function getSubtitle(item) {
  if (item.catalog_no) return `${item.catalog_no}${item.cas ? ' | ' + item.cas : ''}`
  if (item.journal) return `${item.journal}${item.year ? ' (' + item.year + ')' : ''}`
  if (item.purpose) return item.purpose
  if (item.objective) return item.objective
  if (item.summary) return item.summary
  return ''
}
</script>

<template>
  <div class="search-page">
    <!-- Header -->
    <div class="search-header">
      <h1 class="page-title">Search</h1>
      <div class="search-bar">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search products, methods, protocols, applications..."
          class="search-input"
          @keyup.enter="doSearch"
        />
        <button class="search-btn" @click="doSearch">Search</button>
      </div>
    </div>

    <!-- Tabs -->
    <div v-if="totalCount > 0" class="search-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span class="tab-count">{{ tabCounts[tab.key] || 0 }}</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-container">
      <div v-for="i in 5" :key="i" class="skeleton-item"></div>
    </div>

    <!-- Results -->
    <div v-else-if="totalCount > 0" class="results-container">
      <p class="result-summary">
        <strong>{{ totalCount }}</strong> result(s) for "<em>{{ searchQuery }}</em>"
      </p>

      <!-- Grouped sections (All tab) -->
      <template v-if="activeTab === 'all'">
        <section v-for="tab in tabs.slice(1)" :key="tab.key" class="result-group" v-show="tabCounts[tab.key] > 0">
          <h2 class="group-title">
            <span class="group-dot" :style="{ background: getTypeColor(tab.key) }"></span>
            {{ tab.label }}
            <span class="group-count">{{ tabCounts[tab.key] }}</span>
          </h2>
          <div class="result-list">
            <article
              v-for="item in grouped[tab.key]"
              :key="item.id"
              class="result-item"
              @click="goToResult({ ...item, _type: tab.key })"
            >
              <div class="result-bar" :style="{ background: getTypeColor(tab.key) }"></div>
              <div class="result-body">
                <h3 class="result-name">{{ item.name || item.title }}</h3>
                <p v-if="getSubtitle(item)" class="result-subtitle">{{ getSubtitle(item) }}</p>
                <span v-if="item.score !== undefined" class="result-score">Score: {{ (item.score * 100).toFixed(0) }}%</span>
              </div>
              <span class="result-arrow">&rarr;</span>
            </article>
          </div>
        </section>
      </template>

      <!-- Single type tab -->
      <template v-else>
        <div class="result-list">
          <article
            v-for="item in displayResults"
            :key="item.id"
            class="result-item"
            @click="goToResult(item)"
          >
            <div class="result-bar" :style="{ background: getTypeColor(activeTab) }"></div>
            <div class="result-body">
              <h3 class="result-name">{{ item.name || item.title }}</h3>
              <p v-if="getSubtitle(item)" class="result-subtitle">{{ getSubtitle(item) }}</p>
              <span v-if="item.score !== undefined" class="result-score">Score: {{ (item.score * 100).toFixed(0) }}%</span>
            </div>
            <span class="result-arrow">&rarr;</span>
          </article>
        </div>
      </template>
    </div>

    <!-- Empty -->
    <div v-else-if="searchQuery" class="empty-container">
      <p class="empty-text">No results for "<strong>{{ searchQuery }}</strong>"</p>
      <p class="empty-hint">Try different keywords or check spelling.</p>
    </div>
  </div>
</template>

<style scoped>
.search-page { max-width: 1200px; margin: 0 auto; padding: 24px; }

/* Header */
.page-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0 0 14px; }
.search-bar { display: flex; gap: 8px; max-width: 600px; }
.search-input {
  flex: 1; height: 44px; padding: 0 14px;
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 14px; font-family: var(--font-sans); color: var(--color-text);
}
.search-input:focus { outline: none; border-color: var(--color-primary); }
.search-btn {
  height: 44px; padding: 0 20px;
  background: var(--color-primary); color: white; border: none;
  border-radius: var(--radius-md); font-size: 14px; font-weight: 600;
  cursor: pointer; font-family: var(--font-sans);
}
.search-btn:hover { opacity: 0.9; }

/* Tabs */
.search-tabs {
  display: flex; gap: 4px; margin: 20px 0 16px;
  border-bottom: 1px solid var(--color-border); padding-bottom: 0;
}
.tab-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px; background: transparent; border: none;
  border-bottom: 2px solid transparent;
  font-size: 13px; font-weight: 500; color: var(--color-text-secondary);
  cursor: pointer; font-family: var(--font-sans); transition: all 0.15s;
}
.tab-btn:hover { color: var(--color-text); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }
.tab-count {
  font-size: 11px; font-weight: 600; background: var(--color-bg);
  padding: 1px 6px; border-radius: 10px; color: var(--color-text-tertiary);
}
.tab-btn.active .tab-count { background: var(--color-primary-light); color: var(--color-primary); }

/* Results */
.result-summary { font-size: 13px; color: var(--color-text-secondary); margin: 0 0 16px; }
.result-summary strong { color: var(--color-text); }
.result-summary em { font-style: normal; color: var(--color-primary); }

/* Grouped sections */
.result-group { margin-bottom: 24px; }
.group-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 700; color: var(--color-text); margin: 0 0 10px;
}
.group-dot { width: 8px; height: 8px; border-radius: 50%; }
.group-count { font-size: 11px; font-weight: 600; color: var(--color-text-tertiary); }

/* Result items */
.result-list { display: flex; flex-direction: column; gap: 6px; }
.result-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; background: var(--color-surface);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  cursor: pointer; transition: all 0.15s;
}
.result-item:hover { border-color: var(--color-primary); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.result-bar { width: 3px; height: 32px; border-radius: 2px; flex-shrink: 0; }
.result-body { flex: 1; min-width: 0; }
.result-name { font-size: 14px; font-weight: 600; color: var(--color-text); margin: 0; }
.result-subtitle {
  font-size: 12px; color: var(--color-text-secondary); margin: 2px 0 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.result-score { font-size: 10px; color: var(--color-text-tertiary); margin-top: 2px; display: inline-block; }
.result-arrow { font-size: 16px; color: var(--color-text-tertiary); flex-shrink: 0; }

/* Loading */
.loading-container { display: flex; flex-direction: column; gap: 8px; margin-top: 16px; }
.skeleton-item {
  height: 60px; background: var(--color-bg); border-radius: var(--radius-md);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

/* Empty */
.empty-container { text-align: center; padding: 60px 0; }
.empty-text { font-size: 15px; color: var(--color-text); margin: 0 0 4px; }
.empty-hint { font-size: 13px; color: var(--color-text-tertiary); margin: 0; }

@media (max-width: 768px) {
  .search-page { padding: 16px; }
  .search-tabs { overflow-x: auto; }
}
</style>
