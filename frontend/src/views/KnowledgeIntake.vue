<script setup>
/**
 * KnowledgeIntake — Online form for postdoc to fill in knowledge content.
 * Similar to PIT (Product Intake Tool) but for knowledge layer.
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/utils/http'
import { useConfirm } from '@/composables/useConfirm'

const { ask } = useConfirm()

const route = useRoute()
const router = useRouter()

/* ── State ── */
const products = ref([])
const selectedProduct = ref(null)
const loading = ref(false)
const saving = ref(false)
const message = ref(null)
const filterClass = ref('')

/** "Copy to Similar Products" 硬上限：同类目标数超过它则一条都不写（防无上限批量写）。 */
const MAX_COPY_TARGETS = 50

/* ── Form data ── */
const form = ref({
  research_goals: [],
  applications: [],
  methods: [],
  protocols: [],
  protocol_objective: '',
  protocol_steps: '',
  protocol_materials: '',
  protocol_time: '',
  protocol_difficulty: 'intermediate',
  reference_pmid: '',
  reference_doi: '',
  key_advantages: '',
  key_limitations: '',
  confidence: 'high',
})

/* ── Options ──
 *
 * ★ A-075 / A-218（2026-11-18 / S4）：三组选项从**硬编码常量**改为**远程搜索 + 可新建**。
 *
 * ## 改前的缺陷（诊断件实测数字：8 / 12 / 11）
 * `GOAL_OPTIONS`(8) / `APP_OPTIONS`(12) / `METHOD_OPTIONS`(11) 是写死的字符串数组，
 * 与库里的 11,047 个 Goal、28,568 个 Application、88 个 Method **完全脱钩**：
 * 无论产品是什么，任何人看到的永远是同样那 8 / 12 / 11 个按钮，
 * **任何新建的实体永远进不去**这个页面。QA 报的"只加载前 200 条"其实是这套常量。
 *
 * ## 为什么不是单纯的 `el-select remote`（关键取舍）
 * 原常量表虽然荒谬，但它**隐含保留了一个真实能力**：可以录入"库里还没有"的名字 ——
 * 后端 `/knowledge-intake/` 是按 name `get_or_create` 的，这是研究员录新知识的主路径。
 * 若只换成"从库里搜索并选择"，这个能力会**静默消失**（而且没有任何报错，只是没法录了）。
 * 所以这里保留 chips 形态，并显式给出「＋ Create “…”」入口：
 *   · 输入框 ⇒ 服务端 `?search=`（与 ProductEditPage 已验证的模式一致，含 `include_unpublished: 1`）；
 *   · 候选里没有你输入的名字 ⇒ 出现「＋ Create」按钮，点一下即作为新名字加入；
 *   · 已选中的名字即使不在当前搜索结果里也**始终显示**（否则搜一次就再也取消不掉了）。
 */
const OPTION_LIMIT = 30
const SEARCH_DEBOUNCE_MS = 250

/** 三组选择器的元数据（模板用 v-for 渲染，避免三份重复标记） */
const GROUPS = [
  {
    key: 'research_goals',
    label: 'Research Goals',
    testid: 'goal',
    endpoint: '/research-goals/',
    placeholder: 'Search all research goals — type a new name to create one',
  },
  {
    key: 'applications',
    label: 'Applications',
    testid: 'app',
    endpoint: '/applications/',
    placeholder: 'Search all applications — type a new name to create one',
  },
  {
    key: 'methods',
    label: 'Methods',
    testid: 'method',
    endpoint: '/methods/',
    // ★ 管理端要能挂草稿：`include_unpublished` 只对 staff 生效（`fixture_visibility.py`），
    //   非 staff 传了也等于没传 —— 与 ProductEditPage 的两处远程搜索同口径。
    extra: { include_unpublished: 1 },
    placeholder: 'Search all methods — type a new name to create one',
  },
]

function makePicker(g) {
  return reactive({
    endpoint: g.endpoint,
    extra: g.extra || {},
    placeholder: g.placeholder,
    options: [],      // 服务端返回的名字（当前 query 的前 OPTION_LIMIT 条）
    search: '',
    searching: false,
    error: '',
    count: 0,         // 当前 query 的服务端命中总数（> options.length 即被截断）
  })
}

const pickers = reactive(
  Object.fromEntries(GROUPS.map((g) => [g.key, makePicker(g)])),
)

