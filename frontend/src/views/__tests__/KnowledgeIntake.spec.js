/**
 * `KnowledgeIntake` 三组选项：硬编码常量 → 远程搜索 + 可新建 —— A-075 / A-218（2026-11-18 / S4）。
 *
 * ## 缺陷
 * `GOAL_OPTIONS`(8) / `APP_OPTIONS`(12) / `METHOD_OPTIONS`(11) 是写死的字符串数组，
 * 与库里 11,047 Goal / 28,568 Application / 88 Method 完全脱钩 ——
 * **任何新建的实体永远进不去这个页面**。
 *
 * ## 本测试同时钉住一个"容易被顺手改掉"的能力
 * 常量表虽然荒谬，但它隐含保留了「可以录入库里还没有的名字」这条路
 * （后端按 name `get_or_create`，这是研究员录新知识的主路径）。
 * 若只换成"从库里搜索并选择"，该能力会**静默消失**且不报错。
 * 所以这里显式断言「＋ Create “…”」入口与其结果。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const httpMock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/utils/http', () => ({
  default: httpMock,
  extractErrorMessage: (d, fallback) => fallback,
}))
vi.mock('@/composables/useConfirm', () => ({ useConfirm: () => ({ ask: vi.fn() }) }))
// 该页是路由内的组件（`useRoute`/`useRouter`）；这里不需要真路由，避免注入告警刷屏
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ query: {}, params: {} }),
    useRouter: () => ({ push: vi.fn() }),
  }
})

import KnowledgeIntake from '../KnowledgeIntake.vue'

const PRODUCT = {
  id: 5454, catalog_no: 'C5454', name: 'Cy5 NHS Ester', cas: '146368-11-8',
  category_l1: 'Dyes', product_class_id: 12,
}

const RESP = {
  '/research-goals/': ['RNA Analysis', 'DNA Sequencing'],
  '/applications/': ['RNA Imaging', 'FISH'],
  '/methods/': ['CuAAC Click Chemistry', 'In Vitro Transcription'],
}

function listResp(names, count) {
  return {
    success: true,
    data: names.map((n, i) => ({ id: i + 1, name: n })),
    meta: { pagination: { count: count ?? names.length } },
  }
}

function defaultGet(url, cfg) {
  if (url === '/products/') return Promise.resolve({ success: true, data: [PRODUCT] })
  const q = (cfg?.params?.search || '').toLowerCase()
  const base = RESP[url] || []
  const hits = q ? base.filter((n) => n.toLowerCase().includes(q)) : base
  return Promise.resolve(listResp(hits))
}

async function mountPage() {
  const w = mount(KnowledgeIntake)
  await flushPromises()
  // 选中产品 ⇒ 右侧表单出现
  await w.find('.ki-product-item').trigger('click')
  await flushPromises()
  return w
}

const search = (w, g) => w.find(`[data-testid="ki-${g}-search"]`)
const createBtn = (w, g) => w.find(`[data-testid="ki-${g}-create"]`)
const sectionEl = (w, g) => w.find(`[data-testid="ki-${g}-section"]`)
const chipTexts = (w, g) =>
  sectionEl(w, g).findAll('.ki-chip').map((c) => c.text())

/** 走完一次 debounce（250ms）并结算请求 */
async function settle(w) {
  vi.advanceTimersByTime(400)
  await flushPromises()
}

