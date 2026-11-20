/**
 * `PoDownloadCenter` 的取数口径（S5 P-2 同日补）。
 *
 * ## 缺陷
 * ```js
 * onMounted(() => store.fetchOrders({ page_size: 100 }))
 * ... .filter(r => r.invoice || r.attachments.length)
 * ```
 * 先在「**最新的 100 单**」里取，再在客户端筛有文档的 ⇒ 客户更早的发票 /
 * PO 附件**根本不出现**。本地 dev 只读实测（全库 1124 单）：
 * **有发票的共 267 单**，落在最新 100 单之外的客户会看到
 * "No downloadable documents yet" —— 看起来像"确实没有文档"。
 *
 * ## 本文件钉住
 * ① 请求带 `has_documents=1`（判定交给服务端，浏览器不再猜）；
 * ② 按页取全（267 单不是一页装得下就收工）；
 * ③ 取数失败必须与"没有文档"区分开。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({ getOrders: vi.fn() }))
vi.mock('@/api/adminPo', () => api)

const portalApi = vi.hoisted(() => ({
  downloadInvoicePdf: vi.fn(),
  downloadPoAttachment: vi.fn(),
}))
vi.mock('@/api/poPortal', () => portalApi)

import PoDownloadCenter from '../PoDownloadCenter.vue'

function docRow(i, { invoice = true, attachments = 0 } = {}) {
  return {
    id: i,
    order_no: `ORD-DL-${String(i).padStart(4, '0')}`,
    status: 'invoiced',
    invoice: invoice ? { id: i * 10, invoice_no: `INV-${i}` } : null,
    attachments: Array.from({ length: attachments }, (_, k) => ({
      id: i * 100 + k, original_filename: `po-${i}-${k}.pdf`,
    })),
  }
}

function envelope(rows, total, page, pageSize) {
  return {
    success: true,
    data: rows,
    meta: { pagination: { count: total, page, page_size: pageSize, next: null } },
  }
}

/** 服务端：总共有 total 张「有文档」的单，按页切。 */
function mockServer(total) {
  api.getOrders.mockImplementation(async (params) => {
    const page = params.page || 1
    const size = params.page_size || 500
    const start = (page - 1) * size
    const rows = []
    for (let i = start; i < Math.min(start + size, total); i += 1) rows.push(docRow(i + 1))
    return envelope(rows, total, page, size)
  })
}

beforeEach(() => {
  api.getOrders.mockReset()
  portalApi.downloadInvoicePdf.mockReset()
  portalApi.downloadPoAttachment.mockReset()
})

describe('PoDownloadCenter 取数（S5 P-2）', () => {
  it('请求带 has_documents=1，交给服务端判定有没有文档', async () => {
    mockServer(2)
    mount(PoDownloadCenter)
    await flushPromises()
    const params = api.getOrders.mock.calls[0][0]
    expect(params.has_documents).toBe(1)
    expect(params.page_size).toBe(500)
    expect(params.page).toBe(1)
  })

  it('★ 267 张有文档的单要取全（原来只看最新 100 单里碰运气）', async () => {
    mockServer(267)
    const w = mount(PoDownloadCenter)
    await flushPromises()
    expect(api.getOrders).toHaveBeenCalledTimes(1) // 267 < 500
    expect(w.findAll('tbody tr').length).toBe(267)
    expect(w.get('[data-testid="download-total"]').text()).toBe('(267)')
  })

  it('超过单页容量时继续翻页', async () => {
    mockServer(1200)
    const w = mount(PoDownloadCenter)
    await flushPromises()
    expect(api.getOrders.mock.calls.map((c) => c[0].page)).toEqual([1, 2, 3])
    expect(w.findAll('tbody tr').length).toBe(1200)
  })

  it('渲染发票号与附件按钮（功能未被改坏）', async () => {
    mockServer(1)
    const w = mount(PoDownloadCenter)
    await flushPromises()
    expect(w.text()).toContain('INV-1')
    expect(w.text()).toContain('Invoice PDF')
  })

  it('取数失败时给出错误落位，而不是"没有文档"', async () => {
    api.getOrders.mockRejectedValue(new Error('Network down'))
    const w = mount(PoDownloadCenter)
    await flushPromises()
    expect(w.find('[data-testid="download-error"]').exists()).toBe(true)
    expect(w.find('[data-testid="download-error-empty"]').exists()).toBe(true)
    expect(w.text()).not.toContain('No downloadable documents yet.')
  })

  it('服务端已筛过时，客户端兜底判据不会把有文档的单滤掉', async () => {
    // 混合返回：一张只有附件、一张只有发票 ⇒ 两张都要渲染
    api.getOrders.mockResolvedValue(
      envelope([docRow(1), docRow(2, { invoice: false, attachments: 2 })], 2, 1, 500),
    )
    const w = mount(PoDownloadCenter)
    await flushPromises()
    expect(w.findAll('tbody tr').length).toBe(2)
  })
})
