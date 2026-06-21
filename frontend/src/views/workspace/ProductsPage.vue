<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/api/http'

const router = useRouter()
const auth = useAuthStore()

if (!auth.isStaff) {
  router.replace('/')
}

const products = ref([])
const loading = ref(true)
const error = ref('')
const selectedIds = ref(new Set())
const filterStatus = ref('')
const filterCompleteness = ref('')

// ── Batch Knowledge Link ────────────────────────────
const showBatchLinkPanel = ref(false)
const batchLinkGoalId = ref('')
const batchLinkAppId = ref('')
const batchLinkMethodId = ref('')
const batchLinkProtocolId = ref('')
const batchLinkPreview = ref(null)
const batchLinkLoading = ref(false)

const goals = ref([])
const applications = ref([])
const methods = ref([])
const protocols = ref([])

const selectedCount = computed(() => selectedIds.value.size)

const statusFilter = ref('all')       // all / active / draft / discontinued
const completenessFilter = ref('all') // all / complete / incomplete / no-cas / no-smiles / no-link / no-category

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
  let list = products.value
  if (statusFilter.value !== 'all') {
    list = list.filter(p => p.status === statusFilter.value)
  }
  switch (completenessFilter.value) {
    case 'complete': list = list.filter(p => p.is_complete); break
    case 'incomplete': list = list.filter(p => !p.is_complete); break
    case 'no-cas': list = list.filter(p => !p.cas); break
    case 'no-smiles': list = list.filter(p => !p.smiles); break
    case 'no-link': list = list.filter(p => (p.incomplete_items || []).some(i => i.includes('关联'))); break
    case 'no-category': list = list.filter(p => !p.category_l1); break
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

function goToNew() {
  router.push('/workspace/products/new')
}

// ── Batch Knowledge Link Logic ─────────────────────
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
  } catch (e) {
    /* ignore */
  }
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
      // Update each product's method/protocol ids
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
    // Reload list
    const resp = await http.get('/products/', { params: { page_size: 500 } })
    if (resp.data?.data) {
      products.value = resp.data.data.results || resp.data.data
    }
  } catch (e) {
    alert('Batch link failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    batchLinkLoading.value = false
  }
}

