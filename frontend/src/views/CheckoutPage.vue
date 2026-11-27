<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useBasketStore } from '@/stores/basket'
import { useAuthStore } from '@/stores/auth'
import { checkout } from '@/api/orders'
import { updateProfile } from '@/api/auth'
import { formatCurrency } from '@/utils/helpers'
import { AppButton, AppInput, EmptyState, LoadingSpinner } from '@/components/common'

const router = useRouter()
const basketStore = useBasketStore()
const authStore = useAuthStore()

const loading = ref(false)
const serverError = ref('')

/* ── Form data ── */
const paymentMethod = ref('purchase_order')
const poNumber = ref('')
const poContact = ref('')
const shippingName = ref('')
const shippingAddress = ref('')
const shippingPhone = ref('')
const shippingEmail = ref('')
const notes = ref('')

/* ── Pre-fill from user profile ── */
onMounted(() => {
  basketStore.loadBasket()
  if (authStore.user) {
    const u = authStore.user
    shippingName.value = u.shipping_name || u.nickname || u.username || ''
    shippingPhone.value = u.shipping_phone || u.phone || ''
    shippingEmail.value = u.shipping_email || u.email || ''
    shippingAddress.value = u.default_shipping_address || ''
    paymentMethod.value = u.default_payment_method || 'purchase_order'
    // ★ 2026-11-27（A-136）：**不再预填 PO Number**。
    //   `default_po_number` 是 handleCheckout 把本单 PO 写回个人资料后留下的，
    //   于是「上一张（甚至已取消的）订单的 PO 号」会一路沿用下去 —— 用户不改直接
    //   提交，就等于拿一个已失效的采购单号下单（QA 实测预填
    //   TEST-PO-…-CANCEL，来自已取消订单）。PO 号天然是**逐单**的采购授权，
    //   不该有"默认值"。下方 handleCheckout 也不再把它写回资料。
  }
})

/* ── Computed ── */
const items = computed(() => basketStore.items || [])
const total = computed(() => {
  if (basketStore.total && basketStore.total !== '0.00') return basketStore.total
  return basketStore.computedTotal || '0.00'
})
const isEmpty = computed(() => items.value.length === 0)

/* ── Validation ── */
const errors = ref({})

function validate() {
  errors.value = {}
  if (!shippingName.value.trim()) errors.value.shippingName = 'Recipient name is required'
  if (!shippingAddress.value.trim()) errors.value.shippingAddress = 'Shipping address is required'
  if (paymentMethod.value === 'purchase_order' && !poNumber.value.trim()) {
    errors.value.poNumber = 'PO number is required for Purchase Order payment'
  }
  return Object.keys(errors.value).length === 0
}