async function fetchPickerOptions(p) {
  p.searching = true
  p.error = ''
  try {
    const params = { page_size: OPTION_LIMIT, ...p.extra }
    const q = p.search.trim()
    if (q) params.search = q
    const r = await http.get(p.endpoint, { params })
    const rows = Array.isArray(r.data) ? r.data : (r.data?.results || [])
    p.options = rows.map((x) => x.name).filter(Boolean)
    p.count = r.meta?.pagination?.count ?? p.options.length
  } catch (e) {
    p.error = 'Could not load options — check your connection and try again.'
    p.options = []
    p.count = 0
  } finally {
    p.searching = false
  }
}

const _timers = {}
function onPickerInput(key) {
  const p = pickers[key]
  clearTimeout(_timers[key])
  _timers[key] = setTimeout(() => fetchPickerOptions(p), SEARCH_DEBOUNCE_MS)
}

/** 当前分区的 chips = 已选 ∪ 当前候选。已选必须在列，否则搜走后无法取消。 */
function chipsFor(key) {
  const selected = form.value[key] || []
  return [...new Set([...selected, ...pickers[key].options])]
}

/** 输入的名字是否可作为**新实体**创建（未被候选覆盖，且不是纯空白/单字符） */
function canCreate(key) {
  const p = pickers[key]
  const name = (p.search || '').trim()
  if (name.length < 2) return false
  return !p.options.some((n) => n.toLowerCase() === name.toLowerCase())
}

function createCandidate(key) {
  const p = pickers[key]
  const name = (p.search || '').trim()
  if (!name) return
  const arr = form.value[key]
  if (!arr.includes(name)) arr.push(name)
  p.search = ''
  clearTimeout(_timers[key])
  fetchPickerOptions(p)
}

const DIFFICULTY_OPTIONS = ['Beginner', 'Intermediate', 'Advanced']
const CONFIDENCE_OPTIONS = ['high', 'medium', 'low']

/* ── Load products ── */
onMounted(async () => {
  loading.value = true
  try {
    const res = await http.get('/products/', { params: { page_size: 200 } })
    products.value = res.data || []
  } catch (e) {
    message.value = { type: 'err', text: 'Failed to load products' }
  }
  loading.value = false
  // 首屏默认候选（不带 search）—— 让三个分区进来就有东西可点，而不是空白等输入
  GROUPS.forEach((g) => fetchPickerOptions(pickers[g.key]))
})

/* ── Filtered products ── */
const filteredProducts = computed(() => {
  if (!filterClass.value) return products.value
  return products.value.filter(p =>
    (p.category_l1 || '').toLowerCase().includes(filterClass.value.toLowerCase()) ||
    (p.name || '').toLowerCase().includes(filterClass.value.toLowerCase()) ||
    (p.catalog_no || '').toLowerCase().includes(filterClass.value.toLowerCase())
  )
})

