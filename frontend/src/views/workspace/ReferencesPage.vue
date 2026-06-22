<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/api/http'

const router = useRouter()
const auth = useAuthStore()
if (!auth.isStaff) { router.replace('/') }

const entities = ref([])
const loading = ref(true)
const error = ref('')
const showEditor = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = ref({ title: '', url: '', doi: '', citation: '', source_type: 'journal' })

onMounted(loadList)

async function loadList() {
  loading.value = true
  try {
    const resp = await http.get('/references/', { params: { page_size: 200 } })
    entities.value = (resp.data?.results || resp.data || [])
  } catch (e) {
    error.value = 'Failed to load references'
  } finally {
    loading.value = false
  }
}

function openNew() {
  editing.value = null
  form.value = { title: '', url: '', doi: '', citation: '', source_type: 'journal' }
  showEditor.value = true
}
function openEdit(e) {
  editing.value = e
  form.value = {
    title: e.title || '',
    url: e.url || '',
    doi: e.doi || '',
    citation: e.citation || '',
    source_type: e.source_type || 'journal',
  }
  showEditor.value = true
}

async function save() {
  saving.value = true
  try {
    if (editing.value) {
      await http.put(`/references/${editing.value.id}/`, form.value)
    } else {
      await http.post('/references/', form.value)
    }
    showEditor.value = false
    await loadList()
  } catch (e) {
    alert('Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="entity-page">
    <div class="entity-header">
      <h2>References</h2>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New Reference</button>
    </div>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="entities.length" class="entity-table">
      <thead><tr><th>ID</th><th>Title</th><th>DOI/URL</th><th>Type</th><th></th></tr></thead>
      <tbody>
        <tr v-for="e in entities" :key="e.id">
          <td>{{ e.id }}</td>
          <td class="col-name">{{ e.title }}</td>
          <td class="col-summary">{{ e.doi || e.url || '—' }}</td>
          <td>{{ e.source_type || '—' }}</td>
          <td><button class="btn btn-ghost btn-sm" @click="openEdit(e)">Edit</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty-text">No references yet.</p>

    <div v-if="showEditor" class="dialog-overlay" @click.self="showEditor = false">
      <div class="dialog">
        <h3>{{ editing ? 'Edit' : 'New' }} Reference</h3>
        <label>Title <input v-model="form.title" class="input-full" /></label>
        <label>URL <input v-model="form.url" class="input-full" placeholder="https://..." /></label>
        <label>DOI <input v-model="form.doi" class="input-full" placeholder="10.xxx/xxx" /></label>
        <label>Citation <textarea v-model="form.citation" rows="3" class="input-full"></textarea></label>
        <label>Source Type
          <select v-model="form.source_type" class="input-full">
            <option value="journal">Journal</option>
            <option value="patent">Patent</option>
            <option value="book">Book</option>
            <option value="website">Website</option>
            <option value="other">Other</option>
          </select>
        </label>
        <div class="dialog-actions">
          <button class="btn btn-ghost btn-sm" @click="showEditor = false">Cancel</button>
          <button class="btn btn-primary btn-sm" @click="save" :disabled="saving">{{ saving ? 'Saving...' : 'Save' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.entity-page { max-width: 900px; }
.entity-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.entity-header h2 { font-size: 20px; font-weight: 600; color: var(--color-text); margin: 0; }
.entity-table { width: 100%; border-collapse: collapse; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; overflow: hidden; }
.entity-table th, .entity-table td { text-align: left; padding: 10px 14px; font-size: 13px; border-bottom: 1px solid var(--color-border); }
.entity-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.col-name { font-weight: 500; color: var(--color-text); }
.col-summary { color: var(--color-text-secondary); font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.dialog { background: var(--color-surface); border-radius: 12px; padding: 24px; max-width: 480px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.dialog h3 { margin-bottom: 16px; color: var(--color-text); }
.dialog label { display: flex; flex-direction: column; font-size: 13px; color: var(--color-text-secondary); gap: 4px; margin-bottom: 12px; }
.input-full { width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 6px; font-size: 14px; background: var(--color-bg); color: var(--color-text); font-family: var(--font-sans); resize: vertical; }
.dialog-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.loading, .error, .empty-text { text-align: center; padding: 40px; color: var(--color-text-secondary); }
</style>
