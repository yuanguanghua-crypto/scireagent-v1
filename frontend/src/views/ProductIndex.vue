<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProductsStore } from '@/stores/products'
import ProductLayout from '@/components/layout/ProductLayout.vue'
import ProductCard from '@/components/cards/ProductCard.vue'
import { LoadingSpinner, EmptyState } from '@/components/common'

const router = useRouter()
const store = useProductsStore()
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = 20

// ── S5 前端接入：知识关联强度排序 ──────────────
// value 直接对应后端 ordering 参数；'default' 不传 ordering（走后端默认序）
const sortOption = ref('default')
const sortOptions = [
  { value: 'default', label: '默认' },
  { value: 'name', label: '名称 A→Z' },
  { value: '-created_at', label: '最新上架' },
  { value: '-aggregate_relevance_score', label: '知识关联最强' },
]

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
  if (sortOption.value && sortOption.value !== 'default') {
    params.ordering = sortOption.value
  }
  store.fetchProducts(params)
}

function onSortChange() {
  currentPage.value = 1
  fetchProducts()
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

const visiblePages = computed(() => {
  const total = totalPages.value
  const cur = currentPage.value
  const pages = [1]  // Always include page 1
  let start = Math.max(2, cur - 1)
  let end = Math.min(total, cur + 1)
  if (cur <= 2) { start = 2; end = Math.min(4, total) }
  if (cur >= total - 1) { start = Math.max(2, total - 3); end = total }
  for (let i = start; i <= end; i++) pages.push(i)
  // Deduplicate and return unique sorted pages
  return [...new Set(pages)].filter(p => p <= total)
})
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
      <!-- Result count + sort -->
      <div class="result-info">
        <span class="result-count">{{ resultCount }} results</span>
        <label class="sort-control">
          <span class="sort-label">排序</span>
          <select v-model="sortOption" class="sort-select" @change="onSortChange">
            <option v-for="o in sortOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </label>
      </div>

      <!-- Loading -->
      <div v-if="store.loading">
        <LoadingSpinner text="Loading products..." />
      </div>

      <!-- Empty -->
      <EmptyState v-else-if="store.products.length === 0"
        title="No products found"
        description="Try adjusting your search or filter."
        icon="Goods"
      />

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

          <!-- First page is included in visiblePages -->
          <span v-if="currentPage > 5" class="page-ellipsis">⋯</span>

          <!-- Page numbers around current -->
          <button
            v-for="p in visiblePages"
            :key="p"
            class="page-btn page-btn-num"
            :class="{ 'page-btn--active': p === currentPage }"
            @click="handlePageChange(p)"
          >{{ p }}</button>

          <!-- Last page -->
          <span v-if="currentPage < totalPages - 4" class="page-ellipsis">⋯</span>
          <button v-if="currentPage < totalPages - 3" class="page-btn page-btn-num" @click="handlePageChange(totalPages)">{{ totalPages }}</button>

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
.result-info { margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.result-count { font-size: 13px; color: var(--color-text-secondary); }
.sort-control { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--color-text-secondary); }
.sort-label { white-space: nowrap; }
.sort-select {
  padding: 5px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: 13px; background: var(--color-surface); color: var(--color-text);
  cursor: pointer; font-family: var(--font-sans);
}
.sort-select:hover { border-color: var(--color-primary); }
.sort-select:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 1px; }
.product-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
.pagination { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 24px 0; }
.page-btn {
  height: 36px; min-width: 36px; padding: 0 12px;
  background: var(--color-surface); color: var(--color-text);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-family: var(--font-sans); font-size: 13px; font-weight: 500; cursor: pointer;
  transition: all 0.15s;
  display: inline-flex; align-items: center; justify-content: center;
}
.page-btn:hover:not(:disabled) { border-color: var(--color-primary); color: var(--color-primary); }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn-num { min-width: 36px; }
.page-btn--active { background: var(--color-primary); border-color: var(--color-primary); color: white; }
.page-ellipsis { font-size: 14px; color: var(--color-text-tertiary); padding: 0 4px; }

/* Responsive column count for product grid */
@media (min-width: 1200px) { .product-grid { grid-template-columns: repeat(4, 1fr); } }
@media (min-width: 1500px) { .product-grid { grid-template-columns: repeat(5, 1fr); } }
@media (min-width: 1800px) { .product-grid { grid-template-columns: repeat(5, 1fr); } }

.loading-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
@media (min-width: 1200px) { .loading-grid { grid-template-columns: repeat(4, 1fr); } }
@media (min-width: 1500px) { .loading-grid { grid-template-columns: repeat(5, 1fr); } }
@media (min-width: 1800px) { .loading-grid { grid-template-columns: repeat(5, 1fr); } }
</style>