/* ── Select product ── */
async function selectProduct(p) {
  selectedProduct.value = p
  // ⚠️ 这里**不加载**该产品已有的知识（原注释写 "Load existing knowledge data if any"
  //    是错的：下面只是把表单清空）。
  //    安全性来自后端语义：`/knowledge-intake/` 是**只增不改**——
  //    目标/方法/协议按 name get-or-create，已有协议不会被覆盖，
  //    已有步骤也不会被追加。所以空表单提交不会毁掉既有内容。
  //    如果将来要支持"在既有内容上编辑"，必须新做一个读取接口，
  //    不能在写接口里悄悄改成 update。
  form.value = {
    research_goals: [],
    applications: [],
    methods: [],
    protocols: [],
    protocol_objective: '',
    protocol_steps: '',
    protocol_materials: '',
    protocol_time: '',
    protocol_difficulty: 'intermediate',
    reference_pmid: '',
    reference_doi: '',
    key_advantages: '',
    key_limitations: '',
    confidence: 'high',
  }
  // ★ A-075/218：换产品时把三组搜索框也清掉 —— 否则上一个产品搜的 "CRISPR" 会留在
  //   输入框里，新产品的可见候选被一个看不见原因的过滤条件窄化。
  GROUPS.forEach((g) => {
    const p = pickers[g.key]
    if (p.search) {
      p.search = ''
      clearTimeout(_timers[g.key])
      fetchPickerOptions(p)
    }
  })

  // ★ A-070 方案 A（用户 2026-11-28 定）：把**上次保存的表单内容**取回来回填。
  //   原实现（上面那段注释）明确说"如果将来要支持在既有内容上编辑，必须新做一个
  //   读取接口" —— 这就是那个接口（`GET /knowledge-intake/?product_id=`）。
  //   ⚠️ 只回填**已知字段**（白名单），不 Object.assign 整个 draft：
  //      草稿里可能残留旧版本表单的键，直接铺开会把未知键塞进 form。
  //   ⚠️ 取草稿失败不阻断录入：用户是来填新内容的，不能因为读旧草稿失败就卡住。
  try {
    const res = await http.get('/knowledge-intake/', { params: { product_id: p.id } })
    const payload = (res && res.data) || res || {}
    const draft = payload.draft
    if (draft && typeof draft === 'object') {
      const known = Object.keys(form.value)
      let restored = 0
      for (const k of known) {
        if (k in draft && draft[k] !== undefined && draft[k] !== null) {
          form.value[k] = draft[k]
          restored += 1
        }
      }
      if (restored > 0) {
        const when = payload.saved_at ? new Date(payload.saved_at).toLocaleString() : ''
        message.value = {
          type: 'ok',
          text: `已回填上次保存的内容（${p.catalog_no}${when ? ' · ' + when : ''}）。可直接改，也可清空重填。`,
        }
      }
    }
  } catch (e) {
    // 读草稿失败：静默（不打断录入），仅记日志
    console.warn('[Intake] draft restore failed:', e && e.message)
  }
}

/* ── Toggle multi-select option ── */
function toggleOption(field, value) {
  const arr = form.value[field]
  const idx = arr.indexOf(value)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(value)
}

/* ── Save ── */
async function save() {
  if (!selectedProduct.value) return
  saving.value = true
  message.value = null
  try {
    const res = await http.post('/knowledge-intake/', {
      product_id: selectedProduct.value.id,
      ...form.value,
    })
    // ★ A-070：后端会回报真实的 created / reused / steps 数与告警。
    //   只显示 "Saved" 会让人以为步骤写进去了 —— 告警必须一起显示出来。
    const d = (res && res.data) || {}
    const parts = [`Saved as draft for ${selectedProduct.value.catalog_no}`]
    // ★ 2026-11-26（A-256）：明确告知「方法链接」增删了多少 ——
    //   此前只报协议/步骤，用户看不出这次保存有没有把方法挂上去。
    if ('method_links_created' in d) {
      const c = d.method_links_created ?? 0
      const e = d.method_links_existing ?? 0
      if (c > 0) parts.push(`方法链接 新增 ${c} 条`)
      else if (e > 0) parts.push(`方法链接 ${e} 条（原本已关联）`)
    }
    if ('protocols_created' in d || 'steps_created' in d) {
      parts.push(
        `协议 新建 ${d.protocols_created ?? 0} / 复用 ${d.protocols_reused ?? 0}｜步骤 ${d.steps_created ?? 0} 条`
      )
    }
    const warn = Array.isArray(d.warnings) && d.warnings.length ? d.warnings.join('；') : ''
    message.value = warn
      ? { type: 'err', text: parts.join('｜') + ' ⚠️ ' + warn }
      : { type: 'ok', text: parts.join('｜') }
  } catch (e) {
    message.value = { type: 'err', text: 'Save failed: ' + (e.message || 'Unknown error') }
  }
  saving.value = false
}

/* ── Copy to similar products ── */
async function copyToSimilar() {
  if (!selectedProduct.value) return
  const similar = products.value.filter(p =>
    p.id !== selectedProduct.value.id &&
    p.product_class_id === selectedProduct.value.product_class_id
  )
  if (!similar.length) {
    message.value = { type: 'err', text: 'No similar products found' }
    return
  }
  // (1) 硬上限：超过则**一条都不写**，先把**实际条数与上限**告知用户。
  //     必须排在确认弹窗**之前**，否则会"先弹确认、再拒绝"，白问用户一次。
  if (similar.length > MAX_COPY_TARGETS) {
    message.value = {
      type: 'err',
      text: `Too many similar products (${similar.length}); limit is ${MAX_COPY_TARGETS}. Nothing was copied.`,
    }
    return
  }
  // (2) 写前确认：明确告知将被写入的目标条数；用户取消则**不做任何写入**。
  const proceed = await ask({
    title: 'Copy knowledge',
    message: `Copy knowledge to ${similar.length} similar product(s)?`,
    confirmText: `Copy to ${similar.length}`,
  })
  if (!proceed) return
  // (3) 逐条计数：成功/失败分别累计，结束时如实汇报（不再只丢一句 "Copy failed"）。
  saving.value = true
  let copied = 0
  let failed = 0
  for (const p of similar) {
    try {
      await http.post('/knowledge-intake/', {
        product_id: p.id,
        ...form.value,
      })
      copied++
    } catch (e) {
      failed++
    }
  }
  message.value = {
    type: failed > 0 ? 'err' : 'ok',
    text: `Copied to ${copied} of ${similar.length} (${failed} failed)`,
  }
  saving.value = false
}
</script>

