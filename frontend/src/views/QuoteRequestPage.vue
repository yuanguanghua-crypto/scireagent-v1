<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBasketStore } from '@/stores/basket'
import { getProduct } from '@/api/products'
import http from '@/utils/http'

const route = useRoute()
const router = useRouter()
const basketStore = useBasketStore()

/* ── Form state ── */
const form = ref({
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  company_name: '',
  country: '',
  notes: '',
})

const items = ref([])
const submitting = ref(false)
const submitted = ref(false)
const submittedId = ref(null)
const errors = ref({})

/* ── Pre-fill from query or cart ── */
onMounted(async () => {
  // Pre-fill from URL query (product_id)
  const productId = route.query.product_id
  if (productId) {
    try {
      const res = await getProduct(productId)
      if (res.data) {
        items.value.push({
          product_id: res.data.id,
          product_name: res.data.name,
          catalog_no: res.data.catalog_no || '',
          quantity: 1,
          note: '',
        })
      }
    } catch {}
  }

  // Pre-fill from cart if no product in query
  if (!items.value.length && basketStore.items?.length) {
    for (const ci of basketStore.items) {
      items.value.push({
        product_id: ci.product_id || ci.product?.id,
        product_name: ci.product_name || ci.product?.name || `Product #${ci.product_id}`,
        catalog_no: ci.sku_code || '',
        quantity: ci.quantity || 1,
        note: '',
      })
    }
  }

  // Add empty row if no items
  if (!items.value.length) {
    addRow()
  }
})

function addRow() {
  items.value.push({ product_id: null, product_name: '', catalog_no: '', quantity: 1, note: '' })
}

function removeRow(idx) {
  items.value.splice(idx, 1)
  if (!items.value.length) addRow()
}

/* ── Validate ── */
function validate() {
  errors.value = {}
  if (!form.value.contact_name.trim()) errors.value.contact_name = 'Required'
  if (!form.value.contact_email.trim()) errors.value.contact_email = 'Required'
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.value.contact_email)) errors.value.contact_email = 'Invalid email'
  const validItems = items.value.filter(i => i.product_id || i.product_name.trim())
  if (!validItems.length) errors.value.items = 'At least one item required'
  return Object.keys(errors.value).length === 0
}

/* ── Submit ── */
async function handleSubmit() {
  if (!validate()) return
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      items: items.value
        .filter(i => i.product_id || i.product_name.trim())
        .map(i => ({
          product_id: i.product_id || undefined,
          quantity: i.quantity || 1,
          note: i.note || '',
        })),
    }
    const res = await http.post('/quote-requests', payload)
    submitted.value = true
    submittedId.value = res.data?.id
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="rfq-page">
    <!-- Success state -->
    <div v-if="submitted" class="rfq-success">
      <div class="rfq-success-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="16 8 10 16 7 13"/></svg>
      </div>
      <h1>Quote Request Submitted</h1>
      <p>Thank you! Our team will review your request and respond within 1-2 business days.</p>
      <p v-if="submittedId" class="rfq-ref">Reference: RFQ #{{ submittedId }}</p>
      <div class="rfq-success-actions">
        <button class="btn-primary" @click="router.push('/')">Back to Home</button>
        <button class="btn-outline" @click="router.push('/products')">Browse Products</button>
      </div>
    </div>

    <!-- Form -->
    <template v-else>
      <div class="rfq-header">
        <h1 class="rfq-title">Request a Quote</h1>
        <p class="rfq-subtitle">Tell us what you need and our team will get back to you with pricing and availability.</p>
      </div>

      <form @submit.prevent="handleSubmit" class="rfq-form">
        <!-- Contact Info -->
        <section class="rfq-section">
          <h2 class="rfq-section-title">Contact Information</h2>
          <div class="rfq-grid">
            <div class="rfq-field">
              <label class="rfq-label">Name <span class="required">*</span></label>
              <input v-model="form.contact_name" type="text" class="rfq-input" :class="{ 'has-error': errors.contact_name }" placeholder="Dr. Smith" />
              <span v-if="errors.contact_name" class="rfq-error">{{ errors.contact_name }}</span>
            </div>
            <div class="rfq-field">
              <label class="rfq-label">Email <span class="required">*</span></label>
              <input v-model="form.contact_email" type="email" class="rfq-input" :class="{ 'has-error': errors.contact_email }" placeholder="smith@lab.edu" />
              <span v-if="errors.contact_email" class="rfq-error">{{ errors.contact_email }}</span>
            </div>
            <div class="rfq-field">
              <label class="rfq-label">Phone</label>
              <input v-model="form.contact_phone" type="tel" class="rfq-input" placeholder="+1 (555) 000-0000" />
            </div>
            <div class="rfq-field">
              <label class="rfq-label">Company / Institution</label>
              <input v-model="form.company_name" type="text" class="rfq-input" placeholder="MIT BioLab" />
            </div>
            <div class="rfq-field">
              <label class="rfq-label">Country</label>
              <input v-model="form.country" type="text" class="rfq-input" placeholder="United States" />
            </div>
          </div>
        </section>

        <!-- Items -->
        <section class="rfq-section">
          <h2 class="rfq-section-title">Products</h2>
          <span v-if="errors.items" class="rfq-error rfq-error-block">{{ errors.items }}</span>
          <div class="rfq-items">
            <div v-for="(item, idx) in items" :key="idx" class="rfq-item-row">
              <div class="rfq-item-fields">
                <div class="rfq-field rfq-field-product">
                  <label v-if="idx === 0" class="rfq-label">Product</label>
                  <input v-model="item.product_name" type="text" class="rfq-input" placeholder="Product name or catalog number" />
                </div>
                <div class="rfq-field rfq-field-qty">
                  <label v-if="idx === 0" class="rfq-label">Qty</label>
                  <input v-model.number="item.quantity" type="number" min="1" class="rfq-input" />
                </div>
                <div class="rfq-field rfq-field-note">
                  <label v-if="idx === 0" class="rfq-label">Note</label>
                  <input v-model="item.note" type="text" class="rfq-input" placeholder="Pack size, grade, etc." />
                </div>
              </div>
              <button v-if="items.length > 1" type="button" class="rfq-remove-btn" @click="removeRow(idx)" title="Remove">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
          <button type="button" class="rfq-add-btn" @click="addRow">+ Add another product</button>
        </section>

        <!-- Notes -->
        <section class="rfq-section">
          <h2 class="rfq-section-title">Additional Notes</h2>
          <textarea v-model="form.notes" class="rfq-textarea" rows="4" placeholder="Special requirements, timeline, shipping preferences..."></textarea>
        </section>

        <!-- Submit -->
        <div class="rfq-actions">
          <button type="submit" class="btn-primary btn-lg" :disabled="submitting">
            <span v-if="submitting">Submitting...</span>
            <span v-else>Submit Quote Request</span>
          </button>
        </div>
      </form>
    </template>
  </div>
