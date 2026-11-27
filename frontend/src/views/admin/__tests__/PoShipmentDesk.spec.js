/**
 * `PoShipmentDesk` 的发货表单校验与反馈 —— A-095 + A-096（2026-11-18 / S4）。
 *
 * ## A-095 缺陷
 * `submitShipment()` 原先**零校验、零反馈**：
 *   ```
 *   if (!selected.value) return
 *   await createShipment(selected.value, { ...shipForm })
 *   openOrder({ id: selected.value })
 *   ```
 * ⇒ 承运商与运单号都空也能提交成功（后端当时也照收），落一条既追不了也索赔不了的
 *   发货记录；成功后既无提示、也不清表单，运营看不出成功还是失败，会重复提交。
 *
 * ## A-096 缺陷
 * `doMarkShipped` / `doMarkDelivered` 原先：
 *   ```
 *   await markShipped(id)
 *   if (selected.value) openOrder({ id: selected.value })   // ← 忘了 await
 *   ```
 * ⇒ ① 详情刷新未 await，失败变 unhandled rejection，页面无任何错误落位；
 *   ② `load()` 从未被调 ⇒ **左侧订单列表 Status 列永久滞后**；
 *   ③ 成功路径零反馈。
 * （QA 报的"面板仍显示 No shipments yet"与代码不符——详情确实重取了，故不采信那半句。）
 *
 * ## 为什么用单测而不是 e2e
 * 被测的是**纯前端前置校验**（"没填就别发请求"）与**刷新编排**（"有没有再调一次
 * `getOrders`"），判据都是「某个函数有没有被调用」。e2e 还得先造 confirmed 订单与
 * 发货记录，慢且依赖环境数据；单测能把这两条判据钉得又准又稳。真闸门在服务端，由
 * `backend/apps/transactions/tests/test_shipment_carrier_guard.py` 覆盖。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({
  getOrders: vi.fn(),
  getOrderDetail: vi.fn(),
  createShipment: vi.fn(),
  markShipped: vi.fn(),
  markDelivered: vi.fn(),
}))

vi.mock('@/api/adminPo', () => api)

// ★ 只替换 toast，保留 StatusBadge 等真组件（否则模板会拿到 undefined）
const toast = vi.hoisted(() => ({
  success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(),
}))
vi.mock('@/components/common', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast }
})

import PoShipmentDesk from '../PoShipmentDesk.vue'

const ORDER = { id: 11, order_no: 'ORD-A095-0001', status: 'confirmed', items_count: 1 }
const DETAIL = {
  order_no: 'ORD-A095-0001',
  items: [{ id: 1, sku_code: 'SKU-A095-1', quantity: 2 }],
  shipments: [],
}

async function mountAndOpen(detailOverride) {
  api.getOrders.mockResolvedValue({ data: { results: [ORDER] } })
  api.getOrderDetail.mockResolvedValue({ data: detailOverride || DETAIL })
  const w = mount(PoShipmentDesk)
  await flushPromises()
  // 点左侧订单行 ⇒ 右侧出现 New Shipment 表单
  await w.find('tbody tr').trigger('click')
  await flushPromises()
  return w
}

const carrierInput = (w) => w.find('[data-testid="ship-carrier"]')
const trackingInput = (w) => w.find('[data-testid="ship-tracking"]')
const createBtn = (w) => w.find('[data-testid="ship-create"]')
const errorBox = (w) => w.find('[data-testid="ship-error"]')

describe('PoShipmentDesk 发货表单（A-095）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.createShipment.mockResolvedValue({ data: { id: 1 } })
  })

  it('承运商与运单号都空 ⇒ 不调接口 + 页内报错', async () => {
    const w = await mountAndOpen()

    await createBtn(w).trigger('click')
    await flushPromises()

    expect(api.createShipment, '★ 空表单居然发出了创建请求（后端会落一条无法追踪的记录）')
      .not.toHaveBeenCalled()
    expect(errorBox(w).exists(), '没有页内错误落位 —— 用户点完看不出发生了什么').toBe(true)
    expect(errorBox(w).text()).toMatch(/carrier/i)
    expect(errorBox(w).text()).toMatch(/tracking/i)
    w.unmount()
  })

  it('纯空格等于没填 ⇒ 同样拦下', async () => {
    const w = await mountAndOpen()

    await carrierInput(w).setValue('   ')
    await trackingInput(w).setValue('  ')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(api.createShipment).not.toHaveBeenCalled()
    expect(errorBox(w).exists()).toBe(true)
    w.unmount()
  })

  it('只填承运商 ⇒ 放行（真实履约里"承运商已知、单号稍后补"是常态）', async () => {
    const w = await mountAndOpen()

    await carrierInput(w).setValue('DHL')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(api.createShipment).toHaveBeenCalledTimes(1)
    expect(api.createShipment.mock.calls[0][0]).toBe(ORDER.id)
    expect(api.createShipment.mock.calls[0][1].carrier).toBe('DHL')
    w.unmount()
  })

  it('只填运单号 ⇒ 放行', async () => {
    const w = await mountAndOpen()

    await trackingInput(w).setValue('TRK-ONLY-1')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(api.createShipment).toHaveBeenCalledTimes(1)
    expect(api.createShipment.mock.calls[0][1].tracking_number).toBe('TRK-ONLY-1')
    w.unmount()
  })

  it('成功后清空物流输入（否则会照着旧值重复提交）', async () => {
    const w = await mountAndOpen()

    await carrierInput(w).setValue('FedEx')
    await trackingInput(w).setValue('TRK-1')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(carrierInput(w).element.value, '★ 成功后承运商没清空').toBe('')
    expect(trackingInput(w).element.value, '★ 成功后运单号没清空').toBe('')
    w.unmount()
  })

  it('成功后有 toast 反馈（原先零反馈）', async () => {
    const w = await mountAndOpen()

    await carrierInput(w).setValue('FedEx')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(toast.success, '创建成功后没有任何反馈').toHaveBeenCalled()
    w.unmount()
  })

  it('后端 400 的错误文案要落到页面上（而不是只弹 3 秒 toast）', async () => {
    api.createShipment.mockRejectedValueOnce({
      response: { data: { meta: { error: { message: 'carrier or tracking_number is required' } } } },
    })
    const w = await mountAndOpen()

    await carrierInput(w).setValue('DHL')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(errorBox(w).exists(), '后端错误没有落页').toBe(true)
    expect(errorBox(w).text()).toContain('tracking_number')
    w.unmount()
  })

  it('报错后再改对重提 ⇒ 错误提示消失（不残留旧错误）', async () => {
    const w = await mountAndOpen()

    await createBtn(w).trigger('click')          // 先空提交 ⇒ 报错
    await flushPromises()
    expect(errorBox(w).exists()).toBe(true)

    await carrierInput(w).setValue('DHL')
    await createBtn(w).trigger('click')          // 再正常提交
    await flushPromises()
    expect(errorBox(w).exists(), '★ 提交成功后旧的错误提示还赖在页面上').toBe(false)
    w.unmount()
  })
})

/* ─────────────────────────── A-096 ─────────────────────────── */

