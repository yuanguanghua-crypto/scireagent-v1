<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import ApplicationCard from '@/components/cards/ApplicationCard.vue'

const router = useRouter()
const store = useApplicationsStore()

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
  </div>
</template>

<style scoped>
.application-index {
  max-width: 1200px;
  margin: 0 auto;
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
  color: #8B5CF6;
  background: #EDE9FE;
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
  border-color: #8B5CF6;
  color: #8B5CF6;
}

.filter-chip.active {
  background: #8B5CF6;
  border-color: #8B5CF6;
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
