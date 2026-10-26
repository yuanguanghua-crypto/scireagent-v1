<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResearchGoalsStore } from '@/stores/researchGoals'
import { formatDate, getStatusType, truncate } from '@/utils/helpers'
import ConvergenceBrowseTab from '@/components/convergence/ConvergenceBrowseTab.vue'

const router = useRouter()
const route = useRoute()
const store = useResearchGoalsStore()

// 双层结构 Step 3：页面顶部加 el-tabs
// Tab 1「All Research Goals」（原列表内容），Tab 2「Browse by Class」（收敛类聚合浏览）
// 支持 ?tab=class 查询参数定位聚合 Tab（从收敛类详情页返回时使用）
const activeTab = ref(route.query.tab === 'class' ? 'class' : 'all')

onMounted(() => {
  store.fetchGoals()
})

function handleSearch(value) {
  store.setFilters({ search: value })
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
    <el-tabs v-model="activeTab" class="index-tabs">
      <!-- Tab 1：全部 Research Goals（原有内容原样移入） -->
      <el-tab-pane label="All Research Goals" name="all">
    <div class="page-header">
      <div class="header-info">
        <h2 class="section-title">Research Goals</h2>
        <p class="section-desc">
          Track and manage your research objectives and milestones.
        </p>
      </div>
      <!-- ★ 2026-10-26：补上总数徽标。此前本页顶部没有任何计数，
           首页卡片写 11036、点进来却看不到数字（只有翻到页底的 pagination
           显示 Total，且仅在总页数 > 1 时才渲染）。 -->
      <span class="result-badge">{{ store.pagination.total }} items</span>
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

      <!-- ★ 2026-10-26 删除 status 下拉（用户拍板）。
           它从来就没生效过：ResearchGoalViewSet 没配 filterset_fields，
           `?status=` 被 DjangoFilterBackend 直接丢弃 —— 实测匿名传
           active/draft/archived 全部返回 11036，选了等于没选。
           而且选项里的 `completed` 不是任何模型的合法状态
           （PublicationStatus 只有 draft/published/superseded/archived）。
           留着只会让人以为能筛。要恢复必须先在后端加 filterset_fields。 -->
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

        <el-table-column prop="summary" label="Summary" min-width="300">
          <template #default="{ row }">
            <span class="goal-desc">{{ truncate(row.summary, 80) }}</span>
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
      </el-tab-pane>

      <!-- Tab 2：收敛类聚合浏览（双层结构 Step 3） -->
      <el-tab-pane label="Browse by Class" name="class">
        <ConvergenceBrowseTab group="rg" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.research-goal-index {
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* Tab 内容沿用原有的纵向 flex 布局（page-header / filter-bar / 表格 / 分页 之间的间距） */
.index-tabs :deep(.el-tab-pane) {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-top: 16px;
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