<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/api/http'
import { toast, LoadingSpinner, EmptyState } from '@/components/common'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { archiveProduct, reactivateProduct, deleteProduct, getArchivedProducts, discontinueProduct, batchRestoreProducts } from '@/api/workspace/products'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

if (!auth.isStaff) {
  router.replace('/')
}

// ── 单一数据源 + 客户端分区（在售 / 回收站）────────
// staff-only ?archived=1 返回全部产品（正常+回收站），前端据 archived 自行分区，
// 一次请求同时拿到两个集合 → 切换零延迟、计数准确。
const allProducts = ref([])
const viewMode = ref(route.query.view === 'recycle' ? 'recycle' : 'active')
const products = computed(() => viewMode.value === 'recycle'
  ? allProducts.value.filter(p => p.archived === true)
  : allProducts.value.filter(p => p.archived !== true))
const recycleCount = computed(() => allProducts.value.filter(p => p.archived === true).length)

// ── 截断检测（Q5/Y3）────────────────────────────────
// 后端 StandardPagination.max_page_size = 500，请求已顶格；总数在 meta.pagination.count。
// 若 count > 实际拿到条数 ⇒ 说明被截断，必须告知用户（此前 count 被丢弃、静默截断）。
const PAGE_LIMIT = 500
const totalCount = ref(null)
const truncated = computed(() =>
  typeof totalCount.value === 'number' && totalCount.value > allProducts.value.length)

/** 统一消化列表响应：写 allProducts + 记录 totalCount（三处取数共用） */
function applyProductsResponse(resp) {
  if (!resp) return
  if (Array.isArray(resp.data)) allProducts.value = resp.data
  else if (resp.data && Array.isArray(resp.data.results)) allProducts.value = resp.data.results
  const c = resp?.meta?.pagination?.count
  totalCount.value = typeof c === 'number' ? c : null
}

const loading = ref(true)
const error = ref('')
const selectedIds = ref(new Set())

function setView(mode) {
  viewMode.value = mode
  selectedIds.value = new Set()
  closeMenu()
  statusFilter.value = 'all'
  // 用 push（非 replace）：`?view=` 是**可分享的深链状态**，既然进了 URL 就应进历史。
  // 若用 replace，用户误点 Recycle Bin 后按 Back 会被**踢出列表页**（退回 Dashboard）、
  // 丢失上下文。配套：下方 watch(route.query.view) 让 Back/Forward 真正驱动视图。
  router.push({ query: mode === 'recycle' ? { view: 'recycle' } : {} })
}

// Y5：URL 是视图状态的唯一可分享来源 —— 浏览器**前进/后退**改变 ?view= 时必须同步视图，
// 否则会出现「URL 已变、列表没变」（此前 viewMode 只在 setup 读一次 query，无 watch）。
// 与 setView 构成双向对齐。
watch(() => route.query.view, (v) => {
  const mode = v === 'recycle' ? 'recycle' : 'active'
  if (mode !== viewMode.value) {
    viewMode.value = mode
    selectedIds.value = new Set()
    closeMenu()
  }
})

// ── Sorting ──────────────────────────────────────
const sortField = ref('catalog_no')
const sortDir = ref('asc')

function toggleSort(field) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = 'asc'
  }
}

function sortIcon(field) {
  if (sortField.value !== field) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const sortedProducts = computed(() => {
  const list = [...products.value]
  const field = sortField.value
  // 知识关联度是数值列：用数值比较，且「无关联」(null) 始终沉底（与后端 nulls_last 一致）
  if (field === 'aggregate_relevance_score') {
    const toNum = (v) => (v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v))) ? null : Number(v)
    list.sort((a, b) => {
      const an = toNum(a.aggregate_relevance_score)
      const bn = toNum(b.aggregate_relevance_score)
      if (an === null && bn === null) return 0
      if (an === null) return 1   // a 沉底
      if (bn === null) return -1  // b 沉底
      const cmp = an - bn
      return sortDir.value === 'asc' ? cmp : -cmp
    })
    return list
  }
  list.sort((a, b) => {
    const av = a[field] ?? ''
    const bv = b[field] ?? ''
    const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' })
    return sortDir.value === 'asc' ? cmp : -cmp
  })
  return list
})

// ── Batch Knowledge Link ──────────────────────────
const showBatchLinkPanel = ref(false)
const batchLinkGoalId = ref('')
const batchLinkAppId = ref('')
const batchLinkMethodId = ref('')
const batchLinkProtocolId = ref('')
const batchLinkPreview = ref(null)
const batchLinkLoading = ref(false)
const batchOverlay = ref(null)
const batchAttrs = useDialogA11y(showBatchLinkPanel, batchOverlay, {
  titleId: 'batch-title',
  close: () => { showBatchLinkPanel.value = false },
})

