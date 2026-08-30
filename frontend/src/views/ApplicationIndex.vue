<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import ApplicationCard from '@/components/cards/ApplicationCard.vue'
import ConvergenceBrowseTab from '@/components/convergence/ConvergenceBrowseTab.vue'

const router = useRouter()
const route = useRoute()
const store = useApplicationsStore()

// 双层结构 Step 3：页面顶部加 el-tabs
// Tab 1「All Applications」（原卡片内容），Tab 2「Browse by Class」（收敛类聚合浏览）
// 支持 ?tab=class 查询参数定位聚合 Tab（从收敛类详情页返回时使用）
const activeTab = ref(route.query.tab === 'class' ? 'class' : 'all')

const statusFilters = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'draft', label: 'Draft' },
  { key: 'deprecated', label: 'Deprecated' },
]

const activeFilter = ref('all')

onMounted(() => {
  store.fetchApplications()
})

function handleSearch() {
  store.fetchApplications()
}

function handleFilter(key) {
  activeFilter.value = key
  store.setFilters({ status: key === 'all' ? '' : key })
}

function handleCardClick(application) {
  router.push({ name: 'ApplicationDetail', params: { id: application.id } })
}

function handlePageChange(page) {
  store.setPage(page)
  store.fetchApplications()
}

watch(
  () => store.filters.search,
  () => { store.fetchApplications() }
)
</script>

<template>
  <div class="application-index">
    <el-tabs v-model="activeTab" class="index-tabs">
      <!-- Tab 1：全部 Applications（原有卡片内容原样移入） -->
      <el-tab-pane label="All Applications" name="all">
    <div class="page-header">
      <div class="header-row">
        <div>
          <h1 class="page-title">Applications</h1>
          <p class="page-subtitle">Browse scientific applications and their associated reagents and methods.</p>
        </div>
        <span class="result-badge">{{ store.applications.length }} items</span>
      </div>
      <div class="filter-bar">
        <el-input
          v-model="store.filters.search"
          placeholder="Search applications..."
          clearable
          size="default"
          class="search-input"
          @input="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <div class="filter-chips">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          class="filter-chip"
          :class="{ active: activeFilter === f.key }"
          @click="handleFilter(f.key)"
        >
          {{ f.label }}
        </button>
      </div>
    </div>

    <div v-if="store.loading && !store.applications.length" class="loading-state">
      <div class="card-grid">
        <div v-for="i in 6" :key="i" class="skeleton-card">
          <el-skeleton :rows="3" animated />
        </div>
      </div>
    </div>

    <div v-else-if="store.applications.length" class="card-grid">
      <ApplicationCard
        v-for="app in store.applications"
        :key="app.id"
        :application="app"
        @click="handleCardClick"
      />
    </div>

    <div v-else class="empty-state">
      <el-empty description="No applications found" />
    </div>

    <div v-if="store.pagination.total > store.pagination.pageSize" class="pagination-bar">
      <el-pagination
        v-model:current-page="store.pagination.page"
        :page-size="store.pagination.pageSize"
        :total="store.pagination.total"
        layout="prev, pager, next, total"
        @current-change="handlePageChange"
      />
    </div>
      </el-tab-pane>

      <!-- Tab 2：收敛类聚合浏览（双层结构 Step 3） -->
      <el-tab-pane label="Browse by Class" name="class">
        <ConvergenceBrowseTab group="ap" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.application-index {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* Tab 内容间距（page-header / 卡片网格 / 分页） */
.index-tabs :deep(.el-tab-pane) {
  padding-top: 8px;
}

.page-header {
  margin-bottom: 20px;
}

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.page-title {
  font-size: 22px;
  font-weight: 800;
  color: var(--color-text);
  margin: 0 0 4px;
  letter-spacing: -0.01em;
}

.page-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.result-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-domain-nucleotide);
  background: var(--color-domain-nucleotide-soft);
  padding: 4px 10px;
  border-radius: var(--radius-full);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.search-input {
  max-width: 380px;
}

.filter-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-chip {
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-chip:hover {
  border-color: var(--color-domain-nucleotide);
  color: var(--color-domain-nucleotide);
}

.filter-chip.active {
  background: var(--color-domain-nucleotide);
  border-color: var(--color-domain-nucleotide);
  color: white;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.skeleton-card {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.empty-state {
  padding: 60px 0;
  text-align: center;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  padding-top: 20px;
}
</style>
