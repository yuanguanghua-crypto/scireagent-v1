<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useBasketStore } from '@/stores/basket'
import { useAuthStore } from '@/stores/auth'
import { formatCurrency } from '@/utils/helpers'

const router = useRouter()
const basketStore = useBasketStore()
const authStore = useAuthStore()

const toastMessage = ref('')
const toastVisible = ref(false)

/** Show a toast notification */
function showToast(msg, duration = 2000) {
  toastMessage.value = msg
  toastVisible.value = true
  setTimeout(() => {
    toastVisible.value = false
  }, duration)
}

/** Check if "Submit for Approval" should be visible */
const showSubmitApproval = computed(() => {
  if (!authStore.isAuthenticated) return false
  if (!authStore.organization) return false
  // Only researcher in a multi-person org
  return authStore.role === 'researcher' && !authStore.isOrgAdmin
})

/** Handle quantity increment */
function incrementQuantity(item) {
  basketStore.updateQuantity(item.id || item.sku_id || item.sku, item.quantity + 1)
}

/** Handle quantity decrement */
function decrementQuantity(item) {
  const newQty = item.quantity - 1
  if (newQty < 1) {
    handleRemove(item)
  } else {
    basketStore.updateQuantity(item.id || item.sku_id || item.sku, newQty)
  }
}

/** Remove an item from the basket */
function handleRemove(item) {
  const itemId = item.id || item.sku_id || item.sku
  basketStore.removeItem(itemId)
  showToast('Item removed from cart')
}

/** Navigate to products page */
function browseProducts() {
  router.push('/products')
}

/** Handle place order */
function handlePlaceOrder() {
  showToast('Order placement coming soon')
}

/** Handle request quote */
function handleRequestQuote() {
  showToast('Quote request coming soon')
}

/** Handle submit for approval */
function handleSubmitApproval() {
  showToast('Approval submission coming soon')
}

onMounted(() => {
  basketStore.loadBasket()
})
</script>

<template>
  <div class="cart-page">
    <!-- Page Header -->
    <div class="cart-header">
      <div class="cart-header-left">
        <h1 class="cart-title">Shopping Cart</h1>
        <span v-if="basketStore.count > 0" class="cart-count">
          ({{ basketStore.count }} {{ basketStore.count === 1 ? 'item' : 'items' }})
        </span>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="basketStore.loading" class="cart-loading">
      <div class="spinner"></div>
      <span>Loading cart...</span>
    </div>

    <!-- Cart Content -->
    <template v-else>
      <!-- Empty Cart -->
      <div v-if="basketStore.items.length === 0" class="cart-empty">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="64" height="64">
            <circle cx="9" cy="21" r="1"/>
            <circle cx="20" cy="21" r="1"/>
            <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
          </svg>
        </div>
        <h2 class="empty-title">Your cart is empty</h2>
        <p class="empty-desc">Start browsing our catalog to find the reagents you need.</p>
        <button class="btn btn-primary" @click="browseProducts">Browse Products</button>
      </div>

      <!-- Cart Items -->
      <div v-else class="cart-layout">
        <div class="cart-items-section">
          <div class="cart-items-list">
            <div v-for="item in basketStore.items" :key="item.id || item.sku_id || item.sku" class="cart-item">
              <div class="cart-item-info">
                <h3 class="cart-item-name">{{ item.product_name || item.name || 'Product' }}</h3>
                <div class="cart-item-meta">
                  <span v-if="item.cas" class="meta-tag">CAS: {{ item.cas }}</span>
                  <span v-if="item.sku_code" class="meta-tag">SKU: {{ item.sku_code }}</span>
                  <span v-if="item.pack_size" class="meta-tag">{{ item.pack_size }}</span>
                </div>
                <div class="cart-item-unit-price">
                  {{ formatCurrency(item.unit_price || item.price || 0, item.currency || 'USD') }}/ea
                </div>
              </div>

              <div class="cart-item-actions">
                <div class="qty-control">
                  <button
                    class="qty-btn"
                    @click="decrementQuantity(item)"
                    :disabled="basketStore.loading"
                    aria-label="Decrease quantity"
                  >&#x2212;</button>
                  <span class="qty-value">{{ item.quantity }}</span>
                  <button
                    class="qty-btn"
                    @click="incrementQuantity(item)"
                    :disabled="basketStore.loading"
                    aria-label="Increase quantity"
                  >+</button>
                </div>

                <div class="cart-item-subtotal">
                  {{ formatCurrency(
                    (item.unit_price || item.price || 0) * item.quantity,
                    item.currency || 'USD'
                  ) }}
                </div>

                <button
                  class="btn-remove"
                  @click="handleRemove(item)"
                  title="Remove item"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                    <line x1="10" y1="11" x2="10" y2="17"/>
                    <line x1="14" y1="11" x2="14" y2="17"/>
                  </svg>
                  Remove
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Order Summary -->
        <aside class="cart-summary">
          <div class="summary-card">
            <h3 class="summary-title">Order Summary</h3>

            <div class="summary-row">
              <span class="summary-label">Subtotal ({{ basketStore.count }} {{ basketStore.count === 1 ? 'item' : 'items' }})</span>
              <span class="summary-value">
                {{ formatCurrency(
                  parseFloat(basketStore.total) || basketStore.computedTotal,
                  'USD'
                ) }}
              </span>
            </div>

            <div class="summary-divider"></div>

            <div class="summary-actions">
              <button class="btn btn-primary btn-full" @click="handlePlaceOrder">
                Place Order
              </button>
              <button class="btn btn-outline btn-full" @click="handleRequestQuote">
                Request Quote
              </button>
              <button
                v-if="showSubmitApproval"
                class="btn btn-outline btn-full"
                @click="handleSubmitApproval"
              >
                Submit for Approval
              </button>
            </div>
          </div>
        </aside>
      </div>
    </template>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="toastVisible" class="toast">
        {{ toastMessage }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.cart-page {
  max-width: 1200px;
  margin: 0 auto;
  padding-bottom: 40px;
}

/* Header */
.cart-header {
  margin-bottom: 24px;
}

.cart-header-left {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.cart-title {
  font-size: 26px;
  font-weight: 800;
  color: var(--color-text);
  margin: 0;
  letter-spacing: -0.01em;
}

.cart-count {
  font-size: 15px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

/* Loading */
.cart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 0;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Empty State */
.cart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  text-align: center;
}

.empty-icon {
  color: var(--color-text-tertiary, #94a3b8);
  margin-bottom: 20px;
  opacity: 0.6;
}

.empty-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}

.empty-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 24px;
  max-width: 320px;
}

/* Cart Layout */
.cart-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
  align-items: start;
}

