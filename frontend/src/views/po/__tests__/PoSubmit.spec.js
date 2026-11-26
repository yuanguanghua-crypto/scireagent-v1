/**
 * `PoSubmit` 的提交闸门 —— A-189（2026-11-20 / S4）。
 *
 * ## 缺陷（已实测坐实，见 `_s4work/probe_a189.cjs` 六场景）
 * 表单里有三条 HTML5 原生约束：`#po-f5` 的 `min`、`#po-f9` 的 `type=email`、
 * 明细行数量框的 `min="1"`。任一不满足，浏览器就**直接吃掉 submit** ——
 * `handleSubmit` 一行都不执行 ⇒ 无 toast、无横幅、无跳转、**0 个网络请求**。
 * QA 报的「提交按钮静默失效」正是这个签名（过去日期/非法邮箱/数量 0 全部 0 请求）。
 *
 * ## 修法与判据
 * 表单加 `novalidate`（约束属性保留，只收回拦截权），由 `validateDateAndEmail`
 * 落**行内常驻提示**。所以本测试钉两件事：
 *   ① 不该发请求时**真的没发**（不是"发了但失败了"）；
 *   ② 不该发请求时**页面上必须有明确原因**（这是 A-189 的核心诉求：
 *      「静默」比「失败」更糟）。只断言①会漏掉"页面上依然什么都没说"。
 *
 * ## ⚠️ 本测试**证明不了**的一件事（别误读成已覆盖）
 * vue-test-utils 的 `trigger('submit')` 是**直接派发事件**，绕过浏览器原生约束校验。
 * 所以「去掉 `novalidate` 后真实浏览器会吃掉 submit」这个因果，单测**验证不到** ——
 * 实测探针里摘掉 `novalidate` 只有属性断言那条变红，其余 6 条照旧绿。
 * 该因果的承重证据是 Playwright 实测（`_s4work/probe_a189.cjs` 场景 B/D/E：
 * `validity.rangeUnderflow=true` ⇒ 0 请求、0 提示），以及 e2e
 * `order-error-paths.spec.cjs` 里那条「过去日期 ⇒ 0 请求 + 必须出现行内提示」。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const state = vi.hoisted(() => ({ submitCalls: [], toasts: [] }))

vi.mock('@/api/poPortal', () => ({
  submitPo: vi.fn(async (args) => {
    state.submitCalls.push(args)
    return { data: { order_no: 'ORD-TEST0001', status: 'po_received' } }
  }),
  getOrderDetail: vi.fn(async () => ({ data: null })),
  getMyQuotes: vi.fn(async () => ({ data: [] })),
}))

vi.mock('@/api/products', () => ({
  getProducts: vi.fn(async () => ({
    data: [{ id: 42, name: '5-Iodo-dUTP', catalog_no: 'SC8023' }],
  })),
  getProductDetail: vi.fn(async () => ({
    data: {
      product: {
        skus: [{ id: 11, sku_code: 'SC8023-1', pack_size: '1 mg', price: '79.00' }],
      },
    },
  })),
}))

vi.mock('@/components/common', () => ({
  toast: {
    error: (m) => state.toasts.push(String(m)),
    success: (m) => state.toasts.push(String(m)),
    warning: (m) => state.toasts.push(String(m)),
  },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ push: vi.fn() }),
  }
})

import PoSubmit from '../PoSubmit.vue'

async function mountPage() {
  // 页内有 <router-link>（成功横幅里的 View My Orders）；不 stub 会每个用例刷一遍解析告警
  const w = mount(PoSubmit, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return w
}

/** 把一行明细填成合法状态（走真实 UI 路径：搜索 → 选中 → 选 SKU）。 */
async function addValidItem(w) {
  await w.findAll('button').find((b) => b.text().includes('Add Line Item')).trigger('click')
  await flushPromises()

  const row = w.findAll('tbody tr')[0]
  await row.find('input.po-input').setValue('SC8023')
  await flushPromises()
  await w.find('.po-search-item').trigger('click')
  await flushPromises()

  const skuSelect = w.find('tbody select.po-select')
  await skuSelect.setValue('11') // onSkuChange 会把单价带成 79.00
  await flushPromises()
}