<template>
  <div class="ki-page">
    <!-- Header -->
    <div class="ki-header">
      <h1 class="ki-title">Knowledge Content Intake</h1>
      <p class="ki-subtitle">Fill in research context for each product</p>
    </div>

    <!-- Toast -->
    <div v-if="message" class="ki-toast" :class="message.type">
      {{ message.text }}
    </div>

    <div class="ki-layout">
      <!-- Left: Product List -->
      <div class="ki-sidebar">
        <input
          v-model="filterClass"
          class="ki-search"
          placeholder="Filter products..."
        />
        <!-- ★ 2026-10-21 修 D7（serious）：`.ki-product-list` 是 max-height + overflow-y:auto 的
             可滚动区，键盘用户无法进入 ⇒ axe `scrollable-region-focusable`。
             加 tabindex=0 + role/aria-label 让它可聚焦并可被读屏识别。 -->
        <div class="ki-product-list" tabindex="0" role="group" aria-label="Product list (scrollable)">
          <div
            v-for="p in filteredProducts"
            :key="p.id"
            class="ki-product-item"
            :class="{ 'ki-active': selectedProduct?.id === p.id }"
            @click="selectProduct(p)"
          >
            <span class="ki-product-cat">{{ p.catalog_no }}</span>
            <span class="ki-product-name">{{ p.name }}</span>
          </div>
        </div>
      </div>

      <!-- Right: Form -->
      <div class="ki-form-area" v-if="selectedProduct">
        <div class="ki-product-header">
          <h2>{{ selectedProduct.name }}</h2>
          <span class="ki-catalog">{{ selectedProduct.catalog_no }}</span>
          <span v-if="selectedProduct.cas" class="ki-cas">CAS: {{ selectedProduct.cas }}</span>
        </div>

        <form @submit.prevent="save" class="ki-form">
          <!-- Research Goals / Applications / Methods：远程搜索 + 可新建（★ A-075 / A-218） -->
          <div v-for="g in GROUPS" :key="g.key" class="ki-section"
               :data-testid="`ki-${g.testid}-section`">
            <h3 class="ki-section-title">{{ g.label }}</h3>

            <div class="ki-picker">
              <input
                v-model="pickers[g.key].search"
                class="ki-input"
                :placeholder="pickers[g.key].placeholder"
                :data-testid="`ki-${g.testid}-search`"
                @input="onPickerInput(g.key)"
                @keyup.enter.prevent="createCandidate(g.key)"
              />
              <button
                v-if="canCreate(g.key)"
                type="button"
                class="ki-create-btn"
                :data-testid="`ki-${g.testid}-create`"
                @click="createCandidate(g.key)"
              >＋ Create “{{ pickers[g.key].search.trim() }}”</button>
            </div>

            <p v-if="pickers[g.key].error" class="ki-hint ki-hint-err"
               :data-testid="`ki-${g.testid}-error`">{{ pickers[g.key].error }}</p>

            <div class="ki-chips" :class="{ 'ki-chips-busy': pickers[g.key].searching }">
              <button
                v-for="opt in chipsFor(g.key)"
                :key="opt"
                type="button"
                class="ki-chip"
                :class="{ 'ki-chip-active': form[g.key].includes(opt) }"
                @click="toggleOption(g.key, opt)"
              >
                {{ opt }}
              </button>
            </div>
            <p v-if="!pickers[g.key].searching && !chipsFor(g.key).length" class="ki-hint">
              Nothing loaded yet — type above to search.
            </p>
            <!-- ★ A-206 同族：截断必须说出来，否则用户以为"库里就这么多" -->
            <p v-if="pickers[g.key].count > pickers[g.key].options.length"
               class="ki-hint" :data-testid="`ki-${g.testid}-truncated`">
              Showing first {{ pickers[g.key].options.length }} of
              {{ pickers[g.key].count }} matches — keep typing to narrow down.
            </p>
          </div>

          <!-- Protocol -->
          <div class="ki-section">
            <h3 class="ki-section-title">Protocol</h3>
            <div class="ki-form-grid">
              <div>
                <label>Protocol Name</label>
                <input v-model="form.protocols[0]" class="ki-input" placeholder="e.g. CuAAC RNA Labeling Protocol" />
              </div>
              <div>
                <label>Objective</label>
                <input v-model="form.protocol_objective" class="ki-input" placeholder="e.g. Covalently label RNA with a fluorescent dye" />
              </div>
              <div>
                <label>Steps (one step per line)</label>
                <textarea v-model="form.protocol_steps" class="ki-textarea" rows="6" placeholder="1. Prepare RNA&#10;2. Add reagents&#10;3. Incubate 30 min&#10;4. Purify product&#10;&#10;每个非空行 = 一个步骤；写成「标题：正文」可自动拆出标题。" />
                <p class="ki-hint">保存后会写入协议的步骤表（不再是塞进 Objective）。</p>
              </div>
              <div>
                <label>Materials</label>
                <input v-model="form.protocol_materials" class="ki-input" placeholder="CuSO4, THPTA, ascorbate, dye" />
              </div>
              <div class="ki-row">
                <div>
                  <label>Time</label>
                  <input v-model="form.protocol_time" class="ki-input" placeholder="2 hours" />
                </div>
                <div>
                  <label>Difficulty</label>
                  <select v-model="form.protocol_difficulty" class="ki-input">
                    <option v-for="d in DIFFICULTY_OPTIONS" :key="d" :value="d">{{ d }}</option>
                  </select>
                </div>
              </div>
              <p class="ki-hint">Time / Difficulty 暂不落库：协议模型还没有对应字段，保存时会回到提示里告诉你（不会硬塞进别的字段）。</p>
            </div>
          </div>

          <!-- References -->
          <div class="ki-section">
            <h3 class="ki-section-title">References</h3>
            <div class="ki-row">
              <div>
                <label>PMID (comma separated)</label>
                <input v-model="form.reference_pmid" class="ki-input" placeholder="24151973, 25959142" />
              </div>
              <div>
                <label>DOI</label>
                <input v-model="form.reference_doi" class="ki-input" placeholder="10.1038/nprot.2014.001" />
              </div>
            </div>
          </div>

          <!-- Advantages / Limitations -->
          <div class="ki-section">
            <h3 class="ki-section-title">Notes</h3>
            <div class="ki-row">
              <div>
                <label>Key Advantages</label>
                <textarea v-model="form.key_advantages" class="ki-textarea" rows="2" placeholder="High specificity; Bioorthogonal" />
              </div>
              <div>
                <label>Key Limitations</label>
                <textarea v-model="form.key_limitations" class="ki-textarea" rows="2" placeholder="Copper toxicity; Needs modified substrates" />
              </div>
            </div>
          </div>

          <!-- Confidence -->
          <div class="ki-section">
            <label>Confidence Level</label>
            <div class="ki-chips">
              <button
                v-for="c in CONFIDENCE_OPTIONS"
                :key="c"
                type="button"
                class="ki-chip"
                :class="{ 'ki-chip-active': form.confidence === c }"
                @click="form.confidence = c"
              >
                {{ c }}
              </button>
            </div>
          </div>

          <!-- Actions -->
          <div class="ki-actions">
            <button type="submit" class="ki-btn ki-btn-primary" :disabled="saving">
              {{ saving ? 'Saving...' : 'Save' }}
            </button>
            <button type="button" class="ki-btn ki-btn-outline" @click="copyToSimilar" :disabled="saving">
              Copy to Similar Products
            </button>
          </div>
        </form>
      </div>

      <!-- Empty state -->
      <div v-else class="ki-empty">
        <p>Select a product from the list to fill in knowledge content</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ki-page { max-width: var(--content-max-width); margin: 0 auto; padding: 24px; }
