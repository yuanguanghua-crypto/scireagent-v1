/**
 * `ApplicationIndex` 的「改条件 → 重取数据」接线 —— A-141（2026-11-20 / S4 收口）。
 *
 * ## 被钉住的两件事（同一个病）
 * ① 状态芯片是**死控件**：`handleFilter` 只写 store 不发请求，`watch` 又只盯
 *    `filters.search` ⇒ 点「Draft」「Deprecated」列表纹丝不动。
 * ② 搜索框有三条路管同一件事（`v-model` + `@input` + `watch`）⇒ **每敲一个字符
 *    发两次相同请求**。两个响应谁后到谁覆盖，翻页时还会错页。
 *
 * ## 为什么用**真实 pinia store**、只 mock api 层
 * A-141 的断点就在「页面 ↔ store」之间；如果把 store 也换成替身，
 * 断言就变成"替身被调了几次"，测不出 `setFilters` 到底有没有把 `status`
 * 拼进请求（`stores/applications.js:43`）。这里让真 store 跑，
 * 只把 `@/api/applications` 换成记录参数的桩。
 *
 * ## 后端为什么不用改（本测试的前提，非拍脑袋）
 * `ApplicationFilter.Meta.fields` 已含 `status`
 * （`backend/apps/knowledge/api/v1/filters.py:22`），且 `apply_public_visibility`
 * 对 staff **绕过** status 公开态过滤（`.../fixture_visibility.py:84`）。
 * ⇒ staff 点 Draft 真的能拿到草稿，不需要 `include_unpublished=1`
 * （那是 MethodIndex 的情形，因为 Method 的 list 端点额外加了 staff 过滤）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'

const state = vi.hoisted(() => ({ isStaff: true, calls: [] }))

vi.mock('@/api/applications', () => ({
  getApplications: vi.fn(async (params) => {
    state.calls.push(params)
    return {
      data: [{ id: 1, name: 'RNA Imaging', status: 'active' }],
      meta: { pagination: { count: 1 } },
    }
  }),
  getApplication: vi.fn(),
  createApplication: vi.fn(),
  updateApplication: vi.fn(),
  deleteApplication: vi.fn(),
}))

// 只关心 isStaff 这一个开关；真 store 会连带拉 user/profile，测试里不需要
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get isStaff() {
      return state.isStaff
    },
  }),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ push: vi.fn() }),
  }
})

import ApplicationIndex from '../ApplicationIndex.vue'
import { useApplicationsStore } from '@/stores/applications'

const OPTIONS = {
  global: {
    plugins: [ElementPlus],
    // 图标是全局注册的（main.js），单测里没有 ⇒ 给一个最小替身，避免解析告警
    components: { Search: { template: '<i />' } },
    stubs: { ApplicationCard: true, ConvergenceBrowseTab: true },
  },
}

async function mountPage() {
  const w = mount(ApplicationIndex, OPTIONS)
  await flushPromises()
  return w
}

const chip = (w, key) => w.find(`[data-testid="status-chip-${key}"]`)
const lastCall = () => state.calls[state.calls.length - 1]

beforeEach(() => {
  state.calls.length = 0
  state.isStaff = true
  setActivePinia(createPinia())
})

describe('A-141 状态芯片必须真的改变结果集', () => {
  it('点 Draft：发请求且把 status=draft 传给后端', async () => {
    const w = await mountPage()
    state.calls.length = 0 // 丢掉 onMounted 那次

    await chip(w, 'draft').trigger('click')
    await flushPromises()

    expect(state.calls).toHaveLength(1)
    expect(lastCall().status).toBe('draft')
  })

  it('点 All：不发 status 参数（status 为空串时按 undefined 处理）', async () => {
    const w = await mountPage()
    await chip(w, 'draft').trigger('click')
    await flushPromises()
    state.calls.length = 0

    await chip(w, 'all').trigger('click')
    await flushPromises()

    expect(state.calls).toHaveLength(1)
    expect(lastCall().status).toBeUndefined()
  })

  it('点芯片时把页码回到第 1 页（否则停在第 3 页会筛出空表）', async () => {
    const w = await mountPage()
    const store = useApplicationsStore()
    store.setPage(3)
    state.calls.length = 0

    await chip(w, 'deprecated').trigger('click')
    await flushPromises()

    expect(lastCall().page).toBe(1)
  })

  it('芯片文案与后端 status 值一一对应（All 是空值，其余取 key）', async () => {
    const w = await mountPage()
    const store = useApplicationsStore()

    for (const [key, expected] of [
      ['active', 'active'],
      ['deprecated', 'deprecated'],
      ['all', ''],
    ]) {
      await chip(w, key).trigger('click')
      await flushPromises()
      expect(store.filters.status).toBe(expected)
    }
  })
})

describe('A-141 搜索一次输入只许发一次请求', () => {
  it('键入一个字符：恰好 1 次请求，且带上关键词', async () => {
    const w = await mountPage()
    state.calls.length = 0

    await w.find('input').setValue('RNA')
    await flushPromises()

    // 原实现这里是 2 次（@input 一次 + watch 一次）
    expect(state.calls).toHaveLength(1)
    expect(lastCall().search).toBe('RNA')
  })

  it('在第 3 页输入关键词：回到第 1 页再查', async () => {
    const w = await mountPage()
    const store = useApplicationsStore()
    store.setPage(3)
    state.calls.length = 0

    await w.find('input').setValue('PCR')
    await flushPromises()

    expect(lastCall().page).toBe(1)
    expect(lastCall().search).toBe('PCR')
  })
})

describe('A-123 的 isStaff 守卫不能被顺手改掉', () => {
  it('非 staff：不渲染芯片栏，也不多发请求', async () => {
    state.isStaff = false
    const w = await mountPage()

    expect(w.find('[data-testid="status-chips"]').exists()).toBe(false)
    // 只剩 onMounted 那一次
    expect(state.calls).toHaveLength(1)
  })
})
