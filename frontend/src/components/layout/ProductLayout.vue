<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCategories } from '@/api/products'

const route = useRoute()
const router = useRouter()

/* ── Page title props ── */
const props = defineProps({
  pageTitle: { type: String, default: 'Products' },
  pageSubtitle: { type: String, default: '' },
})

/* ── Category tree state ── */
const categories = ref({})
const selectedL1 = ref('')
const selectedL2 = ref('')
const selectedL3 = ref('')
const selectedProductClassId = ref(null)
const expandedL1 = ref({})

onMounted(async () => {
  try {
    const res = await getCategories()
    categories.value = res.data || res || {}
  } catch { /* ignore */ }
})

const l1List = computed(() =>
  Object.entries(categories.value).map(([key, val]) => ({
    key,
    label: val.label,
    children: val.children || [],
    count: val.count || 0,
    l2Counts: val.l2_counts || {},
  })).filter(l1 => l1.count > 0)  // only show categories with products
)

/* Get L3 children for a given L1+L2 */
function getL3Children(l1Key, l2Name) {
  // L3 children come from ProductClass tree - for now use the categories API data
  // L3 entries are ProductClass entries whose parent is the L2 ProductClass
  const l2Data = categories.value[l1Key]?.l2_counts?.[l2Name]
  if (l2Data?.children) return l2Data.children
  return []
}

function toggleL1(key) {
  expandedL1.value[key] = !expandedL1.value[key]
  if (selectedL1.value === key && !expandedL1.value[key]) {
    clearFilter()
  }
}

function selectL1(key) {
  selectedL1.value = key
  selectedL2.value = ''
  selectedL3.value = ''
  selectedProductClassId.value = null
  emitFilter()
}

function selectL2(l1Key, l2Name) {
  selectedL1.value = l1Key
  selectedL2.value = l2Name
  selectedL3.value = ''
  expandedL1.value[l1Key] = true
  const l2Data = categories.value[l1Key]?.l2_counts?.[l2Name]
  selectedProductClassId.value = l2Data?.id || null
  emitFilter()
}

function selectL3(l1Key, l2Name, l3Name) {
  selectedL1.value = l1Key
  selectedL2.value = l2Name
  selectedL3.value = l3Name
  expandedL1.value[l1Key] = true
  // L3 filtering by name
  selectedProductClassId.value = null
  emitFilter()
}

function clearFilter() {
  selectedL1.value = ''
  selectedL2.value = ''
  selectedL3.value = ''
  selectedProductClassId.value = null
  emitFilter()
}

const emit = defineEmits(['filter', 'search'])
function emitFilter() {
  emit('filter', {
    l1: selectedL1.value,
    l2: selectedL2.value,
    l3: selectedL3.value,
    productClassId: selectedProductClassId.value,
  })
}

/* ── Search state ── */
const searchQuery = ref('')
const localSearchQuery = ref('')

function handleSearch() {
  const q = localSearchQuery.value.trim()
  searchQuery.value = q
  emit('search', q)
}

function clearSearch() {
  localSearchQuery.value = ''
  searchQuery.value = ''
  emit('search', '')
}

// Sync with route query on mount
onMounted(() => {
  if (route.query.q) {
    localSearchQuery.value = route.query.q
    searchQuery.value = route.query.q
  }
})

/* L3 tags for the selected L2 */
const l3Tags = computed(() => {
  if (!selectedL1.value || !selectedL2.value) return []
  const l2Data = categories.value[selectedL1.value]?.l2_counts?.[selectedL2.value]
  if (l2Data?.children) return l2Data.children
  // Fallback: get L3 from ProductClass children
  return []
})

const hasActiveFilter = computed(() => selectedL1.value || selectedL2.value)

/* Expose for parent to set filter from route */
function setFilter(l1, l2, l3) {
  if (l1) selectedL1.value = l1
  if (l2) selectedL2.value = l2
  if (l3) selectedL3.value = l3
  if (l1) expandedL1.value[l1] = true
}

