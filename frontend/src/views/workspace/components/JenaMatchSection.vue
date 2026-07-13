<script setup>
import { computed } from 'vue'

const props = defineProps({
  jena: { type: Object, default: null },
})
const emit = defineEmits(['apply'])

const matched = computed(() => !!props.jena?.matched)
const normalized = computed(() => props.jena?.normalized || {})

// 归一化规格中可填入表单的字段（仅非空项才计数）
const normalizedEntries = computed(() => {
  const n = normalized.value
  return [
    { key: 'purity', label: 'Purity', value: n.purity },
    { key: 'storage_condition', label: 'Storage', value: n.storage_condition },
    { key: 'shipping_condition', label: 'Shipping', value: n.shipping_condition },
    { key: 'shelf_life', label: 'Shelf Life', value: n.shelf_life },
    { key: 'concentration', label: 'Concentration', value: n.concentration },
    { key: 'category_l1', label: 'Category L1', value: n.category_l1 },
  ].filter(e => e.value != null && e.value !== '')
})

const hasFillable = computed(() => normalizedEntries.value.length > 0)
</script>

<template>
  <div v-if="jena" class="jena-section pubchem-preview">
    <h4 class="jena-title">🧪 Jena Spec Match</h4>

    <!-- 命中：凭证表 + 归一化规格表 -->
    <template v-if="matched">
      <p class="jena-match-key">Matched ({{ jena.match_key }})</p>
      <table class="jena-table">
        <tr><td>Catalog No:</td><td class="prop-highlight">{{ jena.catalog_no || '—' }}</td></tr>
        <tr><td>Product Name:</td><td>{{ jena.product_name || '—' }}</td></tr>
        <tr v-if="jena.systematic_name"><td>Systematic Name:</td><td>{{ jena.systematic_name }}</td></tr>
        <tr v-if="jena.cas_number"><td>CAS (jena):</td><td>{{ jena.cas_number }}</td></tr>
      </table>

      <div v-if="normalizedEntries.length" class="jena-norm">
        <div class="jena-norm-title">Normalized specs (fillable into form)</div>
        <table>
          <tr v-for="e in normalizedEntries" :key="e.key">
            <td>{{ e.label }}:</td>
            <td class="prop-highlight">{{ e.value }}</td>
          </tr>
        </table>
      </div>

      <button
        v-if="hasFillable"
        type="button"
        class="btn btn-ghost btn-sm jena-apply-btn"
        @click="emit('apply')"
      >Apply empty fields only</button>
      <span v-if="hasFillable" class="form-hint" style="margin-left:8px">Scope: Jena spec fields only (Purity, Storage, …) — won't overwrite filled fields</span>
    </template>

    <!-- 未命中 -->
    <p v-else class="jena-miss">Jena index not matched — cannot retrieve spec credentials or Bioz references</p>
  </div>
</template>

<style scoped>
.jena-section { background: #f0f9ff; border: 1px solid #bae6fd; }
.jena-title { margin: 0 0 6px 0; font-size: 13px; }
.jena-match-key { font-size: 11px; color: var(--color-info); margin: 0 0 4px 0; font-style: italic; }
.jena-table { width: 100%; border-collapse: collapse; }
.jena-table td { padding: 4px 8px; border-bottom: 1px solid #e0f2fe; font-size: 12px; }
.jena-table td:first-child { color: var(--color-text-secondary); width: 130px; }
.jena-norm { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #bae6fd; }
.jena-norm-title { font-size: 11px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; }
.jena-norm table { width: 100%; border-collapse: collapse; }
.jena-norm td { padding: 3px 8px; border-bottom: 1px solid #e0f2fe; font-size: 12px; }
.jena-norm td:first-child { color: var(--color-text-secondary); width: 130px; }
.prop-highlight { color: var(--color-info); font-weight: 600; }
.jena-apply-btn { margin-top: 8px; border-color: #0284c7; color: #0284c7; }
.jena-apply-btn:hover { background: #e0f2fe; }
.jena-miss { font-size: 12px; color: var(--color-text-secondary); font-style: italic; margin: 0; }
.form-hint { font-size: 12px; color: var(--color-text-secondary); }
</style>
