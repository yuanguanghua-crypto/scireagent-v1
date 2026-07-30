<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  bioz: { type: Object, default: null },
  // 可落库（已存盘产品）— false 时 Adopt 按钮 disabled
  canAdopt: { type: Boolean, default: true },
})
const emit = defineEmits(['adopt', 'adopt-all'])

const expanded = ref({})
const adoptedSet = ref(new Set())
const adoptingAll = ref(false)

const shouldRender = computed(() => {
  if (!props.bioz) return false
  if (props.bioz.queried) return true
  return !!props.bioz.error
})

const isError = computed(() => !props.bioz?.queried && !!props.bioz?.error)
const refs = computed(() => props.bioz?.references || [])
const visibleRefs = computed(() => refs.value)

const equivClass = computed(() => {
  const e = props.bioz?.equivalence
  if (e === 'exact' || e === 'name_match') return 'equiv-strong'
  if (e === 'weak') return 'equiv-moderate'
  return 'equiv-weak'   // mismatch 及其他
})

// 去重 key：优先 doi，其次 pmid，最后 title
function refKey(r, i) {
  return r.doi || r.pmid || r.article_title || `idx-${i}`
}

function isAdopted(i) {
  return adoptedSet.value.has(i)
}

function toggleExpand(i) {
  expanded.value[i] = !expanded.value[i]
}

function adoptOne(i) {
  if (isAdopted(i) || !props.canAdopt) return
  emit('adopt', { ref: refs.value[i], index: i })
}

function adoptAll() {
  if (!props.canAdopt || adoptingAll.value) return
  emit('adopt-all', { refs: refs.value })
}

// 父组件落库成功后回调本组件标记（通过 v-model:adopted 或 expose）
defineExpose({
  markAdopted: (indices) => {
    indices.forEach(i => adoptedSet.value.add(i))
    adoptedSet.value = new Set(adoptedSet.value)
  },
  setAdoptingAll: (v) => { adoptingAll.value = v },
})
</script>

<template>
  <div v-if="shouldRender" class="bioz-section pubchem-preview">
    <div class="bioz-header">
      <h4 class="bioz-title">📚 Bioz Literature Evidence</h4>
      <button
        v-if="!isError && refs.length"
        type="button"
        class="btn btn-primary btn-sm bioz-adopt-all"
        :disabled="!canAdopt || adoptingAll || adoptedSet.size >= refs.length"
        :title="!canAdopt ? 'Save the product before adopting' : ''"
        @click="adoptAll"
      >{{ adoptingAll ? 'Adopting…' : `Adopt all (${refs.length})` }}</button>
    </div>

    <!-- 错误态 -->
    <p v-if="isError" class="bioz-err">Bioz query failed: {{ bioz.error }}</p>

    <!-- 正常态 -->
    <template v-else>
      <div class="bioz-meta">
        <span class="equiv-badge" :class="equivClass">equivalence: {{ bioz.equivalence || '—' }}</span>
        <span class="bioz-total">{{ bioz.total ?? 0 }} references total</span>
      </div>
      <div v-if="bioz.needs_review" class="bioz-warn">
        ⚠ This evidence requires manual review — queried by vendor "{{ bioz.vendor || 'Jena Bioscience' }}" catalog "{{ bioz.catalog_no || '?' }}"; CAS unavailable, vendor/lot variance possible
      </div>
      <p v-if="bioz.disclaimer" class="bioz-disclaimer">{{ bioz.disclaimer }}</p>

      <!-- 文献列表 -->
      <div v-if="visibleRefs.length" class="bioz-refs">
        <div v-for="(r, i) in visibleRefs" :key="i" class="bioz-ref-card">
          <div class="bioz-ref-header" @click="toggleExpand(i)">
            <span class="bioz-ref-title">{{ r.article_title || 'Untitled' }}</span>
            <span v-if="r.impact_factor" class="bioz-if">IF {{ r.impact_factor }}</span>
            <span class="bioz-journal">{{ r.journal || '—' }}</span>
            <span class="bioz-date">{{ r.pub_date || '' }}</span>
            <span class="bioz-expand">{{ expanded[i] ? '▲' : '▼' }}</span>
          </div>
          <div v-if="expanded[i]" class="bioz-ref-body">
            <div v-if="r.authors" class="bioz-line"><strong>Authors:</strong> {{ r.authors }}</div>
            <div v-if="r.techniques" class="bioz-line"><strong>Techniques:</strong> {{ r.techniques }}</div>
            <div v-if="r.doi" class="bioz-line">
              <strong>DOI:</strong>
              <a :href="`https://doi.org/${r.doi}`" target="_blank" class="bioz-link">{{ r.doi }}</a>
            </div>
            <div v-if="r.pmid" class="bioz-line">
              <strong>PMID:</strong>
              <a :href="`https://pubmed.ncbi.nlm.nih.gov/${r.pmid}/`" target="_blank" class="bioz-link">{{ r.pmid }}</a>
            </div>
            <div v-if="r.catalog_number" class="bioz-line"><strong>Catalog (Bioz):</strong> {{ r.catalog_number }}</div>
          </div>
          <!-- per-ref Adopt 按钮 / 已关联徽章 -->
          <div class="bioz-ref-actions">
            <a
              v-if="r.ref_id"
              :href="`/references/${r.ref_id}`"
              target="_blank"
              class="bioz-linked"
              title="Stored in knowledge base"
            >✓ Linked #{{ r.ref_id }}</a>
            <button
              v-else-if="!isAdopted(i)"
              type="button"
              class="btn btn-ghost btn-sm bioz-adopt-one"
              :disabled="!canAdopt"
              :title="!canAdopt ? 'Save the product before adopting' : ''"
              @click.stop="adoptOne(i)"
            >Adopt</button>
            <span v-else class="bioz-adopted">✓ Stored</span>
          </div>
        </div>
        <p v-if="refs.length > 5" class="bioz-more">… {{ refs.length - 5 }} more (P1 previews only the first 5; Adopt all stores all)</p>
      </div>
      <p v-else class="bioz-empty">Bioz query succeeded but returned no records</p>

      <p v-if="!canAdopt" class="bioz-nosave-hint">Save the product before adopting references</p>
    </template>
  </div>
