<script setup>
/**
 * AiToolsPanel — Tabbed AI tools panel for product editing.
 *
 * Three tabs:
 *   Validate     — PubChem SMILES check + BioProCorpus protocol match
 *                    + Molecular Properties + Lipinski + Similar Compounds
 *   Protocols    — BioProCorpus protocol recommendations
 *   Literature   — PubMed literature with knowledge chain extraction + DB matching
 */
import { ref, computed } from 'vue'
import {
  validateProduct, recommendProtocols, recommendLiterature,
  validateUnsavedProduct, recommendProtocolsUnsaved, recommendLiteratureUnsaved,
} from '@/api/aiTools'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const props = defineProps({
  productId: { type: [Number, String], default: null },
  productName: { type: String, required: true },
  productCas: { type: String, default: '' },
  productSmiles: { type: String, default: '' },
})

const emit = defineEmits([
  'adopt-smiles', 'adopt-formula-weight',
  'adopt-protocol', 'adopt-reference',
  'link-method', 'link-app',
])

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

async function runActiveTab() {
  // 新建页（无 productId）必须先填产品名才能调用 unsaved 端点
  if (!props.productId && !props.productName) {
    errorMsg.value = '请先填写产品名，再运行 AI 工具'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    if (activeTab.value === 'validate') {
      const res = props.productId
        ? await validateProduct(props.productId)
        : await validateUnsavedProduct(props.productName, props.productCas, props.productSmiles)
      validateResult.value = res.data
    } else if (activeTab.value === 'protocols') {
      const res = props.productId
        ? await recommendProtocols(props.productId)
        : await recommendProtocolsUnsaved(props.productName)
      protocolRecommendations.value = res.data
    } else if (activeTab.value === 'literature') {
      const res = props.productId
        ? await recommendLiterature(props.productId)
        : await recommendLiteratureUnsaved(props.productName, props.productCas)
      literatureResult.value = res.data
    }
  } catch (e) {
    errorMsg.value = e?.data?.meta?.error?.message || e?.message || 'Request failed'
  } finally {
    loading.value = false
  }
}

/* Auto-run validate on mount — 仅当已有 productId 或 productName 时 */
if (props.productId || props.productName) {
  runActiveTab()
}
</script>