/* Cart Items */
.cart-items-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--color-border);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.cart-item {
  background: var(--color-surface);
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.cart-item-info {
  flex: 1;
  min-width: 0;
}

.cart-item-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 6px;
  line-height: 1.3;
}

.cart-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.meta-tag {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}

.cart-item-unit-price {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.cart-item-actions {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-shrink: 0;
}

/* Quantity Control */
.qty-control {
  display: flex;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  height: 32px;
}

.qty-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  border: none;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-secondary);
  transition: background-color 0.15s ease, color 0.15s ease;
  padding: 0;
  font-family: var(--font-sans);
}

.qty-btn:hover:not(:disabled) {
  background: var(--color-primary);
  color: white;
}

.qty-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.qty-value {
  min-width: 36px;
  text-align: center;
  font-size: 14px;
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

/* Subtotal */
.cart-item-subtotal {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
  min-width: 90px;
  text-align: right;
}

/* Remove Button */
.btn-remove {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text-secondary);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  transition: color 0.15s ease, background-color 0.15s ease;
  font-family: var(--font-sans);
}

.btn-remove:hover {
  color: var(--color-danger);
  background: var(--color-danger-light, #fef2f2);
}

/* Summary */
.cart-summary {
  position: sticky;
  top: 80px;
}

.summary-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 20px;
}

.summary-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 16px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.summary-label {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.summary-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.summary-divider {
  height: 1px;
  background: var(--color-border);
  margin: 16px 0;
}

.summary-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  border: 1px solid transparent;
  font-family: var(--font-sans);
  white-space: nowrap;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.btn-primary:hover {
  background: #0d6d66;
  border-color: #0d6d66;
}

.btn-outline {
  background: var(--color-surface);
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.btn-outline:hover {
  background: var(--color-primary-soft, #f0fdfa);
}

.btn-full {
  width: 100%;
}

/* Toast */
.toast {
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

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(12px);
}

/* Responsive */
@media (max-width: 900px) {
  .cart-layout {
    grid-template-columns: 1fr;
  }

  .cart-summary {
    position: static;
  }

  .cart-item {
    flex-direction: column;
    gap: 12px;
  }

  .cart-item-actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
