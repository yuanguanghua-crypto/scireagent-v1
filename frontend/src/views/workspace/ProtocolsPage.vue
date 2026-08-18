<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { http } from '@/api/http'
import { toast, LoadingSpinner, EmptyState } from '@/components/common'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { getMethods } from '@/api/methods'

const router = useRouter()
const auth = useAuthStore()
if (!auth.isStaff) { router.replace('/') }

const entities = ref([])
const loading = ref(true)
const error = ref('')
const showEditor = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = ref({ name: '', method_id: null })
const methods = ref([])
const overlay = ref(null)
const dialogAttrs = useDialogA11y(showEditor, overlay, {
  titleId: 'entity-editor-title',
  close: () => { showEditor.value = false },
})

onMounted(loadList)

async function loadList() {
  loading.value = true
  try {
    const resp = await http.get('/protocols/', { params: { page_size: 500 } })
    entities.value = (resp.data?.results || resp.data || [])
  } catch (e) {
    error.value = 'Failed to load'
  } finally {
    loading.value = false
  }
}

async function loadMethods() {
  try {
    const resp = await getMethods({ page_size: 200 })
    methods.value = (resp.data?.results || resp.data || [])
  } catch { /* ignore */ }
}

function openNew() {
  editing.value = null
  form.value = { name: '', method_id: null }
  loadMethods()
  showEditor.value = true
}
async function openEdit(e) {
  editing.value = e
  // 列表接口不返回 methods，编辑时拉详情预填已关联方法，避免保存时误清空桥。
  let methodId = null
  try {
    const resp = await http.get(`/protocols/${e.id}/`)
    const data = resp.data?.data || resp.data || {}
    const methods = data.methods || []
    methodId = methods.length ? methods[0].id : null
  } catch { /* 拉取失败则留空，不影响编辑其他字段 */ }
  form.value = { name: e.name || '', method_id: methodId }
  loadMethods()
  showEditor.value = true
}

async function save() {
  saving.value = true
  try {
    // #494 route B：协议↔方法经 MethodProtocol 桥多对多。编辑器维持单选 UX，
    // 保存时把单个 method_id 转成 methods 列表写入桥（后端 ProtocolListSerializer 处理）。
    const payload = { name: form.value.name }
    payload.methods = form.value.method_id ? [form.value.method_id] : []
    if (editing.value) {
      await http.put(`/protocols/${editing.value.id}/`, payload)
    } else {
      await http.post('/protocols/', payload)
    }
    showEditor.value = false
    await loadList()
  } catch (e) {
    toast.error('Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="entity-page">
    <div class="entity-header">
      <h2>Protocols</h2>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New Protocol</button>
    </div>
    <LoadingSpinner v-if="loading" text="Loading..." />
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="entities.length" class="entity-table">
      <thead><tr><th>ID</th><th>Name</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="e in entities" :key="e.id">
          <td>{{ e.id }}</td>
          <td class="col-name">{{ e.name }}</td>
          <td><span class="status-tag" :class="'status-' + (e.status || 'draft')">{{ e.status || '—' }}</span></td>
          <td><button class="btn btn-ghost btn-sm" @click="openEdit(e)">Edit</button></td>
        </tr>
      </tbody>
    </table>
    <EmptyState v-else title="No protocols yet" icon="Document" />

    <div v-if="showEditor" ref="overlay" class="dialog-overlay" v-bind="dialogAttrs" @click.self="showEditor = false">
      <div class="dialog">
        <h3 id="entity-editor-title">{{ editing ? 'Edit' : 'New' }} Protocol</h3>
        <label>Name <input v-model="form.name" class="input-full" /></label>
        <label>Method
          <el-select v-model="form.method_id" placeholder="Select method" clearable :disabled="!methods.length" style="width: 100%">
            <el-option v-for="m in methods" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
          <span v-if="!methods.length" class="fk-empty">No Method available</span>
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
.entity-table { width: 100%; border-collapse: collapse; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 4px; overflow: hidden; }
.entity-table th, .entity-table td { text-align: left; padding: 10px 14px; font-size: 13px; border-bottom: 1px solid var(--color-border); }
.entity-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); }
.col-name { font-weight: 500; color: var(--color-text); }
.status-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.status-active { background: var(--color-success-light); color: var(--color-primary-active); }
.status-draft { background: var(--color-warning-light); color: var(--color-warning); }
.error { text-align: center; padding: 40px; color: var(--color-text-secondary); }
.fk-empty { font-size: 12px; color: var(--color-text-secondary); font-style: italic; }
</style>
