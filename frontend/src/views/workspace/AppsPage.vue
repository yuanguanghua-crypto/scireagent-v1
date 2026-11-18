<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isInternal } from '@/utils/internalAccess'
import { http } from '@/api/http'
import { toast, LoadingSpinner, EmptyState } from '@/components/common'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { getResearchGoals } from '@/api/researchGoals'
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
const form = ref({ name: '', summary: '', research_goal_id: null })
const researchGoals = ref([])          // 远程搜索结果（≤50 条）
const pinnedGoal = ref(null)           // 编辑态当前关联的目标，必须常驻选项表
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
  // ★ 2026-11-18（A-062）：预载一次，避免对话框先渲染成「disabled + No Research Goal available」。
  searchResearchGoals('')
})

async function loadList() {
  loading.value = true
  pendingArchiveId.value = null
  try {
    const resp = await http.get('/applications/', { params: { page_size: 200 } })
    entities.value = (resp.data?.results || resp.data || [])
    totalCount.value = resp.meta?.pagination?.count ?? (Array.isArray(resp.data) ? resp.data.length : 0)
  } catch (e) {
    error.value = 'Failed to load'
  } finally {
    loading.value = false
  }
}

/** 远程搜索目标（生产 11,047 条，「前 200 条枚举」等于让用户在 1.8% 的池子里选）。 */
async function searchResearchGoals(query) {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    const resp = await getResearchGoals({
      search: query || '',
      page_size: 50,
      include_unpublished: 1,   // 管理端要能挂到草稿目标上
    })
    let list = (resp.data?.results || resp.data || [])
    // ★ A-062「真实应用显示裸数字 612」的直接根因：当前值不在选项表里 ⇒
    //   el-select 无 label 可渲染，把 id 原样吐出来。把已关联目标钉在表头即可。
    const pin = pinnedGoal.value
    if (pin && pin.id && !list.some((g) => g.id === pin.id)) {
      list = [pin, ...list]
    }
    researchGoals.value = list
  } catch (e) {
    researchGoals.value = pinnedGoal.value ? [pinnedGoal.value] : []
    // 改前是 `catch { /* ignore */ }`：加载失败与"没有目标"同形，用户只看到禁用框
    optionsError.value = '目标列表加载失败：' + (e.response?.data?.meta?.error?.message || e.message)
  } finally {
    optionsLoading.value = false
  }
}

async function openNew() {
  editing.value = null
  pinnedGoal.value = null
  form.value = { name: '', summary: '', research_goal_id: null }
  allowDuplicate.value = false
  showEditor.value = true
  await searchResearchGoals('')
}

async function openEdit(e) {
  editing.value = e
  pinnedGoal.value = e.research_goal_id
    ? { id: e.research_goal_id, name: e.research_goal_name || `#${e.research_goal_id}` }
    : null
  form.value = { name: e.name || '', summary: e.summary || '', research_goal_id: e.research_goal_id || null }
  allowDuplicate.value = false
  showEditor.value = true
  await searchResearchGoals('')
}

async function save() {
  saving.value = true
  try {
    const config = allowDuplicate.value ? { params: { allow_duplicate: 1 } } : undefined
    if (editing.value) {
      await http.put(`/applications/${editing.value.id}/`, form.value, config)
    } else {
      await http.post('/applications/', form.value, config)
    }
    showEditor.value = false
    allowDuplicate.value = false
    await loadList()
  } catch (e) {
    // ★ A-155：同名冲突改由后端 409 显式拒绝（改前一模一样地建副本）
    if (e.response?.status === 409) {
      allowDuplicate.value = true
      const msg = e.response?.data?.meta?.error?.message || '已存在同名应用'
      toast.warning(`${msg} —— 再点一次 Save 就会照样新建。`)
      return
    }
    toast.error('Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    saving.value = false
  }
}

/** ★ 2026-11-18（A-212）：归档入口（模型层早有 `archived`，缺的只是 UI）。 */
async function archiveRow(e) {
  if (pendingArchiveId.value !== e.id) {
    pendingArchiveId.value = e.id
    return
  }
  pendingArchiveId.value = null
  try {
    await http.patch(`/applications/${e.id}/`, { status: 'archived' })
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
      <h2>Applications</h2>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New Application</button>
    </div>

    <ListTruncationHint :count="totalCount" :shown="entities.length" />

    <LoadingSpinner v-if="loading" text="Loading..." />
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="entities.length" class="entity-table">
      <thead><tr><th>ID</th><th>Name</th><th>Summary</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="e in entities" :key="e.id">
          <td>{{ e.id }}</td>
          <td class="col-name">{{ e.name }}</td>
          <td class="col-summary">{{ (e.summary || '').slice(0, 120) }}</td>
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
    <EmptyState v-else title="No applications yet" icon="FolderOpened" />

    <div v-if="showEditor" ref="overlay" class="dialog-overlay" v-bind="dialogAttrs" @click.self="showEditor = false">
      <div class="dialog">
        <h3 id="entity-editor-title">{{ editing ? 'Edit' : 'New' }} Application</h3>
        <label>Name <input v-model="form.name" class="input-full" /></label>
        <label>Summary <textarea v-model="form.summary" rows="4" class="input-full"></textarea></label>
        <label>Research Goal
          <el-select
            v-model="form.research_goal_id"
            filterable remote reserve-keyword
            :remote-method="searchResearchGoals"
            :loading="optionsLoading"
            placeholder="Search research goal"
            clearable style="width: 100%"
          >
            <el-option v-for="g in researchGoals" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <span v-if="optionsLoading" class="fk-empty">Loading research goals…</span>
          <span v-else-if="optionsError" class="fk-empty fk-error">{{ optionsError }}</span>
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
.col-summary { color: var(--color-text-secondary); font-size: 12px; }
.status-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.status-active { background: var(--color-success-light); color: var(--color-primary-active); }
.status-draft { background: var(--color-warning-light); color: var(--color-warning); }
.error { text-align: center; padding: 40px; color: var(--color-text-secondary); }
.fk-empty { font-size: 12px; color: var(--color-text-secondary); font-style: italic; }
.fk-error { color: var(--color-danger, #dc2626); font-style: normal; }
</style>
