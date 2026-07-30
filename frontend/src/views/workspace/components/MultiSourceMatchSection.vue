<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  jena: { type: Object, default: null },
})
const emit = defineEmits(['apply'])

// 兼容新旧格式
const sources = computed(() => {
  if (!props.jena) return []
  // 新格式: sources 数组
  if (props.jena.sources) {
    return props.jena.sources
  }
  // 旧格式: 单源，包装成 sources
  if (props.jena.matched) {
    return [{
      vendor: 'jena',
      matched: true,
      match_key: props.jena.match_key,
      catalog_no: props.jena.catalog_no,
      product_name: props.jena.product_name,
      systematic_name: props.jena.systematic_name,
      cas_number: props.jena.cas_number,
      category_path: props.jena.category_path,
      normalized: props.jena.normalized || {},
    }]
  }
  return []
})

const anyMatched = computed(() => sources.value.some(s => s.matched))
const matchedSources = computed(() => sources.value.filter(s => s.matched))

// 默认选中 jena（品牌主供应商），其次第一个命中
const defaultTab = computed(() => {
  const arr = sources.value
  const jena = arr.findIndex(s => s.vendor === 'jena' && s.matched)
  if (jena >= 0) return jena
  const hit = arr.findIndex(s => s.matched)
  return hit >= 0 ? hit : 0
})
const activeTab = ref(defaultTab.value)

const vendorColors = {
  jena: { dot: '#047857', bg: '#ECFDF5', border: '#A7F3D0', tag: '#047857' },
  cayman: { dot: '#7AAEDB', bg: '#EFF6FF', border: '#BFDBFE', tag: '#3B82F6' },
  trilink: { dot: '#C9A34E', bg: '#FFFBEB', border: '#FDE68A', tag: '#D97706' },
  biotium: { dot: '#D47C7C', bg: '#FEF2F2', border: '#FECACA', tag: '#DC2626' },
}

const getColors = (vendor) => vendorColors[vendor] || { dot: '#888', bg: '#f5f5f5', border: '#ddd', tag: '#888' }

function normalizedEntries(source) {
  const n = source.normalized || {}
  return [
    { key: 'purity', label: 'Purity', value: n.purity },
    { key: 'storage_condition', label: 'Storage', value: n.storage_condition },
    { key: 'shipping_condition', label: 'Shipping', value: n.shipping_condition },
    { key: 'shelf_life', label: 'Shelf Life', value: n.shelf_life },
    { key: 'concentration', label: 'Concentration', value: n.concentration },
    { key: 'category_l1', label: 'Category L1', value: n.category_l1 },
  ].filter(e => e.value != null && e.value !== '')
}

function hasFillable(source) {
  return normalizedEntries(source).length > 0
}

// Biotium 接入（D5）：fuzzy_reference = 仅由 name 命中、无精确对应性担保的模糊参考
const isFuzzy = (source) => source.match_quality === 'fuzzy_reference'

function onApply(source) {
  emit('apply', source)
}
</script>

