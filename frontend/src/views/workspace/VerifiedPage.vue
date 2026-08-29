<template>
  <div class="wv-page">
    <div class="wv-header">
      <h2 class="wv-title">Verified Applicability</h2>
      <p class="wv-sub">
        Researcher-curated product → method applicability facts. AI-mined drafts
        (origin: ai_extracted) await your review; approving promotes them to the
        public product page.
      </p>
    </div>

    <div class="wv-tabs">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="wv-tab"
        :class="{ 'wv-tab-active': activeTab === t.key }"
        @click="switchTab(t.key)"
      >
        {{ t.label }}
      </button>
    </div>

    <div v-if="loading" class="wv-empty">Loading…</div>
    <div v-else-if="error" class="wv-empty">{{ error }}</div>
    <div v-else-if="!rows.length" class="wv-empty">No verified relations in this state.</div>

    <table v-else class="wv-table">
      <thead>
        <tr>
          <th>Product</th>
          <th>Method</th>
          <th>Status</th>
          <th>Evidence</th>
          <th>Strength</th>
          <th>Curator</th>
          <th>Created</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>
            <router-link :to="`/products/${r.product_id}`" class="wv-link">
              {{ r.product_name || `#${r.product_id}` }}
            </router-link>
            <div class="wv-meta">{{ r.product_catalog_no }}</div>
          </td>
          <td>
            <router-link :to="`/methods/${r.method_id}`" class="wv-link">
              {{ r.method_name || `#${r.method_id}` }}
            </router-link>
          </td>
          <td><span class="wv-badge" :class="`wv-badge-${r.status}`">{{ r.status }}</span></td>
          <td>
            <span
              v-for="(ref, i) in evidenceChips(r)"
              :key="i"
              class="wv-chip"
            >{{ ref }}</span>
            <span v-if="!evidenceChips(r).length" class="wv-meta">—</span>
            <div v-if="r.evidence_note" class="wv-note" :title="r.evidence_note">
              {{ r.evidence_note.split('\n')[0] }}
            </div>
          </td>
          <td>{{ r.evidence_strength || '—' }}</td>
          <td>{{ r.curator || '—' }}</td>
          <td>{{ fmtDate(r.created_at) }}</td>
          <td class="wv-actions">
            <template v-if="r.status === 'review'">
              <button class="wv-btn wv-btn-approve" @click="approve(r)">Approve</button>
              <button class="wv-btn wv-btn-reject" @click="reject(r)">Reject</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as bridgesApi from '@/api/bridges'
import { toast } from '@/components/common'

const tabs = [
  { key: 'review', label: 'Review' },
  { key: 'active', label: 'Active' },
  { key: 'rejected', label: 'Rejected' },
  { key: '', label: 'All' },
]
const activeTab = ref('review')
const rows = ref([])
const loading = ref(false)
const error = ref('')

function evidenceChips(r) {
  const refs = Array.isArray(r.evidence_reference) ? r.evidence_reference : []
  return refs
    .filter((x) => x && x.type && x.value)
    .map((x) => `${x.type}: ${x.value}`)
}

function fmtDate(s) {
  return s ? String(s).slice(0, 10) : '—'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = activeTab.value ? { status: activeTab.value } : {}
    rows.value = (await bridgesApi.listVerified(params)) || []
  } catch (e) {
    console.error('Failed to load verified list', e)
    error.value = 'Failed to load review queue.'
    rows.value = []
  } finally {
    loading.value = false
  }
}

function switchTab(key) {
  activeTab.value = key
  load()
}

async function approve(r) {
  if (!window.confirm(`Approve "${r.method_name}" as verified applicable for "${r.product_name}"?\nThis publishes it to the public product page.`)) return
  try {
    await bridgesApi.approveVerified(r.id)
    toast.success('Approved')
    load()
  } catch (e) {
    toast.error('Approve failed: ' + (e?.message || 'unknown'))
  }
}

async function reject(r) {
  const note = window.prompt(`Reject "${r.method_name}" for "${r.product_name}" — reason (optional):`, '') ?? ''
  try {
    await bridgesApi.rejectVerified(r.id, note)
    toast.success('Rejected')
    load()
  } catch (e) {
    toast.error('Reject failed: ' + (e?.message || 'unknown'))
  }
}

onMounted(load)
</script>

<style scoped>
.wv-page { padding: 24px; max-width: 1100px; }
.wv-title { font-size: 20px; margin: 0 0 4px; }
.wv-sub { color: #6B7280; font-size: 13px; margin: 0 0 16px; max-width: 720px; }
.wv-tabs { display: flex; gap: 8px; margin-bottom: 14px; }
.wv-tab {
  padding: 6px 14px; border-radius: 999px; border: 1px solid #D1D5DB;
  background: #fff; cursor: pointer; font-size: 13px; color: #374151;
}
.wv-tab-active { background: #1B7A43; border-color: #1B7A43; color: #fff; }
.wv-empty { color: #6B7280; font-size: 14px; padding: 24px 0; }
.wv-table { width: 100%; border-collapse: collapse; background: #fff; font-size: 13px; }
.wv-table th, .wv-table td {
  text-align: left; padding: 9px 10px; border-bottom: 1px solid #E5E7EB; vertical-align: top;
}
.wv-table th { color: #6B7280; font-weight: 600; font-size: 12px; }
.wv-link { color: #1D4ED8; text-decoration: none; }
.wv-meta { color: #9CA3AF; font-size: 12px; }
.wv-badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.wv-badge-review { background: #FEF3C7; color: #92400E; }
.wv-badge-active { background: #D1FAE5; color: #065F46; }
.wv-badge-rejected { background: #FEE2E2; color: #991B1B; }
.wv-chip {
  display: inline-block; margin: 1px 4px 1px 0; padding: 2px 7px; border-radius: 999px;
  background: #F1F5F9; color: #475569; font-size: 12px;
}
.wv-note { color: #9CA3AF; font-size: 11px; margin-top: 3px; }
.wv-actions { white-space: nowrap; }
.wv-btn { margin-right: 6px; padding: 4px 12px; border-radius: 6px; border: none; cursor: pointer; font-size: 12px; }
.wv-btn-approve { background: #1B7A43; color: #fff; }
.wv-btn-reject { background: #fff; color: #B91C1C; border: 1px solid #FCA5A5; }
</style>
