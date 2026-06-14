<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProductsStore } from '@/stores/products'
import ProductLayout from '@/components/layout/ProductLayout.vue'
import ProductCard from '@/components/cards/ProductCard.vue'

const router = useRouter()
const store = useProductsStore()
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = 20

const productLayoutRef = ref(null)

/* Current filter state from ProductLayout */
const currentFilter = ref({})

onMounted(() => {
  store.fetchProducts()
})

function onFilterChange(filter) {
  currentFilter.value = filter
  currentPage.value = 1
  fetchProducts()
}

function fetchProducts() {
  const params = { page: currentPage.value, page_size: pageSize }
  if (searchQuery.value) params.search = searchQuery.value
  if (currentFilter.value.productClassId) {
    params.product_class_id = currentFilter.value.productClassId
  } else if (currentFilter.value.l1) {
    params.category_l1 = currentFilter.value.l1
  }
  store.fetchProducts(params)
}

function handleSearch() {
  currentPage.value = 1
  fetchProducts()
}

function onSearch(query) {
  searchQuery.value = query
  currentPage.value = 1
  fetchProducts()
}

function handlePageChange(page) {
  currentPage.value = page
  fetchProducts()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function goToDetail(product) {
  router.push(`/products/${product.id}`)
}

const resultCount = computed(() => store.total || store.products.length)
const totalPages = computed(() => Math.ceil(resultCount.value / pageSize))
</script>

<template>
  <div class="product-index">
    <ProductLayout
      ref="productLayoutRef"
      page-title="Products"
      page-subtitle="Browse scientific reagents with full chemical identity and context."
      @filter="onFilterChange"
      @search="onSearch"
    >
      <!-- Result count -->
      <div class="result-info">
        <span class="result-count">{{ resultCount }} results</span>
      </div>

      <!-- Loading -->
      <div v-if="store.loading" class="loading-grid">
        <div v-for="i in 6" :key="i" class="skeleton-card">
          <div class="skeleton-line sk-w60"></div>
          <div class="skeleton-line sk-w80"></div>
          <div class="skeleton-line sk-w40"></div>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="store.products.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        <p>No products found</p>
      </div>

      <!-- Product grid -->
      <div v-else>
        <div class="product-grid">
          <ProductCard
            v-for="product in store.products"
            :key="product.id"
            :product="product"
            @click="goToDetail(product)"
          />
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="pagination">
          <button class="page-btn" :disabled="currentPage <= 1" @click="handlePageChange(currentPage - 1)">← Prev</button>
          <span class="page-info">Page {{ currentPage }} of {{ totalPages }}</span>
          <button class="page-btn" :disabled="currentPage >= totalPages" @click="handlePageChange(currentPage + 1)">Next →</button>
        </div>
      </div>
    </ProductLayout>
  </div>
</template>

<style scoped>
.product-index { }

/* Search bar - now in ProductLayout */

/* Results */
.result-info { margin-bottom: 10px; }
.result-count { font-size: 13px; color: var(--color-text-secondary); }
.product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.loading-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.skeleton-card { padding: 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); display: flex; flex-direction: column; gap: 8px; }
.skeleton-line { height: 14px; background: var(--color-bg); border-radius: 4px; }
.sk-w60 { width: 60%; } .sk-w80 { width: 80%; } .sk-w40 { width: 40%; }
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 60px 0; color: var(--color-text-tertiary); }
.empty-state p { margin: 0; font-size: 15px; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 20px 0; }
.page-btn {
  height: 36px; padding: 0 16px; background: var(--color-surface); color: var(--color-text);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-family: var(--font-sans); font-size: 13px; font-weight: 500; cursor: pointer;
}
.page-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 13px; color: var(--color-text-secondary); }
</style>