</template>

<style scoped>
.rfq-page {
  max-width: 760px;
  margin: 0 auto;
  padding: 24px;
}

/* Header */
.rfq-header { margin-bottom: 28px; }
.rfq-title { font-size: 26px; font-weight: 800; color: var(--color-text); margin: 0 0 6px; }
.rfq-subtitle { font-size: 14px; color: var(--color-text-secondary); margin: 0; }

/* Sections */
.rfq-section { margin-bottom: 28px; }
.rfq-section-title { font-size: 16px; font-weight: 700; color: var(--color-text); margin: 0 0 14px; padding-bottom: 6px; border-bottom: 2px solid var(--color-primary); display: inline-block; }

/* Grid */
.rfq-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.rfq-field { display: flex; flex-direction: column; gap: 4px; }
.rfq-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.required { color: #dc2626; }
.rfq-input {
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: var(--font-sans);
  color: var(--color-text);
  background: var(--color-surface);
  transition: border-color 0.15s;
}
.rfq-input:focus { outline: none; border-color: var(--color-primary); }
.rfq-input.has-error { border-color: #dc2626; }
.rfq-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: var(--font-sans);
  color: var(--color-text);
  background: var(--color-surface);
  resize: vertical;
}
.rfq-textarea:focus { outline: none; border-color: var(--color-primary); }
.rfq-error { font-size: 11px; color: #dc2626; }
.rfq-error-block { display: block; margin-bottom: 8px; }

/* Items */
.rfq-items { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.rfq-item-row { display: flex; align-items: flex-end; gap: 8px; }
.rfq-item-fields { display: flex; gap: 8px; flex: 1; }
.rfq-field-product { flex: 3; }
.rfq-field-qty { flex: 1; min-width: 70px; }
.rfq-field-note { flex: 2; }
.rfq-remove-btn {
  width: 32px; height: 38px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: 1px solid var(--color-border);
  border-radius: var(--radius-md); color: var(--color-text-tertiary);
  cursor: pointer; flex-shrink: 0;
}
.rfq-remove-btn:hover { background: #fef2f2; color: #dc2626; border-color: #dc2626; }
.rfq-add-btn {
  padding: 8px 16px;
  background: transparent;
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary);
  cursor: pointer;
  font-family: var(--font-sans);
}
.rfq-add-btn:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }

/* Actions */
.rfq-actions { margin-top: 24px; }
.btn-primary {
  height: 42px;
  padding: 0 28px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: background 0.15s;
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-lg { height: 46px; padding: 0 32px; font-size: 15px; }
.btn-outline {
  height: 42px;
  padding: 0 24px;
  background: transparent;
  color: var(--color-primary);
  border: 2px solid var(--color-primary);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-sans);
}
.btn-outline:hover { background: var(--color-primary); color: white; }

/* Success */
.rfq-success { text-align: center; padding: 60px 0; }
.rfq-success-icon { margin-bottom: 16px; }
.rfq-success h1 { font-size: 24px; font-weight: 800; margin: 0 0 8px; color: var(--color-text); }
.rfq-success p { font-size: 14px; color: var(--color-text-secondary); margin: 0 0 6px; }
.rfq-ref { font-family: var(--font-mono); font-size: 13px; color: var(--color-primary); }
.rfq-success-actions { display: flex; justify-content: center; gap: 12px; margin-top: 24px; }

@media (max-width: 768px) {
  .rfq-grid { grid-template-columns: 1fr; }
  .rfq-item-fields { flex-direction: column; }
  .rfq-field-product, .rfq-field-qty, .rfq-field-note { flex: none; }
}
</style>
