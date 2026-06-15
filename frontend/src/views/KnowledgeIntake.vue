<script setup>
/**
 * KnowledgeIntake — Online form for postdoc to fill in knowledge content.
 * Similar to PIT (Product Intake Tool) but for knowledge layer.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/utils/http'

const route = useRoute()
const router = useRouter()

/* ── State ── */
const products = ref([])
const selectedProduct = ref(null)
const loading = ref(false)
const saving = ref(false)
const message = ref(null)
const filterClass = ref('')

/* ── Form data ── */
const form = ref({
  research_goals: [],
  applications: [],
  methods: [],
  protocols: [],
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

/* ── Options ── */
const GOAL_OPTIONS = [
  'RNA Analysis', 'DNA Sequencing', 'Click Chemistry', 'Protein Engineering',
  'RNA Modification', 'RNA Therapeutics', 'Epigenetics', 'Cell Biology',
]

const APP_OPTIONS = [
  'RNA Fluorescent Labeling', 'RNA Biotin Labeling', 'RNA Quantification',
  'RNA Imaging', 'Sanger Sequencing', 'NGS Library Preparation',
  'CuAAC Bioconjugation', 'SPAAC Bioconjugation', 'Protein Fluorescent Labeling',
  'mRNA Modification', 'DNA Probe Synthesis', 'FISH',
]

const METHOD_OPTIONS = [
  'CuAAC Click Chemistry', 'SPAAC Click Chemistry', 'NHS-Ester Conjugation',
  'Enzymatic Incorporation', 'BigDye Terminator Sequencing', 'Nextera DNA Library Prep',
  'RiboGreen Quantification', 'Cy3/Cy5 Protein Labeling', 'Maleimide Conjugation',
  'Biotin-Streptavidin Capture', 'In Vitro Transcription',
]

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
function selectProduct(p) {
  selectedProduct.value = p
  // Load existing knowledge data if any
  form.value = {
    research_goals: [],
    applications: [],
    methods: [],
    protocols: [],
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
    await http.post('/knowledge-intake/', {
      product_id: selectedProduct.value.id,
      ...form.value,
    })
    message.value = { type: 'ok', text: `Saved knowledge for ${selectedProduct.value.catalog_no}` }
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
  saving.value = true
  try {
    for (const p of similar) {
      await http.post('/knowledge-intake/', {
        product_id: p.id,
        ...form.value,
      })
    }
    message.value = { type: 'ok', text: `Copied to ${similar.length} similar products` }
  } catch (e) {
    message.value = { type: 'err', text: 'Copy failed' }
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
        <div class="ki-product-list">
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
          <!-- Research Goals -->
          <div class="ki-section">
            <h3 class="ki-section-title">Research Goals</h3>
            <div class="ki-chips">
              <button
                v-for="opt in GOAL_OPTIONS"
                :key="opt"
                type="button"
                class="ki-chip"
                :class="{ 'ki-chip-active': form.research_goals.includes(opt) }"
                @click="toggleOption('research_goals', opt)"
              >
                {{ opt }}
              </button>
            </div>
          </div>

          <!-- Applications -->
          <div class="ki-section">
            <h3 class="ki-section-title">Applications</h3>
            <div class="ki-chips">
              <button
                v-for="opt in APP_OPTIONS"
                :key="opt"
                type="button"
                class="ki-chip"
                :class="{ 'ki-chip-active': form.applications.includes(opt) }"
                @click="toggleOption('applications', opt)"
              >
                {{ opt }}
              </button>
            </div>
          </div>

          <!-- Methods -->
          <div class="ki-section">
            <h3 class="ki-section-title">Methods</h3>
            <div class="ki-chips">
              <button
                v-for="opt in METHOD_OPTIONS"
                :key="opt"
                type="button"
                class="ki-chip"
                :class="{ 'ki-chip-active': form.methods.includes(opt) }"
                @click="toggleOption('methods', opt)"
              >
                {{ opt }}
              </button>
            </div>
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
                <label>Steps (brief)</label>
                <textarea v-model="form.protocol_steps" class="ki-textarea" rows="3" placeholder="1. Prepare RNA 2. Add reagents 3. Incubate 4. Purify" />
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
.ki-page { max-width: 1400px; margin: 0 auto; padding: 24px; }
.ki-header { margin-bottom: 24px; }
.ki-title { font-size: 24px; font-weight: 800; color: var(--color-text); margin: 0; }
.ki-subtitle { font-size: 14px; color: var(--color-text-secondary); margin: 4px 0 0; }

.ki-toast { padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; font-weight: 500; }
.ki-toast.ok { background: #d1fae5; color: #065f46; }
.ki-toast.err { background: #fee2e2; color: #991b1b; }

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
.ki-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ki-row label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; display: block; }
.ki-input { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 13px; font-family: var(--font-sans); }
.ki-textarea { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); font-size: 13px; font-family: var(--font-sans); resize: vertical; }

/* Chips */
.ki-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.ki-chip { padding: 4px 12px; border: 1px solid var(--color-border); border-radius: 16px; font-size: 12px; cursor: pointer; background: var(--color-surface); color: var(--color-text); font-family: var(--font-sans); transition: all 0.15s; }
.ki-chip:hover { border-color: var(--color-primary); }
.ki-chip-active { background: var(--color-primary); border-color: var(--color-primary); color: white; }

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