const goals = ref([])
const applications = ref([])
const methods = ref([])
const protocols = ref([])

const selectedCount = computed(() => selectedIds.value.size)

const statusFilter = ref('all')
const completenessFilter = ref('all')

const completenessOptions = [
  { value: 'all', label: 'All' },
  { value: 'complete', label: 'Complete' },
  { value: 'incomplete', label: 'Incomplete' },
  { value: 'no-cas', label: 'No CAS' },
  { value: 'no-smiles', label: 'No SMILES' },
  { value: 'no-link', label: 'No Knowledge Link' },
  { value: 'no-category', label: 'No Category' },
]

const statusOptions = [
  { value: 'all', label: 'All Status' },
  { value: 'active', label: 'Active' },
  { value: 'draft', label: 'Draft' },
  { value: 'deprecated', label: 'Deprecated' },
  { value: 'archived', label: 'Unpublished' },
]

const filteredProducts = computed(() => {
  let list = sortedProducts.value
  if (statusFilter.value !== 'all') {
    list = list.filter(p => p.status === statusFilter.value)
  }
  switch (completenessFilter.value) {
    case 'complete': list = list.filter(p => p.is_complete); break
    case 'incomplete': list = list.filter(p => !p.is_complete); break
    case 'no-cas': list = list.filter(p => !p.cas); break
    case 'no-smiles': list = list.filter(p => !p.smiles); break
    // Q3/Y2：「无知识链接」= 列表 Knowledge Link 列的聚合值为空。
    // 与列显示同口径（`aggregate_relevance_score`），不再依赖 incomplete_items 里的
    // 中文文案做字符串匹配（旧实现 `i.includes('关联')` 会因文案改动而静默失效，
    // 且 is_complete 的 5 条件本就不含知识链接 ⇒ 语义失真）。
    case 'no-link': list = list.filter(p => p.aggregate_relevance_score === null || p.aggregate_relevance_score === undefined); break
    case 'no-category': list = list.filter(p => !p.product_class_id); break
  }
  return list
})

// ── Q1：空态分场景 ────────────────────────────────
// 单一文案会误导：回收站为空与「筛选条件」无关；而「在售视图为空但库里有产品」
// 意味着全部进了回收站（当前生产就是这个状态）—— 必须给出明确出口。
const emptyKind = computed(() => {
  if (allProducts.value.length === 0) return 'none-at-all'
  if (products.value.length === 0) {
    return viewMode.value === 'recycle' ? 'recycle-empty' : 'all-in-recycle'
  }
  if (filteredProducts.value.length === 0) return 'filtered-out'
  return null
})
const emptyTitle = computed(() => ({
  'none-at-all': 'No products yet',
  'recycle-empty': 'Recycle bin is empty',
  'all-in-recycle': 'No products in the catalog',
  'filtered-out': 'No products match the current filters',
}[emptyKind.value] || 'No products'))
const emptyDescription = computed(() => ({
  'none-at-all': 'Create your first product to get started.',
  'recycle-empty': 'Products you move to the recycle bin will appear here and can be restored at any time.',
  'all-in-recycle': `All ${recycleCount.value} products are currently in the recycle bin. Storefront shows nothing until they are restored.`,
  'filtered-out': 'Try clearing the status / completeness filters.',
}[emptyKind.value] || ''))
function clearFilters() {
  statusFilter.value = 'all'
  completenessFilter.value = 'all'
}

const allSelected = computed({
  get() {
    return filteredProducts.value.length > 0 && filteredProducts.value.every(p => selectedIds.value.has(p.id))
  },
  set(val) {
    filteredProducts.value.forEach(p => {
      if (val) selectedIds.value.add(p.id)
      else selectedIds.value.delete(p.id)
    })
  },
})

function toggleSelect(id) {
  if (selectedIds.value.has(id)) selectedIds.value.delete(id)
  else selectedIds.value.add(id)
}

function goToProduct(id) {
  router.push(`/workspace/products/${id}/edit`)
}

// ── Batch Knowledge Link Logic ───────────────────
async function loadKnowledgeOptions() {
  try {
    const [g, a, m, p] = await Promise.all([
      http.get('/research-goals/', { params: { page_size: 200 } }),
      http.get('/applications/', { params: { page_size: 200 } }),
      http.get('/methods/', { params: { page_size: 200 } }),
      http.get('/protocols/', { params: { page_size: 500 } }),
    ])
    // ★ 2026-09-22 修 B10：共享 `http` 实例的响应拦截器**已把信封解包**
    //   （`utils/http.js:73-75`：`if (data && data.success) return data`），
    //   调用方拿到的是 **body** ⇒ 这里只能取 `.data`，**不能再多一层 `.data`**。
    //   此前写成 `g.data?.data` ⇒ 恒落 `|| []` ⇒ 四个下拉恒空 ⇒ Batch Link 整块不可用。
    //   （同文件 `applyProductsResponse`(:37-43) 就是按 `resp.data`/`resp.meta` 写的，本处与之对齐。）
    goals.value = (g.data?.results || g.data || [])
    applications.value = (a.data?.results || a.data || [])
    methods.value = (m.data?.results || m.data || [])
    protocols.value = (p.data?.results || p.data || [])
  } catch (e) { /* ignore */ }
}

