<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isInternal } from '@/utils/internalAccess'
import { http } from '@/api/http'
import { toast, LoadingSpinner, EmptyState, DataPagination } from '@/components/common'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { getApplications } from '@/api/applications'
import { useEntityList } from '@/composables/useEntityList'
import EntityListToolbar from './components/EntityListToolbar.vue'

const router = useRouter()
const auth = useAuthStore()
// ★ 内部人员判定收敛到 utils/internalAccess.js（口径= is_staff || role∈(procurement,admin)）
//   ——与后端 permissions.py IsProcurementOrAdmin 一致；普通注册用户仍被踢回首页。
if (!isInternal(auth)) { router.replace('/') }

// ★ 2026-11-18（S4 / A-066 + A-014）：列表取数统一走 useEntityList。
//   改前是 `http.get('/methods/', { params: { page_size: 200 } })` —— 没有搜索框、
//   没有分页、也没有「看草稿」的开关；而 MethodViewSet 的 list 端点对 staff 也套了
//   方案 B 过滤 ⇒ 本页 83 行、Dashboard 86，差的 3 条草稿在界面上无法触达。
//   `publicStatus='active'`：开关关着时**显式**传 status=active，使四页口径一致
//   （Applications / ResearchGoals 后端没做方案 B，不显式传就挡不住草稿）。
const {
  rows: entities, total: totalCount, page, pageSize, totalPages,
  loading, error, search, showDrafts, status,
  load, reload, goPage,
} = useEntityList({ url: '/methods/', publicStatus: 'active' })

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
const form = ref({ name: '', purpose: '', application_ids: [], status: 'draft' })
const applications = ref([])          // 远程搜索结果（≤50 条），不是全量枚举
const optionsLoading = ref(false)
const optionsError = ref('')
const editingAppCount = ref(0)
// ★ 2026-11-18（A-212）：归档入口。两次点击确认（无第三方依赖、不弹阻塞式 confirm）。
const pendingArchiveId = ref(null)
// ★ 2026-11-18（A-155）：后端同名返回 409 后，把「再点一次 Save 就照样建」的
//   逃生口打开（等价于 allow_duplicate=1）。没有这一步，A-155 只是从
//   「静默建副本」变成「永远建不了同名」，是拿一个 bug 换另一个。
const allowDuplicate = ref(false)
const overlay = ref(null)
const dialogAttrs = useDialogA11y(showEditor, overlay, {
  titleId: 'entity-editor-title',
  close: () => { showEditor.value = false },
})

onMounted(() => {
  loadList()
  // ★ 2026-11-18（A-063）：预载一次选项。
  //   改前只有 loadList()，选项在 openNew() 里 fire-and-forget ⇒ 对话框必定先
  //   以「disabled + No Application available」渲染一个 RTT，用户看到的就是
  //   「选择器被禁用」（这正是 QA A-063 的观测；PDF 里"编辑表单同一选择器正常"
  //   只是因为它是在前一次请求已回填之后才被打开）。
  searchApplications('')
})

/** 刷新当前页（保留页码与筛选），并清掉行内「Confirm archive」的待确认态。 */
async function loadList() {
  pendingArchiveId.value = null
  return load()
}

/** 远程搜索应用（2.8 万条，「前 200 条枚举」在这个量级上没有意义）。 */
async function searchApplications(query) {
  optionsLoading.value = true
  optionsError.value = ''
  try {
    const resp = await getApplications({
      search: query || '',
      page_size: 50,
      // 管理端要能挂到草稿应用上，故显式放开未发布过滤
      include_unpublished: 1,
    })
    applications.value = (resp.data?.results || resp.data || [])
  } catch (e) {
    applications.value = []
    // ★ 改前这里是 `catch { /* ignore */ }` —— 请求失败与"真的没有应用"在界面上
    //   完全同形，用户只会看到禁用选择器。现在必须说清楚。
    optionsError.value = '应用列表加载失败：' + (e.response?.data?.meta?.error?.message || e.message)
  } finally {
    optionsLoading.value = false
  }
}

async function openNew() {
  editing.value = null
  editingAppCount.value = 0
  form.value = { name: '', purpose: '', application_ids: [], status: 'draft' }
  allowDuplicate.value = false
  showEditor.value = true
  await searchApplications('')
}

async function openEdit(e) {
  editing.value = e
  editingAppCount.value = e.applications_count || 0
  // ★ 2026-09-24 修「Purpose 死字段」：**列表接口不返回 `purpose`**（只在 Detail 里），
  //   故必须拉详情预填 —— 否则输入框恒空（研究员以为该字段没内容），
  //   且保存时填进去的值会被 DRF 静默忽略（写路径已改为走 Detail，见 MethodViewSet）。
  //   写法与 ProtocolsPage.openEdit 拉详情预填 methods 一致。
  let purpose = e.purpose || ''
  try {
    const resp = await http.get(`/methods/${e.id}/`)
    const data = resp.data?.data || resp.data || {}
    purpose = data.purpose || ''
    if (typeof data.applications_count === 'number') editingAppCount.value = data.applications_count
  } catch { /* 拉取失败则留空，不影响编辑其它字段 */ }
  // ★ 2026-11-18（A-063）：应用关联**只追加不替换**（后端 MethodApplicationWriteMixin），
  //   所以编辑态这里刻意留空 —— 若回填全量再整体 PUT，会把 1,346 条关联删到只剩勾选的几条。
  form.value = { name: e.name || '', purpose, application_ids: [], status: e.status || 'draft' }
  allowDuplicate.value = false
  showEditor.value = true
  await searchApplications('')
}

