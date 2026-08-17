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

function formatPrice(price, currency) {
  if (price == null || price === '') return null
  const sym = currency === 'CNY' ? '¥' : '$'
  return `${sym}${parseFloat(price).toFixed(2)}`
}

// S6 四轴修饰标签 → 按轴着色（与详情页 Modification Signature 共用配色语义）
function ssChipClass(tag) {
  if (/^(A|U|C|G|T|Purine)$/.test(tag)) return 'ss-chip--base'
  if (/Methyl/.test(tag)) return 'ss-chip--base_mod'
  if (/^2'-/.test(tag)) return 'ss-chip--sugar_sub'
  if (/^(deoxy|ribose)$/.test(tag)) return 'ss-chip--sugar_type'
  return 'ss-chip--label'
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
    <!-- Left accent bar - neutral color -->
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

      <!-- S6 四轴修饰标签 -->
      <div v-if="product.substructure_tags && product.substructure_tags.parsed && product.substructure_tags.labels && product.substructure_tags.labels.length"
           class="card-substructure" aria-label="Modification signature">
        <span v-for="(tag, i) in product.substructure_tags.labels" :key="i"
              class="ss-chip" :class="ssChipClass(tag)">{{ tag }}</span>
      </div>

      <h3 class="card-title">{{ product.name }}</h3>
      <p class="card-description">{{ truncate(product.overview || product.storage || '', 90) }}</p>

      <div class="card-footer">
        <div class="card-footer-left">
          <span v-if="product.aggregate_relevance_score != null" class="card-spec card-spec--knowledge"
                :title="`知识关联强度 ${product.aggregate_relevance_score.toFixed(2)}（基于知识图谱关联分聚合）`">
            <span class="card-spec-label">知识关联</span>
            <span class="card-spec-value">{{ product.aggregate_relevance_score.toFixed(2) }}</span>
          </span>
          <span v-if="product.formula" class="card-spec">
            <span class="card-spec-label">Formula</span>
            <span class="card-spec-value">{{ product.formula }}</span>
          </span>
          <span v-else-if="product.purity" class="card-spec">
            <span class="card-spec-label">Purity</span>
            <span class="card-spec-value">{{ product.purity }}</span>
          </span>
          <span v-else class="card-spec">
            <span class="card-spec-label">—</span>
          </span>
        </div>
        <div class="card-footer-right">
          <span v-if="product.price != null" class="card-price">
            {{ formatPrice(product.price, product.currency) }}
          </span>
          <span v-if="product.product_class_name" class="card-class">{{ product.product_class_name }}</span>
        </div>
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
  border-radius: 4px;
  overflow: hidden;
  transition: box-shadow 0.2s var(--ease-out), border-color 0.2s var(--ease-out), transform 0.2s var(--ease-out);
}

.product-card:hover {
  box-shadow: var(--shadow-card-hover);
  border-color: var(--color-border-hover);
  transform: translateY(-2px);
}

.product-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Left accent */
.card-accent {
  width: 3px;
  flex-shrink: 0;
  background: var(--color-border);
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
  background: var(--color-primary-light);
  padding: 1px 6px;
  border-radius: 4px;
  letter-spacing: 0.02em;
}

.chem-id--primary { background: var(--color-primary); color: white; }

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  line-height: 1.35;
  font-family: var(--font-display);
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
  gap: 8px;
}
.card-footer-left { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.card-footer-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

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

/* S5 知识关联强度徽标：主色突出，区别于普通规格 */
.card-spec--knowledge { gap: 5px; }
.card-spec--knowledge .card-spec-value {
  color: var(--color-primary);
  font-weight: 700;
}

.card-price {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.card-class {
  font-size: 11px;
  color: var(--color-text-tertiary);
  background: var(--color-bg);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}

/* S6 四轴修饰标签 chips（与详情页共用配色语义） */
.card-substructure {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}
.ss-chip {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
  padding: 1px 7px;
  border-radius: 4px;
  white-space: nowrap;
}
.ss-chip--base { color: #1d4ed8; background: #dbeafe; }
.ss-chip--base_mod { color: #7c3aed; background: #ede9fe; }
.ss-chip--sugar_sub { color: #047857; background: #d1fae5; }
.ss-chip--sugar_type { color: #b45309; background: #fef3c7; }
.ss-chip--label { color: #be123c; background: #ffe4e6; }
</style>
