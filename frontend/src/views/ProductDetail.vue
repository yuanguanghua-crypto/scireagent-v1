<script setup>
import { onMounted, onUnmounted, ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProductsStore } from '@/stores/products'
import { useBasketStore } from '@/stores/basket'
import { formatDate, getStatusType, formatCurrency } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const store = useProductsStore()
const basketStore = useBasketStore()
const activeTab = ref('overview')

/** Per-SKU quantity tracking (reactive map: skuId -> qty) */
const skuQuantities = reactive({})

/** Get quantity for a given SKU, defaulting to 1 */
function getSkuQty(skuId) {
  return skuQuantities[skuId] ?? 1
}

/** Set quantity for a given SKU */
function setSkuQty(skuId, qty) {
  skuQuantities[skuId] = Math.max(1, qty)
}

/** Toast notification */
const toastMessage = ref('')
const toastVisible = ref(false)

function showToast(msg, duration = 2000) {
  toastMessage.value = msg
  toastVisible.value = true
  setTimeout(() => { toastVisible.value = false }, duration)
}

/** Add SKU to cart */
async function handleAddToCart(skuId) {
  const qty = getSkuQty(skuId)
  try {
    await basketStore.addItem(skuId, qty)
    showToast('Added to cart')
  } catch (err) {
    console.error('[Cart] Failed to add:', err)
    showToast('Failed to add to cart. Please try again.')
  }
}

onMounted(() => {
  store.fetchProduct(route.params.id)
})

onUnmounted(() => {
  store.clearCurrent()
})
</script>

