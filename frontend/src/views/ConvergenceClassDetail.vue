<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getConvergenceClass } from '@/api/convergence'

// 收敛类详情页（Step 3）：三级导航第二级 → 第三级（类内实体列表 → 实体详情）。
// 路由 params：group（'rg'|'ap'）、class_id（如 rg_c001 / ap_k011）。
// 请求失败 / 成员为空时展示空态，不崩。
const props = defineProps({
  group: { type: String, required: true }, // 'rg' | 'ap'
  class_id: { type: String, required: true }, // 如 rg_c001 / ap_k011
})

const router = useRouter()

// ── 本地状态 ──
const detail = ref(null) // 收敛类详情（含成员列表）
const members = ref([])
const memberTotal = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const failed = ref(false)

// 返回浏览列表路径（rg → /research-goals，ap → /applications），并携带 tab=class 定位聚合 Tab
const backPath = computed(() => {
  const base = props.group === 'ap' ? '/applications' : '/research-goals'
  return `${base}?tab=class`
})

// 成员详情路由名：rg → ResearchGoalDetail，ap → ApplicationDetail
const memberDetailRouteName = computed(() =>
  props.group === 'ap' ? 'ApplicationDetail' : 'ResearchGoalDetail'
)

// 关联数列头：rg 显示「协议数」/ ap 显示「关联数」
const memberCountHeader = computed(() => (props.group === 'ap' ? '关联数' : '协议数'))

// ── 来源徽标映射（与浏览列表一致） ──
const sourceBadgeMap = {
  curated: { type: 'primary', label: '策展' },
  high_freq: { type: 'success', label: '高频' },
  kmeans: { type: 'info', label: '聚合' },
}

/** 低内聚提示：kmeans 类且 avg_cos < 0.60 → 类名可能误导，提示以成员列表为准 */
function isLowCohesion() {
  return detail.value?.source === 'kmeans' && detail.value.avg_cos != null && Number(detail.value.avg_cos) < 0.6
}

// ── 成员 origin 徽标：human_curated/imported → 策展；ai_extracted → AI；其余显示原值 ──
function originBadge(origin) {
  if (origin === 'human_curated' || origin === 'imported') {
    return { type: 'primary', label: '策展' }
  }
  if (origin === 'ai_extracted') {
    return { type: 'info', label: 'AI' }
  }
  return { type: 'info', label: origin || '—' }
}

// ── 数据加载 ──
async function fetchDetail() {
  loading.value = true
  failed.value = false
  try {
    const result = await getConvergenceClass(props.class_id, {
      page: page.value,
      page_size: pageSize,
    })
    detail.value = result?.data || null
    members.value = result?.data?.members || []
    memberTotal.value = result?.meta?.member_total || 0
  } catch (err) {
    // 请求失败（404 等）：展示空态 + 提示，不崩
    failed.value = true
    detail.value = null
    members.value = []
    memberTotal.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(nextPage) {
  page.value = nextPage
  fetchDetail()
}

// 成员名称点击 → 实体详情页（rg → /research-goals/:id，ap → /applications/:id）
function goMemberDetail(row) {
  router.push({ name: memberDetailRouteName.value, params: { id: row.id } })
}

onMounted(() => {
  fetchDetail()
})
</script>

<template>
  <div class="convergence-class-detail">
    <!-- 加载中骨架屏 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 请求失败空态 -->
    <div v-else-if="failed" class="empty-container">
      <el-empty description="收敛类信息暂不可用">
        <el-button type="primary" link @click="router.push(backPath)">返回浏览列表</el-button>
      </el-empty>
    </div>

    <!-- 详情 -->
    <template v-else-if="detail">
      <!-- 返回浏览列表 -->
      <div class="back-row">
        <el-button type="primary" link class="back-link" @click="router.push(backPath)">
          ← 返回浏览列表
        </el-button>
      </div>

      <!-- 类名大标题 + 徽标 -->
      <div class="detail-header">
        <h1 class="class-detail-title">{{ detail.name }}</h1>
        <div class="header-tags">
          <el-tag
            :type="sourceBadgeMap[detail.source]?.type || 'info'"
            size="small"
            effect="plain"
          >
            {{ sourceBadgeMap[detail.source]?.label || detail.source || '—' }}
          </el-tag>
          <el-tooltip
            v-if="isLowCohesion()"
            content="该类聚合了多种不同方法，请以成员列表为准"
            placement="top"
          >
            <el-tag type="warning" size="small" effect="plain">混合方法</el-tag>
          </el-tooltip>
          <el-tag size="small" type="info" effect="plain">Members: {{ detail.size ?? 0 }}</el-tag>
          <el-tag
            v-if="detail.avg_cos != null"
            size="small"
            type="info"
            effect="plain"
          >
            Avg Cos: {{ Number(detail.avg_cos).toFixed(2) }}
          </el-tag>
        </div>
      </div>

      <!-- 成员列表 -->
      <section class="member-section">
        <h2 class="section-title">Members</h2>

        <el-card v-if="members.length" class="members-table-card">
          <el-table :data="members" stripe>
            <el-table-column label="Name" min-width="260">
              <template #default="{ row }">
                <el-link type="primary" :underline="false" class="member-link" @click="goMemberDetail(row)">
                  {{ row.name }}
                </el-link>
              </template>
            </el-table-column>

            <el-table-column prop="slug" label="Slug" min-width="200">
              <template #default="{ row }">
                <span class="slug-value">{{ row.slug || '—' }}</span>
              </template>
            </el-table-column>

            <!-- origin 徽标 -->
            <el-table-column label="Origin" width="110">
              <template #default="{ row }">
                <el-tag :type="originBadge(row.origin).type" size="small" effect="plain">
                  {{ originBadge(row.origin).label }}
                </el-tag>
              </template>
            </el-table-column>

            <!-- 关联数：rg=协议数，ap=关联数 -->
            <el-table-column :label="memberCountHeader" width="100" align="center">
              <template #default="{ row }">
                <span class="count-value">{{ row.n ?? 0 }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 成员为空（匿名下常见） → 空态，不崩 -->
        <div v-else class="empty-container">
          <el-empty description="暂无可见成员" />
        </div>

        <div v-if="memberTotal > pageSize" class="pagination-bar">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="memberTotal"
            layout="prev, pager, next, total"
            @current-change="handlePageChange"
          />
        </div>
      </section>
    </template>

    <!-- 兜底空态（detail 为 null 且未失败，理论上不会走到） -->
    <div v-else class="empty-container">
      <el-empty description="收敛类不存在">
        <el-button type="primary" link @click="router.push(backPath)">返回浏览列表</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.convergence-class-detail {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.loading-container {
  padding: 24px;
}

.back-row {
  margin-bottom: 4px;
}

.back-link {
  font-size: 14px;
}

.detail-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.class-detail-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}

.header-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 12px 0;
}

.member-link {
  font-weight: 600;
}

.slug-value {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.count-value {
  font-weight: 600;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.members-table-card {
  background: var(--color-surface);
}

.empty-container {
  padding: 48px 0;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}
</style>
