<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useMethodsStore } from '@/stores/methods'
import MethodCard from '@/components/cards/MethodCard.vue'
import { AppButton } from '@/components/common'

const router = useRouter()
const store = useMethodsStore()
const searchQuery = ref('')
const currentPage = ref(1)
// ★ 2026-10-26（方案 B）：默认 active —— 对齐首页 "Browse 93" 的数字。
//   此前默认 'all' 且 handleFilter 根本没把筛选传给 API ⇒ staff 进来看到 47,927
//   （含 47,834 个只有名字、零描述的 draft），与首页 93 矛盾。
const activeFilter = ref('active')

const filters = [
  { key: 'all', label: 'All Methods' },
  { key: 'active', label: 'Active' },
  { key: 'draft', label: 'Draft' },
]

/**
 * 把筛选状态翻译成 API 参数。
 *
 * 注意后端两段过滤的顺序：`apply_public_visibility` 先按 status 公开态过滤，
 * DjangoFilterBackend 的 `?status=` 再过滤一次。所以看非公开态必须**同时**
 * 带 `include_unpublished=1`，否则会被前一段先筛成 active、再按 draft 筛成空。
 * `include_unpublished` 对非 staff 一律无效（后端先判身份），所以匿名访客
 * 点 "All" / "Draft" 仍只会看到 active，不需要前端额外判断身份。
 */
function buildParams(extra = {}) {
  const p = { search: searchQuery.value, ...extra }
  if (activeFilter.value === 'all') {
    p.include_unpublished = 1
  } else if (activeFilter.value === 'draft') {
    p.include_unpublished = 1
    p.status = 'draft'
  }
  // 'active'：什么都不传 —— 后端默认只返回公开态
  return p
}

onMounted(() => {
  store.fetchMethods(buildParams())
})

function handleSearch() {
  currentPage.value = 1
  store.fetchMethods(buildParams())
}

function handlePageChange(page) {
  currentPage.value = page
  store.fetchMethods(buildParams({ page }))
}

function handleFilter(filter) {
  activeFilter.value = filter
  currentPage.value = 1
  store.fetchMethods(buildParams())
}

function goToDetail(method) {
  router.push(`/methods/${method.id}`)
}

const resultCount = computed(() => store.total || store.methods.length)
</script>

<template>
  <div class="method-index">
    <div class="page-header">
      <div class="header-row">
        <div>
          <h1 class="page-title">Methods</h1>
          <p class="page-subtitle">Scientific workflow families for nucleotide and click chemistry research.</p>
        </div>
        <span class="result-badge">{{ resultCount }} items</span>
      </div>
      <div class="filter-bar">
        <el-input
          v-model="searchQuery"
          placeholder="Search methods..."
          prefix-icon="Search"
          clearable
          size="default"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
          class="search-input"
        />
        <AppButton variant="primary" @click="handleSearch">Search</AppButton>
      </div>
      <div class="filter-chips">
        <button
          v-for="f in filters"
          :key="f.key"
          class="filter-chip"
          :class="{ active: activeFilter === f.key }"
          @click="handleFilter(f.key)"
        >
          {{ f.label }}
        </button>
      </div>
    </div>

    <div v-if="store.loading" class="loading-grid">
      <div v-for="i in 4" :key="i" class="skeleton-card">
        <el-skeleton :rows="3" animated />
      </div>
    </div>

    <div v-else-if="store.methods.length === 0" class="empty-container">
      <el-empty description="No methods found">
        <AppButton variant="ghost" @click="searchQuery = ''; handleSearch()">Clear</AppButton>
      </el-empty>
    </div>

    <div v-else>
      <div class="card-grid">
        <MethodCard
          v-for="method in store.methods"
          :key="method.id"
          :method="method"
          @click="goToDetail(method)"
        />
      </div>

      <div v-if="store.total > 20" class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="20"
          :total="store.total"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.method-index {
  max-width: var(--content-max-width);
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
  /* ★ 2026-10-21 修 D7：--color-secondary 是 emerald-400，作**字色**只有 1.82:1
     （`--color-secondary` 保留给边框/装饰等不需要文字对比度的地方） */
  color: var(--color-primary);
  background: var(--color-secondary-soft);
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
  border-color: var(--color-secondary);
  color: var(--color-secondary);
}

.filter-chip.active {
  /* ★ 2026-10-21 修 D7：白字压 emerald-400 只有 1.92:1 ⇒ 激活底用 primary(emerald-700)=5.48:1 */
  background: var(--color-primary);
  border-color: var(--color-secondary);
  color: white;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.loading-grid {
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

.empty-container {
  padding: 60px 0;
  text-align: center;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}
</style>