<template>
  <div class="product-detail">
    <div v-if="store.loading" class="loading-container">
      <el-skeleton :rows="8" animated />
    </div>

    <template v-else-if="store.currentProduct">
      <!-- Breadcrumb -->
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <router-link to="/products" class="breadcrumb-link">Products</router-link>
        <span class="breadcrumb-sep" aria-hidden="true">/</span>
        <span class="breadcrumb-current">{{ store.currentProduct.name }}</span>
      </nav>

      <!-- Detail header -->
      <div class="detail-header">
        <div class="detail-header-left">
          <h1 class="detail-title">{{ store.currentProduct.name }}</h1>
          <div class="detail-tags">
            <el-tag :type="getStatusType(store.currentProduct.status)" size="small">
              {{ store.currentProduct.status }}
            </el-tag>
            <el-tag v-if="store.currentProduct.research_use_only" size="small" type="warning">RUO</el-tag>
            <span v-if="store.currentProduct.cas" class="chem-id-lg">{{ store.currentProduct.cas }}</span>
          </div>
        </div>
      </div>

      <!-- Main layout: content + sidebar -->
      <div class="detail-layout">
        <!-- Main content -->
        <div class="detail-main">
          <el-tabs v-model="activeTab" class="detail-tabs">
            <el-tab-pane label="Overview" name="overview">
              <section class="detail-section">
                <h2 class="section-title">Chemical Identity</h2>
                <div class="data-grid">
                  <div class="data-item">
                    <span class="data-label">CAS Number</span>
                    <span class="data-value data-mono">{{ store.currentProduct.cas || '—' }}</span>
                  </div>
                  <div class="data-item">
                    <span class="data-label">SMILES</span>
                    <span class="data-value data-mono data-smiles">{{ store.currentProduct.smiles || '—' }}</span>
                  </div>
                  <div class="data-item">
                    <span class="data-label">InChI</span>
                    <span class="data-value data-mono data-smiles">{{ store.currentProduct.inchi || '—' }}</span>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Purity</span>
                    <span class="data-value">{{ store.currentProduct.purity || '—' }}</span>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Storage</span>
                    <span class="data-value">{{ store.currentProduct.storage || '—' }}</span>
                  </div>
                  <div class="data-item">
                    <span class="data-label">Shipping</span>
                    <span class="data-value">{{ store.currentProduct.shipping || '—' }}</span>
                  </div>
                </div>
              </section>

              <section v-if="store.currentProduct.handling_notes" class="detail-section">
                <h2 class="section-title">Handling Notes</h2>
                <p class="section-content">{{ store.currentProduct.handling_notes }}</p>
              </section>
            </el-tab-pane>

            <el-tab-pane label="SKUs" name="skus">
              <el-table v-if="store.currentProduct.skus?.length" :data="store.currentProduct.skus" stripe size="small">
                <el-table-column prop="sku_code" label="SKU" width="140" />
                <el-table-column prop="pack_size" label="Pack Size" width="120" />
                <el-table-column prop="price" label="Price" width="120">
                  <template #default="{ row }">{{ formatCurrency(row.price, row.currency) }}</template>
                </el-table-column>
                <el-table-column prop="inventory_status" label="Status" width="120">
                  <template #default="{ row }">
                    <el-tag :type="getStatusType(row.inventory_status)" size="small">{{ row.inventory_status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Action" width="220">
                  <template #default="{ row }">
                    <div class="sku-add-row">
                      <div class="qty-control-inline">
                        <button class="qty-btn-sm" @click="setSkuQty(row.id, getSkuQty(row.id) - 1)">&#x2212;</button>
                        <span class="qty-val-sm">{{ getSkuQty(row.id) }}</span>
                        <button class="qty-btn-sm" @click="setSkuQty(row.id, getSkuQty(row.id) + 1)">+</button>
                      </div>
                      <button class="btn-add-cart" @click="handleAddToCart(row.id)">Add to Cart</button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="No SKUs available" :image-size="48" />
            </el-tab-pane>

            <el-tab-pane label="Connections" name="connections">
              <div class="connections-grid">
                <div class="connection-group">
                  <h3 class="connection-title">Applications</h3>
                  <div v-if="store.currentProduct.application_ids?.length" class="connection-list">
                    <router-link
                      v-for="id in store.currentProduct.application_ids"
                      :key="'app-'+id"
                      :to="`/applications/${id}`"
                      class="connection-link"
                    >
                      Application #{{ id }} →
                    </router-link>
                  </div>
                  <p v-else class="connection-empty">No applications linked</p>
                </div>
                <div class="connection-group">
                  <h3 class="connection-title">Methods</h3>
                  <div v-if="store.currentProduct.method_ids?.length" class="connection-list">
                    <router-link
                      v-for="id in store.currentProduct.method_ids"
                      :key="'meth-'+id"
                      :to="`/methods/${id}`"
                      class="connection-link"
                    >
                      Method #{{ id }} →
                    </router-link>
                  </div>
                  <p v-else class="connection-empty">No methods linked</p>
                </div>
                <div class="connection-group">
                  <h3 class="connection-title">Protocols</h3>
                  <div v-if="store.currentProduct.protocol_ids?.length" class="connection-list">
                    <router-link
                      v-for="id in store.currentProduct.protocol_ids"
                      :key="'proto-'+id"
                      :to="`/protocols/${id}`"
                      class="connection-link"
                    >
                      Protocol #{{ id }} →
                    </router-link>
                  </div>
                  <p v-else class="connection-empty">No protocols linked</p>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <!-- Sidebar -->
        <aside class="detail-sidebar">
          <div class="sidebar-card">
            <h3 class="sidebar-card-title">Quick Info</h3>
            <div class="sidebar-data">
              <div class="sidebar-row">
                <span class="sidebar-label">CAS</span>
                <span class="sidebar-value sidebar-mono">{{ store.currentProduct.cas || '—' }}</span>
              </div>
              <div class="sidebar-row">
                <span class="sidebar-label">Purity</span>
                <span class="sidebar-value">{{ store.currentProduct.purity || '—' }}</span>
              </div>
              <div class="sidebar-row">
                <span class="sidebar-label">Storage</span>
                <span class="sidebar-value">{{ store.currentProduct.storage || '—' }}</span>
              </div>
              <div class="sidebar-row">
                <span class="sidebar-label">Shelf Life</span>
                <span class="sidebar-value">{{ store.currentProduct.shelf_life || '—' }}</span>
              </div>
              <div class="sidebar-row">
                <span class="sidebar-label">Lead Time</span>
                <span class="sidebar-value">{{ store.currentProduct.lead_time || '—' }}</span>
              </div>
            </div>
          </div>

          <div v-if="store.currentProduct.skus?.length" class="sidebar-card sidebar-card-cta">
            <h3 class="sidebar-card-title">Order</h3>
            <div v-for="sku in store.currentProduct.skus.slice(0, 3)" :key="sku.sku_code" class="sku-option">
              <div class="sku-info">
                <span class="sku-pack">{{ sku.pack_size }}</span>
                <span class="sku-code">{{ sku.sku_code }}</span>
              </div>
              <div class="sku-right">
                <span class="sku-price">{{ formatCurrency(sku.price, sku.currency) }}</span>
                <el-tag :type="getStatusType(sku.inventory_status)" size="small" effect="light">
                  {{ sku.inventory_status }}
                </el-tag>
              </div>
              <div class="sku-add-row sidebar-add">
                <div class="qty-control-inline">
                  <button class="qty-btn-sm" @click="setSkuQty(sku.id, getSkuQty(sku.id) - 1)">&#x2212;</button>
                  <span class="qty-val-sm">{{ getSkuQty(sku.id) }}</span>
                  <button class="qty-btn-sm" @click="setSkuQty(sku.id, getSkuQty(sku.id) + 1)">+</button>
                </div>
                <button class="btn-add-cart" @click="handleAddToCart(sku.id)">Add to Cart</button>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </template>

    <div v-else class="empty-container">
      <el-empty description="Product not found">
        <el-button @click="router.push('/products')">Back to Products</el-button>
      </el-empty>
    </div>

    <!-- Toast notification -->
    <Transition name="pd-toast">
      <div v-if="toastVisible" class="pd-toast">{{ toastMessage }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.product-detail {
  max-width: 1200px;
  margin: 0 auto;
}

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  margin-bottom: 16px;
}

.breadcrumb-link {
  color: var(--color-primary);
  text-decoration: none;
}

.breadcrumb-link:hover {
  text-decoration: underline;
}

.breadcrumb-sep {
  color: var(--color-text-tertiary);
}

.breadcrumb-current {
  color: var(--color-text-secondary);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Header */
.detail-header {
  margin-bottom: 20px;
}

.detail-header-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-title {
  font-size: 26px;
  font-weight: 800;
  color: var(--color-text);
  margin: 0;
  letter-spacing: -0.01em;
}

.detail-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chem-id-lg {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

/* Layout */
.detail-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 20px;
  align-items: start;
}

.detail-main {
  min-width: 0;
}

.detail-tabs {
  margin-top: 0;
}

.detail-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 10px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--color-primary);
  display: inline-block;
}

.section-content {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text);
}