describe('KnowledgeIntake 选项来源（A-075 / A-218）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })
    httpMock.get.mockImplementation(defaultGet)
    httpMock.post.mockResolvedValue({ success: true, data: { warnings: [] } })
  })
  afterEach(() => { vi.useRealTimers() })

  it('首屏三个分区各自从服务端拉默认候选（不再来自硬编码常量）', async () => {
    const w = await mountPage()

    const urls = httpMock.get.mock.calls.map((c) => c[0])
    expect(urls, '★ 没有请求 /research-goals/ ⇒ 仍可能来自硬编码')
      .toContain('/research-goals/')
    expect(urls).toContain('/applications/')
    expect(urls).toContain('/methods/')

    expect(chipTexts(w, 'goal')).toEqual(RESP['/research-goals/'])
    expect(chipTexts(w, 'app')).toEqual(RESP['/applications/'])
    expect(chipTexts(w, 'method')).toEqual(RESP['/methods/'])
    w.unmount()
  })

  it('候选来自库，名字不必在旧常量表里（这正是缺陷本体）', async () => {
    httpMock.get.mockImplementation((url, cfg) => {
      if (url === '/products/') return Promise.resolve({ success: true, data: [PRODUCT] })
      if (url === '/research-goals/') {
        return Promise.resolve(listResp(['Lipid Nanoparticle Delivery']))
      }
      return defaultGet(url, cfg)
    })
    const w = await mountPage()
    expect(chipTexts(w, 'goal'), '★ 库里新增的目标没能进到这个页面').toContain(
      'Lipid Nanoparticle Delivery',
    )
    w.unmount()
  })

  it('输入即服务端搜索（methods 带 include_unpublished=1，能看到草稿）', async () => {
    const w = await mountPage()
    httpMock.get.mockClear()

    await search(w, 'method').setValue('CuAAC')
    await settle(w)

    const call = httpMock.get.mock.calls.find((c) => c[0] === '/methods/')
    expect(call, '★ 输入没有触发服务端搜索').toBeTruthy()
    expect(call[1].params.search).toBe('CuAAC')
    expect(call[1].params.include_unpublished, '★ 草稿方法会搜不到').toBe(1)
    expect(call[1].params.page_size).toBe(30)
    w.unmount()
  })

  it('点 chip 选中 / 再点取消', async () => {
    const w = await mountPage()
    const chip = () => sectionEl(w, 'goal').findAll('.ki-chip')[0]

    await chip().trigger('click')
    expect(chip().classes()).toContain('ki-chip-active')
    await chip().trigger('click')
    expect(chip().classes()).not.toContain('ki-chip-active')
    w.unmount()
  })

  it('★ 已选中的名字在搜索后仍留在列表里（否则搜一次就再也取消不掉）', async () => {
    const w = await mountPage()
    await sectionEl(w, 'goal').findAll('.ki-chip')[0].trigger('click')   // 选中 RNA Analysis

    // 搜一个不含已选项的词 ⇒ 服务端只回 DNA Sequencing
    await search(w, 'goal').setValue('DNA')
    await settle(w)

    const texts = chipTexts(w, 'goal')
    expect(texts, '已选但不在结果里的名字消失了').toContain('RNA Analysis')
    expect(texts).toContain('DNA Sequencing')
    const rna = sectionEl(w, 'goal').findAll('.ki-chip').find((c) => c.text() === 'RNA Analysis')
    expect(rna.classes(), '已选项必须保持 active 才能取消').toContain('ki-chip-active')
    w.unmount()
  })

  it('★ 输入库里没有的名字 ⇒ 出现 Create 入口，点击后作为新实体进入表单', async () => {
    const w = await mountPage()
    httpMock.get.mockImplementation((url, cfg) => {
      if (url === '/products/') return Promise.resolve({ success: true, data: [PRODUCT] })
      if (url === '/methods/' && cfg?.params?.search) return Promise.resolve(listResp([]))
      return defaultGet(url, cfg)
    })

    expect(createBtn(w, 'method').exists(), '还没输入就出现了 Create 入口').toBe(false)

    await search(w, 'method').setValue('E2E Brand New Method')
    await settle(w)

    expect(createBtn(w, 'method').exists(), '★ 库里没有的名字无法录入 —— 丢了"录新实体"能力')
      .toBe(true)
    expect(createBtn(w, 'method').text()).toContain('E2E Brand New Method')

    await createBtn(w, 'method').trigger('click')
    await flushPromises()

    expect(chipTexts(w, 'method'), '新建的名字没有进入 chip 列表').toContain('E2E Brand New Method')
    const created = sectionEl(w, 'method').findAll('.ki-chip').find((c) => c.text() === 'E2E Brand New Method')
    expect(created.classes(), '新建后应自动选中').toContain('ki-chip-active')
    w.unmount()
  })

  it('输入与已有候选同名（仅大小写不同）⇒ 不提供 Create，避免造出大小写变体', async () => {
    const w = await mountPage()
    httpMock.get.mockImplementation((url, cfg) => {
      if (url === '/products/') return Promise.resolve({ success: true, data: [PRODUCT] })
      if (url === '/research-goals/' && cfg?.params?.search) {
        return Promise.resolve(listResp(['RNA Analysis']))
      }
      return defaultGet(url, cfg)
    })

    await search(w, 'goal').setValue('rna analysis')
    await settle(w)

    expect(createBtn(w, 'goal').exists()).toBe(false)
    w.unmount()
  })

  it('命中数超过返回条数时提示"只是前 N 条"（同 A-206 的截断静默问题）', async () => {
    httpMock.get.mockImplementation((url, cfg) => {
      if (url === '/products/') return Promise.resolve({ success: true, data: [PRODUCT] })
      if (url === '/applications/') return Promise.resolve(listResp(['RNA Imaging'], 4200))
      return defaultGet(url, cfg)
    })
    const w = await mountPage()

    const hint = w.find('[data-testid="ki-app-truncated"]')
    expect(hint.exists(), '★ 只给了 1 条却不说共有 4200 条 —— 用户以为库里就这么多').toBe(true)
    expect(hint.text()).toContain('4200')
    w.unmount()
  })

  it('保存时三组提交的是**名字数组**（后端按 name get_or_create）', async () => {
    const w = await mountPage()
    await sectionEl(w, 'goal').findAll('.ki-chip')[0].trigger('click')
    await sectionEl(w, 'app').findAll('.ki-chip')[1].trigger('click')

    await w.find('form.ki-form').trigger('submit')
    await flushPromises()

    const body = httpMock.post.mock.calls[0][1]
    expect(body.product_id).toBe(PRODUCT.id)
    expect(body.research_goals).toEqual(['RNA Analysis'])
    expect(body.applications).toEqual(['FISH'])
    w.unmount()
  })
})
