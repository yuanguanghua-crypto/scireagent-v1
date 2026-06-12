<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProductsStore } from '@/stores/products'
import ProductCard from '@/components/cards/ProductCard.vue'

const router = useRouter()
const store = useProductsStore()
const searchQuery = ref('')
const currentPage = ref(1)
const activeFilter = ref('all')

const filters = [
  { key: 'all', label: 'All Products' },
  { key: 'in_stock', label: 'In Stock' },
  { key: 'limited', label: 'Limited' },
  { key: 'pre_order', label: 'Pre-order' },
]

onMounted(() => {
  store.fetchProducts()
})

function handleSearch() {
  currentPage.value = 1
  store.fetchProducts({ search: searchQuery.value })
}

function handlePageChange(page) {
  currentPage.value = page
  store.fetchProducts({ page, search: searchQuery.value })
}

function handleFilter(filter) {
  activeFilter.value = filter
  currentPage.value = 1
  // In production, pass filter to API
  store.fetchProducts({ search: searchQuery.value })
}

function goToDetail(product) {
  router.push(`/products/${product.id}`)
}

const resultCount = computed(() => store.total || store.products.length)
</script>

<template>
  <div class="product-index">
    <!-- Page header with search -->
    <div class="page-header">
      <div class="header-row">
        <div>
          <h1 class="page-title">Products</h1>
          <p class="page-subtitle">Browse scientific reagents with full chemical identity and context.</p>
        </div>
        <span class="result-badge">{{ resultCount }} items</span>
      </div>
      <div class="filter-bar">
        <el-input
          v-model="searchQuery"
          placeholder="Search by name, CAS, SMILES..."
          prefix-icon="Search"
          clearable
          size="default"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
          class="search-input"
        />
        <el-button type="primary" @click="handleSearch" size="default">Search</el-button>
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
      <div v-for="i in 6" :key="i" class="skeleton-card">
        <el-skeleton :rows="3" animated />
      </div>
    </div>

    <div v-else-if="store.products.length === 0" class="empty-container">
      <el-empty description="No products found" />
    </div>

    <div v-else>
      <div class="card-grid">
        <ProductCard
          v-for="product in store.products"
          :key="product.id"
          :product="product"
          @click="goToDetail(product)"
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
.product-index {
  max-width: 1200px;
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
  color: var(--color-primary);
  background: var(--color-primary-soft);
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
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.filter-chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
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
