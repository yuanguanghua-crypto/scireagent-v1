<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApplicationsStore } from '@/stores/applications'
import { useAuthStore } from '@/stores/auth'
import ApplicationCard from '@/components/cards/ApplicationCard.vue'
import ConvergenceBrowseTab from '@/components/convergence/ConvergenceBrowseTab.vue'

const router = useRouter()
const route = useRoute()
const store = useApplicationsStore()
const auth = useAuthStore()

// 双层结构 Step 3：页面顶部加 el-tabs
// Tab 1「All Applications」（原卡片内容），Tab 2「Browse by Class」（收敛类聚合浏览）
// 支持 ?tab=class 查询参数定位聚合 Tab（从收敛类详情页返回时使用）
const activeTab = ref(route.query.tab === 'class' ? 'class' : 'all')

// ★ 2026-11-18（S4 / A-123）：状态芯片加 isStaff 守卫。
//   后端对非 staff 的 list 一律只返回 active（`fixture_visibility.apply_public_visibility`，
//   Application 的 public_statuses = ['active']），所以对研究者而言
//   「All」和「Active」两个芯片点下去是**同一批结果**，「Draft」「Deprecated」则是
//   永远空表 —— 三个芯片是纯噪声，且会让人误以为站内有草稿/已弃用的应用。
//   因此非 staff 不渲染芯片栏（只剩「全部公开应用」这一种语义）。
const statusFiltersAll = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'draft', label: 'Draft' },
  { key: 'deprecated', label: 'Deprecated' },
]
const statusFilters = computed(() => (auth.isStaff ? statusFiltersAll : []))

const activeFilter = ref('all')

onMounted(() => {
  store.fetchApplications()
})

/**
 * ★ 2026-11-20（S4 / A-141 收口）：把「改条件 → 重取数据」收成两个**显式**处理器，
 * 并**删掉对 `filters.search` 的 watch**。原实现有两处毛病，其实是同一个病：
 *
 * ① 状态芯片是死控件（QA A-141 报的现象）：`handleFilter` 只 `setFilters({status})`
 *    不发请求，而 `watch` 只盯 `filters.search`、不盯 `status`
 *    ⇒ 点「Draft」「Deprecated」后列表纹丝不动，看上去像筛选没生效。
 *
 * ② 搜索框三条路管同一件事：`v-model="store.filters.search"` + `@input="handleSearch"`
 *    + `watch(() => store.filters.search)` ⇒ **每敲一个字符发两次一模一样的请求**
 *    （handleSearch 一次、watch 一次）。两个响应谁后到谁覆盖，翻页时还会错页。
 *
 * 现在与 `MethodIndex.vue:58-72` / `ProtocolIndex.vue:117-126` 同构：
 * 本地事件显式触发，一个事件 = 一次请求，没有隐式 watch。
 *
 * 后端无需改：`ApplicationFilter.Meta.fields` 已含 `status`
 * （`backend/apps/knowledge/api/v1/filters.py:22`），且 `apply_public_visibility`
 * 对 **staff 绕过** status 公开态过滤（`.../fixture_visibility.py:84`
 * `if statuses and not is_staff_request(request)`），所以 staff 点 Draft 真的能拿到草稿。
 * 芯片本身只对 staff 渲染（见上方 A-123 注释），匿名访客拿不到这条路径。
 */
function handleSearch() {
  // 换关键词必须回第 1 页：否则停在第 3 页输入新关键词会拿到一个空表，
  // 而结果总数又显示有命中 —— 看起来像搜索坏了。
  store.setPage(1)
  store.fetchApplications()
}

function handleFilter(key) {
  activeFilter.value = key
  // setFilters 内部已把 page 重置为 1，不必再 setPage
  store.setFilters({ status: key === 'all' ? '' : key })
  store.fetchApplications()
}

function handleCardClick(application) {
  router.push({ name: 'ApplicationDetail', params: { id: application.id } })
}

function handlePageChange(page) {
  store.setPage(page)
  store.fetchApplications()
}

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
        <!-- ★ 2026-10-26：改为显示**总数**。原先是 store.applications.length（当前页数组，
             固定 20 条），与首页卡片写的 28564 直接矛盾。统一用 pagination.total，
             与 Methods / Protocols / Research Goals 三页口径一致。 -->
        <span class="result-badge">{{ store.pagination.total }} items</span>
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
      <!-- ★ 2026-11-18（S4 / A-123）：容器也要 v-if，否则非 staff 会留下一条空的
           `.filter-chips`（flex + gap），在页面上表现为一段莫名的空白。 -->
      <div v-if="statusFilters.length" class="filter-chips" data-testid="status-chips">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          class="filter-chip"
          :data-testid="`status-chip-${f.key}`"
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