<template>
  <div class="ai-tools-panel">
    <h2 class="panel-title">🤖 AI Tools</h2>

    <!-- Tab bar -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs" :key="tab.key" type="button" class="tab-btn"
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

    <LoadingSpinner v-if="loading" text="Running AI tool…" />
    <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

    <!-- ═══ Validate Tab ═══ -->
    <div v-if="activeTab === 'validate' && validateResult && !loading" class="result-panel">
      <!-- PubChem Card -->
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

        <!-- Molecular Properties -->
        <div v-if="validateResult.pubchem?.molecular_properties" class="props-table">
          <h4>📊 Molecular Properties</h4>
          <table>
            <tr v-if="validateResult.pubchem.molecular_properties.molecular_formula">
              <td>Formula</td><td class="prop-val">{{ validateResult.pubchem.molecular_properties.molecular_formula }}</td>
            </tr>
            <tr v-if="validateResult.pubchem.molecular_properties.molecular_weight">
              <td>MW</td><td class="prop-val">{{ validateResult.pubchem.molecular_properties.molecular_weight }} Da</td>
            </tr>
            <tr v-if="validateResult.pubchem.molecular_properties.xlogp != null">
              <td>LogP</td><td class="prop-val">{{ validateResult.pubchem.molecular_properties.xlogp }}</td>
            </tr>
            <tr v-if="validateResult.pubchem.molecular_properties.tpsa != null">
              <td>TPSA</td><td class="prop-val">{{ validateResult.pubchem.molecular_properties.tpsa }} Å²</td>
            </tr>
            <tr v-if="validateResult.pubchem.molecular_properties.h_bond_donor_count != null">
              <td>HBD</td><td class="prop-val">{{ validateResult.pubchem.molecular_properties.h_bond_donor_count }}</td>
            </tr>
            <tr v-if="validateResult.pubchem.molecular_properties.h_bond_acceptor_count != null">
              <td>HBA</td><td class="prop-val">{{ validateResult.pubchem.molecular_properties.h_bond_acceptor_count }}</td>
            </tr>
            <tr v-if="validateResult.pubchem.molecular_properties.rotatable_bond_count != null">
              <td>RotBonds</td><td class="prop-val">{{ validateResult.pubchem.molecular_properties.rotatable_bond_count }}</td>
            </tr>
          </table>
        </div>

        <!-- Lipinski -->
        <div v-if="validateResult.pubchem?.lipinski" class="lipinski-badge" :class="validateResult.pubchem.lipinski.passed ? 'lipinski-pass' : 'lipinski-fail'">
          💊 Lipinski Rule of Five:
          <strong>{{ validateResult.pubchem.lipinski.passed ? '✅ PASS' : '⚠️ FAIL' }}</strong>
          <ul v-if="validateResult.pubchem.lipinski.violations?.length" class="issue-list">
            <li v-for="v in validateResult.pubchem.lipinski.violations" :key="v">{{ v }}</li>
          </ul>
          <span v-else class="dim"> All 5 rules satisfied</span>
        </div>

        <!-- Similar Compounds -->
        <div v-if="validateResult.pubchem?.similar_compounds?.length" class="similar-list">
          <h4>🔍 Similar Compounds (PubChem)</h4>
          <div v-for="sc in validateResult.pubchem.similar_compounds" :key="sc.cid" class="similar-item">
            <a :href="`https://pubchem.ncbi.nlm.nih.gov/compound/${sc.cid}`" target="_blank" rel="noopener">
              CID {{ sc.cid }}: {{ sc.iupac_name || sc.molecular_formula || '—' }}
            </a>
            <span class="dim">(MW: {{ sc.molecular_weight || '?' }})</span>
          </div>
        </div>
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

      <!-- Adopt buttons -->
      <div v-if="validateResult?.pubchem?.canonical_smiles" class="adopt-row">
        <button type="button" class="btn-adopt" @click="emit('adopt-smiles', validateResult.pubchem.canonical_smiles)">
          💡 Adopt canonical SMILES
        </button>
      </div>
      <div v-if="validateResult?.pubchem?.molecular_properties" class="adopt-row">
        <button type="button" class="btn-adopt" @click="emit('adopt-formula-weight', {
          formula: validateResult.pubchem.molecular_properties.molecular_formula,
          weight: validateResult.pubchem.molecular_properties.molecular_weight
        })">
          💡 Adopt molecular properties (formula & MW)
        </button>
      </div>
    </div>

    <!-- ═══ Protocols Tab ═══ -->
    <div v-if="activeTab === 'protocols' && !loading" class="result-panel">
      <div v-if="protocolRecommendations.length">
        <div v-for="(rec, i) in protocolRecommendations" :key="i" class="result-card">
          <h3>{{ rec.protocol?.title }}</h3>
          <div class="score-bar"><div class="score-fill" :style="{ width: (rec.relevance_score * 20) + '%' }"></div></div>
          <p class="dim">Score: {{ rec.relevance_score?.toFixed(2) }}</p>
          <p class="reason">{{ rec.match_reason }}</p>
          <button type="button" class="btn-adopt" @click="emit('adopt-protocol', rec.protocol)">💡 Adopt this protocol</button>
        </div>
      </div>
      <EmptyState v-else-if="validateResult !== null || errorMsg" title="No protocols found" description="No matching protocols in BioProCorpus for this product name." />
    </div>

    <!-- ═══ Literature Tab ═══ -->
    <div v-if="activeTab === 'literature' && literatureResult && !loading" class="result-panel">
      <!-- Matched Methods -->
      <div v-if="literatureResult.matched_methods?.length" class="result-card card-success">
        <h3>🔗 Matched Methods ({{ literatureResult.matched_methods.length }})</h3>
        <div v-for="mm in literatureResult.matched_methods" :key="mm.keyword" class="match-group">
          <p class="match-kw">"{{ mm.keyword }}" →</p>
          <div v-for="m in mm.matches" :key="m.id" class="match-row">
            <span class="match-name">{{ m.name }}</span>
            <span class="match-slug">({{ m.slug }})</span>
            <button type="button" class="btn-adopt" @click="emit('link-method', m)">🔗 Link this method</button>
          </div>
        </div>
      </div>
      <!-- Matched Apps -->
      <div v-if="literatureResult.matched_apps?.length" class="result-card card-success">
        <h3>🔗 Matched Applications ({{ literatureResult.matched_apps.length }})</h3>
        <div v-for="ma in literatureResult.matched_apps" :key="ma.keyword" class="match-group">
          <p class="match-kw">"{{ ma.keyword }}" →</p>
          <div v-for="a in ma.matches" :key="a.id" class="match-row">
            <span class="match-name">{{ a.name }}</span>
            <span class="match-slug">({{ a.slug }})</span>
            <button type="button" class="btn-adopt" @click="emit('link-app', a)">🔗 Link this application</button>
          </div>
        </div>
      </div>
      <!-- Unmatched -->
      <div v-if="literatureResult.unmatched_method_keywords?.length" class="result-card card-info">
        <h3>💡 Unmatched — may need creation</h3>
        <p class="dim">These method keywords have no match in the knowledge base:</p>
        <div class="chips">
          <span v-for="kw in literatureResult.unmatched_method_keywords" :key="kw" class="chip unmatched-chip">{{ kw }}</span>
        </div>
      </div>
      <div v-if="literatureResult.unmatched_app_keywords?.length" class="result-card card-info">
        <h3>💡 Unmatched Applications</h3>
        <div class="chips">
          <span v-for="kw in literatureResult.unmatched_app_keywords" :key="kw" class="chip unmatched-chip">{{ kw }}</span>
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
          <button type="button" class="btn-adopt" @click="emit('adopt-reference', ref)">💡 Adopt as reference</button>
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
        v-if="!literatureResult.matched_methods?.length && !literatureResult.matched_apps?.length
          && !literatureResult.unmatched_method_keywords?.length && !literatureResult.unmatched_app_keywords?.length
          && !literatureResult.references?.length"
        title="No literature found" description="No PubMed articles match this product."
      />
    </div>
  </div>