const submitBtn = (w) => w.find('button[type="submit"]')
const text = (w, sel) => (w.find(sel).exists() ? w.find(sel).text() : null)

const tomorrow = new Date(Date.now() + 86400000).toLocaleDateString('en-CA')

beforeEach(() => {
  state.submitCalls.length = 0
  state.toasts.length = 0
})

describe('A-189 提交闸门不再让浏览器原生校验静默吃掉 submit', () => {
  it('form 上是 novalidate（约束属性保留，但拦截权收回应用层）', async () => {
    const w = await mountPage()
    expect(w.find('form.po-card').attributes('novalidate')).toBeDefined()
    // 约束属性本身必须还在：日期选择器仍不许选过去、邮箱键盘不变
    expect(w.find('#po-f5').attributes('min')).toBeTruthy()
    expect(w.find('#po-f9').attributes('type')).toBe('email')
  })

  it('过去日期：0 次请求，且日期旁与按钮旁都给出常驻原因', async () => {
    const w = await mountPage()
    await addValidItem(w)

    await w.find('#po-f5').setValue('2000-01-01')
    await submitBtn(w).trigger('submit')
    await flushPromises()

    expect(state.submitCalls).toHaveLength(0)
    expect(text(w, '[data-testid="po-date-error"]')).toContain('cannot be earlier than')
    // 「静默」是 A-189 的本体：只在字段旁报错不够，按钮旁也必须说清楚
    expect(text(w, '[data-testid="po-submit-error"]')).toContain('cannot be earlier than')
    // 提示里要带上今天，用户才知道该填哪天
    const today = new Date().toLocaleDateString('en-CA')
    expect(text(w, '[data-testid="po-date-error"]')).toContain(today)
  })

  it('非法邮箱：0 次请求 + 行内原因', async () => {
    const w = await mountPage()
    await addValidItem(w)

    await w.find('#po-f5').setValue(tomorrow)
    await w.find('#po-f9').setValue('abc')
    await submitBtn(w).trigger('submit')
    await flushPromises()

    expect(state.submitCalls).toHaveLength(0)
    expect(text(w, '[data-testid="po-email-error"]')).toContain('valid email')
  })

  it('数量 0：0 次请求 + 明确 toast（此前被 type=number min=1 静默吃掉）', async () => {
    const w = await mountPage()
    await addValidItem(w)

    await w.find('#po-f5').setValue(tomorrow)
    await w.find('tbody input[type="number"]').setValue('0')
    await submitBtn(w).trigger('submit')
    await flushPromises()

    expect(state.submitCalls).toHaveLength(0)
    expect(state.toasts.join(' | ')).toContain('Each line item requires')
  })

  it('日期与邮箱都合法：真的提交（不误拦）', async () => {
    const w = await mountPage()
    await addValidItem(w)

    await w.find('#po-f5').setValue(tomorrow)
    await w.find('#po-f9').setValue('buyer@lab.edu')
    await submitBtn(w).trigger('submit')
    await flushPromises()

    expect(state.submitCalls).toHaveLength(1)
    expect(state.toasts).toHaveLength(0)
    expect(w.text()).toContain('ORD-TEST0001')
  })

  it('留空日期与邮箱：允许提交（后端两者都 required=False，前端不得收紧）', async () => {
    const w = await mountPage()
    await addValidItem(w)

    await submitBtn(w).trigger('submit')
    await flushPromises()

    expect(state.submitCalls).toHaveLength(1)
  })

  it('把日期改对后，红字自动消失（不必再点一次提交）', async () => {
    const w = await mountPage()
    await addValidItem(w)

    await w.find('#po-f5').setValue('2000-01-01')
    await submitBtn(w).trigger('submit')
    await flushPromises()
    expect(w.find('[data-testid="po-date-error"]').exists()).toBe(true)

    await w.find('#po-f5').setValue(tomorrow)
    await flushPromises()
    expect(w.find('[data-testid="po-date-error"]').exists()).toBe(false)
    expect(w.find('[data-testid="po-submit-error"]').exists()).toBe(false)
  })
})