const SHIPMENT_PENDING = {
  id: 501, status: 'pending', tracking_number: 'TRK-501', carrier: 'DHL',
}
const SHIPMENT_SHIPPED = {
  id: 502, status: 'shipped', tracking_number: 'TRK-502', carrier: 'FedEx',
}
const DETAIL_PENDING = { ...DETAIL, shipments: [SHIPMENT_PENDING] }
const DETAIL_SHIPPED = { ...DETAIL, shipments: [SHIPMENT_SHIPPED] }

const actionErrorBox = (w) => w.find('[data-testid="ship-action-error"]')
const markShippedBtn = (w) => w.find('[data-testid="ship-mark-shipped"]')
const markDeliveredBtn = (w) => w.find('[data-testid="ship-mark-delivered"]')

describe('PoShipmentDesk 标记发货 / 送达后的刷新与反馈（A-096）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.createShipment.mockResolvedValue({ data: { id: 1 } })
    api.markShipped.mockResolvedValue({ data: {} })
    api.markDelivered.mockResolvedValue({ data: {} })
  })

  it('创建发货成功 ⇒ 左侧列表也要重取（同一类滞后，别只修两个动作）', async () => {
    const w = await mountAndOpen()
    const ordersBefore = api.getOrders.mock.calls.length

    await carrierInput(w).setValue('DHL')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(api.getOrders.mock.calls.length, '★ 建完发货记录后左侧列表没刷新').toBeGreaterThan(ordersBefore)
    w.unmount()
  })

  it('标记发货成功 ⇒ 左侧列表真的重取了（原先 load() 从不被调）', async () => {
    const w = await mountAndOpen(DETAIL_PENDING)
    const ordersBefore = api.getOrders.mock.calls.length
    const detailBefore = api.getOrderDetail.mock.calls.length

    await markShippedBtn(w).trigger('click')
    await flushPromises()

    expect(api.markShipped).toHaveBeenCalledWith(SHIPMENT_PENDING.id)
    expect(api.getOrders.mock.calls.length, '★ load() 没跑 ⇒ 左侧列表 Status 列会永久滞后')
      .toBeGreaterThan(ordersBefore)
    expect(api.getOrderDetail.mock.calls.length, '详情没有重取（openOrder 未 await/未执行）')
      .toBeGreaterThan(detailBefore)
    expect(toast.success, '标记发货成功后没有任何反馈').toHaveBeenCalled()
    w.unmount()
  })

  it('标记发货失败 ⇒ 错误落页 + 不弹成功 toast（原先失败是静默 unhandled rejection）', async () => {
    api.markShipped.mockRejectedValueOnce({
      response: { data: { meta: { error: { message: 'shipment already delivered' } } } },
    })
    const w = await mountAndOpen(DETAIL_PENDING)

    await markShippedBtn(w).trigger('click')
    await flushPromises()

    expect(actionErrorBox(w).exists(), '★ 标记发货失败后页面上没有任何提示').toBe(true)
    expect(actionErrorBox(w).text()).toContain('already delivered')
    expect(toast.success, '失败了却弹了成功提示').not.toHaveBeenCalled()
    w.unmount()
  })

  it('标记送达成功 ⇒ 列表与详情一起刷新 + toast', async () => {
    const w = await mountAndOpen(DETAIL_SHIPPED)
    const ordersBefore = api.getOrders.mock.calls.length

    // 「Received by」输入框与 Mark Delivered 同处一个 po-row，取第一个 text input 即可
    await w.find('.po-shipment input.po-input').setValue('Alice')
    await markDeliveredBtn(w).trigger('click')
    await flushPromises()

    expect(api.markDelivered).toHaveBeenCalledWith(SHIPMENT_SHIPPED.id, 'Alice')
    expect(api.getOrders.mock.calls.length, '★ 送达后左侧列表没刷新').toBeGreaterThan(ordersBefore)
    expect(toast.success).toHaveBeenCalled()
    w.unmount()
  })

  it('标记送达失败 ⇒ 错误落页', async () => {
    api.markDelivered.mockRejectedValueOnce({
      response: { data: { detail: 'Shipment is not in a shippable state.' } },
    })
    const w = await mountAndOpen(DETAIL_SHIPPED)

    // ★ 2026-11-27（A-224）：Received by 现在是必填 —— 不填会在前端就被挡下，
    //   根本发不出请求，这个用例要验的是"服务端错误能否落到页面上"，
    //   所以必须先填签收人（否则测的就变成必填拦截了）。
    await w.find('.po-shipment input.po-input').setValue('Alice')
    await markDeliveredBtn(w).trigger('click')
    await flushPromises()

    expect(actionErrorBox(w).exists()).toBe(true)
    expect(actionErrorBox(w).text()).toContain('not in a shippable state')
    w.unmount()
  })

  it('未填签收人 ⇒ 前端直接拦下，不发请求（A-224）', async () => {
    const w = await mountAndOpen(DETAIL_SHIPPED)
    await markDeliveredBtn(w).trigger('click')
    await flushPromises()

    expect(api.markDelivered).not.toHaveBeenCalled()
    expect(actionErrorBox(w).text()).toContain('Received by')
    w.unmount()
  })

  it('按钮飞行中连点两次 ⇒ 只发一次请求', async () => {
    const w = await mountAndOpen(DETAIL_PENDING)
    let resolveFn
    api.markShipped.mockReturnValueOnce(new Promise((res) => { resolveFn = res }))

    const btn = markShippedBtn(w)
    await btn.trigger('click')
    await btn.trigger('click')

    expect(api.markShipped, '★ 连点两次发出了两个标记请求').toHaveBeenCalledTimes(1)
    resolveFn({ data: {} })
    await flushPromises()
    w.unmount()
  })
})

