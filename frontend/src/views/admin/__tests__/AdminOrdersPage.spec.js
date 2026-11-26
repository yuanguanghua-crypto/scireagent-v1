/**
 * Orders 列表的 CUSTOMER 列（S5 P-3 / A-077）。
 *
 * ## 缺陷
 * 模板里是 `<td>{{ order.user_id }}</td>` —— 一个**裸数字 id**。
 * `user` 为 NULL 的历史单整列空白（QA Batch 8 实测 21 行全空白），
 * 运营拿到 "12" 既联系不上客户、也判断不出这单是谁下的。
 *
 * ## 本文件钉住
 * ① 有客户名时显示姓名（不再显示裸 id）；
 * ② 邮箱与组织名作为副行显示（运营要能在列表上直接联系）；
 * ③ `customer_name` 为空（后端 user 为 NULL）时显示 "—"，**不是空白也不是 "undefined"**。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({ getAdminOrders: vi.fn() }))
vi.mock('@/api/orders', () => api)

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

import AdminOrdersPage from '../AdminOrdersPage.vue'

function row(over = {}) {
  return {
    id: 1,
    order_no: 'ORD-CUST-1',
    status: 'confirmed',
    payment_method: 'purchase_order',
    po_number: null,
    grand_total: '100.00',
    currency: 'USD',
    created_at: '2026-11-01T00:00:00Z',
    customer_name: 'alice_cust',
    customer_email: 'alice@acme.example',
    organization_name: 'Acme Labs',
    ...over,
  }
}

function envelope(rows) {
  return {
    success: true,
    data: rows,
    meta: { pagination: { page: 1, pageSize: 20, count: rows.length } },
  }
}

async function mountWith(rows) {
  api.getAdminOrders.mockResolvedValue(envelope(rows))
  const w = mount(AdminOrdersPage, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return w
}

describe('AdminOrdersPage — CUSTOMER 列（A-077）', () => {
  beforeEach(() => {
    api.getAdminOrders.mockReset()
  })

  it('显示客户姓名，而不是裸 user_id', async () => {
    const w = await mountWith([row()])
    const tds = w.findAll('tbody tr')[0].findAll('td')
    // 第 2 列是 Customer
    expect(tds[1].text()).toContain('alice_cust')
  })

  it('副行同时给出邮箱与组织名', async () => {
    const w = await mountWith([row()])
    const cell = w.findAll('tbody tr')[0].findAll('td')[1]
    expect(cell.find('.cust-sub').exists()).toBe(true)
    expect(cell.text()).toContain('alice@acme.example')
    expect(cell.text()).toContain('Acme Labs')
  })

  it('客户名为空时显示 “—”，不是空白也不是 undefined', async () => {
    const w = await mountWith([
      row({ order_no: 'ORD-ORPHAN', customer_name: '', customer_email: '', organization_name: '' }),
    ])
    const cell = w.findAll('tbody tr')[0].findAll('td')[1]
    expect(cell.find('.cust-name').text()).toBe('—')
    expect(cell.text()).not.toContain('undefined')
    // 没有邮箱/组织时不渲染无意义的副行
    expect(cell.find('.cust-sub').exists()).toBe(false)
  })

  it('多行时每行显示各自的客户', async () => {
    const w = await mountWith([
      row({ id: 1, order_no: 'ORD-A', customer_name: 'alice_cust' }),
      row({
        id: 2, order_no: 'ORD-B', customer_name: 'bob_cust',
        customer_email: 'bob@other.example', organization_name: '',
      }),
    ])
    const rows = w.findAll('tbody tr')
    expect(rows[0].findAll('td')[1].text()).toContain('alice_cust')
    expect(rows[1].findAll('td')[1].text()).toContain('bob_cust')
    expect(rows[1].findAll('td')[1].text()).toContain('bob@other.example')
  })
})
