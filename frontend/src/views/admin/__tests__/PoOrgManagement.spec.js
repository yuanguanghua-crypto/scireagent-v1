/**
 * `PoOrgManagement` 的机构订单队列取数（S5 P-2 同日补）。
 *
 * ## 缺陷
 * ```js
 * const res = await getOrgOrders(org.id, { page_size: 100 })
 * orgOrders.value = payload.results || payload.data || payload || []
 * ```
 * 只取**一页**、且页面上**没有任何翻页手段** ⇒ 本地 dev 只读实测
 * org 4 有 **1123 单**，点进去只看到 100 单，**漏 1023 单且毫无提示**。
 * 更差的是 `finally` 之后什么都不报：取数**失败**与"该机构没有订单"
 * 在屏幕上长得一模一样（都是 "No orders for this organization."）。
 *
 * ## 本文件钉住
 * ① 请求带 `organization_id` 且**按页取全**（不是只取第一页就收工）；
 * ② 标题旁显示机构订单**真值**计数；
 * ③ 取数失败必须与"没有订单"区分开（错误落位可见）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({ getOrganizations: vi.fn(), getOrders: vi.fn() }))
vi.mock('@/api/adminPo', () => api)

import PoOrgManagement from '../PoOrgManagement.vue'

const ORG = { id: 4, name: 'Acme Bio', org_type: 'industry', country: 'US' }

function envelope(total, page, pageSize) {
  const start = (page - 1) * pageSize
  const rows = []
  for (let i = start; i < Math.min(start + pageSize, total); i += 1) {
    rows.push({
      id: i + 1,
      order_no: `ORD-ORG-${String(i + 1).padStart(4, '0')}`,
      status: 'confirmed',
      grand_total: '100.00',
      currency: 'USD',
      created_at: '2026-11-01T00:00:00Z',
    })
  }
  return {
    success: true,
    data: rows,
    meta: { pagination: { count: total, page, page_size: pageSize, next: null } },
  }
}

async function mountAndSelect(total = 3) {
  api.getOrganizations.mockResolvedValue({ data: { results: [ORG] } })
  api.getOrders.mockImplementation(async (params) =>
    envelope(total, params.page || 1, params.page_size || 500))
  const w = mount(PoOrgManagement)
  await flushPromises()
  await w.find('tbody tr').trigger('click')
  await flushPromises()
  return w
}

beforeEach(() => {
  api.getOrganizations.mockReset()
  api.getOrders.mockReset()
})

/** 只数右侧「机构订单」卡片里的行（左栏机构表也是 tbody tr，别混进来）。 */
function orderRowCount(w) {
  const cards = w.findAll('.po-card')
  return cards[cards.length - 1].findAll('tbody tr').length
}

describe('PoOrgManagement 机构订单取数（S5 P-2）', () => {
  it('请求带 organization_id，并按服务端分页上限取数', async () => {
    await mountAndSelect(3)
    expect(api.getOrders).toHaveBeenCalledTimes(1)
    const params = api.getOrders.mock.calls[0][0]
    expect(params.organization_id).toBe(ORG.id)
    expect(params.page_size).toBe(500) // 与 backend max_page_size 对齐
    expect(params.page).toBe(1)
  })

  it('★ 1123 单必须翻页取全（原来只取 100 单，漏 1023）', async () => {
    const w = await mountAndSelect(1123)
    expect(api.getOrders.mock.calls.map((c) => c[0].page)).toEqual([1, 2, 3])
    // 每页 500 ⇒ 1123 单渲染成 1123 行
    expect(orderRowCount(w)).toBe(1123)
  })

  it('标题旁显示机构订单真值（不是当前页条数）', async () => {
    const w = await mountAndSelect(1123)
    expect(w.get('[data-testid="org-order-total"]').text()).toBe('(1123)')
    expect(w.find('[data-testid="org-order-truncated"]').exists()).toBe(false)
  })

  it('取数失败时给出错误落位，而不是"该机构没有订单"', async () => {
    api.getOrganizations.mockResolvedValue({ data: { results: [ORG] } })
    api.getOrders.mockRejectedValue(new Error('Network down'))
    const w = mount(PoOrgManagement)
    await flushPromises()
    await w.find('tbody tr').trigger('click')
    await flushPromises()

    expect(w.find('[data-testid="org-order-error"]').exists()).toBe(true)
    expect(w.find('[data-testid="org-order-error-empty"]').exists()).toBe(true)
    // 关键：不能同时说"没有订单" —— 那是把故障伪装成正常空态
    expect(w.text()).not.toContain('No orders for this organization.')
  })
})
