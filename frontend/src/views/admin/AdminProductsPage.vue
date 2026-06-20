<script setup>
/**
 * AdminProductsPage — Product management list for admins.
 * Batch operations for AI tools: validate, literature recommend.
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import http from '@/utils/http'
import { batchValidate, batchRecommendLiterature } from '@/api/aiTools'

const router = useRouter()
const auth = useAuthStore()
const products = ref([])
const loading = ref(false)
const searchQuery = ref('')
const selectedIds = ref([])
const batchLoading = ref(false)
const batchResults = ref(null)
const batchMode = ref('')  // 'validate' | 'literature'

const isAdmin = computed(() => auth.role === 'admin' || auth.isOrgAdmin || auth.user?.is_superuser)

const filteredProducts = computed(() => {
  if (!searchQuery.value) return products.value
  const q = searchQuery.value.toLowerCase()
  return products.value.filter(p =>
    (p.name || '').toLowerCase().includes(q) ||
    (p.catalog_no || '').toLowerCase().includes(q)
  )
})

const selectedCount = computed(() => selectedIds.value.length)

function toggleSelectAll() {
  if (selectedIds.value.length === filteredProducts.value.length) {
    selectedIds.value = []
  } else {
    selectedIds.value = filteredProducts.value.map(p => p.id)
  }
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

async function runBatchValidate() {
  if (!selectedIds.value.length) return
  batchLoading.value = true
  batchMode.value = 'validate'
  batchResults.value = null
  try {
    const res = await batchValidate(selectedIds.value)
    batchResults.value = res.data
  } catch { /* ignore */ }
  batchLoading.value = false
}

async function runBatchLiterature() {
  if (!selectedIds.value.length) return
  batchLoading.value = true
  batchMode.value = 'literature'
  batchResults.value = null
  try {
    const res = await batchRecommendLiterature(selectedIds.value)
    batchResults.value = res.data
  } catch { /* ignore */ }
  batchLoading.value = false
}

onMounted(async () => {
  if (!isAdmin.value) { router.push('/'); return }
  loading.value = true
  try {
    const res = await http.get('/products/', { params: { page_size: 200 } })
    products.value = res.data || res || []
  } catch { /* ignore */ }
  loading.value = false
})
</script>

<template>
  <div class="admin-page" v-if="isAdmin">
    <div class="admin-header">
      <div>
        <h1 class="admin-title">Product Management</h1>
        <p class="admin-subtitle">{{ products.length }} products</p>
      </div>
      <div class="header-right">
        <div v-if="selectedIds.length" class="batch-actions">
          <span class="selected-count">{{ selectedCount }} selected</span>
          <button class="btn-batch" :disabled="batchLoading" @click="runBatchValidate">
            {{ batchLoading && batchMode === 'validate' ? 'Running…' : '🔬 Batch Validate' }}
          </button>
          <button class="btn-batch" :disabled="batchLoading" @click="runBatchLiterature">
            {{ batchLoading && batchMode === 'literature' ? 'Running…' : '📚 Batch Literature' }}
          </button>
        </div>
        <button class="btn-primary" @click="router.push('/admin/products/new')">+ New Product</button>
      </div>
    </div>

    <div class="search-bar">
      <input v-model="searchQuery" class="search-input" placeholder="Search by name or catalog no..." />
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <table v-else class="product-table">
      <thead>
        <tr>
          <th class="th-check">
            <input type="checkbox" @change="toggleSelectAll" :checked="selectedIds.length === filteredProducts.length && filteredProducts.length > 0" />
          </th>
          <th>Catalog No</th>
          <th>Product Name</th>
          <th>CAS</th>
          <th>Status</th>
          <th>Category</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in filteredProducts" :key="p.id" :class="{ 'row-selected': selectedIds.includes(p.id) }">
          <td>
            <input type="checkbox" :checked="selectedIds.includes(p.id)" @change="toggleSelect(p.id)" />
          </td>
          <td class="mono">{{ p.catalog_no }}</td>
          <td>{{ p.name }}</td>
          <td class="mono">{{ p.cas || '—' }}</td>
          <td>
            <span class="status-badge" :class="`status-${p.status}`">{{ p.status }}</span>
          </td>
          <td class="cat">{{ p.category_l1 || '—' }}</td>
          <td>
            <button class="btn-edit" @click="router.push(`/admin/products/${p.id}/edit`)">Edit</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Batch Results -->
    <div v-if="batchResults" class="batch-results">
      <h3>{{ batchMode === 'validate' ? 'Batch Validation Results' : 'Batch Literature Results' }}</h3>
      <div v-for="r in batchResults" :key="r.product_id" class="batch-result-item">
        <h4>{{ r.product_name }}</h4>
        <template v-if="batchMode === 'validate' && r.validation">
          <p>
            PubChem: {{ r.validation.pubchem?.match ? '✅ Match' : '❌ No match' }}
            <span v-if="r.validation.pubchem?.cid">(CID: {{ r.validation.pubchem.cid }})</span>
          </p>
          <p>BioProCorpus: {{ r.validation.bioprocorpus?.match_count || 0 }} protocols</p>
          <p :class="r.validation.overall_match ? 'text-success' : 'text-warning'">
            Overall: {{ r.validation.overall_match ? '✅ PASS' : '⚠️ REVIEW' }}
          </p>
        </template>
        <template v-if="batchMode === 'literature' && r.literature">
          <p>{{ r.literature.applications?.length || 0 }} applications, {{ r.literature.methods?.length || 0 }} methods, {{ r.literature.references?.length || 0 }} references</p>
        </template>
      </div>
    </div>
  </div>

  <div v-else class="access-denied">
    <h2>Access Denied</h2>
    <p>Admin only.</p>
    <button @click="router.push('/')">Back to Home</button>
  </div>