</template>

<style scoped>
.bioz-section { background: var(--color-surface, #fff); border: 1px solid var(--color-border, #CBD5E1); border-radius: 8px; padding: 12px 14px; }
.bioz-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.bioz-title { margin: 0; font-size: 14px; font-weight: 500; color: var(--color-text, #0F172A); }
.bioz-adopt-all { font-size: 11px; padding: 4px 12px; }
.bioz-err { font-size: 12px; color: var(--color-danger); margin: 0; }
.bioz-meta { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; flex-wrap: wrap; }
.equiv-badge { font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 12px; }
.equiv-strong { background: var(--color-success-bg); color: var(--color-emerald-700); border: 1px solid var(--color-emerald-200); }
.equiv-moderate { background: var(--color-warning-bg); color: var(--color-amber-800); border: 1px solid var(--color-amber-200); }
.equiv-weak { background: var(--color-bg, #F1F5F9); color: var(--color-text-tertiary, #94A3B8); border: 1px solid var(--color-border, #CBD5E1); }
html.dark .equiv-badge { color: #fff; }
.bioz-total { font-size: 12px; color: var(--color-text-secondary); }
.bioz-warn { background: var(--color-bg, #F1F5F9); border: 1px solid var(--color-border, #CBD5E1); border-radius: 6px; padding: 6px 10px; font-size: 11px; color: var(--color-text-secondary, #475569); margin-bottom: 6px; }
.bioz-disclaimer { font-size: 11px; color: var(--color-text-secondary); margin: 0 0 8px 0; font-style: italic; }
.bioz-refs { margin-top: 4px; }
.bioz-ref-card { border: 1px solid var(--color-border); border-radius: 6px; margin-bottom: 6px; overflow: hidden; background: var(--color-surface); }
.bioz-ref-header { display: flex; gap: 8px; align-items: center; padding: 6px 10px; cursor: pointer; user-select: none; }
.bioz-ref-header:hover { background: var(--color-bg); }
.bioz-ref-title { font-size: 12px; font-weight: 600; flex: 1; }
.bioz-if { font-size: 11px; color: var(--color-amber-700); font-weight: 600; background: var(--color-warning-light); padding: 1px 6px; border-radius: 4px; }
.bioz-journal { font-size: 11px; color: var(--color-text-secondary); font-style: italic; }
.bioz-date { font-size: 11px; color: var(--color-text-secondary); }
.bioz-expand { font-size: 11px; color: var(--color-text-secondary); }
.bioz-ref-body { padding: 6px 10px; border-top: 1px solid var(--color-border); }
.bioz-line { font-size: 11px; margin-bottom: 3px; color: var(--color-text-secondary); }
.bioz-link { color: var(--color-info); text-decoration: none; }
.bioz-link:hover { text-decoration: underline; }
.bioz-ref-actions { padding: 4px 10px; border-top: 1px dashed var(--color-border); }
.bioz-adopt-one { font-size: 11px; padding: 2px 10px; }
.bioz-adopted { font-size: 11px; color: var(--color-success); font-weight: 600; }
.bioz-linked { font-size: 11px; color: var(--color-info); text-decoration: none; font-weight: 600; }
.bioz-linked:hover { text-decoration: underline; }
.bioz-more { font-size: 11px; color: var(--color-text-secondary); margin: 6px 0 0 0; font-style: italic; }
.bioz-empty { font-size: 12px; color: var(--color-text-secondary); font-style: italic; margin: 0; }
.bioz-nosave-hint { font-size: 11px; color: var(--color-amber-800); margin: 6px 0 0 0; font-style: italic; }
html.dark .bioz-warn { color: var(--color-text-secondary); }
html.dark .bioz-nosave-hint { color: var(--color-amber-200); }
html.dark .bioz-if { color: var(--color-amber-200); }
</style>
