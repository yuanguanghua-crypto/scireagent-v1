<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isInternal } from '@/utils/internalAccess'
import { http } from '@/api/http'
import { toast, LoadingSpinner, EmptyState } from '@/components/common'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { getMethods } from '@/api/methods'
import ListTruncationHint from './components/ListTruncationHint.vue'

const router = useRouter()
const auth = useAuthStore()
// ★ 内部人员判定收敛到 utils/internalAccess.js（口径= is_staff || role∈(procurement,admin)）
//   ——与后端 permissions.py IsProcurementOrAdmin 一致；普通注册用户仍被踢回首页。
if (!isInternal(auth)) { router.replace('/') }

const entities = ref([])
const totalCount = ref(0)
const loading = ref(true)
const error = ref('')
const showEditor = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = ref({
  name: '',
  // ★ 2026-11-18（A-076）：改前是单选 `method_id`，编辑一个有 3 条显式桥的协议时
  //   只会回填 methods[0]，保存即把另 2 条 explicit 桥删掉（后端 update 会清理
  //   未勾选的 explicit 行）。实测生产 explicit 桥现为 0 条，所以还没炸过 ——
  //   但这是颗地雷，扩字段的同时必须改成多选。
  method_ids: [],
  status: 'draft',
  objective: '',
  principle: '',
  materials: '',
  reagents: '',
  equipment: '',
  troubleshooting: '',
  expected_results: '',
})
const methods = ref([])
const optionsLoading = ref(false)
const optionsError = ref('')
// ★ 2026-11-18（A-212）：归档入口（两次点击确认）
const pendingArchiveId = ref(null)
// ★ 2026-11-18（A-155）：409 后允许「再点一次 Save 就照样建」（= allow_duplicate=1）
const allowDuplicate = ref(false)
const overlay = ref(null)
const dialogAttrs = useDialogA11y(showEditor, overlay, {
  titleId: 'entity-editor-title',
  close: () => { showEditor.value = false },
})

onMounted(() => {
  loadList()
  // ★ 2026-11-18（A-064）：预载方法选项 —— 改前 openNew() 里 fire-and-forget，
  //   对话框必定先渲染成「disabled + No Method available」。
  loadMethods()
})

async function loadList() {
  loading.value = true
  pendingArchiveId.value = null
  try {
    const resp = await http.get('/protocols/', { params: { page_size: 500 } })
    entities.value = (resp.data?.results || resp.data || [])
    totalCount.value = resp.meta?.pagination?.count ?? (Array.isArray(resp.data) ? resp.data.length : 0)
  } catch (e) {
    error.value = 'Failed to load'
  } finally {
    loading.value = false
  }
}

async function loadMethods() {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    const resp = await getMethods({
      page_size: 200,
      // 管理端要能挂到草稿方法上；后端列表端点默认只给 active（方案 B）
      include_unpublished: 1,
    })
    methods.value = (resp.data?.results || resp.data || [])
  } catch (e) {
    methods.value = []
    // 改前是 `catch { /* ignore */ }`：失败与"没有方法"同形，用户只看到禁用框
    optionsError.value = '方法列表加载失败：' + (e.response?.data?.meta?.error?.message || e.message)
  } finally {
    optionsLoading.value = false
  }
}

function blankForm() {
  return {
    name: '', method_ids: [], status: 'draft',
    objective: '', principle: '', materials: '', reagents: '',
    equipment: '', troubleshooting: '', expected_results: '',
  }
}

function openNew() {
  editing.value = null
  form.value = blankForm()
  allowDuplicate.value = false
  showEditor.value = true
  loadMethods()
}

async function openEdit(e) {
  editing.value = e
  const next = blankForm()
  next.name = e.name || ''
  next.status = e.status || 'draft'
  // 列表接口不返回 methods/内容字段，编辑时拉详情预填，避免保存时误清空桥与正文
  try {
    const resp = await http.get(`/protocols/${e.id}/`)
    const data = resp.data?.data || resp.data || {}
    next.method_ids = (data.methods || []).map((m) => m.id)
    for (const k of ['objective', 'principle', 'materials', 'reagents',
                     'equipment', 'troubleshooting', 'expected_results']) {
      next[k] = data[k] || ''
    }
    if (data.status) next.status = data.status
  } catch { /* 拉取失败则留空，不影响编辑其他字段 */ }
  form.value = next
  allowDuplicate.value = false
  showEditor.value = true
  loadMethods()
}

