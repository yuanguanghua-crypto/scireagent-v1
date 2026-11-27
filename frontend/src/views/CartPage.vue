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

/**
 * 该行的 `product_structure_svg` 是不是**真结构式**（A-178）。
 *
 * 与 ProductDetail.vue:219 同一判据：数据里存在批量的
 * "Structure rendering requires RDKit.js" 占位卡，它带产品名/分子式/MW，
 * 缩到 56px 只是一团糊字，不能当商品图展示。
 */
function hasRealStructure(item) {
  const svg = item?.product_structure_svg || ''
  return !!svg && !svg.includes('Structure rendering requires')
}

/** Handle place order */
/**
 * ★ 2026-11-27（A-125）：结账与报价的登录门槛**本来就不一样**，这是业务规则
 * （下单要账户与账单主体；询价允许访客先问）。真正的缺陷是**一句话都没说**：
 * 访客点 Place Order 被瞬间甩到 /login?redirect=/checkout，全程无解释。
 * 现在先明确告知「下单需要登录、购物车会保留」，再跳登录页；
 * 同时按钮下方常驻一句说明，访客不必靠"点一下试试"才知道门槛。
 */
function handlePlaceOrder() {
  if (!authStore.isAuthenticated) {
    toast.info('Placing an order requires an account — your cart will be kept.')
    router.push({ path: '/login', query: { redirect: '/checkout' } })
    return
  }
  router.push('/checkout')
}

/** Handle request quote */
function handleRequestQuote() {
  // ★ 2026-11-27（A-129）：显式标记来源，询价页据此决定要不要把购物车商品带过去。
  //   不加这个参数的话，任何入口进来的询价页都会"自动"塞满购物车里的东西。
  router.push({ path: '/quote-request', query: { from: 'cart' } })
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
              <!-- ★ 2026-11-27（A-178）：购物车行原本是纯文本、没有任何图。
                   本仓库没有栅格图片字段，"商品图"只能是产品的结构式 SVG。
                   ⚠️ 实测数据侧要小心：不少产品的 `structure_svg` 根本不是结构式，
                   而是一张写着 "Structure rendering requires RDKit.js" 的占位卡
                   （带产品名/分子式/MW）。产品详情页已经有同样的判断
                   （ProductDetail.vue:219），这里沿用同一条件 —— 占位卡一律**不当图**
                   显示，改显示中性占位，绝不把"渲染失败"的卡片缩成缩略图糊弄用户。 -->
              <div class="cart-item-thumb" aria-hidden="true">
                <span v-if="hasRealStructure(item)" class="cart-item-thumb-svg" v-html="item.product_structure_svg"></span>
                <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
                  <circle cx="6" cy="18" r="2.4"/><circle cx="18" cy="6" r="2.4"/>
                  <path d="M7.7 16.3L16.3 7.7"/>
                </svg>
              </div>
              <div class="cart-item-info">
                <!-- ★ 2026-11-27（A-143）：商品名原来是纯文本 h3，点了没反应。
                     购物车行必须能回到商品详情 —— 用 `product_slug` 走人类可读 URL；
                     slug 缺失时退回数字 id（与产品页 /products/:id 的兼容路由一致）。 -->
                <h3 class="cart-item-name">
                  <router-link
                    v-if="item.product_slug || item.product"
                    class="cart-item-name-link"
                    :to="item.product_slug ? `/products/${item.product_slug}` : `/products/${item.product}`"
                  >{{ item.product_name || item.name || 'Product' }}</router-link>
                  <template v-else>{{ item.product_name || item.name || 'Product' }}</template>
                </h3>
                <div class="cart-item-meta">
                  <!-- ★ 2026-11-27（A-143 顺带）：序列化器给的字段是 `product_cas`，
                       这里原来读 `item.cas` ⇒ CAS 标签从来没有渲染过。 -->
                  <span v-if="item.product_cas" class="meta-tag">CAS: {{ item.product_cas }}</span>
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

              <!-- ★ 2026-11-27（A-125）：把两种门槛的差异写成一句话，访客不用试点才知道。 -->
              <p v-if="!authStore.isAuthenticated" class="summary-note">
                Placing an order needs an account. Quote requests can be submitted as a guest.
              </p>
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

/* ★ 2026-11-27（A-178）：结构式缩略图。固定 56×56 方框 + overflow hidden，
   结构式 SVG 的原始 viewBox 尺寸差异很大，必须由容器约束而不是靠 SVG 自己。 */
.cart-item-thumb {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text-tertiary);
  overflow: hidden;
}
.cart-item-thumb-svg {
  width: 100%;
  height: 100%;
  display: block;
}
.cart-item-thumb-svg :deep(svg) {
  width: 100%;
  height: 100%;
  /* 结构式多半是黑线稿，缩到 56px 时靠 contain 保住比例，不拉伸变形 */
  max-width: 100%;
  max-height: 100%;
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

.cart-item-name-link {
  color: inherit;
  text-decoration: none;
}
.cart-item-name-link:hover {
  color: var(--color-emerald-500, var(--color-primary));
  text-decoration: underline;
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

.summary-note {
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-text-tertiary);
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
