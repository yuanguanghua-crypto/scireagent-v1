<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getConvergenceClasses } from '@/api/convergence'

// 收敛类聚合浏览 Tab（Step 3）
// 用于 RG/AP 列表页的「Browse by Class」Tab：三级导航第一级（类列表）。
// 全部使用本地 ref 状态，不建 Pinia store，保持轻量。
const props = defineProps({
  group: { type: String, required: true }, // 'rg' | 'ap'
})

const router = useRouter()

// ── 本地状态（ref 声明在前，避免 watch/computed TDZ） ──
const classes = ref([]) // 类列表数据
const total = ref(0) // 后端返回的总数（data.total）
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const failed = ref(false) // 请求失败 → 静默降级为空态
const searchQuery = ref('') // 类名搜索（防抖）
const sourceFilter = ref('') // 来源过滤：'' | curated | high_freq | kmeans

const sourceOptions = [
  { label: 'All Sources', value: '' },
  { label: 'Curated', value: 'curated' },
  { label: 'High Frequency', value: 'high_freq' },
  { label: 'KMeans', value: 'kmeans' },
]

// ── 来源徽标映射 ──
const sourceBadgeMap = {
  curated: { type: 'primary', label: '策展' },
  high_freq: { type: 'success', label: '高频' },
  kmeans: { type: 'info', label: '聚合' },
}

/** 低内聚提示：kmeans 类且 avg_cos < 0.60 → 类名可能误导（如 assay 大杂烩） */
function isLowCohesion(row) {
  return row.source === 'kmeans' && row.avg_cos != null && Number(row.avg_cos) < 0.6
}

function formatAvgCos(row) {
  // avg_cos 仅 kmeans 类存在；保留 2 位小数，其余显示 —
  if (row.source === 'kmeans' && row.avg_cos != null) {
    return Number(row.avg_cos).toFixed(2)
  }
  return '—'
}

// ── 数据加载 ──
async function fetchClasses() {
  loading.value = true
  failed.value = false
  try {
    const result = await getConvergenceClasses({
      group: props.group,
      search: searchQuery.value || undefined,
      source: sourceFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    classes.value = result?.data?.items || []
    total.value = result?.data?.total || 0
  } catch (err) {
    // 静默降级：请求失败不抛错，展示「聚合数据暂不可用」空态
    failed.value = true
    classes.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// ── 搜索防抖（300ms） ──
let debounceTimer = null
function handleSearchInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    page.value = 1
    fetchClasses()
  }, 300)
}

// 来源切换：重置页码并重新加载
function handleSourceChange() {
  page.value = 1
  fetchClasses()
}

function handlePageChange(nextPage) {
  page.value = nextPage
  fetchClasses()
}

// ── 行点击 → 收敛类详情页（按 group 选择不同 name 的路由） ──
function handleRowClick(row) {
  const detailName = props.group === 'ap' ? 'ConvergenceClassDetailAp' : 'ConvergenceClassDetailRg'
  router.push({ name: detailName, params: { group: props.group, class_id: row.class_id } })
}

onMounted(() => {
  fetchClasses()
})
</script>

<template>
  <div class="convergence-browse-tab">
    <!-- 筛选栏：类名搜索 + 来源过滤 -->
    <div class="filter-bar">
      <el-input
        v-model="searchQuery"
        placeholder="Search classes..."
        clearable
        class="convergence-search"
        @input="handleSearchInput"
        @clear="handleSearchInput"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="sourceFilter"
        placeholder="Source"
        class="convergence-source"
        @change="handleSourceChange"
      >
        <el-option
          v-for="opt in sourceOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </div>

    <!-- 加载中骨架屏 -->
    <div v-if="loading && !classes.length" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 静默降级：请求失败空态（不抛错） -->
    <div v-else-if="failed" class="failed-state">
      <el-empty description="聚合数据暂不可用" />
    </div>

    <!-- 类表格 -->
    <el-card v-else-if="classes.length" class="classes-table-card">
      <el-table
        :data="classes"
        stripe
        highlight-current-row
        @row-click="handleRowClick"
        style="cursor: pointer"
      >
        <!-- 类名（加粗）+ 低内聚提示 -->
        <el-table-column label="Class Name" min-width="260">
          <template #default="{ row }">
            <div class="class-name-cell">
              <span class="class-name">{{ row.name }}</span>
              <el-tooltip
                v-if="isLowCohesion(row)"
                content="该类聚合了多种不同方法，请以成员列表为准"
                placement="top"
              >
                <el-tag type="warning" size="small" effect="plain" class="low-cohesion-tag">
                  混合方法
                </el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="class_id" label="Class ID" width="120" />

        <!-- 来源徽标 -->
        <el-table-column label="Source" width="110">
          <template #default="{ row }">
            <el-tag
              :type="sourceBadgeMap[row.source]?.type || 'info'"
              size="small"
              effect="plain"
            >
              {{ sourceBadgeMap[row.source]?.label || row.source || '—' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="size" label="Members" width="100" align="center">
          <template #default="{ row }">
            <span class="count-value">{{ row.size ?? 0 }}</span>
          </template>
        </el-table-column>

        <!-- avg_cos：仅 kmeans 类显示实际值，其余显示 — -->
        <el-table-column label="Avg Cos" width="100" align="center">
          <template #default="{ row }">
            <span class="cos-value">{{ formatAvgCos(row) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 空数据（搜索无结果等） -->
    <div v-else class="empty-state">
      <el-empty description="暂无聚合类" />
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="pagination-bar">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.convergence-browse-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.convergence-search {
  max-width: 320px;
}

.convergence-source {
  width: 180px;
}

.loading-state {
  padding: 24px;
}

.class-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.class-name {
  font-weight: 600;
  color: var(--color-text);
}

.low-cohesion-tag {
  flex-shrink: 0;
}

.count-value {
  font-weight: 600;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.cos-value {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.classes-table-card {
  background: var(--color-surface);
}

.empty-state {
  padding: 48px 0;
}

.failed-state {
  padding: 48px 0;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}
</style>