defineExpose({ setFilter, clearFilter, selectedL1, selectedL2, selectedL3 })
</script>

<template>
  <div class="product-layout">
    <!-- Top: Category pills bar (horizontal) -->
    <div class="category-pills-bar" v-if="l1List.length">
      <button
        v-for="l1 in l1List"
        :key="l1.key"
        class="cat-pill"
        :class="{ 'cat-pill--active': selectedL1 === l1.key }"
        @click="selectL1(l1.key)"
      >
        {{ l1.label }}
        <span class="cat-pill-count">{{ l1.count }}</span>
      </button>
      <button v-if="hasActiveFilter" class="cat-pill-clear" @click="clearFilter">Clear filter</button>
    </div>

    <!-- L2 sub-pills (shown when L1 is selected) -->
    <div v-if="selectedL1 && l1List.find(l => l.key === selectedL1)?.children.length" class="cat-l2-pills">
      <button
        v-for="l2 in l1List.find(l => l.key === selectedL1)?.children || []"
        :key="l2"
        class="cat-l2-pill"
        :class="{ 'cat-l2-pill--active': selectedL2 === l2 }"
        @click="selectL2(selectedL1, l2)"
      >
        {{ l2 }}
      </button>
    </div>

    <!-- Content area -->
    <div class="product-content">
      <!-- Page title (shared across product pages) -->
      <div class="product-page-header">
        <h1 class="product-page-title">{{ pageTitle }}</h1>
        <p v-if="pageSubtitle" class="product-page-subtitle">{{ pageSubtitle }}</p>
      </div>

      <!-- Search bar -->
      <div class="product-search-bar">
        <div class="product-search-wrap">
          <svg class="product-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <input
            v-model="localSearchQuery"
            class="product-search-input"
            placeholder="Search products by name, CAS, catalog no..."
            @keyup.enter="handleSearch"
          />
          <button v-if="localSearchQuery" class="product-search-clear" @click="clearSearch">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          </button>
        </div>
        <button class="product-search-btn" @click="handleSearch">Search</button>
      </div>

      <!-- L3 filter tags (shown when L2 is selected) -->
      <div v-if="selectedL2 && l3Tags.length > 0" class="l3-tags">
        <span class="l3-label">Subcategory:</span>
        <button
          v-for="l3 in l3Tags"
          :key="l3"
          class="l3-tag"
          :class="{ 'l3-tag--active': selectedL3 === l3 }"
          @click="selectL3(selectedL1, selectedL2, l3)"
        >
          {{ l3 }}
        </button>
        <button v-if="selectedL3" class="l3-tag-clear" @click="selectL2(selectedL1, selectedL2)">×</button>
      </div>

      <!-- Active filter display -->
      <div v-if="hasActiveFilter" class="active-filter">
        <span class="filter-tag">
          {{ categories[selectedL1]?.label || selectedL1 }}
          <span v-if="selectedL2"> › {{ selectedL2 }}</span>
          <span v-if="selectedL3"> › {{ selectedL3 }}</span>
          <button class="filter-tag-x" @click="clearFilter">×</button>
        </span>
      </div>

      <!-- Slot for page content -->
      <slot />
    </div>
  </div>
</template>

<style scoped>
.product-layout { max-width: 1280px; margin: 0 auto; padding: 0 32px; }

/* Category pills bar (horizontal, top) */
.category-pills-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 12px 0 20px; margin-bottom: 20px;
  border-bottom: 1px solid var(--color-border);
}
.cat-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: 9999px;
  font-size: 13px; font-weight: 500; font-family: var(--font-sans);
  background: var(--color-surface); color: var(--color-text-secondary);
  border: 1.5px solid var(--color-border); cursor: pointer;
  transition: all 0.15s;
}
.cat-pill:hover { border-color: var(--color-primary); color: var(--color-text); }
.cat-pill--active { background: var(--color-primary); border-color: var(--color-primary); color: white; }
.cat-pill-count { font-size: 11px; opacity: 0.7; }
.cat-pill-clear {
  font-size: 12px; background: none; border: none; cursor: pointer; color: var(--color-text-tertiary);
  margin-left: 4px; font-family: var(--font-sans);
}
.cat-pill-clear:hover { color: var(--color-danger); }