/**
 * ★ S5 P-2（2026-11-20）：队列取数从"拉一页 + 客户端筛"改为"服务端 status__in + 翻页取全"。
 *
 * 原缺陷：`getOrders({page_size:200})` + `filter(status)` ⇒ 队列越过 200 单即**静默漏单**
 * （本地实测 confirmed 全库 94、最新 200 内仅 24 ⇒ 70 单运营看不到，页面还不提示）。
 * 这里钉住页面侧的两条可观测结果：请求参数正确、显示的计数是**服务端总数**。
 */
describe('PoShipmentDesk 队列取数（S5 P-2）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getOrderDetail.mockResolvedValue({ data: DETAIL })
  })

  it('向服务端按状态集合取数（status__in），不再自己 filter', async () => {
    api.getOrders.mockResolvedValue({
      success: true, data: [ORDER], meta: { pagination: { count: 1, next: null } },
    })
    const w = mount(PoShipmentDesk)
    await flushPromises()

    const params = api.getOrders.mock.calls[0][0]
    expect(params.status__in, '★ 队列状态必须交给服务端筛').toBe('confirmed,shipped,in_production')
    expect(params.page_size).toBe(500)
    expect(params.page).toBe(1)
    w.unmount()
  })

  it('★ 显示服务端总数（437），而不是"本页取到几条"', async () => {
    api.getOrders.mockImplementation(async (p) => {
      if (p.page === 1) {
        return {
          success: true,
          data: [ORDER, { ...ORDER, id: 12, order_no: 'ORD-P2-0002' }],
          meta: { pagination: { count: 437, next: '?page=2' } },
        }
      }
      return { success: true, data: [], meta: { pagination: { count: 437, next: null } } }
    })
    const w = mount(PoShipmentDesk)
    await flushPromises()

    expect(w.find('[data-testid="queue-total"]').text()).toBe('(437)')
    // 页面上不该出现"仅显示前 N 单"的错误警告：437 在翻页上限内，已取全
    expect(w.find('[data-testid="queue-truncated"]').exists()).toBe(false)
    w.unmount()
  })

  it('取数失败落在页面上（空表 ≠ 队列为空）', async () => {
    api.getOrders.mockRejectedValue(new Error('boom'))
    const w = mount(PoShipmentDesk)
    await flushPromises()
    expect(w.find('[data-testid="queue-error"]').exists(), '★ 取数失败必须落到页面，不能只弹 3 秒 toast').toBe(true)
    w.unmount()
  })
})

