/**
 * `useEntityList` 单测 —— 治理列表页的统一取数口径（S4 / A-066 + A-014）。
 *
 * ## 为什么值得测
 * 这个 composable 的**参数翻译**就是 A-066 的全部语义：`showDrafts` 关着时
 * 到底传不传 `include_unpublished`、要不要**显式**补 `status=<公开态>`。
 * 写错任何一个组合，结果不是报错，而是**静默返回多一倍的草稿**（或一条都不返回）——
 * 界面上看起来完全正常，只有对着数字才会发现。E2E 能验当前数据，但换一份数据集
 * （比如草稿数为 0 的库）就分不清"过滤生效"和"恰好没有草稿"。所以在这里钉死。
 *
 * ★ 四条组合是**互相排斥**的，别"统一一下"：
 *   showDrafts=false            → status=publicStatus（**必须显式**，见下）
 *   showDrafts=true  无 status  → include_unpublished=1
 *   showDrafts=true  有 status  → include_unpublished=1 & status=…
 *   publicStatus=null（Reference 页未改造）→ 什么都不传
 *
 * ## 关于「为什么关着也要显式传 status」
 * Methods / Protocols 的后端 list 端点有「方案 B」过滤，不带 include_unpublished 就
 * 自动只给公开态；但 Applications / ResearchGoals **没有**这一步
 * （`apply_public_visibility` 对 staff 不过滤 status）⇒ 不显式传的话，staff 在
 * 「Show drafts 关」的状态下看到的仍是含 draft/archived 的全量，四页口径就分叉了。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/api/http', () => ({
  http: { get: vi.fn() },
}))

const { http } = await import('@/api/http')
const { useEntityList } = await import('../useEntityList')

/** 造一个信封形状的响应（`core/renderers.py`：分页列表 → data 是数组、count 在 meta） */
function envelope(rows, count) {
  return {
    success: true,
    data: rows,
    meta: { pagination: { count, next: null, previous: null } },
  }
}

/** 取最近一次 `http.get` 的 (url, config) */
const lastCall = () => http.get.mock.calls[http.get.mock.calls.length - 1]
const lastParams = () => lastCall()[1].params

beforeEach(() => {
  http.get.mockReset()
  http.get.mockResolvedValue(envelope([{ id: 1, name: 'x' }], 1))
})

describe('useEntityList：翻页与取数', () => {
  it('默认第 1 页、每页 50，并把 page/page_size 传下去', async () => {
    const { load, page, pageSize } = useEntityList({ url: '/methods/', publicStatus: 'active' })
    expect(page.value).toBe(1)
    expect(pageSize).toBe(50)
    await load()
    expect(lastCall()[0]).toBe('/methods/')
    expect(lastParams()).toMatchObject({ page: 1, page_size: 50 })
  })

  it('从信封 meta.pagination.count 读总数（不是 data.length）', async () => {
    http.get.mockResolvedValue(envelope([{ id: 1 }], 83))
    const { load, total, rows } = useEntityList({ url: '/methods/', publicStatus: 'active' })
    await load()
    expect(rows.value).toHaveLength(1)
    expect(total.value).toBe(83)
  })

  it('totalPages 按 pageSize 向上取整，且至少为 1', async () => {
    const { totalPages, total } = useEntityList({ url: '/x/', publicStatus: 'active' })
    expect(total.value).toBe(0)
    expect(totalPages.value).toBe(1) // 0 条也算 1 页，避免页面上出现 "1 / 0"
    total.value = 101
    expect(totalPages.value).toBe(3)
  })

  it('goPage 换页后保留搜索与开关条件', async () => {
    http.get.mockResolvedValue(envelope([], 480))
    const { load, goPage, search, showDrafts, page } = useEntityList({
      url: '/applications/', publicStatus: 'active',
    })
    search.value = 'kinase'
    showDrafts.value = true
    await load()
    await goPage(4)
    expect(page.value).toBe(4)
    expect(lastParams()).toMatchObject({ page: 4, search: 'kinase', include_unpublished: 1 })
  })

  it('reload 把页码重置回第 1 页（改条件后不能停在空页上）', async () => {
    http.get.mockResolvedValue(envelope([], 480))
    const { load, goPage, reload } = useEntityList({ url: '/x/', publicStatus: 'active' })
    await load()
    await goPage(7)
    expect(lastParams().page).toBe(7)
    await reload()
    expect(lastParams().page).toBe(1)
  })

  it('当前页越界时自动退到最后一页（末页归档最后一条的场景）', async () => {
    // 第 3 页有 1 条；再请求时后端说只剩 101 条 ⇒ 最后一页应为 3
    http.get.mockResolvedValue(envelope([], 101))
    const { load, goPage, page } = useEntityList({ url: '/x/', publicStatus: 'active' })
    await goPage(9)
    // 9 > ceil(101/50)=3 ⇒ load 内部会修正页码并重取
    expect(page.value).toBe(3)
    expect(lastParams().page).toBe(3)
  })
})