function openBatchLink() {
  batchLinkGoalId.value = ''; batchLinkAppId.value = ''
  batchLinkMethodId.value = ''; batchLinkProtocolId.value = ''
  batchLinkPreview.value = null
  loadKnowledgeOptions()
  showBatchLinkPanel.value = true
}

const filteredApps = computed(() => {
  if (!batchLinkGoalId.value) return applications.value
  return applications.value.filter(a => a.research_goal_id == batchLinkGoalId.value)
})
const filteredMethods = computed(() => {
  if (!batchLinkAppId.value) return methods.value
  return methods.value.filter(m => m.application_id == batchLinkAppId.value)
})

function previewBatchLink() {
  const ids = Array.from(selectedIds.value)
  const skipped = products.value.filter(p =>
    ids.includes(p.id) && p.is_complete &&
    !((p.incomplete_items || []).some(i => i.includes('关联')))
  )
  batchLinkPreview.value = {
    total: ids.length,
    willLink: ids.length - skipped.length,
    skipped: skipped.length,
    ids,
  }
}

async function applyBatchLink() {
  if (!batchLinkMethodId.value || !selectedIds.value.size) return
  batchLinkLoading.value = true
  try {
    const ids = Array.from(selectedIds.value)
    for (const pid of ids) {
      const product = products.value.find(p => p.id === pid)
      if (!product) continue
      const methodIds = product.method_ids ? [...product.method_ids] : []
      if (batchLinkMethodId.value && !methodIds.includes(Number(batchLinkMethodId.value))) {
        methodIds.push(Number(batchLinkMethodId.value))
      }
      const protocolIds = product.protocol_ids ? [...product.protocol_ids] : []
      if (batchLinkProtocolId.value && !protocolIds.includes(Number(batchLinkProtocolId.value))) {
        protocolIds.push(Number(batchLinkProtocolId.value))
      }
      // ★ 2026-09-22 修 **B11**：原先用 `http.put()`（**全量更新**）却只传两个字段
      //   ⇒ 实测 **6ms 返回 400**：`"name: This field is required.; slug: This field is required."`
      //   ⇒ Batch Link 的 Apply **必然失败**（与下拉是否为空无关）。改用 `patch`（局部更新）
      //   —— 语义也更贴："只改桥，不动其它字段"。
      await http.patch(`/products/${pid}/`, { method_ids: methodIds, protocol_ids: protocolIds })
    }
    showBatchLinkPanel.value = false
    applyProductsResponse(await getArchivedProducts())
  } catch (e) {
    // P0-3: now supports research_goal_ids as well
    const msg = 'Batch link failed: ' + (e.response?.data?.meta?.error?.message || e.message)
    toast.error(msg)
  } finally {
    batchLinkLoading.value = false
  }
}

onMounted(async () => {
  try {
    applyProductsResponse(await getArchivedProducts())
  } catch (e) {
    error.value = 'Failed to load products'
  } finally {
    loading.value = false
  }
})

// ── 列表刷新 ───────────────────────────────────────
async function refreshProducts() {
  applyProductsResponse(await getArchivedProducts())
}

// ── 行内操作下拉菜单 ───────────────────────────────
const openMenuId = ref(null)

function toggleMenu(id) {
  openMenuId.value = openMenuId.value === id ? null : id
}

function closeMenu() { openMenuId.value = null }

function onMenuKeydown(e) {
  if (e.key === 'Escape') closeMenu()
}

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onMenuKeydown)
})

function onDocClick(e) {
  // 点击菜单外部关闭
  if (!e.target.closest('.row-actions')) closeMenu()
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onMenuKeydown)
})

// ── 下架 / 重新上架 / 删除 ─────────────────────────
// 删除二次确认：须勾选确认框才允许提交
const showDeleteDialog = ref(false)
const deleteTarget = ref(null)        // 单条删除目标 { id, name } 或 { batch: [...] }
const deleteConfirmChecked = ref(false)
const deleteLoading = ref(false)
const deleteOverlay = ref(null)
const deleteAttrs = useDialogA11y(showDeleteDialog, deleteOverlay, {
  titleId: 'delete-title',
  close: () => { showDeleteDialog.value = false },
})