/**
 * A-249：Est. Delivery 从 `<input type="date">` 换成文本框 + 归一化。
 *
 * 实测背景（Edge/zh-CN，真实浏览器）：`type=date` 下手打 `2026-11-27` 会变成
 * `202611-02-07`，手打 `11272026` 直接变空 —— 而全站日期显示都是 YYYY-MM-DD，
 * 运营照屏幕格式打就是打不进去。这里钉住三件事：
 *   ① 手打 ISO 能进、失焦后原样留存；
 *   ② 8 位数字会被归一成 ISO（不逼用户补横杠）；
 *   ③ 看不懂/不存在/有歧义的写法 ⇒ 页内报错且**一个请求都不发**。
 */
describe('PoShipmentDesk Est. Delivery 手打（A-249）', () => {
  const dateInput = (w) => w.find('[data-testid="ship-est-delivery"]')
  const dateErr = (w) => w.find('[data-testid="ship-date-error"]')

  beforeEach(() => {
    vi.clearAllMocks()
    api.createShipment.mockResolvedValue({ data: { id: 1 } })
  })

  async function fillRequired(w) {
    await carrierInput(w).setValue('DHL')
    await trackingInput(w).setValue('TRK-A249')
  }

  it('控件已不是 type=date（否则手打必然被浏览器拆坏）', async () => {
    const w = await mountAndOpen()
    expect(dateInput(w).attributes('type')).toBe('text')
    expect(dateInput(w).attributes('placeholder')).toMatch(/YYYY-MM-DD/)
    w.unmount()
  })

  it('手打 2026-11-27 ⇒ 失焦后原样保留，并随请求发出', async () => {
    const w = await mountAndOpen()
    await fillRequired(w)
    await dateInput(w).setValue('2026-11-27')
    await dateInput(w).trigger('blur')
    expect(dateInput(w).element.value).toBe('2026-11-27')

    await createBtn(w).trigger('click')
    await flushPromises()
    expect(api.createShipment).toHaveBeenCalledTimes(1)
    expect(api.createShipment.mock.calls[0][1].estimated_delivery).toBe('2026-11-27')
    w.unmount()
  })

  it('手打 20261127 ⇒ 归一成 2026-11-27', async () => {
    const w = await mountAndOpen()
    await fillRequired(w)
    await dateInput(w).setValue('20261127')
    await dateInput(w).trigger('blur')
    expect(dateInput(w).element.value).toBe('2026-11-27')
    w.unmount()
  })

  it('★ 有歧义的 03/04/2026 ⇒ 报错且不发请求（不猜是 3 月还是 4 月）', async () => {
    const w = await mountAndOpen()
    await fillRequired(w)
    await dateInput(w).setValue('03/04/2026')
    await createBtn(w).trigger('click')
    await flushPromises()

    expect(api.createShipment, '歧义写法不该被猜着提交').not.toHaveBeenCalled()
    expect(dateErr(w).exists()).toBe(true)
    expect(dateErr(w).text()).toMatch(/YYYY-MM-DD/)
    w.unmount()
  })

  it('★ 2026-02-30（格式对但不存在）⇒ 拦下', async () => {
    const w = await mountAndOpen()
    await fillRequired(w)
    await dateInput(w).setValue('2026-02-30')
    await dateInput(w).trigger('blur')
    expect(dateErr(w).text()).toMatch(/no day 30/)
    await createBtn(w).trigger('click')
    await flushPromises()
    expect(api.createShipment).not.toHaveBeenCalled()
    w.unmount()
  })

  it('留空仍然合法（Est. Delivery 是可选项）', async () => {
    const w = await mountAndOpen()
    await fillRequired(w)
    await createBtn(w).trigger('click')
    await flushPromises()
    expect(api.createShipment).toHaveBeenCalledTimes(1)
    expect(api.createShipment.mock.calls[0][1].estimated_delivery).toBe('')
    w.unmount()
  })
})
