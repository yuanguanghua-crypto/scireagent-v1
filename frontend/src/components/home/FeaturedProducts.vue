<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  products: { type: Array, default: () => [] },
})

const router = useRouter()

function formatPrice(price, currency) {
  if (price == null || price === '') return null
  const sym = currency === 'CNY' ? '¥' : '$'
  return `${sym}${parseFloat(price).toFixed(2)}`
}

function domainStyle(category) {
  const map = {
    nucleotide: { bg: '#EDE9FE', color: '#7C3AED' },
    click: { bg: '#F0FDFA', color: '#0F766E' },
    fluor: { bg: '#E0F2FE', color: '#0EA5E9' },
    bioconjugate: { bg: '#FEF3C7', color: '#CA8A04' },
    modifier: { bg: '#FCE7F3', color: '#E11D48' },
  }
  const key = (category || '').toLowerCase().replace(/[^a-z]/g, '')
  for (const [k, v] of Object.entries(map)) {
    if (key.includes(k)) return v
  }
  return { bg: '#F1F5F9', color: '#64748B' }
}

function viewAllLink() {
  return `/products`
}
</script>

<template>
  <section v-if="products.length" class="fp" aria-label="Featured products">
    <div class="section-h">
      <div>
        <h2>Featured Products</h2>
        <div class="sub">High-purity reagents for life science research</div>
      </div>
      <router-link :to="viewAllLink()" class="section-link">View all {{ products.length }}+ →</router-link>
    </div>
    <div class="section-divider"></div>

    <div class="product-grid">
      <button
        v-for="p in products.slice(0, 10)"
        :key="p.id"
        class="product-card"
        @click="router.push(`/products/${p.id}`)"
      >
        <span
          class="domain-tag"
          :style="{ background: domainStyle(p.category_l1).bg, color: domainStyle(p.category_l1).color }"
        >
          {{ p.category_l1 || 'General' }}
        </span>
        <h3>{{ p.name }}</h3>
        <div class="cas-meta">
          <span v-if="p.cas" class="cas">CAS: {{ p.cas }}</span>
          <span v-if="p.formula" class="formula-badge">{{ p.formula }}</span>
        </div>
        <div class="price-row">
          <span v-if="formatPrice(p.price, p.currency)" class="price">
            <span class="currency">{{ p.currency === 'CNY' ? '¥' : '$' }}</span>
            {{ formatPrice(p.price, p.currency) }}
          </span>
          <span v-else class="price">—</span>
          <span class="stock in-stock">In Stock</span>
        </div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.fp {
  padding: 8px 0 48px;
}
.section-h {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 20px;
}
.section-h h2 {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}
.sub {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.section-link {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-primary);
  text-decoration: none;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.section-link:hover {
  color: var(--color-primary-hover);
  gap: 8px;
}
.section-divider {
  height: 2px;
  width: 80px;
  background: linear-gradient(90deg, var(--color-primary) 0%, var(--color-teal-100) 100%);
  border-radius: 2px;
  margin-bottom: 24px;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}

.product-card {
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  padding: 20px;
  text-decoration: none;
  color: inherit;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.product-card::before {
  content: '';
  position: absolute;
  top: -1.5px;
  left: 15%;
  right: 15%;
  height: 3px;
  background: linear-gradient(90deg, var(--color-primary), #38BDF8);
  border-radius: 0 0 3px 3px;
  opacity: 0;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.product-card:hover {
  border-color: var(--color-teal-100);
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.10);
}
.product-card:hover::before {
  opacity: 1;
  left: 10%;
  right: 10%;
}

.domain-tag {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.product-card h3 {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.3;
  margin: 0 0 4px;
  color: var(--color-text);
}
.cas-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.cas {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}
.formula-badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: var(--color-gray-100);
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}
.price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--color-gray-100);
}
.price {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
}
.currency {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-tertiary);
}
.stock {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.stock.in-stock {
  background: #D1FAE5;
  color: #065F46;
}

@media (max-width: 1024px) {
  .product-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 768px) {
  .product-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .product-grid { grid-template-columns: 1fr; }
}
</style>
