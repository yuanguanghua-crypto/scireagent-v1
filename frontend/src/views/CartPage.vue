<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useBasketStore } from '@/stores/basket'
import { useAuthStore } from '@/stores/auth'
import { formatCurrency } from '@/utils/helpers'
import { AppButton, LoadingSpinner, EmptyState, toast } from '@/components/common'

const router = useRouter()
const basketStore = useBasketStore()
const authStore = useAuthStore()

/** Check if "Submit for Approval" should be visible */
const showSubmitApproval = computed(() => {
  if (!authStore.isAuthenticated) return false
  if (!authStore.organization) return false
  // All researchers (including org admins) can submit for approval
  return authStore.role === 'researcher'
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
  toast.success('Item removed from cart')
}

/** Navigate to products page */
function browseProducts() {
  router.push('/products')
}

/** Handle place order */
function handlePlaceOrder() {
  router.push('/checkout')
}

/** Handle request quote */
function handleRequestQuote() {
  router.push('/quote-request')
}

/** Handle submit for approval */
function handleSubmitApproval() {
  router.push('/checkout')
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
    <LoadingSpinner v-if="basketStore.loading" text="Loading cart..." />

    <!-- Cart Content -->
    <template v-else>
      <!-- Empty Cart -->
      <EmptyState
        v-if="basketStore.items.length === 0"
        title="Your cart is empty"
        description="Start browsing our catalog to find the reagents you need."
        icon="ShoppingCart"
      >
        <template #action>
          <AppButton variant="primary" @click="browseProducts">Browse Products</AppButton>
        </template>
      </EmptyState>

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

                <AppButton
                  variant="ghost"
                  size="sm"
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
                </AppButton>
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
              <AppButton variant="primary" style="width:100%" @click="handlePlaceOrder">
                Place Order
              </AppButton>
              <AppButton variant="outline" style="width:100%" @click="handleRequestQuote">
                Request Quote
              </AppButton>
              <AppButton
                v-if="showSubmitApproval"
                variant="outline"
                style="width:100%"
                @click="handleSubmitApproval"
              >
                Submit for Approval
              </AppButton>
            </div>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cart-page {
  max-width: var(--content-max-width);
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