async function save() {
  saving.value = true
  try {
    // #494 route B：协议↔方法经 MethodProtocol 桥多对多。
    const payload = {
      name: form.value.name,
      status: form.value.status,
      methods: [...form.value.method_ids],
    }
    for (const k of ['objective', 'principle', 'materials', 'reagents',
                     'equipment', 'troubleshooting', 'expected_results']) {
      payload[k] = form.value[k] || ''
    }
    const config = allowDuplicate.value ? { params: { allow_duplicate: 1 } } : undefined
    if (editing.value) {
      await http.put(`/protocols/${editing.value.id}/`, payload, config)
    } else {
      await http.post('/protocols/', payload, config)
    }
    showEditor.value = false
    allowDuplicate.value = false
    await loadList()
  } catch (e) {
    // ★ A-155：同名冲突改由后端 409 显式拒绝（生产已有 63 组真实同名，不能加唯一约束）
    if (e.response?.status === 409) {
      allowDuplicate.value = true
      const msg = e.response?.data?.meta?.error?.message || '已存在同名协议'
      toast.warning(`${msg} —— 再点一次 Save 就会照样新建。`)
      return
    }
    toast.error('Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    saving.value = false
  }
}

/** ★ 2026-11-18（A-212）：归档入口。
 *  协议用自有 `PublicationStatus`（draft/published/superseded/archived），
 *  与其余知识实体的 StatusMixin **枚举不同**（Protocol 的 `active` 恒为 0）。 */
async function archiveRow(e) {
  if (pendingArchiveId.value !== e.id) {
    pendingArchiveId.value = e.id
    return
  }
  pendingArchiveId.value = null
  try {
    await http.patch(`/protocols/${e.id}/`, { status: 'archived' })
    toast.success(`已归档「${e.name}」`)
    await loadList()
  } catch (err) {
    toast.error('Archive failed: ' + (err.response?.data?.meta?.error?.message || err.message))
  }
}
</script>

<template>
  <div class="entity-page">
    <div class="entity-header">
      <h2>Protocols</h2>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New Protocol</button>
    </div>
    <ListTruncationHint :count="totalCount" :shown="entities.length" />

    <LoadingSpinner v-if="loading" text="Loading..." />
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="entities.length" class="entity-table">
      <thead><tr><th>ID</th><th>Name</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="e in entities" :key="e.id">
          <td>{{ e.id }}</td>
          <td class="col-name">{{ e.name }}</td>
          <td><span class="status-tag" :class="'status-' + (e.status || 'draft')">{{ e.status || '—' }}</span></td>
          <td>
            <button class="btn btn-ghost btn-sm" @click="openEdit(e)">Edit</button>
            <button class="btn btn-ghost btn-sm btn-danger" @click="archiveRow(e)">
              {{ pendingArchiveId === e.id ? 'Confirm archive' : 'Archive' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <EmptyState v-else title="No protocols yet" icon="Document" />

    <div v-if="showEditor" ref="overlay" class="dialog-overlay" v-bind="dialogAttrs" @click.self="showEditor = false">
      <div class="dialog">
        <h3 id="entity-editor-title">{{ editing ? 'Edit' : 'New' }} Protocol</h3>
        <label>Name <input v-model="form.name" class="input-full" /></label>
        <label>Status
          <select v-model="form.status" class="input-full">
            <option value="draft">draft</option>
            <option value="published">published</option>
            <option value="superseded">superseded</option>
            <option value="archived">archived</option>
          </select>
        </label>
        <label>Methods
          <el-select
            v-model="form.method_ids" multiple collapse-tags collapse-tags-tooltip
            filterable placeholder="Select method(s)" clearable
            :loading="optionsLoading" style="width: 100%"
          >
            <el-option v-for="m in methods" :key="m.id" :label="m.status ? `${m.name} · ${m.status}` : m.name" :value="m.id" />
          </el-select>
          <span v-if="optionsLoading" class="fk-empty">Loading methods…</span>
          <span v-else-if="optionsError" class="fk-empty fk-error">{{ optionsError }}</span>
        </label>
        <label>Objective <textarea v-model="form.objective" rows="3" class="input-full"></textarea></label>
        <label>Principle <textarea v-model="form.principle" rows="3" class="input-full"></textarea></label>
        <label>Materials <textarea v-model="form.materials" rows="3" class="input-full"></textarea></label>
        <label>Reagents <textarea v-model="form.reagents" rows="3" class="input-full"></textarea></label>
        <label>Equipment <textarea v-model="form.equipment" rows="2" class="input-full"></textarea></label>
        <label>Troubleshooting <textarea v-model="form.troubleshooting" rows="3" class="input-full"></textarea></label>
        <label>Expected Results <textarea v-model="form.expected_results" rows="3" class="input-full"></textarea></label>
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
.fk-error { color: var(--color-danger, #dc2626); font-style: normal; }
</style>
