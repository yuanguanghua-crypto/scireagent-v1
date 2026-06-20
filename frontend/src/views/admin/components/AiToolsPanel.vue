<script setup>
/**
 * AiToolsPanel — Tabbed AI tools panel for product editing.
 *
 * Three tabs:
 *   Validate     — PubChem SMILES check + BioProCorpus protocol match
 *   Protocols    — BioProCorpus protocol recommendations
 *   Literature   — PubMed literature recommendations with knowledge chain extraction
 */
import { ref, computed, watch } from 'vue'
import { validateProduct, recommendProtocols, recommendLiterature } from '@/api/aiTools'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const props = defineProps({
  productId: { type: [Number, String], required: true },
  productName: { type: String, required: true },
  productCas: { type: String, default: '' },
  productSmiles: { type: String, default: '' },
})

/* ── Tab state ── */
const tabs = [
  { key: 'validate', label: 'Validate', icon: '🔬' },
  { key: 'protocols', label: 'Protocols', icon: '🧪' },
  { key: 'literature', label: 'Literature', icon: '📚' },
]
const activeTab = ref('validate')
const loading = ref(false)
const validateResult = ref(null)
const protocolRecommendations = ref([])
const literatureResult = ref(null)
const errorMsg = ref('')

const activeTabLabel = computed(() => {
  const t = tabs.find(t => t.key === activeTab.value)
  return t ? t.label : ''
})

/* ── Actions ── */
async function runActiveTab() {
  loading.value = true
  errorMsg.value = ''
  try {
    if (activeTab.value === 'validate') {
      const res = await validateProduct(props.productId)
      validateResult.value = res.data
    } else if (activeTab.value === 'protocols') {
      const res = await recommendProtocols(props.productId)
      protocolRecommendations.value = res.data
    } else if (activeTab.value === 'literature') {
      const res = await recommendLiterature(props.productId)
      literatureResult.value = res.data
    }
  } catch (e) {
    errorMsg.value = e?.data?.meta?.error?.message || e?.message || 'Request failed'
  } finally {
    loading.value = false
  }
}

/* Auto-run validate on mount */
runActiveTab()
</script>

<template>
  <div class="ai-tools-panel">
    <h2 class="panel-title">🤖 AI Tools</h2>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab-btn"
        :class="{ 'tab-active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </button>
    </div>

    <!-- Run button -->
    <div class="run-section">
      <button class="btn-run" :disabled="loading" @click="runActiveTab">
        {{ loading ? 'Running…' : `Run ${activeTabLabel}` }}
      </button>
    </div>

    <!-- Loading / Error -->
    <LoadingSpinner v-if="loading" text="Running AI tool…" />
    <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

    <!-- ═══ Validate Tab ═══ -->
    <div v-if="activeTab === 'validate' && validateResult && !loading" class="result-panel">
      <!-- PubChem -->
      <div class="result-card" :class="validateResult.pubchem?.match ? 'card-success' : 'card-warning'">
        <h3>PubChem</h3>
        <p v-if="validateResult.pubchem?.cid">
          CID:
          <a :href="`https://pubchem.ncbi.nlm.nih.gov/compound/${validateResult.pubchem.cid}`" target="_blank" rel="noopener">
            {{ validateResult.pubchem.cid }}
          </a>
        </p>
        <p v-else class="dim">No PubChem match found</p>
        <p v-if="validateResult.pubchem">
          Match: <strong>{{ validateResult.pubchem.match ? '✅ Yes' : '❌ No' }}</strong>
        </p>
        <ul v-if="validateResult.mismatches?.length" class="issue-list">
          <li v-for="m in validateResult.mismatches" :key="m">Mismatch: {{ m }}</li>
        </ul>
      </div>

      <!-- BioProCorpus -->
      <div class="result-card" :class="validateResult.bioprocorpus?.match_count > 0 ? 'card-success' : 'card-info'">
        <h3>BioProCorpus</h3>
        <p>Matched protocols: <strong>{{ validateResult.bioprocorpus?.match_count || 0 }}</strong></p>
        <ul v-if="validateResult.matched_protocols?.length" class="protocol-list">
          <li v-for="(p, i) in validateResult.matched_protocols" :key="i">{{ p.title }}</li>
        </ul>
      </div>

      <!-- Overall -->
      <div class="result-card" :class="validateResult.overall_match ? 'card-success' : 'card-warning'">
        <h3>Overall</h3>
        <p class="verdict">{{ validateResult.overall_match ? '✅ PASS' : '⚠️ REVIEW NEEDED' }}</p>
      </div>
    </div>

    <!-- ═══ Protocols Tab ═══ -->
    <div v-if="activeTab === 'protocols' && !loading" class="result-panel">
      <div v-if="protocolRecommendations.length">
        <div v-for="(rec, i) in protocolRecommendations" :key="i" class="result-card">
          <h3>{{ rec.protocol?.title }}</h3>
          <div class="score-bar">
            <div class="score-fill" :style="{ width: (rec.relevance_score * 20) + '%' }"></div>
          </div>
          <p class="dim">Score: {{ rec.relevance_score?.toFixed(2) }}</p>
          <p class="reason">{{ rec.match_reason }}</p>
        </div>
      </div>
      <EmptyState
        v-else-if="validateResult !== null || errorMsg"
        title="No protocols found"
        description="No matching protocols in BioProCorpus for this product name."
      />
    </div>

    <!-- ═══ Literature Tab ═══ -->
    <div v-if="activeTab === 'literature' && literatureResult && !loading" class="result-panel">
      <!-- Applications -->
      <div v-if="literatureResult.applications?.length" class="result-card">
        <h3>Applications ({{ literatureResult.applications.length }})</h3>
        <div class="chips">
          <span v-for="app in literatureResult.applications" :key="app" class="chip">{{ app }}</span>
        </div>
      </div>

      <!-- Methods -->
      <div v-if="literatureResult.methods?.length" class="result-card">
        <h3>Methods ({{ literatureResult.methods.length }})</h3>
        <div class="chips">
          <span v-for="m in literatureResult.methods" :key="m" class="chip method-chip">{{ m }}</span>
        </div>
      </div>

      <!-- References -->
      <div v-if="literatureResult.references?.length" class="result-card">
        <h3>References ({{ literatureResult.references.length }})</h3>
        <div v-for="ref in literatureResult.references" :key="ref.pmid" class="ref-item">
          <p class="citation">{{ ref.citation }}</p>
          <p class="pmid">
            PMID: <a :href="`https://pubmed.ncbi.nlm.nih.gov/${ref.pmid}/`" target="_blank" rel="noopener">{{ ref.pmid }}</a>
            <span v-if="ref.doi"> | DOI: {{ ref.doi }}</span>
          </p>
        </div>
      </div>

      <!-- Protocol references -->
      <div v-if="literatureResult.protocols?.length" class="result-card">
        <h3>Protocol References ({{ literatureResult.protocols.length }})</h3>
        <div v-for="p in literatureResult.protocols" :key="p.pmid" class="ref-item">
          <p><strong>{{ p.title }}</strong></p>
          <p class="dim">{{ p.source }} — PMID: {{ p.pmid }}</p>
        </div>
      </div>

      <EmptyState
        v-if="!literatureResult.applications?.length && !literatureResult.references?.length"
        title="No literature found"
        description="No PubMed articles match this product."
      />
    </div>
  </div>
