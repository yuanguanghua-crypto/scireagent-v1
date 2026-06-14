<script setup>
import { formatCurrency, getStatusType, truncate } from '@/utils/helpers'

const props = defineProps({
  product: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['click'])

function handleClick() {
  emit('click', props.product)
}

function getInventoryType(status) {
  const map = {
    in_stock: 'success',
    limited: 'warning',
    out_of_stock: 'danger',
    discontinued: 'info',
    pre_order: '',
  }
  return map[status] || 'info'
}

function getInventoryLabel(status) {
  const map = {
    in_stock: 'In Stock',
    limited: 'Limited',
    out_of_stock: 'Out of Stock',
    discontinued: 'Discontinued',
    pre_order: 'Pre-order',
  }
  return map[status] || status || 'Available'
}
</script>

<template>
  <article
    class="card product-card"
    role="button"
    tabindex="0"
    :aria-label="`Product: ${product.name}`"
    @click="handleClick"
    @keydown.enter="handleClick"
  >
    <!-- Left accent bar - product domain color -->
    <div class="card-accent" aria-hidden="true"></div>

    <div class="card-body">
      <div class="card-header">
        <div class="card-id-group">
          <span v-if="product.catalog_no" class="chem-id chem-id--primary">{{ product.catalog_no }}</span>
          <span v-if="product.cas" class="chem-id">{{ product.cas }}</span>
        </div>
        <el-tag :type="getInventoryType(product.inventory_status)" size="small" effect="light">
          {{ getInventoryLabel(product.inventory_status) }}
        </el-tag>
      </div>

      <h3 class="card-title">{{ product.name }}</h3>
      <p class="card-description">{{ truncate(product.overview || product.storage || '', 90) }}</p>

      <div class="card-footer">
        <span v-if="product.formula" class="card-spec">
          <span class="card-spec-label">Formula</span>
          <span class="card-spec-value">{{ product.formula }}</span>
        </span>
        <span v-else-if="product.purity" class="card-spec">
          <span class="card-spec-label">Purity</span>
          <span class="card-spec-value">{{ product.purity }}</span>
        </span>
        <span v-if="product.product_class_name" class="card-class">{{ product.product_class_name }}</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.product-card {
  cursor: pointer;
  display: flex;
  flex-direction: row;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: box-shadow 0.2s var(--ease-out), border-color 0.2s var(--ease-out);
}

.product-card:hover {
  box-shadow: var(--shadow-card-hover);
  border-color: var(--color-border-hover);
}

.product-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Left accent - teal for products */
.card-accent {
  width: 3px;
  flex-shrink: 0;
  background: var(--color-primary);
  border-radius: 3px 0 0 3px;
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 16px 14px;
  min-width: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-id-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chem-id {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.02em;
}

.chem-id--primary { background: var(--color-primary); color: white; }

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-description {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  margin-top: auto;
  border-top: 1px solid var(--color-border-light);
}

.card-spec {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.card-spec-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.card-spec-value {
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--color-text-secondary);
}

.card-price {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.card-class {
  font-size: 11px;
  color: var(--color-primary);
  background: var(--color-primary-light);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
</style>
