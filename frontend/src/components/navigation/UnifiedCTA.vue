<script setup>
/**
 * UnifiedCTA — Consistent bottom CTA for all detail pages.
 *
 * Props:
 *   - title: CTA headline
 *   - subtitle: CTA description
 *   - showCart: Show "Add to Cart" button
 *   - showRFQ: Show "Request Quote" button
 *   - showExplore: Show "Explore Products" button
 *   - productId: For cart add (optional)
 */
import { useRouter } from 'vue-router'

const props = defineProps({
  title: { type: String, default: 'Request this Product' },
  subtitle: { type: String, default: 'Add items to cart or submit a quote request.' },
  showCart: { type: Boolean, default: false },
  showRFQ: { type: Boolean, default: true },
  showExplore: { type: Boolean, default: true },
  productId: { type: [Number, String], default: null },
})

const router = useRouter()
const emit = defineEmits(['addToCart'])

function requestQuote() {
  const query = props.productId ? { product_id: props.productId } : {}
  router.push({ path: '/quote-request', query })
}

function explore() {
  router.push('/products')
}
</script>

<template>
  <section class="ucta" aria-label="Call to action">
    <div class="ucta-inner">
      <h3 class="ucta-title">{{ title }}</h3>
      <p class="ucta-subtitle">{{ subtitle }}</p>
      <div class="ucta-actions">
        <button v-if="showCart" class="ucta-btn ucta-btn-primary" @click="emit('addToCart')">
          Add to Cart
        </button>
        <button v-if="showRFQ" class="ucta-btn ucta-btn-outline" @click="requestQuote">
          Request Quote
        </button>
        <button v-if="showExplore" class="ucta-btn ucta-btn-ghost" @click="explore">
          Browse Catalog
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ucta {
  margin-top: 16px;
}
.ucta-inner {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: var(--radius-lg, 12px);
  padding: 28px 32px;
}
.ucta-title {
  font-size: 20px;
  font-weight: 800;
  margin: 0 0 6px;
  color: var(--color-text);
}
.ucta-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 16px;
}
.ucta-actions {
  display: flex;
  justify-content: flex-start;
  gap: 10px;
  flex-wrap: wrap;
}
.ucta-btn {
  height: 38px;
  padding: 0 20px;
  border-radius: var(--radius-md, 8px);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
  transition: all 0.15s;
}
.ucta-btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
}
.ucta-btn-primary:hover { background: var(--color-primary-dark, #059669); }
.ucta-btn-outline {
  background: transparent;
  color: var(--color-text);
  border: 2px solid var(--color-border);
}
.ucta-btn-outline:hover {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.ucta-btn-ghost {
  background: transparent;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}
.ucta-btn-ghost:hover {
  background: var(--color-bg);
  color: var(--color-text);
}
</style>
