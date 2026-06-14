<script setup>
import { onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useResearchGoalsStore } from '@/stores/researchGoals'
import { formatDate, getStatusType, truncate } from '@/utils/helpers'

const router = useRouter()
const store = useResearchGoalsStore()

const statusOptions = [
  { label: 'All', value: '' },
  { label: 'Active', value: 'active' },
  { label: 'Draft', value: 'draft' },
  { label: 'Completed', value: 'completed' },
]

onMounted(() => {
  store.fetchGoals()
})

function handleSearch(value) {
  store.setFilters({ search: value })
}

function handleStatusChange(value) {
  store.setFilters({ status: value })
}

function handleRowClick(row) {
  router.push({ name: 'ResearchGoalDetail', params: { id: row.id } })
}

function handlePageChange(page) {
  store.setPage(page)
  store.fetchGoals()
}

watch(
  () => store.filters.search,
  () => {
    store.fetchGoals()
  }
)
</script>

<template>
  <div class="research-goal-index">
    <div class="page-header">
      <div class="header-info">
        <h2 class="section-title">Research Goals</h2>
        <p class="section-desc">
          Track and manage your research objectives and milestones.
        </p>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="store.filters.search"
        placeholder="Search research goals..."
        clearable
        class="search-input"
        @input="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-select
        v-model="store.filters.status"
        placeholder="Status"
        clearable
        class="status-select"
        @change="handleStatusChange"
      >
        <el-option
          v-for="opt in statusOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </div>

    <div v-if="store.loading && !store.goals.length" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <el-card v-else-if="store.goals.length" class="goals-table-card">
      <el-table
        :data="store.goals"
        stripe
        highlight-current-row
        @row-click="handleRowClick"
        style="cursor: pointer"
      >
        <el-table-column prop="name" label="Goal Name" min-width="200">
          <template #default="{ row }">
            <span class="goal-name">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="Description" min-width="300">
          <template #default="{ row }">
            <span class="goal-desc">{{ truncate(row.description, 80) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="application_count" label="Applications" width="120" align="center">
          <template #default="{ row }">
            <span class="count-value">{{ row.application_count || 0 }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="Created" width="140">
          <template #default="{ row }">
            <span class="date-value">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div v-else class="empty-state">
      <el-empty description="No research goals found" />
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
.research-goal-index {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}

.section-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  max-width: 320px;
}

.status-select {
  width: 150px;
}

.goals-table-card {
  background: var(--color-surface);
}

.goal-name {
  font-weight: 600;
  color: var(--color-text);
}

.goal-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.count-value {
  font-weight: 600;
  color: var(--color-text);
}

.date-value {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.loading-state {
  padding: 24px;
}

.empty-state {
  padding: 48px 0;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  padding-top: 16px;
}
</style>