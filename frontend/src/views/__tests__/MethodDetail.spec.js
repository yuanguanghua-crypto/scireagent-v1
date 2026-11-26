/**
 * `MethodDetail` 未审 AI 初稿的对外可见性 —— A-116（2026-11-18 / S4，拍板 ①(b)）。
 *
 * ## 决策链（两轮口径，必须一起看）
 * · 2026-10-30：**有意披露** —— AI 生成的描述必须标注 "AI-generated draft · pending
 *   expert review"，不能让客户把未审初稿当定论。QA 把这条标注本身当成缺陷报了（A-116）。
 * · 2026-11-18 拍板 ①(b)：**升级为不展示内容本身**。给未审内容加个标注，仍然是
 *   "对外发布了未审内容"；不审的不对外更干净。staff 照常看全部内容 + 标注。
 *
 * ## 两组字段为什么必须分开判
 * `description_status` 管 summary + purpose；`specs_status` 管 advantages /
 * limitations / timeline。两批内容由不同证据、不同批次生成，各自有时间戳 ——
 * 专家可能确认了描述却没看四字段。合并成一个开关会让未审规格以「已审」面貌出现。
 *
 * ## ⚠️ 本测试只覆盖**渲染层**
 * 这不是数据闸门：API 仍会把字段返回给非 staff（改后端会影响列表/工作台多处）。
 * 残留缺口记录在 A-116 的汇报里，不在此处假装已封堵。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const state = vi.hoisted(() => ({ method: null, isStaff: false }))

vi.mock('@/stores/methods', () => ({
  useMethodsStore: () => ({
    get currentMethod() { return state.method },
    loading: false,
    fetchMethod: vi.fn().mockResolvedValue(undefined),
    clearCurrent: vi.fn(),
  }),
}))
vi.mock('@/stores/researchPath', () => ({
  useResearchPathStore: () => ({ addStep: vi.fn() }),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ get isStaff() { return state.isStaff } }),
}))
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ params: { id: '1' } }),
    useRouter: () => ({ push: vi.fn() }),
  }
})

import MethodDetail from '../MethodDetail.vue'

const STUBS = {
  ContextCards: true,
  ResearchPathCard: true,
  UnifiedCTA: true,
  ResearchBreadcrumb: true,
  ResearchPathChips: true,
  ExpandableSection: true,
  // 页面里用到 <router-link>；不 stub 会刷 "Failed to resolve component" 告警
  RouterLink: true,
}

const BASE = {
  id: 1, name: 'CuAAC RNA Labeling', slug: 'cuaac-rna-labeling', status: 'active',
  summary: 'Copper-catalysed azide-alkyne cycloaddition for RNA labelling.',
  purpose: 'Attach a fluorophore to RNA.',
  advantages: 'Fast; Specific',
  limitations: 'Copper toxicity',
  cost_band: '',
  timeline: '2h',
  is_step_tag: false,
  protocols: [],
  applications_count: 1,
}

async function mountWith(overrides) {
  state.method = { ...BASE, ...overrides }
  const w = mount(MethodDetail, { global: { stubs: STUBS } })
  await flushPromises()
  return w
}

describe('MethodDetail 未审 AI 初稿可见性（A-116）', () => {
  beforeEach(() => { state.isStaff = false })

  it('非 staff + 描述未审 ⇒ summary / purpose 不渲染，且没有"AI 草稿"标注', async () => {
    const w = await mountWith({ description_status: 'ai_draft' })

    expect(w.find('.detail-summary').exists(), '★ 未审描述仍对外渲染').toBe(false)
    expect(w.find('.detail-purpose').exists(), '★ 未审 purpose 仍对外渲染').toBe(false)
    expect(w.find('.desc-draft-note').exists(), '内容都不显示了，标注不该对访客露面').toBe(false)
    w.unmount()
  })

  it('非 staff + 四字段未审 ⇒ Advantages / Limitations / Timeline 不渲染', async () => {
    const w = await mountWith({ specs_status: 'ai_draft' })

    expect(w.text(), '★ 未审 advantages 仍对外渲染').not.toContain('Fast; Specific')
    expect(w.text()).not.toContain('Copper toxicity')
    expect(w.text(), '★ 未审 timeline 仍对外渲染').not.toContain('2h')
    expect(w.find('.specs-row').exists()).toBe(false)
    expect(w.find('.spec-draft-note').exists()).toBe(false)
    w.unmount()
  })

  it('★ 两组状态互相独立：描述已审但四字段未审 ⇒ 只藏四字段', async () => {
    const w = await mountWith({ description_status: 'reviewed', specs_status: 'ai_draft' })

    expect(w.find('.detail-summary').exists(), '描述已审，不该一起藏掉').toBe(true)
    expect(w.text()).not.toContain('Copper toxicity')
    w.unmount()
  })

  it('非 staff + 都已审 ⇒ 全部渲染，且不出现草稿标注', async () => {
    const w = await mountWith({ description_status: 'reviewed', specs_status: 'reviewed' })

    expect(w.find('.detail-summary').exists()).toBe(true)
    expect(w.text()).toContain('Copper toxicity')
    expect(w.text()).toContain('2h')
    expect(w.find('.desc-draft-note').exists()).toBe(false)
    expect(w.find('.spec-draft-note').exists()).toBe(false)
    w.unmount()
  })

  it('staff + 未审 ⇒ 内容照常可见 + 两条草稿标注都在（内部要能审）', async () => {
    state.isStaff = true
    const w = await mountWith({ description_status: 'ai_draft', specs_status: 'ai_draft' })

    expect(w.find('.detail-summary').exists(), '★ staff 也看不到未审内容 ⇒ 无法审阅').toBe(true)
    expect(w.text()).toContain('Copper toxicity')
    expect(w.find('.desc-draft-note').exists(), 'staff 必须看到"AI 草稿待审"标注').toBe(true)
    expect(w.find('.spec-draft-note').exists()).toBe(true)
    w.unmount()
  })

  it('cost_band 不属于任一批次 ⇒ 未审时也不受影响（现状恒空，纯回归保护）', async () => {
    const w = await mountWith({ cost_band: 'low', description_status: 'ai_draft', specs_status: 'ai_draft' })
    expect(w.text()).toContain('Cost Band')
    w.unmount()
  })
})