/* Data grid */
.data-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2px;
  background: var(--color-border);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.data-item {
  background: var(--color-surface);
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.data-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-tertiary);
}

.data-value {
  font-size: 13px;
  color: var(--color-text);
}

.data-mono {
  font-family: var(--font-mono);
  font-size: 12px;
  word-break: break-all;
}

.data-smiles {
  color: var(--color-text-secondary);
  font-size: 11px;
  line-height: 1.4;
}

/* Connections */
.connections-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.connection-group {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px;
}

.connection-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}

.connection-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.connection-link {
  font-size: 13px;
  color: var(--color-primary);
  text-decoration: none;
  display: block;
  padding: 4px 0;
}

.connection-link:hover {
  text-decoration: underline;
}

.connection-empty {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin: 0;
}

/* Sidebar */
.detail-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 80px;
}

.sidebar-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
}

.sidebar-card-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.sidebar-data {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sidebar-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.sidebar-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.sidebar-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
}

.sidebar-mono {
  font-family: var(--font-mono);
  font-size: 12px;
}

/* CTA sidebar */
.sidebar-card-cta {
  border-color: var(--color-primary);
  border-width: 1px;
  background: linear-gradient(180deg, var(--color-primary-soft) 0%, var(--color-surface) 30%);
}

.sku-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.sku-option:last-child {
  border-bottom: none;
}

.sku-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.sku-pack {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.sku-code {
  font-size: 11px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}

.sku-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.sku-price {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

/* Add to Cart controls */
.sku-add-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sku-add-row.sidebar-add {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border-light, #f1f5f9);
}

.qty-control-inline {
  display: flex;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  height: 32px;
}

.qty-btn-sm {
  width: 28px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary);
  transition: background-color 0.15s ease, color 0.15s ease;
  padding: 0;
  font-family: var(--font-sans);
}

.qty-btn-sm:hover {
  background: var(--color-primary);
  color: white;
}

.qty-val-sm {
  min-width: 28px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
  border-left: 1px solid var(--color-border);
  border-right: 1px solid var(--color-border);
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-add-cart {
  height: 32px;
  padding: 0 14px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
  font-family: var(--font-sans);
  white-space: nowrap;
}

.btn-add-cart:hover {
  background: #0d6d66;
}

/* Loading & empty */
.loading-container, .empty-container {
  padding: 60px 0;
  text-align: center;
}

/* Toast */
.pd-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-text);
  color: white;
  padding: 10px 24px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  z-index: 9999;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.pd-toast-enter-active,
.pd-toast-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.pd-toast-enter-from,
.pd-toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(12px);
}

@media (max-width: 900px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
  .detail-sidebar {
    position: static;
  }
  .connections-grid {
    grid-template-columns: 1fr;
  }
}
</style>
