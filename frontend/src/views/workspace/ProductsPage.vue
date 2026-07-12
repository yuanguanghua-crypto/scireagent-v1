<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/api/http'
import { toast, LoadingSpinner, EmptyState } from '@/components/common'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { archiveProduct, reactivateProduct, deleteProduct } from '@/api/workspace/products'

const router = useRouter()
const auth = useAuthStore()

if (!auth.isStaff) {
  router.replace('/')
}

const products = ref([])
const loading = ref(true)
const error = ref('')
const selectedIds = ref(new Set())

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
  list.sort((a, b) => {
    const av = a[sortField.value] ?? ''
    const bv = b[sortField.value] ?? ''
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
  { value: 'archived', label: 'Archived' },
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
    case 'no-link': list = list.filter(p => !(p.incomplete_items || []).some(i => i.includes('关联')) && p.is_complete); break
    case 'no-category': list = list.filter(p => !p.product_class_id); break
  }
  return list
})

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
    goals.value = (g.data?.data?.results || g.data?.data || [])
    applications.value = (a.data?.data?.results || a.data?.data || [])
    methods.value = (m.data?.data?.results || m.data?.data || [])
    protocols.value = (p.data?.data?.results || p.data?.data || [])
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
      await http.put(`/products/${pid}/`, { method_ids: methodIds, protocol_ids: protocolIds })
    }
    showBatchLinkPanel.value = false
    const resp = await http.get('/products/', { params: { page_size: 500 } })
    if (resp.data) {
      products.value = Array.isArray(resp.data) ? resp.data : (resp.data.results || [])
    }
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
    const resp = await http.get('/products/', { params: { page_size: 500 } })
    if (resp.data) {
      products.value = Array.isArray(resp.data) ? resp.data : (resp.data.results || [])
    }
  } catch (e) {
    error.value = 'Failed to load products'
  } finally {
    loading.value = false
  }
})

// ── 列表刷新 ───────────────────────────────────────
async function refreshProducts() {
  const resp = await http.get('/products/', { params: { page_size: 500 } })
  if (resp.data) {
    products.value = Array.isArray(resp.data) ? resp.data : (resp.data.results || [])
  }
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
    if (fail === 0) toast.success(`Archived ${ok} products`)
    else toast.warning(`Archived ${ok}, failed ${fail}`)
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
    if (fail === 0) toast.success(`Deleted ${ok} products`)
    else toast.warning(`Deleted ${ok}, failed ${fail}`)
  } finally {
    deleteLoading.value = false
  }
}
</script>

<template>
  <div class="products-page">
    <LoadingSpinner v-if="loading" text="Loading..." />
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <!-- Filters -->
      <div class="filters-bar">
        <select v-model="statusFilter" class="filter-select">
          <option v-for="o in statusOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <select v-model="completenessFilter" class="filter-select">
          <option v-for="o in completenessOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <span class="filter-count">{{ filteredProducts.length }} products</span>
        <template v-if="selectedCount > 0">
          <button class="btn btn-ghost btn-sm" @click="openBatchLink">Batch Link</button>
          <button class="btn btn-ghost btn-sm" @click="openBatchArchive">Batch archive</button>
          <button class="btn btn-danger-ghost btn-sm" @click="openBatchDelete">Batch delete</button>
        </template>
        <router-link to="/workspace/products/new" class="btn btn-primary btn-sm" style="margin-left: auto">+ New Product</router-link>
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
            <th>Compliance</th>
            <th class="col-action"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in filteredProducts" :key="p.id" @click="goToProduct(p.id)" class="clickable-row">
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
            <td class="col-compliance">
              <span class="tag" :class="p.sds_published ? 'tag-sds' : 'tag-gray'" :title="p.sds_published ? 'SDS published' : 'SDS not published'">SDS{{ p.sds_published ? '✓' : '—' }}</span>
              <span class="tag" :class="(p.coa_published_count || 0) > 0 ? 'tag-coa' : 'tag-gray'" :title="`Published COA batches: ${p.coa_published_count || 0}`">COA {{ p.coa_published_count || 0 }}</span>
            </td>
            <td class="col-action row-actions" @click.stop>
              <button class="menu-trigger" @click="toggleMenu(p.id)">Actions ▾</button>
              <div v-if="openMenuId === p.id" class="menu-popover">
                <button class="menu-item" @click="goToProduct(p.id); closeMenu()">Edit</button>
                <button v-if="p.status !== 'archived'" class="menu-item" @click="openArchiveOne(p)">Archive</button>
                <button v-else class="menu-item" @click="reactivate(p)">Republish</button>
                <button class="menu-item menu-item--danger" @click="openDeleteOne(p)">Delete</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
      <EmptyState v-else title="No products match the current filters" icon="Goods" />
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
        <h3 id="archive-title">Confirm archive</h3>
        <p class="dialog-sub">After archiving, the product is hidden from the storefront but all data and order history are kept; you can republish at any time.</p>
        <div class="archive-list">
          <p>Will archive <strong>{{ archiveTargets.length }}</strong> products:</p>
          <ul>
            <li v-for="t in archiveTargets.slice(0, 8)" :key="t.id">{{ t.name }}</li>
            <li v-if="archiveTargets.length > 8">… {{ archiveTargets.length - 8 }} more</li>
          </ul>
        </div>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="showArchiveDialog = false">Cancel</button>
          <button class="btn btn-primary" @click="confirmArchive" :disabled="archiveLoading">
            {{ archiveLoading ? 'Archiving…' : 'Confirm archive' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirm dialog -->
    <div v-if="showDeleteDialog" ref="deleteOverlay" class="dialog-overlay" v-bind="deleteAttrs" @click.self="showDeleteDialog = false">
      <div class="dialog">
        <h3 id="delete-title">Confirm delete</h3>
        <div class="dialog-warn" role="alert">
          <p><strong>This action cannot be undone.</strong> Deleting also removes the product's SKUs, documents, knowledge links and cart references; historical order records are kept but the item becomes empty.</p>
        </div>
        <template v-if="deleteTarget?.batch">
          <p>Will permanently delete <strong>{{ deleteTarget.batch.length }}</strong> products:</p>
          <ul class="delete-list">
            <li v-for="t in deleteTarget.batch.slice(0, 8)" :key="t.id">{{ t.name }}</li>
            <li v-if="deleteTarget.batch.length > 8">… {{ deleteTarget.batch.length - 8 }} more</li>
          </ul>
        </template>
        <template v-else>
          <p>Will permanently delete product: <strong>{{ deleteTarget?.name }}</strong></p>
        </template>
        <label class="confirm-check">
          <input type="checkbox" v-model="deleteConfirmChecked" />
          I understand the consequences and confirm permanent deletion
        </label>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="showDeleteDialog = false">Cancel</button>
          <button
            class="btn btn-danger"
            @click="confirmDelete"
            :disabled="deleteLoading || !deleteConfirmChecked"
          >
            {{ deleteLoading ? 'Deleting…' : 'Permanently delete' }}
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
.archive-list ul, .delete-list { margin: 6px 0; padding-left: 20px; font-size: 13px; color: var(--color-text-secondary); max-height: 160px; overflow-y: auto; }
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
