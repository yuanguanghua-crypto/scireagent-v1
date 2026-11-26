import { ref, computed } from 'vue'
import { http } from '@/api/http'

/**
 * 治理列表页统一取数口径（S4 / A-066 + A-014）。
 *
 * 解决三件事，三件都是**实测出来的缺陷**，不是设计偏好：
 *
 * 1) **草稿看不见**（A-066）
 *    Methods / Protocols 的后端 `get_queryset` 对 list 端点做了「方案 B」过滤
 *    （`views.py` 里的 `if self.action == 'list' and not include_unpublished(...)`），
 *    staff 默认也只看公开态；而 Applications / ResearchGoals **没做**这一步
 *    ⇒ 四个页面行为不一致，且屏幕上没有任何开关能翻过来。
 *    这里统一成：`showDrafts=false` ⇒ 只看公开态；`true` ⇒ 带 `include_unpublished=1`。
 *
 *    ★ 为什么关着的时候还要**显式**传 `status=<publicStatus>`：
 *      Methods/Protocols 靠后端默认就能挡住，但 Applications/ResearchGoals 挡不住
 *      （后端没有方案 B）⇒ 不显式传的话「开关关着也能看到草稿」，四页口径又分叉。
 *      显式传对前两者是**重复过滤（无害）**，对后两者才是唯一生效路径。
 *
 * 2) **静默截断**（A-014）
 *    原实现 `page_size` 硬编码 200/200/200/500，超出部分靠
 *    `ListTruncationHint` 写一句 "Showing first 200 of 28568 records"。
 *    那只是**把截断说出口**，用户没有任何手段翻到第 201 条。现改为真分页。
 *
 * 3) **搜索框完全没有**（A-014）
 *    四页 `el-input` 命中数为 0 ⇒ 2.8 万条应用只能靠肉眼在第 1 页里找。
 */
export function useEntityList({ url, publicStatus, pageSize = 50 }) {
  const rows = ref([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(true)
  const error = ref('')
  const search = ref('')
  // 默认关：保留 2026-10-26 方案 B 的默认口径（列表数字与首页统计对齐）
  const showDrafts = ref(false)
  const status = ref('')

  const totalPages = computed(() =>
    pageSize > 0 ? Math.max(1, Math.ceil(total.value / pageSize)) : 1)

  // 竞态守卫：搜索框逐字触发时会有多个请求在飞，先回的旧响应**不得**覆盖新结果。
  let seq = 0

  function buildParams() {
    const p = { page: page.value, page_size: pageSize }
    const term = search.value.trim()
    if (term) p.search = term
    if (showDrafts.value) {
      p.include_unpublished = 1
      if (status.value) p.status = status.value
    } else if (publicStatus) {
      p.status = publicStatus
    }
    return p
  }

  async function load() {
    const mine = ++seq
    loading.value = true
    error.value = ''
    try {
      const resp = await http.get(url, { params: buildParams() })
      if (mine !== seq) return
      rows.value = resp?.data?.results || resp?.data || []
      const count = resp?.meta?.pagination?.count
      total.value = typeof count === 'number' ? count : rows.value.length
      // 归一条目后当前页可能已越界（例如在末页点「归档」）—— 退到最后一页，
      // 不让用户对着空表以为数据被删光了。
      const last = Math.max(1, Math.ceil(total.value / pageSize))
      if (page.value > last) {
        page.value = last
        return load()
      }
    } catch (e) {
      if (mine !== seq) return
      rows.value = []
      total.value = 0
      error.value = 'Failed to load: '
        + (e?.response?.data?.meta?.error?.message || e?.message || 'unknown error')
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  /** 条件变了（搜索 / 开关 / 状态下拉）⇒ 必须回到第 1 页，否则会停在一个空页上。 */
  function reload() {
    page.value = 1
    return load()
  }

  function goPage(n) {
    page.value = n
    return load()
  }

  return {
    rows, total, page, pageSize, totalPages,
    loading, error, search, showDrafts, status,
    load, reload, goPage,
  }
}
