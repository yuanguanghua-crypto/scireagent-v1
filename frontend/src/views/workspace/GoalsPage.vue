<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isInternal } from '@/utils/internalAccess'
import { http } from '@/api/http'
import { toast, LoadingSpinner, EmptyState, DataPagination } from '@/components/common'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { useEntityList } from '@/composables/useEntityList'
import EntityListToolbar from './components/EntityListToolbar.vue'

const router = useRouter()
const auth = useAuthStore()
// ★ 内部人员判定收敛到 utils/internalAccess.js（口径= is_staff || role∈(procurement,admin)）
//   ——与后端 permissions.py IsProcurementOrAdmin 一致；普通注册用户仍被踢回首页。
if (!isInternal(auth)) { router.replace('/') }

const entityType = 'goals'
// ★ 2026-11-18（S4 / A-066 + A-014）：列表取数统一走 useEntityList。
//   改前 `page_size: 200` ⇒ 生产 11,047 个目标只渲染 200 行且无翻页、无搜索框。
//   `publicStatus='active'`：ResearchGoalViewSet 同样**没做方案 B 过滤**，
//   不显式传 status 时 staff 看到的是含 draft/archived 的全量。
//   ⚠️ 该端点原先**没有 filterset**（`filterset_fields` 缺失）⇒ `?status=` 被静默忽略。
//   本次已在 `ResearchGoalViewSet` 补上 `filterset_fields = ['status']`（纯新增，见后端注释）。
const {
  rows: entities, total: totalCount, page, pageSize, totalPages,
  loading, error, search, showDrafts, status,
  load, reload, goPage,
} = useEntityList({ url: '/research-goals/', publicStatus: 'active' })

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'active' },
  { value: 'draft', label: 'draft' },
  { value: 'deprecated', label: 'deprecated' },
  { value: 'archived', label: 'archived' },
]

const showEditor = ref(false)
const editing = ref(null)
const saving = ref(false)

const form = ref({ name: '', summary: '', protocols: [] })
const protocolOptions = ref([])
const protocolSearching = ref(false)
// ★ 2026-11-18（A-212）：归档入口（两次点击确认）
const pendingArchiveId = ref(null)
// ★ 2026-11-18（A-155）：409 后允许「再点一次 Save 就照样建」（= allow_duplicate=1）
const allowDuplicate = ref(false)
const overlay = ref(null)
const dialogAttrs = useDialogA11y(showEditor, overlay, {
  titleId: 'entity-editor-title',
  close: () => { showEditor.value = false },
})

onMounted(loadList)

/** 刷新当前页（保留页码与筛选），并清掉行内「Confirm archive」的待确认态。 */
async function loadList() {
  pendingArchiveId.value = null
  return load()
}

function openNew() {
  editing.value = null
  form.value = { name: '', summary: '', protocols: [] }
  allowDuplicate.value = false
  protocolOptions.value = []
  showEditor.value = true
}

async function openEdit(e) {
  editing.value = e
  let protocols = []
  let options = []
  try {
    const detail = await http.get(`/research-goals/${e.id}/`)
    const cur = (detail.data?.protocols || [])
    protocols = cur.map(p => p.id)
    options = cur.map(p => ({ value: p.id, label: p.name }))
  } catch { /* 详情取不到则回退为空，仍可保存其它字段 */ }
  form.value = { name: e.name || '', summary: e.summary || '', protocols }
  allowDuplicate.value = false
  protocolOptions.value = options
  showEditor.value = true
}

