<script setup>
/**
 * AdminProductsPage — Product management list for admins.
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import http from '@/utils/http'

const router = useRouter()
const auth = useAuthStore()
const products = ref([])
const loading = ref(false)
const searchQuery = ref('')

const isAdmin = computed(() => auth.role === 'admin' || auth.isOrgAdmin)

const filteredProducts = computed(() => {
  if (!searchQuery.value) return products.value
  const q = searchQuery.value.toLowerCase()
  return products.value.filter(p =>
    (p.name || '').toLowerCase().includes(q) ||
    (p.catalog_no || '').toLowerCase().includes(q)
  )
})

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
      <button class="btn-primary" @click="router.push('/admin/products/new')">+ New Product</button>
    </div>

    <div class="search-bar">
      <input v-model="searchQuery" class="search-input" placeholder="Search by name or catalog no..." />
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <table v-else class="product-table">
      <thead>
        <tr>
          <th>Catalog No</th>
          <th>Product Name</th>
          <th>CAS</th>
          <th>Status</th>
          <th>Category</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in filteredProducts" :key="p.id">
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
  </div>

  <div v-else class="access-denied">
    <h2>Access Denied</h2>
    <p>Admin only.</p>
    <button @click="router.push('/')">Back to Home</button>
  </div>
</template>

<style scoped>
.admin-page { max-width: 1200px; margin: 0 auto; padding: 24px; }
.admin-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.admin-title { font-size: 24px; font-weight: 800; margin: 0; }
.admin-subtitle { font-size: 14px; color: var(--color-text-secondary); margin: 4px 0 0; }

.search-bar { margin-bottom: 16px; }
.search-input { width: 100%; padding: 10px 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 14px; }
.search-input:focus { border-color: var(--color-primary); outline: none; }

.product-table { width: 100%; border-collapse: collapse; }
.product-table th { font-size: 11px; font-weight: 600; text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--color-border); color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
.product-table td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); font-size: 13px; }
.product-table tr:hover { background: var(--color-primary-subtle); }
.mono { font-family: var(--font-mono); font-size: 12px; }
.cat { font-size: 12px; color: var(--color-text-secondary); }

.status-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
.status-active, .status-published { background: #d1fae5; color: #065f46; }
.status-draft { background: #fef3c7; color: #92400e; }
.status-archived { background: #f3f4f6; color: #6b7280; }

.btn-primary { height: 36px; padding: 0 16px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-primary:hover { opacity: 0.9; }
.btn-edit { padding: 4px 12px; background: transparent; color: var(--color-primary); border: 1px solid var(--color-primary); border-radius: var(--radius-sm); font-size: 12px; cursor: pointer; }
.btn-edit:hover { background: var(--color-primary-subtle); }

.access-denied { text-align: center; padding: 80px 24px; }
.access-denied h2 { font-size: 20px; margin-bottom: 8px; }
.access-denied p { color: var(--color-text-secondary); margin-bottom: 16px; }
.access-denied button { padding: 8px 20px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); cursor: pointer; }
.loading { text-align: center; padding: 40px; color: var(--color-text-secondary); }
</style>
