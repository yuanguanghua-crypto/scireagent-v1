<script setup>
import { useRouter } from 'vue-router'
import { formatCurrency } from '@/utils/helpers'

defineProps({
  products: { type: Array, default: () => [] },
})

const router = useRouter()

function goToDetail(product) {
  router.push(`/products/${product.id}`)
}
</script>

<template>
  <section v-if="products.length" class="section" aria-label="Featured Products">
    <div class="section-header">
      <h2 class="section-title">Featured Products</h2>
      <router-link to="/products" class="section-link">View all →</router-link>
    </div>
    <div class="products-grid">
      <div
        v-for="product in products"
        :key="product.id"
        class="product-card"
        @click="goToDetail(product)"
      >
        <div class="product-structure">
          <div v-if="product.structure_svg" v-html="product.structure_svg" class="svg-wrap"></div>
          <div v-else class="structure-placeholder">
            <span>{{ product.formula || '—' }}</span>
          </div>
        </div>
        <div class="product-info">
          <h3 class="product-name">{{ product.name }}</h3>
          <div class="product-meta">
            <span v-if="product.catalog_no" class="meta-tag primary">{{ product.catalog_no }}</span>
            <span v-if="product.cas" class="meta-tag">{{ product.cas }}</span>
          </div>
          <p v-if="product.purity" class="product-purity">Purity: {{ product.purity }}</p>
          <div v-if="product.price" class="product-price">
            {{ formatCurrency(product.price, product.currency || 'USD') }}
          </div>
        </div>
        <button class="btn-detail" @click.stop="goToDetail(product)">View Details →</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.section { margin-bottom: 32px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}
.section-link {
  font-size: 14px;
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}
.section-link:hover { text-decoration: underline; }
.products-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.product-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.15s;
}
.product-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.product-structure {
  height: 160px;
  background: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.svg-wrap { max-width: 100%; max-height: 100%; }
.svg-wrap :deep(svg) { max-width: 100%; max-height: 160px; }
.structure-placeholder {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--color-text-secondary);
}
.product-info { padding: 14px; }
.product-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 8px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.product-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.meta-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--color-bg);
  border-radius: var(--radius-full);
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}
.meta-tag.primary {
  background: var(--color-primary);
  color: white;
}
.product-purity {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 8px;
}
.product-price {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}
.btn-detail {
  display: block;
  width: 100%;
  padding: 10px;
  background: var(--color-bg);
  border: none;
  border-top: 1px solid var(--color-border);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  cursor: pointer;
  font-family: var(--font-sans);
  transition: background 0.15s;
}
.btn-detail:hover { background: var(--color-primary-light); }
</style>