async function searchProtocols(query) {
  protocolSearching.value = true
  try {
    const resp = await http.get('/protocols/', {
      params: {
        search: query || '',
        page_size: 50,
        // ★ 2026-11-18（A-061）：后端列表端点对 staff 也默认只给 published（方案 B），
        //   而这里在**策展**目标要挂哪些协议 —— 管理动作必须能看到草稿，
        //   否则刚建好的草稿协议永远搜不到（QA 用 14243 复现的正是这一条）。
        include_unpublished: 1,
      },
    })
    const list = (resp.data?.results || resp.data || [])
    protocolOptions.value = list.map(p => ({ value: p.id, label: p.name }))
  } catch { /* ignore */ }
  finally {
    protocolSearching.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const config = allowDuplicate.value ? { params: { allow_duplicate: 1 } } : undefined
    if (editing.value) {
      await http.put(`/research-goals/${editing.value.id}/`, form.value, config)
    } else {
      await http.post('/research-goals/', form.value, config)
    }
    showEditor.value = false
    allowDuplicate.value = false
    const wasEditing = !!editing.value
    // 新建 ⇒ 回第 1 页（ResearchGoal 按 priority 排序）；编辑 ⇒ 留在当前页
    await (wasEditing ? loadList() : reload())
    // ★ 本页表单没有 status 字段，新建的 ResearchGoal 由 StatusMixin 默认成 draft
    toast.success(`${wasEditing ? '已保存' : '已创建'}「${form.value.name}」`
      + (wasEditing || showDrafts.value ? '' : ' · 新记录默认是 draft，勾选 Show drafts 可见'))
  } catch (e) {
    // ★ A-155：同名冲突改由后端 409 显式拒绝（改前一模一样地建副本）
    if (e.response?.status === 409) {
      allowDuplicate.value = true
      const msg = e.response?.data?.meta?.error?.message || '已存在同名目标'
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
    await http.patch(`/research-goals/${e.id}/`, { status: 'archived' })
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
      <h2>Research Goals</h2>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New Goal</button>
    </div>

    <EntityListToolbar
      v-model:search="search"
      v-model:showDrafts="showDrafts"
      v-model:status="status"
      :status-options="STATUS_OPTIONS"
      placeholder="Search research goals…"
      :loading="loading"
      @submit="reload"
    />

    <LoadingSpinner v-if="loading" text="Loading..." />
    <div v-else-if="error" class="error">{{ error }}</div>

    <table v-else-if="entities.length" class="entity-table">
      <thead>
        <tr><th>ID</th><th>Name</th><th>Summary</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="e in entities" :key="e.id">
          <td>{{ e.id }}</td>
          <td class="col-name">{{ e.name }}</td>
          <td class="col-summary">{{ (e.summary || '').slice(0, 120) }}</td>
          <td><span class="status-tag" :class="`status-${e.status}`">{{ e.status || '—' }}</span></td>
          <td>
            <button class="btn btn-ghost btn-sm" @click="openEdit(e)">Edit</button>
            <button class="btn btn-ghost btn-sm btn-danger" @click="archiveRow(e)">
              {{ pendingArchiveId === e.id ? 'Confirm archive' : 'Archive' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <EmptyState v-else title="No goals yet" icon="Flag" />

    <DataPagination
      v-if="totalPages > 1"
      :current-page="page"
      :page-size="pageSize"
      :total="totalCount"
      layout="total, prev, pager, next"
      @update:current-page="goPage"
    />

    <!-- Editor dialog -->
    <div v-if="showEditor" ref="overlay" class="dialog-overlay" v-bind="dialogAttrs" @click.self="showEditor = false">
      <div class="dialog">
        <h3 id="entity-editor-title">{{ editing ? 'Edit' : 'New' }} Research Goal</h3>
        <label>Name <input v-model="form.name" class="input-full" /></label>
        <label>Summary <textarea v-model="form.summary" rows="4" class="input-full"></textarea></label>
        <label>Curated Protocols
          <!-- ★ 2026-11-18（S4 连带，实测出来的真缺陷）：补 `collapse-tags`。
               改前这里是裸 `multiple` —— 每个已选协议渲染成一个 tag。生产数据里
               `RNA Analysis` 一个目标就挂了**几百条**协议，编辑它时这些 tag 全部
               铺开，把 `.dialog` 撑到 **15,261px** 高、Cancel/Save 跑到 y=7938
               （视口只有 720px 高）⇒ 用户根本点不到按钮，只能按 Esc。
               实测证据：Playwright 在该对话框上点 Cancel 恒报 "element is not stable"，
               探针打印 `dialogBox={x:420,y:-7271,h:15261}`、`cancelBox={x:701,y:7938}`。
               MethodsPage / ProtocolsPage 的同款选择器早就带了这两个属性，唯独本页漏了。 -->
          <el-select
            v-model="form.protocols"
            multiple collapse-tags collapse-tags-tooltip
            filterable remote
            :remote-method="searchProtocols"
            :loading="protocolSearching"
            placeholder="Search protocols to curate"
            class="input-full"
          >
            <el-option v-for="opt in protocolOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
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
</style>
