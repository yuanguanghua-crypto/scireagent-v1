/**
 * A-171：客户订单详情页的自助取消入口（2026-11-27）。
 *
 * ## 被钉住的三件事
 * 1. 只有 `po_received` / `confirmed` 两个阶段出按钮 —— 与后端
 *    `CancelOrderView.CUSTOMER_CANCELLABLE` 是同一个集合。两边一宽一窄就会出现
 *    「按钮能点但后端拒绝」或「后端允许但界面没入口」，都算回归。
 * 2. 点击**必须先确认**（不可逆动作），取消掉就不该发请求。
 * 3. 确认后才真的调 `cancelOrder` 并刷新详情。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const state = vi.hoisted(() => ({
  order: null,
  askResult: true,
  askCalls: [],
  cancelCalls: [],
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/stores/orders', () => ({
  useOrdersStore: () => ({
    get currentOrder() { return state.order },
    fetchOrder: vi.fn(async () => {}),
    clearCurrent: vi.fn(),
    error: null,
  }),
}))
vi.mock('@/api/orders', () => ({
  respondToQuote: vi.fn(),
  cancelOrder: vi.fn(async (id) => { state.cancelCalls.push(id); return {} }),
}))
vi.mock('@/api/poPortal', () => ({
  downloadInvoicePdf: vi.fn(),
  uploadPaymentProof: vi.fn(),
}))
vi.mock('@/composables/useConfirm', () => ({
  useConfirm: () => ({
    ask: vi.fn(async (opts) => { state.askCalls.push(opts); return state.askResult }),
    askText: vi.fn(),
  }),
}))
vi.mock('@/components/common', () => ({
  LoadingSpinner: { template: '<div />' },
  ErrorBanner: { template: '<div />' },
  StatusBadge: { template: '<span />' },
  toast: { success: vi.fn(), error: vi.fn() },
}))

import OrderDetailPage from '@/views/OrderDetailPage.vue'

function makeOrder(status) {
  return {
    id: 1,
    order_no: 'ORD-TEST-1',
    status,
    created_at: '2026-11-27T10:00:00Z',
    items: [],
    shipments: [],
    status_logs: [],
    invoice: null,
    payments: [],
  }
}

async function mountWith(status) {
  state.order = makeOrder(status)
  const w = mount(OrderDetailPage, { global: { stubs: { 'router-link': true } } })
  await flushPromises()
  return w
}

function hasCancel(w) {
  return w.findAll('button').some((b) => /Cancel Order/i.test(b.text()))
}

beforeEach(() => {
  state.askCalls = []
  state.cancelCalls = []
  state.askResult = true
})

describe('A-171 可取消状态集合与后端一致', () => {
  it('confirmed 显示取消入口', async () => {
    expect(hasCancel(await mountWith('confirmed'))).toBe(true)
  })

  it('po_received 显示取消入口', async () => {
    expect(hasCancel(await mountWith('po_received'))).toBe(true)
  })

  for (const st of ['in_production', 'shipped', 'delivered', 'invoiced', 'paid', 'completed', 'cancelled']) {
    it(`${st} 不显示取消入口`, async () => {
      expect(hasCancel(await mountWith(st))).toBe(false)
    })
  }
})

describe('A-171 取消必须先确认', () => {
  it('确认框取消 → 不发请求', async () => {
    state.askResult = false
    const w = await mountWith('confirmed')
    const btn = w.findAll('button').find((b) => /Cancel Order/i.test(b.text()))
    await btn.trigger('click')
    await flushPromises()
    expect(state.askCalls).toHaveLength(1)
    expect(state.cancelCalls).toHaveLength(0)
  })

  it('确认 → 调用 cancelOrder', async () => {
    state.askResult = true
    const w = await mountWith('confirmed')
    const btn = w.findAll('button').find((b) => /Cancel Order/i.test(b.text()))
    await btn.trigger('click')
    await flushPromises()
    expect(state.cancelCalls).toEqual([1])
  })
})