async function save() {
  saving.value = true
  try {
    const payload = { name: form.value.name, purpose: form.value.purpose, status: form.value.status }
    if (form.value.application_ids?.length) {
      payload.application_ids = [...form.value.application_ids]
    }
    const config = allowDuplicate.value ? { params: { allow_duplicate: 1 } } : undefined
    if (editing.value) {
      await http.put(`/methods/${editing.value.id}/`, payload, config)
    } else {
      await http.post('/methods/', payload, config)
    }
    showEditor.value = false
    allowDuplicate.value = false
    const wasEditing = !!editing.value
    // 新建 ⇒ 回第 1 页（新记录按后端 ordering 落在前面）；
    // 编辑 ⇒ 留在当前页，别把人从第 5 页踢回第 1 页。
    await (wasEditing ? loadList() : reload())
    // ★ A-066 的连带体验：草稿默认被 Show drafts 挡住，存完不提示的话
    //   用户会以为「没建成」（正是 QA 观测到的「保存后列表里没有」）。
    if (!showDrafts.value && form.value.status !== 'active') {
      toast.success(`已保存「${form.value.name}」· 当前为 ${form.value.status}，勾选 Show drafts 可见`)
    } else {
      toast.success(`${wasEditing ? '已保存' : '已创建'}「${form.value.name}」`)
    }
  } catch (e) {
    // ★ A-155：同名冲突现在返回 409（改前一模一样地建副本、无任何提示）
    if (e.response?.status === 409) {
      allowDuplicate.value = true
      const msg = e.response?.data?.meta?.error?.message || '已存在同名方法'
      toast.warning(`${msg} —— 再点一次 Save 就会照样新建。`)
      return
    }
    toast.error('Save failed: ' + (e.response?.data?.meta?.error?.message || e.message))
  } finally {
    saving.value = false
  }
}

/**
 * ★ 2026-11-18（A-212）：知识实体原来**没有任何删除/归档入口**（五个页面 grep
 * `delete|archive` 命中数全为 0）。但模型层四类实体早就有 `archived` 状态、
 * 后端 `status` 也可写 ⇒ 缺的只是 UI。这里做**归档**而不是硬删除：
 * 方法可能被协议/产品/订单文档引用，硬删会连着弄坏引用方。
 *
 * 两次点击确认：第一次把按钮变成 "Confirm archive"，第二次才发请求。
 */
async function archiveRow(e) {
  if (pendingArchiveId.value !== e.id) {
    pendingArchiveId.value = e.id
    return
  }
  pendingArchiveId.value = null
  try {
    await http.patch(`/methods/${e.id}/`, { status: 'archived' })
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
      <h2>Methods</h2>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New Method</button>
    </div>

    <EntityListToolbar
      v-model:search="search"
      v-model:showDrafts="showDrafts"
      v-model:status="status"
      :status-options="STATUS_OPTIONS"
      placeholder="Search methods…"
      :loading="loading"
      @submit="reload"
    />

    <LoadingSpinner v-if="loading" text="Loading..." />
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="entities.length" class="entity-table">
      <thead><tr><th>ID</th><th>Name</th><th>Purpose</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="e in entities" :key="e.id">
          <td>{{ e.id }}</td>
          <td class="col-name">{{ e.name }}</td>
          <td class="col-summary">{{ (e.purpose || '').slice(0, 120) }}</td>
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
    <EmptyState v-else title="No methods yet" icon="Tools" />

    <DataPagination
      v-if="totalPages > 1"
      :current-page="page"
      :page-size="pageSize"
      :total="totalCount"
      layout="total, prev, pager, next"
      @update:current-page="goPage"
    />

    <div v-if="showEditor" ref="overlay" class="dialog-overlay" v-bind="dialogAttrs" @click.self="showEditor = false">
      <div class="dialog">
        <h3 id="entity-editor-title">{{ editing ? 'Edit' : 'New' }} Method</h3>
        <label>Name <input v-model="form.name" class="input-full" /></label>
        <label>Status
          <!-- ★ 2026-11-18（A-261）：后端 `status` 在 fields 里且未只读 ⇒ 早就能改，
               只是管理端从来没有这个入口，草稿方法无从转 active。 -->
          <select v-model="form.status" class="input-full">
            <option value="draft">draft</option>
            <option value="active">active</option>
            <option value="deprecated">deprecated</option>
            <option value="archived">archived</option>
          </select>
        </label>
        <label>Purpose <textarea v-model="form.purpose" rows="3" class="input-full"></textarea></label>
        <label>Application
          <el-select
            v-model="form.application_ids"
            multiple collapse-tags collapse-tags-tooltip
            filterable remote reserve-keyword
            :remote-method="searchApplications"
            :loading="optionsLoading"
            placeholder="Search applications"
            clearable style="width: 100%"
          >
            <el-option v-for="a in applications" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
          <span v-if="optionsLoading" class="fk-empty">Loading applications…</span>
          <span v-else-if="optionsError" class="fk-empty fk-error">{{ optionsError }}</span>
          <span v-else-if="editing && editingAppCount" class="fk-empty">
            已关联 {{ editingAppCount }} 个应用；此处只追加，不会删除已有
          </span>
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