</template>

<style scoped>
.ai-tools-panel {}

.panel-title {
  font-size: 16px; font-weight: 700; margin: 0 0 12px; color: var(--color-text);
}

.tab-bar {
  display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 1px solid var(--color-border); padding-bottom: 8px;
}
.tab-btn {
  display: flex; align-items: center; gap: 6px; padding: 6px 14px; border: 1px solid transparent; border-radius: var(--radius-md);
  background: transparent; color: var(--color-text-secondary); font-size: 13px; font-family: var(--font-sans); cursor: pointer; transition: all 0.15s;
}
.tab-btn:hover { color: var(--color-text); background: var(--color-bg); }
.tab-active { background: var(--color-primary); color: white; border-color: var(--color-primary); font-weight: 600; }
.tab-active:hover { background: var(--color-primary); color: white; }
.tab-icon { font-size: 16px; }

.run-section { margin-bottom: 16px; }
.btn-run {
  padding: 8px 24px; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md);
  font-size: 13px; font-weight: 600; cursor: pointer; font-family: var(--font-sans);
}
.btn-run:hover { opacity: 0.9; }
.btn-run:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg {
  padding: 10px 14px; background: #fee2e2; color: #991b1b; border-radius: var(--radius-md); font-size: 13px; margin-bottom: 12px;
}

