<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProtocolsStore } from '@/stores/protocols'
import { useAuthStore } from '@/stores/auth'
import ProtocolCard from '@/components/cards/ProtocolCard.vue'
import { AppButton } from '@/components/common'
import { getProtocolFacets } from '@/api/protocols'

const router = useRouter()
const store = useProtocolsStore()
const auth = useAuthStore()
const searchQuery = ref('')
const currentPage = ref(1)
// ★ 2026-10-26（方案 B）：默认 published —— 对齐首页 "Browse 14121" 的数字。
//   此前默认 'all' 且 handleFilter 没把筛选传给 API ⇒ staff 看到 14,128（含 7 draft）。
const activeFilter = ref('published')

// ── 分类导航（application 维度受控词表，2026-10-26 P0）───────────────────
// 14,121 条协议此前零导航，用户除了搜索无法探索。facet 数据早已存在
// （18 个 application 值覆盖 89.2%），这里只是把它暴露成 chip。
// ⚠️ 一个协议可挂多个分类 ⇒ 各 chip 数字之和 > 去重覆盖数，UI 上必须说明，
//    否则会被当成"数字对不上"（首页/列表计数已经踩过两次同类坑）。
const facets = ref([])
const facetMeta = ref(null)
const activeFacet = ref('')

async function loadFacets() {
  try {
    const res = await getProtocolFacets()
    const payload = res.data ?? res
    facets.value = Array.isArray(payload) ? payload : (payload.data || [])
    facetMeta.value = res.meta ?? null
  } catch {
    facets.value = []   // 导航加载失败不应阻断列表
  }
}

function selectFacet(slug) {
  activeFacet.value = activeFacet.value === slug ? '' : slug   // 再点一次取消
  currentPage.value = 1
  store.fetchProtocols(buildParams())
}

const filters = [
  { key: 'all', label: 'All Protocols' },
  { key: 'published', label: 'Published' },
  { key: 'draft', label: 'Draft' },
  { key: 'superseded', label: 'Superseded' },
]

/**
 * 把筛选状态翻译成 API 参数（同 MethodIndex 的处理，见那里的详细注释）：
 * 看非公开态必须同时带 `include_unpublished=1`，否则会被
 * `apply_public_visibility` 先筛成公开态、再按 status 筛成空。
 * 该参数对非 staff 无效，所以匿名访客行为不变。
 */
function buildParams(extra = {}) {
  const p = { search: searchQuery.value, ...extra }
  if (activeFilter.value !== 'published') {
    p.include_unpublished = 1
    if (activeFilter.value !== 'all') p.status = activeFilter.value
  }
  // 'published'：什么都不传 —— 后端默认只返回公开态
  if (activeFacet.value) p.facet = activeFacet.value
  return p
}

onMounted(() => {
  loadFacets()
  store.fetchProtocols(buildParams())
})

function handleSearch() {
  currentPage.value = 1
  store.fetchProtocols(buildParams())
}

function handlePageChange(page) {
  currentPage.value = page
  store.fetchProtocols(buildParams({ page }))
}

function handleFilter(filter) {
  activeFilter.value = filter
  currentPage.value = 1
  store.fetchProtocols(buildParams())
}

function goToDetail(protocol) {
  router.push(`/protocols/${protocol.id}`)
}

const resultCount = computed(() => store.total || store.protocols.length)
</script>

<template>
  <div class="protocol-index">
    <div class="page-header">
      <div class="header-row">
        <div>
          <h1 class="page-title">Protocols</h1>
          <p class="page-subtitle">Structured, versioned scientific procedures you can follow and cite.</p>
        </div>
        <span class="result-badge">{{ resultCount }} items</span>
      </div>
      <div class="filter-bar">
        <el-input
          v-model="searchQuery"
          placeholder="Search protocols..."
          prefix-icon="Search"
          clearable
          size="default"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
          class="search-input"
        />
        <AppButton variant="primary" @click="handleSearch">Search</AppButton>
      </div>
      <!-- ── 分类导航（application 维度）───────────────────────────────
           给**所有访客**看的业务维度导航，不是内部状态。
           此前 14,121 条协议零导航，用户只能靠搜索。
           ⚠️ 一个协议可属于多个研究领域 ⇒ 各数字之和 > 总数（下方已说明）。 -->
      <div v-if="facets.length" class="facet-nav">
        <button
          class="facet-chip"
          :class="{ active: !activeFacet }"
          @click="selectFacet('')"
        >
          全部领域
        </button>
        <button
          v-for="f in facets"
          :key="f.slug"
          class="facet-chip"
          :class="{ active: activeFacet === f.slug }"
          @click="selectFacet(f.slug)"
        >
          {{ f.value }}
          <span class="facet-count">{{ f.count }}</span>
        </button>
      </div>
      <p v-if="facets.length" class="facet-note">
        一个协议可能属于多个研究领域，因此各分类数字之和大于协议总数
      </p>


      <!-- ★ 2026-10-26：状态筛选器（All / Published / Draft / Superseded）只对内部人员有意义。
           访客实测：All 与 Published 结果相同（冗余），Draft / Superseded 都返回 0 条
           （看起来像网站坏了）—— 因为后端的 include_unpublished 对非 staff 无效。
           访客侧完全隐藏，只保留搜索框。 -->
      <div v-if="auth.isStaff" class="filter-chips">
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

    <div v-else-if="store.protocols.length === 0" class="empty-container">
      <el-empty description="No protocols found">
        <AppButton variant="ghost" @click="searchQuery = ''; handleSearch()">Clear</AppButton>
      </el-empty>
    </div>

    <div v-else>
      <div class="card-grid">
        <ProtocolCard
          v-for="protocol in store.protocols"
          :key="protocol.id"
          :protocol="protocol"
          @click="goToDetail(protocol)"
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
.protocol-index {
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
  color: var(--color-info);
  background: var(--color-info-light);
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

/* 分类导航 chip —— 与状态筛选器（filter-chips）视觉区分：这是主导航，更突出 */
.facet-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.facet-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
  transition: all .15s ease;
  white-space: nowrap;
}
.facet-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.facet-chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.facet-chip.active .facet-count {
  background: rgba(255, 255, 255, .25);
  color: #fff;
}
.facet-count {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.facet-note {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 14px;
}

/* 分类导航 chip —— 与状态筛选器（filter-chips）视觉区分：这是主导航，更突出 */
.facet-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.facet-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
  transition: all .15s ease;
  white-space: nowrap;
}
.facet-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.facet-chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}
.facet-chip.active .facet-count {
  background: rgba(255, 255, 255, .25);
  color: #fff;
}
.facet-count {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.facet-note {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 14px;
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
  border-color: var(--color-info);
  color: var(--color-info);
}

.filter-chip.active {
  background: var(--color-info);
  border-color: var(--color-info);
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