<template>
  <div v-if="jena" class="ms-section">
    <h4 class="ms-title">Supplier Spec Match</h4>

    <!-- Summary bar -->
    <div v-if="anyMatched" class="ms-summary">
      <span class="ms-chip" v-for="s in matchedSources" :key="s.vendor"
        :style="{ borderLeftColor: getColors(s.vendor).tag }">
        <span class="ms-dot" :style="{ background: getColors(s.vendor).dot }"></span>
        {{ s.vendor }} &middot; {{ s.match_key || '?' }}
        <span v-if="s.match_quality === 'fuzzy_reference'" class="ms-chip-ref">参考</span>
      </span>
      <span class="ms-chip ms-chip-muted" v-if="sources.length > matchedSources.length">
        {{ sources.length - matchedSources.length }} source(s) no match
      </span>
    </div>

    <!-- Tabs -->
    <div v-if="anyMatched" class="ms-tabs">
      <button
        v-for="(s, i) in sources"
        :key="i"
        class="ms-tab"
        :class="{ active: activeTab === i, miss: !s.matched }"
        :style="activeTab === i ? { borderBottomColor: getColors(s.vendor).tag, color: getColors(s.vendor).tag } : {}"
        @click="activeTab = i"
      >
        <span class="ms-dot-sm" :style="{ background: s.matched ? getColors(s.vendor).dot : '#bbb' }"></span>
        {{ s.vendor }}
        <span v-if="s.matched && s.match_quality === 'fuzzy_reference'" class="ms-badge-ref">参考</span>
        <span v-if="!s.matched" class="ms-badge-miss">miss</span>
      </button>
    </div>

    <!-- Tab content：全部 miss 时显示全部，否则仅显示 active tab -->
    <div v-for="(source, i) in sources" :key="i" v-show="anyMatched ? activeTab === i : true">
      <template v-if="source.matched">
        <div v-if="isFuzzy(source)" class="ms-fuzzy-warn">
          ⚠ 模糊匹配（按名称近似）· 仅供参考 · 需手动确认对应性
        </div>
        <p class="ms-match-key">Matched by {{ source.match_key }}{{ source.match_quality === 'fuzzy_reference' ? ' · 模糊参考' : '' }}</p>
        <table class="ms-table">
          <tr><td>Catalog No:</td><td class="prop-highlight" :style="{ color: getColors(source.vendor).tag }">{{ source.catalog_no || '—' }}</td></tr>
          <tr v-if="source.product_name"><td>Product Name:</td><td class="prop-highlight" :style="{ color: getColors(source.vendor).tag }">{{ source.product_name }}</td></tr>
          <tr v-if="source.systematic_name"><td>Systematic Name:</td><td class="prop-highlight" :style="{ color: getColors(source.vendor).tag }">{{ source.systematic_name }}</td></tr>
          <tr v-if="source.cas_number"><td>CAS:</td><td class="prop-highlight" :style="{ color: getColors(source.vendor).tag }">{{ source.cas_number }}</td></tr>
        </table>

        <div v-if="normalizedEntries(source).length" class="ms-norm">
          <div class="ms-norm-title">Normalized specs (fillable into form)</div>
          <table>
            <tr v-for="e in normalizedEntries(source)" :key="e.key">
              <td>{{ e.label }}:</td>
              <td class="prop-highlight" :style="{ color: getColors(source.vendor).tag }">{{ e.value }}</td>
            </tr>
          </table>
        </div>

        <button
          v-if="hasFillable(source)"
          type="button"
          class="btn btn-ghost btn-sm ms-apply-btn"
          :style="{ borderColor: getColors(source.vendor).tag, color: getColors(source.vendor).tag }"
          @click="onApply(source)"
        >Apply from {{ source.vendor }}</button>
        <span v-if="hasFillable(source)" class="form-hint" style="margin-left:8px">Scope: fill empty fields only (Purity, Storage, …)</span>
        <span v-if="isFuzzy(source)" class="form-hint ms-fuzzy-hint" style="margin-left:8px">参考匹配：仅手动采纳，勿盲选</span>
      </template>

      <p v-else class="ms-miss">{{ source.vendor }}: no product matched for this compound</p>
    </div>

    <!-- 全部未命中 -->
    <p v-if="!anyMatched && sources.length === 0" class="ms-miss">No supplier index loaded</p>
  </div>
</template>