.result-panel { display: flex; flex-direction: column; gap: 12px; }
.result-card {
  padding: 14px 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface);
}
.result-card h3 { font-size: 13px; font-weight: 700; margin: 0 0 8px; color: var(--color-text); }
.result-card p { font-size: 13px; margin: 4px 0; color: var(--color-text-secondary); }
.result-card a { color: var(--color-primary); }
.card-success { border-left: 3px solid #059669; }
.card-warning { border-left: 3px solid #d97706; }
.card-info { border-left: 3px solid var(--color-primary); }
.dim { color: var(--color-text-tertiary); font-size: 12px; }
.verdict { font-size: 16px; font-weight: 700; }
.issue-list { margin: 4px 0 0; padding-left: 20px; font-size: 12px; color: var(--color-text-secondary); }
.issue-list li { margin-bottom: 2px; }
.protocol-list { margin: 4px 0 0; padding-left: 20px; font-size: 12px; }
.score-bar { height: 4px; background: var(--color-border); border-radius: 2px; margin: 6px 0; overflow: hidden; }
.score-fill { height: 100%; background: var(--color-primary); border-radius: 2px; max-width: 100%; }
.reason { font-size: 12px; color: var(--color-text-tertiary); font-style: italic; }

/* Props table */
.props-table { margin-top: 12px; border-top: 1px solid var(--color-border); padding-top: 10px; }
.props-table h4 { font-size: 12px; font-weight: 600; margin: 0 0 6px; color: var(--color-text-secondary); }
.props-table table { width: 100%; border-collapse: collapse; font-size: 12px; }
.props-table td { padding: 3px 6px; border-bottom: 1px solid var(--color-border-light, #f1f5f9); }
.props-table td:first-child { color: var(--color-text-secondary); width: 80px; }
.prop-val { font-weight: 600; color: var(--color-text); font-family: var(--font-mono); }

/* Lipinski badge */
.lipinski-badge { margin-top: 10px; padding: 8px 10px; border-radius: 6px; font-size: 12px; }
.lipinski-pass { background: #dcf7e8; color: #176b3a; }
.lipinski-fail { background: #fff3cd; color: #856404; }

/* Similar compounds */
.similar-list { margin-top: 12px; border-top: 1px solid var(--color-border); padding-top: 10px; }
.similar-list h4 { font-size: 12px; font-weight: 600; margin: 0 0 6px; color: var(--color-text-secondary); }
.similar-item { font-size: 12px; margin-bottom: 4px; }
.similar-item a { color: var(--color-primary); text-decoration: none; }
.similar-item a:hover { text-decoration: underline; }

/* Chips */
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.chip {
  display: inline-flex; padding: 3px 10px; border-radius: 14px; font-size: 11px; font-weight: 600;
  background: #dbeafe; color: #1e40af;
}
.unmatched-chip { background: #fef3c7; color: #92400e; }

/* Match groups */
.match-group { margin-bottom: 8px; }
.match-kw { font-size: 12px; color: var(--color-text-tertiary); margin: 4px 0; font-style: italic; }
.match-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.match-name { font-size: 13px; font-weight: 600; color: var(--color-text); }
.match-slug { font-size: 11px; color: var(--color-text-tertiary); font-family: var(--font-mono); }

/* References */
.ref-item { padding: 10px 0; border-bottom: 1px solid var(--color-border-light, #f1f5f9); }
.ref-item:last-child { border-bottom: none; }
.citation { font-size: 13px; color: var(--color-text); margin: 0; line-height: 1.5; }
.pmid { font-size: 11px; color: var(--color-text-tertiary); margin: 4px 0 0; font-family: var(--font-mono); }
.pmid a { color: var(--color-primary); }

.adopt-row { margin: 8px 0; }
.btn-adopt {
  padding: 4px 10px; border: 1px solid var(--color-primary); background: var(--color-primary-light);
  color: var(--color-primary); border-radius: 6px; font-size: 12px; cursor: pointer; font-weight: 500; font-family: var(--font-sans);
}
.btn-adopt:hover { background: var(--color-primary); color: white; }
</style>