// 下架确认
const showArchiveDialog = ref(false)
const archiveTargets = ref([])        // 单条或批量目标列表
const archiveLoading = ref(false)
const archiveOverlay = ref(null)
const archiveAttrs = useDialogA11y(showArchiveDialog, archiveOverlay, {
  titleId: 'archive-title',
  close: () => { showArchiveDialog.value = false },
})


function openDeleteOne(product) {
  deleteTarget.value = { id: product.id, name: product.name }
  deleteConfirmChecked.value = false
  showDeleteDialog.value = true
  closeMenu()
}

function openArchiveOne(product) {
  archiveTargets.value = [{ id: product.id, name: product.name }]
  showArchiveDialog.value = true
  closeMenu()
}

function openBatchArchive() {
  const ids = Array.from(selectedIds.value)
  archiveTargets.value = ids.map(id => {
    const p = products.value.find(x => x.id === id)
    return { id, name: p?.name || `#${id}` }
  })
  showArchiveDialog.value = true
}

function openBatchDelete() {
  const ids = Array.from(selectedIds.value)
  const targets = ids.map(id => {
    const p = products.value.find(x => x.id === id)
    return { id, name: p?.name || `#${id}` }
  })
  // 批量删除：复用单条弹窗，提示信息改为多条
  deleteTarget.value = { id: null, name: '', batch: targets }
  deleteConfirmChecked.value = false
  showDeleteDialog.value = true
}

async function confirmArchive() {
  archiveLoading.value = true
  let ok = 0, fail = 0
  try {
    for (const t of archiveTargets.value) {
      try {
        await archiveProduct(t.id)
        ok++
      } catch { fail++ }
    }
    await refreshProducts()
    showArchiveDialog.value = false
    selectedIds.value = new Set()
    if (fail === 0) toast.success(`Unpublished ${ok} products`)
    else toast.warning(`Unpublished ${ok}, failed ${fail}`)
  } finally {
    archiveLoading.value = false
  }
}