</template>

<style scoped>
.admin-page { max-width: 1200px; margin: 0 auto; padding: 24px; }
.admin-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.admin-title { font-size: 24px; font-weight: 800; margin: 0; }
.admin-subtitle { font-size: 14px; color: var(--color-text-secondary); margin: 4px 0 0; }

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-count {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
}

.btn-batch {
  padding: 6px 12px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  font-family: var(--font-sans);
  white-space: nowrap;
}

.btn-batch:hover {
  background: var(--color-primary-subtle);
}

.btn-batch:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.search-bar { margin-bottom: 16px; }
.search-input { width: 100%; padding: 10px 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 14px; }
.search-input:focus { border-color: var(--color-primary); outline: none; }

.product-table { width: 100%; border-collapse: collapse; }
.product-table th { font-size: 11px; font-weight: 600; text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--color-border); color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
.product-table td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); font-size: 13px; }
.product-table tr:hover { background: var(--color-primary-subtle); }
.product-table tr.row-selected { background: #eff6ff; }
.th-check { width: 40px; }

.mono { font-family: var(--font-mono); font-size: 12px; }
.cat { font-size: 12px; color: var(--color-text-secondary); }

.status-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
.status-active, .status-published { background: #d1fae5; color: #065f46; }
.status-draft { background: #fef3c7; color: #92400e; }
.status-archived { background: #f3f4f6; color: #6b7280; }

.btn-primary { height: 36px; padding: 0 16px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.btn-primary:hover { opacity: 0.9; }
.btn-edit { padding: 4px 12px; background: transparent; color: var(--color-primary); border: 1px solid var(--color-primary); border-radius: var(--radius-sm); font-size: 12px; cursor: pointer; }
.btn-edit:hover { background: var(--color-primary-subtle); }

/* Batch results */
.batch-results {
  margin-top: 24px;
}

.batch-results h3 {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 12px;
}

.batch-result-item {
  padding: 12px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
  background: var(--color-surface);
}

.batch-result-item h4 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 6px;
}

.batch-result-item p {
  font-size: 12px;
  margin: 2px 0;
  color: var(--color-text-secondary);
}

.text-success { color: #059669 !important; font-weight: 600; }
.text-warning { color: #d97706 !important; font-weight: 600; }

.access-denied { text-align: center; padding: 80px 24px; }
.access-denied h2 { font-size: 20px; margin-bottom: 8px; }
.access-denied p { color: var(--color-text-secondary); margin-bottom: 16px; }
.access-denied button { padding: 8px 20px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); cursor: pointer; }
.loading { text-align: center; padding: 40px; color: var(--color-text-secondary); }
</style>
