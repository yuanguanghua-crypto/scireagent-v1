/**
 * `PoInvoicingDesk` 的记账表单 —— A-099（S6 第三批）。
 *
 * ## QA 报的现象
 * 记完账（$79.00 / Wire Transfer / "TEST payment 2026-11-10"）后：
 *   ① 表单原样保留 → 下次误点就是**同一笔再记一次**；
 *   ② 「Record Payment」按钮仍可点，发票已是 Paid 也没有任何拦截；
 *   ③ 失败时异常直接冒泡，页面上什么提示都没有。
 *
 * ## 为什么用单测
 * 三条判据都是"某个请求发没发、某个值变没变"，不需要真跑一遍记账（那是**写**操作，
 * 不该为了验证界面去污染任何库）。服务端的金额/状态校验由
 * `backend/apps/transactions/tests/test_partial_payment.py` 钉住。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({
  getOrderDetail: vi.fn(),
  issueInvoice: vi.fn(),
  payInvoice: vi.fn(),
}))

vi.mock('@/api/adminPo', () => api)

const queue = vi.hoisted(() => ({ fetchOrderQueue: vi.fn() }))
vi.mock('@/composables/useOrderQueue', () => queue)

const ordersApi = vi.hoisted(() => ({ verifyPayment: vi.fn() }))
vi.mock('@/api/orders', () => ordersApi)

vi.mock('@/components/common', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() } }
})

import PoInvoicingDesk from '../PoInvoicingDesk.vue'

const QUEUE_ROW = { id: 42, order_no: 'ORD-A099-0001', status: 'invoiced', grand_total: '79.00' }

function detailWith(invoice) {
  return { id: 42, order_no: 'ORD-A099-0001', status: 'invoiced', invoice }
}

const ISSUED_INVOICE = {
  id: 7, invoice_no: 'INV-2026-0011', status: 'issued', due_date: '2026-12-10',
  grand_total: '79.00', currency: 'USD', amount_paid: '0.00', balance_due: '79.00',
  payments: [],
}

async function mountAndOpen(invoice = ISSUED_INVOICE) {
  queue.fetchOrderQueue.mockResolvedValue({ orders: [QUEUE_ROW], total: 1, truncated: false })
  api.getOrderDetail.mockResolvedValue({ data: detailWith(invoice) })
  const w = mount(PoInvoicingDesk, { global: { stubs: { StatusBadge: true } } })
  await flushPromises()
  await w.find('.po-table tbody tr').trigger('click')
  await flushPromises()
  return w
}

const amountInput = (w) => w.find('[data-testid="pay-amount"]')
const refInput = (w) => w.find('[data-testid="pay-reference"]')
const submitBtn = (w) => w.find('[data-testid="pay-submit"]')

beforeEach(() => {
  vi.clearAllMocks()
})

describe('记账表单（A-099）', () => {
  it('成功后：金额/参考号清空，避免同一笔再记一次', async () => {
    api.payInvoice.mockResolvedValue({})
    const w = await mountAndOpen()

    await amountInput(w).setValue('79.00')
    await refInput(w).setValue('TEST payment')
    await submitBtn(w).trigger('click')
    await flushPromises()

    expect(api.payInvoice).toHaveBeenCalledTimes(1)
    expect(amountInput(w).element.value, '★ 金额没清空 ⇒ 下次误点就是重复入账').toBe('')
    expect(refInput(w).element.value).toBe('')
    w.unmount()
  })

  it('成功后重取详情（余额/状态/付款明细都会变）', async () => {
    api.payInvoice.mockResolvedValue({})
    const w = await mountAndOpen()
    const before = api.getOrderDetail.mock.calls.length
    await amountInput(w).setValue('10.00')
    await submitBtn(w).trigger('click')
    await flushPromises()
    expect(api.getOrderDetail.mock.calls.length).toBeGreaterThan(before)
    w.unmount()
  })

  it('请求进行中按钮禁用 ⇒ 连点只发一次', async () => {
    let resolveFn
    api.payInvoice.mockReturnValue(new Promise((res) => { resolveFn = res }))
    const w = await mountAndOpen()
    await amountInput(w).setValue('79.00')

    await submitBtn(w).trigger('click')
    await flushPromises()
    expect(submitBtn(w).attributes('disabled')).toBeDefined()

    await submitBtn(w).trigger('click')       // 第二次点击必须被挡
    await flushPromises()
    expect(api.payInvoice).toHaveBeenCalledTimes(1)

    resolveFn({})
    await flushPromises()
    w.unmount()
  })

  it('失败 ⇒ 错误落在页面上（不是静默）', async () => {
    api.payInvoice.mockRejectedValue({ response: { data: { detail: 'Amount exceeds balance due.' } } })
    const w = await mountAndOpen()
    await amountInput(w).setValue('999.00')
    await submitBtn(w).trigger('click')
    await flushPromises()

    const err = w.find('[data-testid="pay-error"]')
    expect(err.exists()).toBe(true)
    expect(err.text()).toContain('exceeds balance')
    w.unmount()
  })

  it('发票已付清 ⇒ 表单消失，只留"已结清"提示', async () => {
    const paid = { ...ISSUED_INVOICE, status: 'paid', amount_paid: '79.00', balance_due: '0.00' }
    const w = await mountAndOpen(paid)

    expect(submitBtn(w).exists(), '★ 已付清的发票不该还有记账按钮').toBe(false)
    expect(w.find('[data-testid="invoice-settled"]').exists()).toBe(true)
    w.unmount()
  })
})