</template>

<style scoped>
.ai-tools-panel {
  /* Uses parent card styling */
}

.panel-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 12px;
  color: var(--color-text);
}

/* ── Tab bar ── */
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-family: var(--font-sans);
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn:hover {
  color: var(--color-text);
  background: var(--color-bg);
}

.tab-active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
  font-weight: 600;
}

.tab-active:hover {
  background: var(--color-primary);
  color: white;
}

.tab-icon {
  font-size: 16px;
}

/* ── Run section ── */
.run-section {
  margin-bottom: 16px;
}

.btn-run {
  padding: 8px 24px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-sans);
}

.btn-run:hover {
  opacity: 0.9;
}

.btn-run:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-msg {
  padding: 10px 14px;
  background: #fee2e2;
  color: #991b1b;
  border-radius: var(--radius-md);
  font-size: 13px;
  margin-bottom: 12px;
}

/* ── Result panel ── */
.result-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.result-card h3 {
  font-size: 13px;
  font-weight: 700;
  margin: 0 0 8px;
  color: var(--color-text);
}

.result-card p {
  font-size: 13px;
  margin: 4px 0;
  color: var(--color-text-secondary);
}

.result-card a {
  color: var(--color-primary);
}

.card-success {
  border-left: 3px solid #059669;
}

.card-warning {
  border-left: 3px solid #d97706;
}

.card-info {
  border-left: 3px solid var(--color-primary);
}

.dim {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.verdict {
  font-size: 16px;
  font-weight: 700;
}

/* ── Issue list ── */
.issue-list {
  margin: 4px 0 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.issue-list li {
  margin-bottom: 2px;
}

/* ── Protocol list ── */
.protocol-list {
  margin: 4px 0 0;
  padding-left: 20px;
  font-size: 12px;
}

/* ── Score bar ── */
.score-bar {
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  margin: 6px 0;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 2px;
  max-width: 100%;
}

.reason {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-style: italic;
}

/* ── Chips ── */
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.chip {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 14px;
  font-size: 11px;
  font-weight: 600;
  background: #dbeafe;
  color: #1e40af;
}

.method-chip {
  background: #d1fae5;
  color: #065f46;
}

/* ── References ── */
.ref-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-light, #f1f5f9);
}

.ref-item:last-child {
  border-bottom: none;
}

.citation {
  font-size: 13px;
  color: var(--color-text);
  margin: 0;
  line-height: 1.5;
}

.pmid {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin: 4px 0 0;
  font-family: var(--font-mono);
}

.pmid a {
  color: var(--color-primary);
}
</style>