/* L2 sub-pills */
.cat-l2-pills {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 0 0 16px; margin-top: -8px; margin-bottom: 8px;
}
.cat-l2-pill {
  padding: 5px 14px; border-radius: 9999px;
  font-size: 12px; font-weight: 500; font-family: var(--font-sans);
  background: var(--color-bg); color: var(--color-text-secondary);
  border: 1px solid var(--color-border); cursor: pointer;
  transition: all 0.15s;
}
.cat-l2-pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
.cat-l2-pill--active { background: var(--color-primary-light); border-color: var(--color-primary); color: var(--color-primary); font-weight: 600; }

/* Product content area */
.product-content { flex: 1; min-width: 0; }

/* Page header */
.product-page-header { margin-bottom: 12px; }
.product-page-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0 0 4px; }
.product-page-subtitle { font-size: 14px; color: var(--color-text-secondary); margin: 0; }

/* Product search bar */
.product-search-bar {
  display: flex; gap: 8px; margin-bottom: 12px;
}
.product-search-wrap {
  flex: 1; position: relative; display: flex; align-items: center;
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  background: var(--color-surface); transition: border-color 0.2s;
}
.product-search-wrap:focus-within {
  border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-light);
}
.product-search-icon {
  position: absolute; left: 12px; color: var(--color-text-tertiary); pointer-events: none;
}
.product-search-input {
  width: 100%; padding: 10px 12px 10px 36px; border: none; background: transparent;
  font-size: 14px; color: var(--color-text); outline: none; font-family: var(--font-sans);
}
.product-search-input::placeholder { color: var(--color-text-tertiary); }
.product-search-clear {
  position: absolute; right: 8px; background: none; border: none; cursor: pointer;
  color: var(--color-text-tertiary); padding: 4px; display: flex; align-items: center;
}
.product-search-clear:hover { color: var(--color-text); }
.product-search-btn {
  padding: 0 16px; background: var(--color-primary); color: white; border: none;
  border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer;
  font-family: var(--font-sans); white-space: nowrap;
}
.product-search-btn:hover { background: var(--color-primary-dark); }

/* L3 tags */
.l3-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.l3-label { font-size: 11px; font-weight: 600; color: var(--color-text-tertiary); text-transform: uppercase; letter-spacing: 0.04em; }
.l3-tag {
  font-size: 11px; font-weight: 500; padding: 3px 10px; border-radius: var(--radius-full);
  border: 1px solid var(--color-border); background: var(--color-surface);
  color: var(--color-text-secondary); cursor: pointer; font-family: var(--font-sans);
  transition: all 0.15s;
}
.l3-tag:hover { border-color: var(--color-primary); color: var(--color-primary); }
.l3-tag--active { background: var(--color-primary); border-color: var(--color-primary); color: white; }
.l3-tag-clear {
  font-size: 14px; background: none; border: none; cursor: pointer;
  color: var(--color-text-tertiary); padding: 2px 4px;
}
.l3-tag-clear:hover { color: var(--color-danger); }

/* Active filter */
.active-filter { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.filter-tag {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 500; color: var(--color-primary);
  background: var(--color-primary-light); padding: 4px 10px; border-radius: var(--radius-sm);
}
.filter-tag-x {
  background: none; border: none; cursor: pointer; color: var(--color-primary);
  font-size: 14px; line-height: 1; padding: 0 2px; margin-left: 2px;
}
.filter-tag-x:hover { color: var(--color-danger); }

@media (max-width: 768px) {
  .product-layout { flex-direction: column; }
  .category-sidebar { width: 100%; position: static; max-height: none; }
}
</style>