onMounted(async () => {
  try {
    const resp = await http.get('/products/', { params: { page_size: 500 } })
    if (resp.data?.data) {
      products.value = resp.data.data.results || resp.data.data
    }
  } catch (e) {
    error.value = 'Failed to load products'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="products-page">
    <div v-if="loading" class="loading">Loading...</div>
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
        <button v-if="selectedCount > 0" class="btn btn-ghost btn-sm" @click="openBatchLink">Batch Link Knowledge</button>
        <router-link to="/workspace/products/new" class="btn btn-primary btn-sm" style="margin-left: auto">+ New Product</router-link>
      </div>

      <!-- Table -->
      <table class="products-table" v-if="filteredProducts.length">
        <thead>
          <tr>
            <th class="col-check"><input type="checkbox" v-model="allSelected" /></th>
            <th>Catalog No</th>
            <th>Name</th>
            <th>CAS</th>
            <th>Complete</th>
            <th>Status</th>
            <th>Category</th>
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
            <td>{{ p.category_l1 || '—' }}</td>
            <td class="col-action" @click.stop>
              <router-link :to="`/workspace/products/${p.id}/edit`" class="btn btn-ghost btn-sm">Edit</router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty-text">No products match the current filters.</p>
    </template>

    <!-- Batch Knowledge Link Dialog -->
    <div v-if="showBatchLinkPanel" class="dialog-overlay" @click.self="showBatchLinkPanel = false">
      <div class="dialog dialog--wide">
        <h3>Batch Knowledge Link</h3>
        <p class="dialog-sub">Link {{ selectedCount }} selected products to a knowledge chain.</p>

        <div class="batch-link-form">
          <label>Research Goal
            <select v-model="batchLinkGoalId" class="filter-select">
              <option value="">— Any —</option>
              <option v-for="g in goals" :key="g.id" :value="g.id">{{ g.name }}</option>
            </select>
          </label>
          <label>Application
            <select v-model="batchLinkAppId" class="filter-select">
              <option value="">— Any —</option>
              <option v-for="a in filteredApps" :key="a.id" :value="a.id">{{ a.name }}</option>
            </select>
          </label>
          <label>Method *
            <select v-model="batchLinkMethodId" class="filter-select">
              <option value="">— Required —</option>
              <option v-for="m in filteredMethods" :key="m.id" :value="m.id">{{ m.name }}</option>
            </select>
          </label>
          <label>Protocol
            <select v-model="batchLinkProtocolId" class="filter-select">
              <option value="">— Optional —</option>
              <option v-for="p in protocols" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </label>
          <button type="button" class="btn btn-ghost btn-sm" @click="previewBatchLink" :disabled="!batchLinkMethodId">Preview</button>
        </div>

        <div v-if="batchLinkPreview" class="batch-preview">
          <p>Will link <strong>{{ batchLinkPreview.willLink }}</strong> products,
             skip <strong>{{ batchLinkPreview.skipped }}</strong> (already linked).</p>
          <button class="btn btn-primary btn-sm" @click="applyBatchLink" :disabled="batchLinkLoading">
            {{ batchLinkLoading ? 'Linking...' : 'Confirm' }}
          </button>
        </div>

        <button class="btn btn-ghost btn-sm" style="margin-top:12px" @click="showBatchLinkPanel = false">Cancel</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.products-page { max-width: 1400px; }
.filters-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.filter-select { padding: 6px 12px; border: 1px solid var(--color-border); border-radius: 8px; font-size: 13px; background: var(--color-surface); color: var(--color-text); }
.filter-count { font-size: 13px; color: var(--color-text-secondary); }
.products-table { width: 100%; border-collapse: collapse; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; overflow: hidden; }
.products-table th, .products-table td { text-align: left; padding: 10px 14px; font-size: 13px; border-bottom: 1px solid var(--color-border); }
.products-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); white-space: nowrap; }
.clickable-row { cursor: pointer; transition: background 0.1s; color: var(--color-text); }
.clickable-row:hover { background: var(--color-bg); }
.col-check { width: 36px; text-align: center; }
.col-code { font-family: monospace; white-space: nowrap; }
.col-name { font-weight: 500; }
.col-cas { font-family: monospace; font-size: 12px; white-space: nowrap; }
.col-action { width: 60px; text-align: right; }
.tag { padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.tag-complete { background: #dcf7e8; color: #176b3a; }
.tag-incomplete { background: #ffeeba; color: #856404; }
.status-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.status-active { background: #dcf7e8; color: #176b3a; }
.status-draft { background: #ffeeba; color: #856404; }
.status-deprecated, .status-archived { background: #f0f0f0; color: #888; }
.loading, .error { text-align: center; padding: 40px; color: var(--color-text-secondary); }
.empty-text { color: var(--color-text-secondary); font-size: 14px; padding: 20px; }
.dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--color-surface); border-radius: 12px; padding: 24px; max-width: 420px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.dialog h3 { margin-bottom: 16px; color: var(--color-text); }
.dialog--wide { max-width: 520px; }
.dialog-sub { font-size: 13px; color: var(--color-text-secondary); margin-bottom: 12px; }
.batch-link-form { display: flex; flex-direction: column; gap: 8px; }
.batch-link-form label { display: flex; flex-direction: column; font-size: 13px; color: var(--color-text-secondary); gap: 4px; }
.batch-link-form select { width: 100%; }
.batch-preview { background: #dcf7e8; border-radius: 8px; padding: 12px; margin-top: 12px; font-size: 13px; }
.batch-preview p { margin: 0 0 8px; color: #176b3a; }
</style>