.ki-header { margin-bottom: 24px; }
.ki-title { font-size: 24px; font-weight: 800; color: var(--color-text); margin: 0; }
.ki-subtitle { font-size: 14px; color: var(--color-text-secondary); margin: 4px 0 0; }

.ki-toast { padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; font-weight: 500; }
.ki-toast.ok { background: var(--color-success-light); color: var(--color-primary-active); }
.ki-toast.err { background: var(--color-danger-light); color: #991b1b; }

.ki-layout { display: flex; gap: 24px; }

/* Sidebar */
.ki-sidebar { width: 280px; flex-shrink: 0; }
.ki-search { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 13px; margin-bottom: 12px; }
.ki-product-list { max-height: calc(100vh - 200px); overflow-y: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.ki-product-item { padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--color-border); transition: background 0.1s; }
.ki-product-item:hover { background: var(--color-primary-subtle); }
.ki-product-item.ki-active { background: var(--color-primary-light); border-left: 3px solid var(--color-primary); }
.ki-product-cat { font-size: 11px; font-weight: 600; color: var(--color-primary); display: block; }
.ki-product-name { font-size: 13px; color: var(--color-text); }

/* Form area */
.ki-form-area { flex: 1; min-width: 0; }
.ki-product-header { margin-bottom: 24px; }
.ki-product-header h2 { font-size: 20px; font-weight: 700; margin: 0; }
.ki-catalog { font-size: 12px; font-weight: 600; color: var(--color-primary); margin-right: 12px; }
.ki-cas { font-size: 12px; color: var(--color-text-secondary); font-family: var(--font-mono); }

/* Form */
.ki-form { display: flex; flex-direction: column; gap: 24px; }
.ki-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 16px; }
.ki-section-title { font-size: 14px; font-weight: 700; margin: 0 0 12px; color: var(--color-text); }
.ki-form-grid { display: flex; flex-direction: column; gap: 12px; }
.ki-form-grid label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; display: block; }
.ki-hint { font-size: 11px; line-height: 1.5; color: var(--color-text-tertiary); margin: 2px 0 0; }
.ki-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ki-row label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; display: block; }
.ki-input { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 13px; font-family: var(--font-sans); }
.ki-textarea { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 13px; font-family: var(--font-sans); resize: vertical; }