/* ── Submit ── */
async function handleCheckout() {
  if (!validate()) return
  loading.value = true
  serverError.value = ''

  try {
    const data = {
      payment_method: paymentMethod.value,
      shipping_name: shippingName.value.trim(),
      shipping_address: shippingAddress.value.trim(),
      shipping_phone: shippingPhone.value.trim(),
      shipping_email: shippingEmail.value.trim(),
      notes: notes.value.trim(),
    }
    if (paymentMethod.value === 'purchase_order') {
      data.po_number = poNumber.value.trim()
      data.po_contact = poContact.value.trim()
    }

    const res = await checkout(data)
    const order = res.data || res

    // Save shipping info to user profile for next time
    // ★ 2026-11-27（A-136）：**刻意不再写 default_po_number** ——
    //   写回去就等于给下一单造了一个"默认 PO 号"，而 PO 是逐单的采购授权，
    //   沿用旧号（尤其已取消订单的号）会让账单落到错误的采购单上。
    try {
      await updateProfile({
        shipping_name: shippingName.value.trim(),
        shipping_phone: shippingPhone.value.trim(),
        shipping_email: shippingEmail.value.trim(),
        default_shipping_address: shippingAddress.value.trim(),
        default_payment_method: paymentMethod.value,
      })
      // Update local auth store
      authStore.updateUser({
        shipping_name: shippingName.value.trim(),
        shipping_phone: shippingPhone.value.trim(),
        shipping_email: shippingEmail.value.trim(),
        default_shipping_address: shippingAddress.value.trim(),
        default_payment_method: paymentMethod.value,
      })
    } catch (e) {
      // Non-critical: don't block checkout if profile save fails
      console.warn('Failed to save shipping info to profile:', e)
    }

    basketStore.clearBasket()
    router.push(`/orders/${order.id}`)
  } catch (err) {
    serverError.value = err?.response?.data?.meta?.error?.message || err?.data?.meta?.error?.message || err?.message || 'Checkout failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="checkout-page">
    <h1 class="page-title">Checkout</h1>

    <!-- ★ 2026-11-27（A-148）：必须先判 loading，再判 isEmpty。
         原来只有 `v-if="isEmpty"`，而 `basketStore.items` 初值是 `[]`、
         `loadBasket()` 在 onMounted 才发起 ⇒ 直接在地址栏敲 /checkout 时，
         第一帧必然渲染「Your cart is empty」再被真实数据替换（QA 报的
         「有商品也显示空购物车」）。经 /cart → Place Order 进来时篮子已加载过，
         所以只有"直接输入地址"能复现 —— 与 QA 的定位完全一致。 -->
    <LoadingSpinner v-if="basketStore.loading" text="Loading cart..." />

    <!-- Empty cart -->
    <EmptyState
      v-else-if="isEmpty"
      title="Your cart is empty"
      description="Browse our catalog to find the reagents you need."
      icon="ShoppingCart"
    >
      <template #action>
        <AppButton variant="primary" to="/products">Browse Products</AppButton>
      </template>
    </EmptyState>

    <form v-else class="checkout-form" @submit.prevent="handleCheckout">
      <!-- Server error -->
      <div v-if="serverError" class="error-banner">{{ serverError }}</div>

      <!-- Shipping Info -->
      <section class="checkout-section">
        <h2 class="section-title">Shipping Information</h2>
        <div class="form-grid">
          <div class="form-group">
            <AppInput v-model="shippingName" label="Recipient Name *" placeholder="Dr. John Smith" :error="errors.shippingName" />
          </div>
          <div class="form-group">
            <AppInput v-model="shippingPhone" label="Phone" placeholder="+1-617-555-0123" />
          </div>
          <div class="form-group">
            <AppInput v-model="shippingEmail" label="Email" type="email" placeholder="jsmith@university.edu" />
          </div>
          <div class="form-group form-group--full">
            <AppInput v-model="shippingAddress" label="Shipping Address *" type="textarea" rows="3" placeholder="123 Lab Street, Cambridge, MA 02139, USA" :error="errors.shippingAddress" />
          </div>
        </div>
      </section>

      <!-- Payment Method -->
      <section class="checkout-section">
        <h2 class="section-title">Payment Method</h2>
        <div class="payment-options">
          <label class="payment-option" :class="{ 'payment-option--active': paymentMethod === 'purchase_order' }">
            <input type="radio" v-model="paymentMethod" value="purchase_order" />
            <div class="payment-option-content">
              <span class="payment-option-title">Purchase Order</span>
              <span class="payment-option-desc">Pay by institutional PO number (Net 30/60/90)</span>
            </div>
          </label>
          <label class="payment-option" :class="{ 'payment-option--active': paymentMethod === 'credit_card' }">
            <input type="radio" v-model="paymentMethod" value="credit_card" />
            <div class="payment-option-content">
              <span class="payment-option-title">Credit Card / Online Payment</span>
              <span class="payment-option-desc">Pay immediately by credit card</span>
            </div>
          </label>
          <label class="payment-option" :class="{ 'payment-option--active': paymentMethod === 'wire_transfer' }">
            <input type="radio" v-model="paymentMethod" value="wire_transfer" />
            <div class="payment-option-content">
              <span class="payment-option-title">Wire Transfer</span>
              <span class="payment-option-desc">Bank transfer after invoice is issued</span>
            </div>
          </label>
          <label class="payment-option" :class="{ 'payment-option--active': paymentMethod === 'quote' }">
            <input type="radio" v-model="paymentMethod" value="quote" />
            <div class="payment-option-content">
              <span class="payment-option-title">Request Quote</span>
              <span class="payment-option-desc">Get a custom price quote for bulk or special orders</span>
            </div>
          </label>
        </div>

        <!-- PO fields -->
        <div v-if="paymentMethod === 'purchase_order'" class="po-fields">
          <div class="form-group">
            <AppInput v-model="poNumber" label="PO Number *" placeholder="PO-2026-00123" :error="errors.poNumber" />
          </div>
          <div class="form-group">
            <AppInput v-model="poContact" label="PO Contact" placeholder="Procurement department contact" />
          </div>
        </div>
      </section>

      <!-- Order Notes -->
      <section class="checkout-section">
        <h2 class="section-title">Order Notes</h2>
        <AppInput v-model="notes" type="textarea" rows="2" placeholder="Special instructions, delivery preferences..." />
      </section>

      <!-- Order Summary -->
      <section class="checkout-section checkout-summary">
        <h2 class="section-title">Order Summary</h2>
        <div class="summary-items">
          <!-- ★ 2026-11-27（A-135）：摘要行原来只有「名称 ×数量 金额」，
               缺 SKU（同款不同规格只靠名称无法区分）也缺小计行。
               现在：名称 + SKU 码 + 单价×数量 + 行小计，摘要尾部再补 Subtotal。 -->
          <div v-for="item in items" :key="item.id || item.sku_id" class="summary-item">
            <span class="summary-item-main">
              <span class="summary-item-name">{{ item.product_name || `SKU ${item.sku_code || item.sku_id}` }}</span>
              <span v-if="item.sku_code" class="summary-item-sku">{{ item.sku_code }}</span>
            </span>
            <span class="summary-item-qty">x{{ item.quantity }}</span>
            <span class="summary-item-price">{{ formatCurrency(item.subtotal || (item.unit_price * item.quantity) || 0) }}</span>
          </div>
        </div>
        <div class="summary-subtotal">
          <span>Subtotal ({{ items.length }} {{ items.length === 1 ? 'line' : 'lines' }})</span>
          <span class="summary-subtotal-value">{{ formatCurrency(total) }}</span>
        </div>
        <div class="summary-total">
          <span>Total</span>
          <span class="summary-total-value">{{ formatCurrency(total) }}</span>
        </div>
      </section>

      <!-- Submit -->
      <AppButton variant="primary" size="lg" nativeType="submit" :loading="loading" style="width:100%">
        <span v-if="paymentMethod === 'quote'">Request Quote</span>
        <span v-else>Place Order</span>
      </AppButton>
    </form>
  </div>
</template>

<style scoped>
.checkout-page { max-width: 800px; margin: 0 auto; }
.page-title { font-size: 22px; font-weight: 800; color: var(--color-text); margin: 0 0 20px; }

.checkout-section { margin-bottom: 24px; }
.section-title { font-size: 16px; font-weight: 700; color: var(--color-text); margin: 0 0 12px; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group--full { grid-column: 1 / -1; }
.form-label { font-size: 13px; font-weight: 600; color: var(--color-text-secondary); }
.form-error { font-size: 12px; color: var(--color-danger); }

.payment-options { display: flex; flex-direction: column; gap: 8px; }
.payment-option {
  display: flex; align-items: flex-start; gap: 12px; padding: 14px 16px;
  border: 1px solid var(--color-border); border-radius: var(--radius-md); cursor: pointer;
  transition: all 0.15s;
}
.payment-option:hover { border-color: var(--color-primary); }
.payment-option--active { border-color: var(--color-primary); background: var(--color-primary-light); }
.payment-option input[type="radio"] { margin-top: 2px; accent-color: var(--color-primary); }
.payment-option-content { display: flex; flex-direction: column; gap: 2px; }
.payment-option-title { font-size: 14px; font-weight: 600; color: var(--color-text); }
.payment-option-desc { font-size: 12px; color: var(--color-text-secondary); }

.po-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }

.summary-items { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.summary-item { display: flex; align-items: center; gap: 12px; font-size: 14px; }
/* ★ 2026-11-27（A-135）：名称与 SKU 竖排成一组，SKU 用小号等宽字体；
   min-width:0 + 换行兜底，避免长商品名把数量与金额挤出卡片。 */
.summary-item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.summary-item-name { color: var(--color-text); overflow-wrap: anywhere; }
.summary-item-sku { font-size: 11px; font-family: var(--font-mono); color: var(--color-text-tertiary); }
.summary-item-qty { color: var(--color-text-secondary); flex-shrink: 0; }
.summary-item-price { font-weight: 600; color: var(--color-text); font-variant-numeric: tabular-nums; flex-shrink: 0; white-space: nowrap; }
.summary-subtotal { display: flex; justify-content: space-between; padding-top: 12px; border-top: 1px solid var(--color-border); font-size: 14px; color: var(--color-text-secondary); }
.summary-subtotal-value { font-variant-numeric: tabular-nums; color: var(--color-text); }
.summary-total { display: flex; justify-content: space-between; padding-top: 12px; margin-top: 8px; border-top: 1px solid var(--color-border); font-size: 16px; font-weight: 700; }
.summary-total-value { color: var(--color-primary); }

.error-banner {
  padding: 12px 16px; background: var(--color-danger-bg); border: 1px solid #FCA5A5; border-radius: var(--radius-md);
  color: var(--color-danger); font-size: 14px; margin-bottom: 16px;
}

@media (max-width: 768px) {
  .form-grid, .po-fields { grid-template-columns: 1fr; }
}
</style>
