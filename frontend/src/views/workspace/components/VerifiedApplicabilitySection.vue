<script setup>
/**
 * Verified Applicability 策展区块（P1-2「verified 破冰」）。
 *
 * - 列出当前产品的 verified 关系（GET /products/{id}/methods/ 的 verified_methods，
 *   含 REVIEW/ACTIVE/REJECTED 全状态，研究员自审用）。
 * - 提供创建入口：选 Method（autocomplete）+ evidence 三件套 → POST /verified/ 建 REVIEW 草稿。
 * 后端 VerifiedCreateView 仅 IsAuthenticated（ProductEditPage 本身 staff-only，创建即策展草稿）；
 * 发布仍需 workspace VerifiedPage 审核 approve（IsStaffUser）。
 *
 * 复用：methodsApi.getMethods（autocomplete）、bridgesApi.createVerified/getProductMethods。
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import * as bridgesApi from '@/api/bridges'
import * as methodsApi from '@/api/methods'
import { toast } from '@/components/common'

const props = defineProps({
  productId: { type: [Number, String], default: null },
})

const EVIDENCE_REF_TYPES = ['PMID', 'DOI', 'PROTOCOL', 'MANUFACTURER', 'DOC']
const EVIDENCE_TYPES = ['pubmed', 'doi', 'msds', 'literature', 'other']
const EVIDENCE_STRENGTHS = ['high', 'medium', 'low']

// ── 现有列表 ──
const verifiedList = ref([])
const loadingList = ref(false)

async function loadList() {
  if (!props.productId) { verifiedList.value = []; return }
  loadingList.value = true
  try {
    const data = await bridgesApi.getProductMethods(props.productId)
    verifiedList.value = (data && data.verified_methods) || []
  } catch (e) {
    console.error('Failed to load verified methods', e)
    verifiedList.value = []
  } finally {
    loadingList.value = false
  }
}

onMounted(loadList)
watch(() => props.productId, loadList)

function evidenceChips(r) {
  const refs = Array.isArray(r.evidence_reference) ? r.evidence_reference : []
  return refs.filter((x) => x && x.type && x.value).map((x) => `${x.type}: ${x.value}`)
}

// ── 创建表单 ──
const showForm = ref(false)
const submitting = ref(false)
const methodQuery = ref('')
const methodOptions = ref([])
const methodSearching = ref(false)
const methodOpen = ref(false)
const form = reactive({
  methodId: null,
  methodName: '',
  evidence_type: 'pubmed',
  evidence_reference: [],   // [{type, value}]
  evidence_strength: 'medium',
  evidence_note: '',
})

function addRefRow() {
  form.evidence_reference.push({ type: 'PMID', value: '' })
}
function removeRefRow(i) {
  form.evidence_reference.splice(i, 1)
}

async function onMethodQuery() {
  const q = methodQuery.value.trim()
  if (!q) { methodOptions.value = []; return }
  methodSearching.value = true
  try {
    const resp = await methodsApi.getMethods({ search: q, page_size: 20 })
    const data = resp && resp.data ? resp.data : resp
    const results = data && Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : [])
    methodOptions.value = results.map((m) => ({ id: m.id, name: m.name, slug: m.slug }))
    methodOpen.value = true
  } catch (e) {
    console.error('Method search failed', e)
    methodOptions.value = []
  } finally {
    methodSearching.value = false
  }
}

function pickMethod(m) {
  form.methodId = m.id
  form.methodName = m.name
  methodQuery.value = m.name
  methodOpen.value = false
}

function resetForm() {
  form.methodId = null
  form.methodName = ''
  form.evidence_type = 'pubmed'
  form.evidence_reference = []
  form.evidence_strength = 'medium'
  form.evidence_note = ''
  methodQuery.value = ''
  methodOptions.value = []
  methodOpen.value = false
  showForm.value = false
}

const canSubmit = computed(() => !!form.methodId && !submitting.value)

async function submit() {
  if (!form.methodId) { toast.error('请先选择 Method'); return }
  // 仅收集完整 reference 项；REVIEW 草稿允许 evidence 不全
  const refs = form.evidence_reference
    .filter((x) => x && x.type && String(x.value || '').trim())
    .map((x) => ({ type: x.type, value: String(x.value).trim() }))
  submitting.value = true
  try {
    await bridgesApi.createVerified({
      product_id: Number(props.productId),
      method_id: Number(form.methodId),
      evidence_type: form.evidence_type || '',
      evidence_reference: refs.length ? refs : null,
      evidence_strength: form.evidence_strength || '',
      evidence_note: form.evidence_note || '',
    })
    toast.success('已创建 verified 草稿（待 workspace 审核发布）')
    resetForm()
    await loadList()
  } catch (e) {
    const msg = e?.response?.data?.meta?.error?.message || e?.message || 'unknown'
    toast.error('创建失败：' + msg)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="va-section">
    <div class="va-header">
      <h4 class="va-title">✅ Verified Applicability</h4>
      <button
        type="button"
        class="btn btn-primary btn-sm"
        :disabled="!productId"
        :title="!productId ? '保存产品后再添加策展关联' : ''"
        @click="showForm = !showForm"
      >{{ showForm ? '收起' : '＋ Add verified' }}</button>
    </div>

    <p v-if="!productId" class="va-hint">保存产品后即可添加策展（verified）关联。</p>

    <!-- 现有列表 -->
    <div v-else-if="loadingList" class="va-empty">Loading…</div>
    <div v-else-if="!verifiedList.length" class="va-empty">暂无 verified 关联。</div>
    <ul v-else class="va-list">
      <li v-for="r in verifiedList" :key="r.id" class="va-card">
        <div class="va-card-head">
          <router-link :to="`/methods/${r.method_id}`" class="va-link">{{ r.method_name || ('#' + r.method_id) }}</router-link>
          <span class="va-badge" :class="`va-badge-${r.status}`">{{ r.status }}</span>
        </div>
        <div class="va-meta">strength: {{ r.evidence_strength || '—' }} · curator: {{ r.curator || '—' }}</div>
        <div v-if="evidenceChips(r).length" class="va-chips">
          <span v-for="(c, i) in evidenceChips(r)" :key="i" class="va-chip">{{ c }}</span>
        </div>
        <div v-if="r.evidence_note" class="va-note">{{ r.evidence_note }}</div>
      </li>
    </ul>

    <!-- 创建表单 -->
    <div v-if="showForm && productId" class="va-form">
      <div class="va-field">
        <label class="va-label">Method *</label>
        <div class="va-combo">
          <input
            v-model="methodQuery"
            class="va-input"
            type="text"
            placeholder="搜索方法名…"
            @input="onMethodQuery"
            @focus="onMethodQuery"
          />
          <div v-if="methodOpen && methodOptions.length" class="va-dropdown">
            <button
              v-for="m in methodOptions"
              :key="m.id"
              type="button"
              class="va-option"
              @click="pickMethod(m)"
            >{{ m.name }}</button>
          </div>
          <div v-else-if="methodOpen && !methodSearching && methodQuery" class="va-dropdown va-dropdown-empty">无匹配</div>
        </div>
        <div v-if="form.methodName" class="va-picked">已选：{{ form.methodName }}</div>
      </div>

      <div class="va-row">
        <div class="va-field">
          <label class="va-label">Evidence type</label>
          <select v-model="form.evidence_type" class="va-input">
            <option v-for="t in EVIDENCE_TYPES" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div class="va-field">
          <label class="va-label">Strength</label>
          <select v-model="form.evidence_strength" class="va-input">
            <option v-for="s in EVIDENCE_STRENGTHS" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
      </div>

      <div class="va-field">
        <label class="va-label">Evidence reference</label>
        <div v-for="(ref, i) in form.evidence_reference" :key="i" class="va-ref-row">
          <select v-model="ref.type" class="va-input va-ref-type">
            <option v-for="t in EVIDENCE_REF_TYPES" :key="t" :value="t">{{ t }}</option>
          </select>
          <input v-model="ref.value" class="va-input va-ref-value" type="text" placeholder="value（如 PMID / DOI）" />
          <button type="button" class="va-ref-del" @click="removeRefRow(i)">×</button>
        </div>
        <button type="button" class="va-add-ref" @click="addRefRow">＋ 添加引用</button>
      </div>

      <div class="va-field">
        <label class="va-label">Note</label>
        <textarea v-model="form.evidence_note" class="va-input va-textarea" rows="2" placeholder="可选说明"></textarea>
      </div>

      <div class="va-actions">
        <button type="button" class="btn btn-primary btn-sm" :disabled="!canSubmit" @click="submit">
          {{ submitting ? '提交中…' : '创建草稿' }}
        </button>
        <button type="button" class="btn btn-ghost btn-sm" @click="resetForm">取消</button>
      </div>
      <p class="va-tip">草稿进入 REVIEW 状态，需到 workspace → Verified 审核发布后才公开。</p>
    </div>
  </div>
</template>

<style scoped>
.va-section { background: var(--color-surface, #fff); border: 1px solid var(--color-border, #CBD5E1); border-radius: 8px; padding: 12px 14px; margin-top: 8px; }
.va-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.va-title { margin: 0; font-size: 14px; font-weight: 500; color: var(--color-text, #0F172A); }
.va-hint, .va-empty { font-size: 12px; color: var(--color-text-secondary, #64748B); font-style: italic; margin: 0; }
.va-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.va-card { border: 1px solid var(--color-border, #E2E8F0); border-radius: 6px; padding: 8px 10px; background: var(--color-surface, #fff); }
.va-card-head { display: flex; justify-content: space-between; align-items: center; }
.va-link { color: var(--color-info, #1D4ED8); text-decoration: none; font-weight: 600; font-size: 13px; }
.va-link:hover { text-decoration: underline; }
.va-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
.va-badge-active { background: #D1FAE5; color: #065F46; }
.va-badge-review { background: #FEF3C7; color: #92400E; }
.va-badge-rejected { background: #FEE2E2; color: #991B1B; }
.va-badge-deprecated { background: #F1F5F9; color: #64748B; }
.va-meta { font-size: 11px; color: var(--color-text-secondary, #64748B); margin-top: 2px; }
.va-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.va-chip { font-size: 11px; padding: 1px 7px; border-radius: 999px; background: #F1F5F9; color: #475569; }
.va-note { font-size: 11px; color: var(--color-text-secondary, #94A3B8); margin-top: 3px; }
.va-form { margin-top: 10px; border-top: 1px dashed var(--color-border, #CBD5E1); padding-top: 10px; }
.va-field { margin-bottom: 8px; }
.va-label { display: block; font-size: 11px; font-weight: 600; color: var(--color-text-secondary, #475569); margin-bottom: 3px; }
.va-row { display: flex; gap: 10px; }
.va-row .va-field { flex: 1; }
.va-input { width: 100%; box-sizing: border-box; padding: 5px 8px; font-size: 12px; border: 1px solid var(--color-border, #CBD5E1); border-radius: 6px; background: var(--color-surface, #fff); color: var(--color-text, #0F172A); }
.va-textarea { resize: vertical; }
.va-combo { position: relative; }
.va-dropdown { position: absolute; z-index: 20; left: 0; right: 0; max-height: 180px; overflow-y: auto; background: var(--color-surface, #fff); border: 1px solid var(--color-border, #CBD5E1); border-radius: 6px; margin-top: 2px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.va-option { display: block; width: 100%; text-align: left; padding: 6px 10px; border: none; background: none; font-size: 12px; color: var(--color-text, #0F172A); cursor: pointer; }
.va-option:hover { background: var(--color-bg, #F1F5F9); }
.va-dropdown-empty { padding: 6px 10px; font-size: 12px; color: var(--color-text-secondary, #94A3B8); }
.va-picked { font-size: 11px; color: #1B7A43; margin-top: 3px; }
.va-ref-row { display: flex; gap: 6px; margin-bottom: 4px; align-items: center; }
.va-ref-type { width: 130px; flex: none; }
.va-ref-value { flex: 1; }
.va-ref-del { border: none; background: none; color: #B91C1C; font-size: 16px; cursor: pointer; line-height: 1; padding: 0 6px; }
.va-add-ref { margin-top: 2px; font-size: 11px; color: var(--color-info, #1D4ED8); background: none; border: none; cursor: pointer; padding: 0; }
.va-actions { display: flex; gap: 8px; margin-top: 4px; }
.va-tip { font-size: 11px; color: var(--color-text-secondary, #94A3B8); margin: 6px 0 0 0; font-style: italic; }
html.dark .va-badge-active { color: #fff; background: #065F46; }
html.dark .va-badge-review { color: #1F2937; }
html.dark .va-badge-rejected { color: #fff; background: #991B1B; }
</style>