async function reactivate(product) {
  try {
    await reactivateProduct(product.id)
    await refreshProducts()
    toast.success(`${product.name} republished`)
  } catch (e) {
    toast.error('Republish failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  }
  closeMenu()
}

// S4-4f 退出目录（停产）：status='deprecated'。与「回收站」不同 —— 货号不释放、
// 公开详情页保留（只是退出店铺列表与在售状态）。真实网站里这才是「下架商品」的正解，
// 回收站只用于撤销误操作。
async function discontinue(product) {
  try {
    await discontinueProduct(product.id)
    await refreshProducts()
    toast.success(`${product.name} discontinued`)
  } catch (e) {
    toast.error('Discontinue failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  }
  closeMenu()
}

async function confirmDelete() {
  if (!deleteConfirmChecked.value) return
  deleteLoading.value = true
  let ok = 0, fail = 0
  try {
    const targets = deleteTarget.value.batch
      ? deleteTarget.value.batch
      : [deleteTarget.value]
    for (const t of targets) {
      try {
        await deleteProduct(t.id)
        ok++
      } catch { fail++ }
    }
    await refreshProducts()
    showDeleteDialog.value = false
    selectedIds.value = new Set()
    if (fail === 0) toast.success(`Moved ${ok} products to the recycle bin`)
    else toast.warning(`Moved ${ok}, failed ${fail}`)
  } finally {
    deleteLoading.value = false
  }
}

// ── 回收站：恢复 ───────────────────────────────────
const showRestoreDialog = ref(false)
const restoreTargets = ref([])        // [{ id, name }]
const restoreLoading = ref(false)
const restoreOverlay = ref(null)
const restoreAttrs = useDialogA11y(showRestoreDialog, restoreOverlay, {
  titleId: 'restore-title',
  close: () => { showRestoreDialog.value = false },
})

function openRestoreOne(product) {
  restoreTargets.value = [{ id: product.id, name: product.name }]
  showRestoreDialog.value = true
  closeMenu()
}

function openBatchRestore() {
  const ids = Array.from(selectedIds.value)
  restoreTargets.value = ids.map(id => {
    const p = allProducts.value.find(x => x.id === id)
    return { id, name: p?.name || `#${id}` }
  })
  showRestoreDialog.value = true
}

async function confirmRestore() {
  restoreLoading.value = true
  try {
    const ids = restoreTargets.value.map(t => t.id)
    // Q6：改用后端**幂等**批量端点。此前逐条循环 `restoreProduct` ⇒ 若被重复触发，
    // 单条 `restore/` 会无条件再写一条 RESTORE 审计（端点本身非幂等）。
    const resp = await batchRestoreProducts(ids)
    const data = resp?.data || {}
    const restored = data.restored ?? 0
    const skipped = data.skipped ?? 0
    const notFound = data.not_found || []
    await refreshProducts()
    showRestoreDialog.value = false
    selectedIds.value = new Set()
    const extra = []
    if (skipped) extra.push(`${skipped} already active`)
    if (notFound.length) extra.push(`${notFound.length} not found`)
    if (extra.length) toast.warning(`Restored ${restored} (${extra.join(', ')})`)
    else toast.success(`Restored ${restored} products`)
  } catch (e) {
    toast.error('Restore failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    restoreLoading.value = false
  }
}
</script>

<template>
  <div class="products-page">
    <LoadingSpinner v-if="loading" text="Loading..." />
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <!-- Recycle bin notice banner -->
      <div v-if="viewMode === 'recycle'" class="recycle-banner" role="note">
        Recycle bin: {{ recycleCount }} products. Deleted products are hidden from the storefront and from the Products list. No data is removed — SKUs, documents, knowledge links, cart references and order history are all preserved.
      </div>

      <!-- Filters -->
      <div class="filters-bar">
        <div class="view-toggle">
          <button type="button" :class="['view-toggle__btn', { 'is-active': viewMode === 'active' }]" @click="setView('active')">Products</button>
          <button type="button" :class="['view-toggle__btn', { 'is-active': viewMode === 'recycle' }]" @click="setView('recycle')">Recycle Bin ({{ recycleCount }})</button>
        </div>
        <select v-model="statusFilter" class="filter-select">
          <option v-for="o in statusOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <select v-model="completenessFilter" class="filter-select">
          <option v-for="o in completenessOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <span class="filter-count">{{ filteredProducts.length }} products</span>
        <template v-if="selectedCount > 0">
          <template v-if="viewMode === 'active'">
            <button class="btn btn-ghost btn-sm" @click="openBatchLink">Batch Link</button>
            <button class="btn btn-ghost btn-sm" @click="openBatchArchive">Batch archive</button>
            <button class="btn btn-danger-ghost btn-sm" @click="openBatchDelete">Batch delete</button>
          </template>
          <button v-else class="btn btn-primary btn-sm" @click="openBatchRestore">Restore selected</button>
        </template>
        <router-link v-if="viewMode === 'active'" to="/workspace/products/new" class="btn btn-primary btn-sm" style="margin-left: auto">+ New Product</router-link>
      </div>

      <!-- Q5/Y3：分页上限截断告警（总数取自 meta.pagination.count，此前被丢弃 ⇒ 静默截断） -->
      <div v-if="truncated" class="truncate-notice" role="alert">
        Showing the first {{ PAGE_LIMIT }} of {{ totalCount }} products — the list is truncated.
        Server-side filtering / pagination is required before the catalog grows past this limit.
      </div>

      <!-- Table with sortable headers -->
      <div class="table-wrapper" v-if="filteredProducts.length">
      <table class="products-table">
        <thead>
          <tr>
            <th class="col-check"><input type="checkbox" v-model="allSelected" /></th>
            <th class="sortable" @click="toggleSort('catalog_no')">Catalog No{{ sortIcon('catalog_no') }}</th>
            <th class="sortable" @click="toggleSort('name')">Name{{ sortIcon('name') }}</th>
            <th class="sortable" @click="toggleSort('cas')">CAS{{ sortIcon('cas') }}</th>
            <th>Complete</th>
            <th class="sortable" @click="toggleSort('status')">Status{{ sortIcon('status') }}</th>
            <th class="sortable" @click="toggleSort('category_l1')">Category{{ sortIcon('category_l1') }}</th>
            <th class="sortable" @click="toggleSort('aggregate_relevance_score')" title="知识关联度 (0–1)，点击按关联强弱排序，无关联商品沉底">Knowledge Link{{ sortIcon('aggregate_relevance_score') }}</th>
            <th>Compliance</th>
            <th class="col-action"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in filteredProducts" :key="p.id" @click="viewMode === 'active' && goToProduct(p.id)" class="clickable-row">
            <td class="col-check" @click.stop><input type="checkbox" :checked="selectedIds.has(p.id)" @change="toggleSelect(p.id)" /></td>
            <td class="col-code">{{ p.catalog_no }}</td>
            <td class="col-name">{{ p.name }}</td>
            <td class="col-cas">{{ p.cas || '—' }}</td>
            <td>
              <span v-if="p.is_complete" class="tag tag-complete">✓</span>
              <span v-else class="tag tag-incomplete">✗ {{ (p.incomplete_items || []).join(', ') }}</span>
            </td>
            <td><span class="status-tag" :class="`status-${p.status}`">{{ p.status }}</span></td>
            <td>{{ p.product_class_name || p.category_l1 || '—' }}</td>
            <td class="col-rel">
              <span v-if="p.aggregate_relevance_score !== null && p.aggregate_relevance_score !== undefined" class="rel-score">{{ p.aggregate_relevance_score.toFixed(2) }}</span>
              <span v-else class="rel-none">—</span>
            </td>
            <td class="col-compliance">
              <span class="tag" :class="p.sds_published ? 'tag-sds' : 'tag-gray'" :title="p.sds_published ? 'SDS published' : 'SDS not published'">SDS{{ p.sds_published ? '✓' : '—' }}</span>
              <span class="tag" :class="(p.coa_published_count || 0) > 0 ? 'tag-coa' : 'tag-gray'" :title="`Published COA batches: ${p.coa_published_count || 0}`">COA {{ p.coa_published_count || 0 }}</span>
            </td>
            <td class="col-action row-actions" @click.stop>
              <button class="menu-trigger" @click="toggleMenu(p.id)">Actions ▾</button>
              <div v-if="openMenuId === p.id" class="menu-popover">
                <template v-if="viewMode === 'active'">
                  <button class="menu-item" @click="goToProduct(p.id); closeMenu()">Edit</button>
                  <!-- Q2：Unpublish 仅对「在售/草稿」有意义（deprecated 已经不在售，再下架无意义） -->
                  <button v-if="p.status === 'active' || p.status === 'draft'" class="menu-item" @click="openArchiveOne(p)">Unpublish</button>
                  <button v-if="p.status === 'archived'" class="menu-item" @click="reactivate(p)">Republish</button>
                  <!-- S4-4f 退出目录（停产）：货号不释放、页面保留，与「回收站」语义区分 -->
                  <button v-if="p.status !== 'deprecated'" class="menu-item" @click="discontinue(p)">Discontinue</button>
                  <button v-if="p.status === 'deprecated'" class="menu-item" @click="reactivate(p)">Reopen</button>
                  <button class="menu-item menu-item--danger" @click="openDeleteOne(p)">Move to Recycle Bin</button>
                </template>
                <button v-else class="menu-item" @click="openRestoreOne(p)">Restore</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
      <EmptyState
        v-else
        :title="emptyTitle"
        :description="emptyDescription"
        icon="Goods"
      >
        <template #action>
          <router-link
            v-if="emptyKind === 'none-at-all'"
            to="/workspace/products/new"
            class="btn btn-primary btn-sm"
          >+ New Product</router-link>
          <button
            v-else-if="emptyKind === 'all-in-recycle'"
            type="button"
            class="btn btn-primary btn-sm"
            @click="setView('recycle')"
          >Go to Recycle Bin ({{ recycleCount }})</button>
          <button
            v-else-if="emptyKind === 'filtered-out'"
            type="button"
            class="btn btn-ghost btn-sm"
            @click="clearFilters"
          >Clear filters</button>
        </template>
      </EmptyState>
    </template>

    <!-- Batch Knowledge Link Dialog -->
    <div v-if="showBatchLinkPanel" ref="batchOverlay" class="dialog-overlay" v-bind="batchAttrs" @click.self="showBatchLinkPanel = false">
      <div class="dialog dialog--wide">
        <h3 id="batch-title">Batch Knowledge Link</h3>
        <p class="dialog-sub">Link {{ selectedCount }} selected products to a knowledge chain.</p>
        <div class="batch-link-form">
          <label>Research Goal <select v-model="batchLinkGoalId" class="filter-select"><option value="">— Any —</option><option v-for="g in goals" :key="g.id" :value="g.id">{{ g.name }}</option></select></label>
          <label>Application <select v-model="batchLinkAppId" class="filter-select"><option value="">— Any —</option><option v-for="a in filteredApps" :key="a.id" :value="a.id">{{ a.name }}</option></select></label>
          <label>Method * <select v-model="batchLinkMethodId" class="filter-select"><option value="">— Required —</option><option v-for="m in filteredMethods" :key="m.id" :value="m.id">{{ m.name }}</option></select></label>
          <label>Protocol <select v-model="batchLinkProtocolId" class="filter-select"><option value="">— Optional —</option><option v-for="p in protocols" :key="p.id" :value="p.id">{{ p.name }}</option></select></label>
          <button type="button" class="btn btn-ghost btn-sm" @click="previewBatchLink" :disabled="!batchLinkMethodId">Preview</button>
        </div>
        <div v-if="batchLinkPreview" class="batch-preview">
          <p>Will link <strong>{{ batchLinkPreview.willLink }}</strong> products, skip <strong>{{ batchLinkPreview.skipped }}</strong> (already linked).</p>
          <button class="btn btn-primary btn-sm" @click="applyBatchLink" :disabled="batchLinkLoading">{{ batchLinkLoading ? 'Linking...' : 'Confirm' }}</button>
        </div>
        <button class="btn btn-ghost btn-sm" style="margin-top:12px" @click="showBatchLinkPanel = false">Cancel</button>
      </div>
    </div>

    <!-- Archive confirm dialog -->
    <div v-if="showArchiveDialog" ref="archiveOverlay" class="dialog-overlay" v-bind="archiveAttrs" @click.self="showArchiveDialog = false">
      <div class="dialog">
        <h3 id="archive-title">Confirm unpublish</h3>
        <p class="dialog-sub">After unpublishing, the product is hidden from the storefront but all data and order history are kept; you can republish it at any time.</p>
        <div class="archive-list">
          <p>Will unpublish <strong>{{ archiveTargets.length }}</strong> products:</p>
          <ul>
            <li v-for="t in archiveTargets.slice(0, 8)" :key="t.id">{{ t.name }}</li>
            <li v-if="archiveTargets.length > 8">… {{ archiveTargets.length - 8 }} more</li>
          </ul>
        </div>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="showArchiveDialog = false">Cancel</button>
          <button class="btn btn-primary" @click="confirmArchive" :disabled="archiveLoading">
            {{ archiveLoading ? 'Unpublishing…' : 'Unpublish' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Move to recycle bin confirm dialog -->
    <div v-if="showDeleteDialog" ref="deleteOverlay" class="dialog-overlay" v-bind="deleteAttrs" @click.self="showDeleteDialog = false">
      <div class="dialog">
        <h3 id="delete-title">Move to recycle bin</h3>
        <p class="dialog-sub">These products are moved to the recycle bin and hidden from the storefront and the Products list. No data is removed — SKUs, documents, knowledge links, cart references and order history are all preserved. You can restore them from the Recycle Bin at any time.</p>
        <template v-if="deleteTarget?.batch">
          <p>Will move <strong>{{ deleteTarget.batch.length }}</strong> products to the recycle bin:</p>
          <ul class="delete-list">
            <li v-for="t in deleteTarget.batch.slice(0, 8)" :key="t.id">{{ t.name }}</li>
            <li v-if="deleteTarget.batch.length > 8">… {{ deleteTarget.batch.length - 8 }} more</li>
          </ul>
        </template>
        <template v-else>
          <p>Will move product to the recycle bin: <strong>{{ deleteTarget?.name }}</strong></p>
        </template>
        <label class="confirm-check">
          <input type="checkbox" v-model="deleteConfirmChecked" />
          I understand these products will be moved to the recycle bin
        </label>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="showDeleteDialog = false">Cancel</button>
          <button
            class="btn btn-primary"
            @click="confirmDelete"
            :disabled="deleteLoading || !deleteConfirmChecked"
          >
            {{ deleteLoading ? 'Moving…' : 'Move to recycle bin' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Restore confirm dialog -->
    <div v-if="showRestoreDialog" ref="restoreOverlay" class="dialog-overlay" v-bind="restoreAttrs" @click.self="showRestoreDialog = false">
      <div class="dialog">
        <h3 id="restore-title">Restore from recycle bin</h3>
        <p class="dialog-sub">Restored products return to the Products list. Products whose status is Active become visible on the storefront again; drafts stay hidden.</p>
        <div class="restore-list">
          <p>Will restore <strong>{{ restoreTargets.length }}</strong> products:</p>
          <ul>
            <li v-for="t in restoreTargets.slice(0, 8)" :key="t.id">{{ t.name }}</li>
            <li v-if="restoreTargets.length > 8">… {{ restoreTargets.length - 8 }} more</li>
          </ul>
        </div>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="showRestoreDialog = false">Cancel</button>
          <button class="btn btn-primary" @click="confirmRestore" :disabled="restoreLoading">
            {{ restoreLoading ? 'Restoring…' : 'Restore' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.products-page { max-width: 1400px; }
.table-wrapper { border: 1px solid var(--color-border); border-radius: 12px; overflow: hidden; }
.filters-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.view-toggle { display: inline-flex; border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
.view-toggle__btn { padding: 6px 12px; border: none; background: var(--color-surface); color: var(--color-text-secondary); font-size: 13px; cursor: pointer; }
.view-toggle__btn + .view-toggle__btn { border-left: 1px solid var(--color-border); }
.view-toggle__btn:hover { background: var(--color-bg); }
.view-toggle__btn.is-active { background: var(--color-primary); color: var(--color-primary-fg); }
.recycle-banner { background: var(--color-warning-bg); border-left: 3px solid var(--color-warning); border-radius: 6px; padding: 10px 12px; margin-bottom: 16px; font-size: 13px; color: var(--color-text); }
/* Q5/Y3：截断告警（与回收站横幅同族但在其下方，语义是「数据不全」） */
.truncate-notice { background: var(--color-warning-bg); border-left: 3px solid var(--color-warning); border-radius: 6px; padding: 10px 12px; margin-bottom: 12px; font-size: 13px; color: var(--color-text); }
.filter-select { padding: 6px 12px; border: 1px solid var(--color-border); border-radius: 8px; font-size: 13px; background: var(--color-surface); color: var(--color-text); }
.filter-count { font-size: 13px; color: var(--color-text-secondary); }
.products-table { width: 100%; border-collapse: collapse; background: var(--color-surface); }
.products-table th, .products-table td { text-align: left; padding: 10px 14px; font-size: 13px; border-bottom: 1px solid var(--color-border); }
.products-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); white-space: nowrap; }
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--color-primary); }
.clickable-row { cursor: pointer; transition: background 0.1s; color: var(--color-text); }
.clickable-row:hover { background: var(--color-bg); }
.col-check { width: 36px; text-align: center; }
.col-code { font-family: monospace; white-space: nowrap; }
.col-name { font-weight: 500; }
.col-cas { font-family: monospace; font-size: 12px; white-space: nowrap; }
.col-rel { white-space: nowrap; text-align: right; font-variant-numeric: tabular-nums; }
.rel-score { font-family: var(--font-mono); font-weight: 600; color: var(--color-primary); }
.rel-none { color: var(--color-text-tertiary); }
.col-action { width: 90px; text-align: right; }
.row-actions { position: relative; }
.menu-trigger { padding: 4px 10px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-surface); color: var(--color-text); font-size: 12px; cursor: pointer; }
.menu-trigger:hover { background: var(--color-bg); }
.menu-popover { position: absolute; right: 0; top: 100%; margin-top: 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.12); z-index: 10; min-width: 120px; padding: 4px; }
.menu-item { display: block; width: 100%; text-align: left; padding: 6px 10px; border: none; background: transparent; color: var(--color-text); font-size: 13px; border-radius: 4px; cursor: pointer; }
.menu-item:hover { background: var(--color-bg); }
.menu-item--danger { color: var(--color-danger); }
.menu-item--danger:hover { background: var(--color-danger-light); }
.btn-danger { background: var(--color-danger); color: var(--color-primary-fg); }
.btn-danger:hover { background: var(--color-danger); }
.btn-danger-ghost { background: transparent; color: var(--color-danger); border: 1px solid var(--color-danger); }
.btn-danger-ghost:hover { background: var(--color-danger-light); }
.dialog-sub { color: var(--color-text-secondary); font-size: 13px; margin: 8px 0 12px; }
.dialog-warn { background: var(--color-danger-bg); border-left: 3px solid var(--color-danger); padding: 10px 12px; border-radius: 6px; margin: 8px 0 12px; font-size: 13px; color: var(--color-danger); }
.dialog-warn p { margin: 0; }
.archive-list ul, .delete-list, .restore-list ul { margin: 6px 0; padding-left: 20px; font-size: 13px; color: var(--color-text-secondary); max-height: 160px; overflow-y: auto; }
.confirm-check { display: flex; align-items: flex-start; gap: 8px; font-size: 13px; color: var(--color-text); margin: 12px 0; cursor: pointer; }
.tag { padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.tag-complete { background: var(--color-success-bg); color: var(--color-primary-active); }
.tag-incomplete { background: var(--color-warning-bg); color: var(--color-warning); }
.tag-sds { background: var(--color-success-bg); color: var(--color-primary-active); }
.tag-coa { background: var(--color-info-bg); color: var(--color-info); }
.tag-gray { background: var(--color-bg); color: var(--color-text-secondary); }
.col-compliance { white-space: nowrap; }
.col-compliance .tag + .tag { margin-left: 4px; }
.status-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.status-active { background: var(--color-success-bg); color: var(--color-primary-active); }
.status-draft { background: var(--color-warning-bg); color: var(--color-warning); }
.status-deprecated, .status-archived { background: var(--color-bg); color: var(--color-text-tertiary); }
.loading, .error { text-align: center; padding: 40px; color: var(--color-text-secondary); }
.batch-link-form { display: flex; flex-direction: column; gap: 8px; }
.batch-link-form label { display: flex; flex-direction: column; font-size: 13px; color: var(--color-text-secondary); gap: 4px; }
.batch-link-form select { width: 100%; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 13px; background: var(--color-bg); color: var(--color-text); }
.batch-preview { background: var(--color-success-bg); border-radius: 8px; padding: 12px; margin-top: 12px; font-size: 13px; }
.batch-preview p { margin: 0 0 8px; color: var(--color-success); }
</style>