/* Chips */
.ki-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ki-chip { padding: 4px 12px; border: 1px solid var(--color-border); border-radius: 16px; font-size: 12px; cursor: pointer; background: var(--color-surface); color: var(--color-text); font-family: var(--font-sans); transition: all 0.15s; }
.ki-chip:hover { border-color: var(--color-primary); }
.ki-chip-active { background: var(--color-primary); border-color: var(--color-primary); color: white; }

/* ★ A-075 / A-218：远程搜索选择器 */
.ki-picker { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.ki-picker .ki-input { flex: 1; min-width: 220px; }
/* 「＋ Create …」刻意**不带** `.ki-chip` class —— 它不是候选项，是"新建"动作；
   混进 `.ki-chip` 会让按选项遍历的逻辑（含 e2e 的候选筛选）把它当实体名。 */
.ki-create-btn {
  padding: 6px 12px; border: 1px dashed var(--color-primary); border-radius: 16px;
  font-size: 12px; cursor: pointer; background: transparent; color: var(--color-primary);
  font-family: var(--font-sans); white-space: nowrap;
}
.ki-create-btn:hover { background: var(--color-primary-subtle); }
.ki-chips-busy { opacity: .5; }
.ki-hint-err { color: var(--color-danger, #dc2626); }

/* Actions */
.ki-actions { display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid var(--color-border); }
.ki-btn { height: 40px; padding: 0 20px; border-radius: var(--radius-md); font-size: 14px; font-weight: 600; cursor: pointer; font-family: var(--font-sans); }
.ki-btn-primary { background: var(--color-primary); color: white; border: none; }
.ki-btn-primary:hover { opacity: 0.9; }
.ki-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.ki-btn-outline { background: transparent; color: var(--color-primary); border: 1px solid var(--color-primary); }
.ki-btn-outline:hover { background: var(--color-primary-subtle); }

/* Empty */
.ki-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--color-text-tertiary); font-size: 15px; }

@media (max-width: 768px) { .ki-layout { flex-direction: column; } .ki-sidebar { width: 100%; } }
</style>