<style scoped>
.ms-section { background: var(--color-surface, #fff); border: 1px solid var(--color-border, #CBD5E1); border-radius: 8px; padding: 12px 14px; }
.ms-title { margin: 0 0 8px 0; font-size: 14px; font-weight: 500; color: var(--color-text, #0F172A); }

/* summary chips */
.ms-summary { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.ms-chip { font-size: 11px; padding: 3px 10px; border-radius: 12px; background: var(--color-bg, #F1F5F9); border: 1px solid var(--color-border, #CBD5E1); border-left: 3px solid; display: flex; align-items: center; gap: 5px; color: var(--color-text-secondary, #475569); }
.ms-chip-muted { color: var(--color-text-tertiary, #94A3B8); border-left-color: var(--color-text-tertiary, #94A3B8); }
.ms-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

/* tabs — miss tab 深灰背景 + 删除线 */
.ms-tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--color-border, #CBD5E1); margin-bottom: 10px; }
.ms-tab { padding: 7px 14px; border: none; background: transparent; cursor: pointer; font-size: 12px; color: var(--color-text-tertiary, #94A3B8); border-bottom: 2px solid transparent; transition: all 0.15s; display: flex; align-items: center; gap: 5px; border-radius: 4px 4px 0 0; }
.ms-tab.active { font-weight: 500; color: var(--color-primary, #047857); border-bottom-color: var(--color-primary, #047857); background: transparent; }
.ms-tab.miss { opacity: 0.65; text-decoration: line-through; }
.ms-tab.miss:hover { opacity: 0.85; background: var(--color-bg, #F1F5F9); }
.ms-tab:hover { background: var(--color-primary-subtle, #ECFDF5); }
.ms-dot-sm { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.ms-badge-miss { font-size: 10px; padding: 0 5px; border-radius: 6px; background: var(--color-bg, #F1F5F9); color: var(--color-text-tertiary, #94A3B8); }

/* match key */
.ms-match-key { font-size: 11px; color: var(--color-text-tertiary, #94A3B8); margin: 0 0 6px 0; font-style: italic; }

/* tables */
.ms-table { width: 100%; border-collapse: collapse; border: 1px solid var(--color-border-light, #E2E8F0); border-radius: 6px; overflow: hidden; }
.ms-table td { padding: 5px 10px; border-bottom: 1px solid var(--color-border-light, #E2E8F0); font-size: 12px; }
.ms-table tr:last-child td { border-bottom: none; }
.ms-table td:first-child { color: var(--color-text-secondary, #475569); width: 130px; font-weight: 400; }
.prop-highlight { font-weight: 500; }

/* normalized specs */
.ms-norm { margin-top: 8px; padding-top: 6px; border-top: 1px dashed var(--color-border, #CBD5E1); }
.ms-norm-title { font-size: 11px; font-weight: 500; color: var(--color-text-tertiary, #94A3B8); margin-bottom: 4px; }
.ms-norm table { width: 100%; border-collapse: collapse; border: 1px solid var(--color-border-light, #E2E8F0); border-radius: 6px; overflow: hidden; }
.ms-norm td { padding: 4px 10px; border-bottom: 1px solid var(--color-border-light, #E2E8F0); font-size: 12px; }
.ms-norm tr:last-child td { border-bottom: none; }
.ms-norm td:first-child { color: var(--color-text-secondary, #475569); width: 130px; }

/* apply button */
.ms-apply-btn { margin-top: 8px; background: var(--color-surface, #FFF); border-radius: 6px; }
.ms-apply-btn:hover { opacity: 0.8; }

/* miss */
.ms-miss { font-size: 12px; color: var(--color-text-tertiary, #94A3B8); font-style: italic; margin: 0; }
.form-hint { font-size: 12px; color: var(--color-text-tertiary, #94A3B8); }

/* fuzzy reference（Biotium D5）：琥珀警示，明确"模糊匹配·仅供参考·需手动确认" */
.ms-chip-ref { font-size: 10px; padding: 0 6px; border-radius: 6px; background: #FEF3C7; color: #B45309; margin-left: 6px; font-weight: 500; }
.ms-badge-ref { font-size: 10px; padding: 0 5px; border-radius: 6px; background: #FEF3C7; color: #B45309; margin-left: 4px; }
.ms-fuzzy-warn { font-size: 11px; color: #B45309; background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 6px; padding: 6px 10px; margin: 0 0 8px 0; }
.ms-fuzzy-hint { color: #B45309; font-weight: 500; }
</style>