describe('useEntityList：showDrafts 的四种参数组合（A-066 的核心语义）', () => {
  it('关着 ⇒ 只播 status=<publicStatus>，**不带** include_unpublished', async () => {
    const { load } = useEntityList({ url: '/methods/', publicStatus: 'active' })
    await load()
    const p = lastParams()
    expect(p.status).toBe('active')
    expect(p).not.toHaveProperty('include_unpublished')
  })

  it('Protocol 的公开态是 published 而不是 active（用错会筛出空表）', async () => {
    const { load } = useEntityList({ url: '/protocols/', publicStatus: 'published' })
    await load()
    expect(lastParams().status).toBe('published')
  })

  it('开着且没选状态 ⇒ 只带 include_unpublished=1，不夹带 status', async () => {
    const { load, showDrafts } = useEntityList({ url: '/methods/', publicStatus: 'active' })
    showDrafts.value = true
    await load()
    const p = lastParams()
    expect(p.include_unpublished).toBe(1)
    expect(p).not.toHaveProperty('status')
  })

  it('开着且选了状态 ⇒ 两者同时带（缺 include_unpublished 会被方案 B 先筛成空）', async () => {
    const { load, showDrafts, status } = useEntityList({ url: '/methods/', publicStatus: 'active' })
    showDrafts.value = true
    status.value = 'draft'
    await load()
    expect(lastParams()).toMatchObject({ include_unpublished: 1, status: 'draft' })
  })

  it('publicStatus 为 null（Reference 页未改造）⇒ 两个参数都不传', async () => {
    const { load } = useEntityList({ url: '/references/' })
    await load()
    const p = lastParams()
    expect(p).not.toHaveProperty('status')
    expect(p).not.toHaveProperty('include_unpublished')
  })
})

describe('useEntityList：搜索与错误', () => {
  it('搜索词为空/纯空格时不传 search（空 search 会改变后端的过滤分支）', async () => {
    const { load, search } = useEntityList({ url: '/x/', publicStatus: 'active' })
    search.value = '   '
    await load()
    expect(lastParams()).not.toHaveProperty('search')
  })

  it('搜索词两侧空格被裁掉再传', async () => {
    const { load, search } = useEntityList({ url: '/x/', publicStatus: 'active' })
    search.value = '  CuAAC  '
    await load()
    expect(lastParams().search).toBe('CuAAC')
  })

  it('请求失败 ⇒ error 带后端文案且不留半截 rows', async () => {
    http.get.mockRejectedValue({
      response: { data: { meta: { error: { message: 'boom' } } } },
    })
    const { load, error, rows, total } = useEntityList({ url: '/x/', publicStatus: 'active' })
    await load()
    expect(error.value).toContain('boom')
    expect(rows.value).toHaveLength(0)
    expect(total.value).toBe(0)
  })
})

describe('useEntityList：竞态守卫', () => {
  it('先发的旧请求晚回 ⇒ 不得覆盖后发的新结果', async () => {
    let resolveOld
    http.get
      .mockImplementationOnce(() => new Promise((r) => { resolveOld = r })) // 第 1 次：挂住
      .mockResolvedValueOnce(envelope([{ id: 2, name: 'new' }], 1))        // 第 2 次：立即返回

    const { load, search, rows } = useEntityList({ url: '/x/', publicStatus: 'active' })
    const p1 = load()                      // 旧请求（search 为空）
    search.value = 'new'
    await load()                           // 新请求先完成
    expect(rows.value[0].name).toBe('new')

    resolveOld(envelope([{ id: 1, name: 'old' }], 1))  // 旧请求现在才回
    await p1
    expect(rows.value[0].name).toBe('new') // 仍是新结果
  })
})
