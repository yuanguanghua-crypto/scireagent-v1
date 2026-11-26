/**
 * `InventoryDesk` 的「脱管」反馈与 Tracked 可见性 —— A-260（2026-11-18 / S4）。
 *
 * ## 缺陷（诊断件原文，已在改动前逐行核对过源码）
 * ① `stopTracking()` 失败时只 `toast.error(msg)` —— 3 秒消失，而运营要照着
 *    `available / allocated / reserved_allocations` 三个数去调平库存、释放占用，
 *    抄不下来。后端其实已经把这几个数放在 `meta.error.details[0]` 里了，前端没读。
 * ② 表格按 `Inventory` 行渲染，**没有 Tracked 列**，也不按 `is_stock_tracked` 过滤
 *    ⇒ 已脱管的 SKU（退出缺货校验 ≡ 不限量）和普通库存行长得一模一样。
 * ③ 脱管成功后该行**不会消失**（后端只翻 `SKU.is_stock_tracked`，不动 Inventory 行），
 *    但页面没有任何标记 ⇒ 看起来像"点了没反应"。
 *
 * ## 附带修掉的两处「点了没反应」
 * 已脱管行原本仍渲染 `Stop tracking` 按钮：点了后端是 no-op 却返回 200，
 * 界面毫无变化 —— 正是 QA 报 A-260 的观感来源。现在不渲染该按钮，改显示 `Not tracked`。
 * `submitReceipt` / `submitAdjust` 参数不全时原本静默 `return`（一个请求都不发），
 * 现在给 `toast.warning` 说明缺什么。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const invApi = vi.hoisted(() => ({
  getInventoryList: vi.fn(),
  getInventoryDetail: vi.fn(),
  receiptStock: vi.fn(),
  adjustStock: vi.fn(),
  getTrackedGaps: vi.fn(),
  setStockTracked: vi.fn(),
}))

vi.mock('@/api/inventory', () => invApi)
vi.mock('@/api/products', () => ({
  getProducts: vi.fn().mockResolvedValue({ data: [] }),
  getProductDetail: vi.fn().mockResolvedValue({ data: {} }),
}))

// 确认框：默认返回 true（确认）；单个用例可改
const ask = vi.hoisted(() => vi.fn().mockResolvedValue(true))
vi.mock('@/composables/useConfirm', () => ({ useConfirm: () => ({ ask }) }))

const toast = vi.hoisted(() => ({
  success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(),
}))
vi.mock('@/components/common', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast }
})

import InventoryDesk from '../InventoryDesk.vue'

const TRACKED = {
  id: 901, sku_id: 301, sku_code: 'SKU-TRACKED-1', product_name: 'Tracked Reagent',
  lot_number: null, location: 'MAIN', available: 25, allocated: 0, on_hand: 25,
  is_stock_tracked: true,
}
const UNTRACKED = {
  id: 902, sku_id: 302, sku_code: 'SKU-UNTRACKED-1', product_name: 'Made to Order Reagent',
  lot_number: null, location: 'MAIN', available: 0, allocated: 0, on_hand: 0,
  is_stock_tracked: false,
}

async function mountDesk(rows = [TRACKED, UNTRACKED]) {
  invApi.getInventoryList.mockResolvedValue({ data: rows })
  invApi.getTrackedGaps.mockResolvedValue({ data: { count: 0, items: [] } })
  const w = mount(InventoryDesk)
  await flushPromises()
  return w
}

const rowEl = (w, code) => w.find(`[data-testid="inv-row-${code}"]`)

describe('InventoryDesk Tracked 可见性（A-260 ②③）', () => {
  beforeEach(() => { vi.clearAllMocks(); ask.mockResolvedValue(true) })

  it('已纳管行显示 Yes，且保留 Stop tracking 按钮', async () => {
    const w = await mountDesk()
    const tr = rowEl(w, 'SKU-TRACKED-1')
    expect(tr.find('[data-testid="inv-tracked-yes"]').exists()).toBe(true)
    expect(tr.find('[data-testid="inv-untrack-btn"]').exists()).toBe(true)
    w.unmount()
  })

  it('已脱管行显示 No + 置灰 + 不再给 Stop tracking（点了只会 no-op 返回 200）', async () => {
    const w = await mountDesk()
    const tr = rowEl(w, 'SKU-UNTRACKED-1')
    expect(tr.find('[data-testid="inv-tracked-no"]').exists(), '★ 没有 No 标记 ⇒ 与普通库存行无法区分')
      .toBe(true)
    expect(tr.classes(), '★ 未纳管行没有置灰').toContain('po-row-untracked')
    expect(tr.find('[data-testid="inv-untrack-btn"]').exists(),
      '★ 仍渲染 Stop tracking ⇒ 点击后静默 no-op，正是 QA 报的"点了没反应"').toBe(false)
    expect(tr.find('[data-testid="inv-untracked-note"]').exists()).toBe(true)
    w.unmount()
  })

  it('未纳管行不再叠加"低库存"红底（available=0 是因为不校验库存，不是缺货）', async () => {
    const w = await mountDesk()
    expect(rowEl(w, 'SKU-UNTRACKED-1').classes()).not.toContain('po-row-low')
    w.unmount()
  })
})

describe('InventoryDesk 脱管动作的反馈（A-260 ①）', () => {
  beforeEach(() => { vi.clearAllMocks(); ask.mockResolvedValue(true) })

  it('确认后调接口 + 成功 toast + 重新拉列表（行会带着 No 回来，不消失）', async () => {
    const w = await mountDesk()
    const callsBefore = invApi.getInventoryList.mock.calls.length

    await rowEl(w, 'SKU-TRACKED-1').find('[data-testid="inv-untrack-btn"]').trigger('click')
    await flushPromises()

    expect(invApi.setStockTracked).toHaveBeenCalledWith(TRACKED.sku_id, false)
    expect(toast.success, '脱管成功后没有任何反馈').toHaveBeenCalled()
    expect(invApi.getInventoryList.mock.calls.length, '★ 脱管后没重新拉列表').toBeGreaterThan(callsBefore)
    w.unmount()
  })

  it('确认框取消 ⇒ 一个请求都不发', async () => {
    ask.mockResolvedValueOnce(false)
    const w = await mountDesk()

    await rowEl(w, 'SKU-TRACKED-1').find('[data-testid="inv-untrack-btn"]').trigger('click')
    await flushPromises()

    expect(invApi.setStockTracked).not.toHaveBeenCalled()
    w.unmount()
  })

  it('★ 400 STOCK_NOT_EMPTY ⇒ available/allocated/reserved 三个数落页', async () => {
    invApi.setStockTracked.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          success: false,
          data: null,
          meta: {
            error: {
              code: 'STOCK_NOT_EMPTY',
              message: 'Cannot stop tracking: this SKU still holds stock or allocations '
                + '(available=10, allocated=2, reserved_allocations=1). '
                + 'Clear them first (adjust to 0 / release allocations).',
              details: [{ available: 10, allocated: 2, reserved_allocations: 1 }],
            },
          },
        },
      },
    })
    const w = await mountDesk()

    await rowEl(w, 'SKU-TRACKED-1').find('[data-testid="inv-untrack-btn"]').trigger('click')
    await flushPromises()

    const box = w.find('[data-testid="inv-stop-error"]')
    expect(box.exists(), '★ 被拒后页面上没有持久落位（只有 3 秒 toast）').toBe(true)
    expect(box.find('[data-testid="inv-stop-error-title"]').text()).toContain('SKU-TRACKED-1')
    expect(box.find('[data-testid="inv-stop-available"]').text(),
      '★ 没有把 available 落到页面上 —— 运营没法照着它调平').toBe('10')
    expect(box.find('[data-testid="inv-stop-allocated"]').text()).toBe('2')
    expect(box.find('[data-testid="inv-stop-reserved"]').text()).toBe('1')
    w.unmount()
  })

  it('被拒时不再额外弹 toast.error（拦截器已经弹过一次，避免两条一样的红条）', async () => {
    invApi.setStockTracked.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { success: false, meta: { error: { code: 'STOCK_NOT_EMPTY', message: 'nope' } } },
      },
    })
    const w = await mountDesk()

    await rowEl(w, 'SKU-TRACKED-1').find('[data-testid="inv-untrack-btn"]').trigger('click')
    await flushPromises()

    expect(toast.error, '★ 与 http 拦截器重复弹了同一句错误').not.toHaveBeenCalled()
    w.unmount()
  })

  it('Dismiss 清掉横幅', async () => {
    invApi.setStockTracked.mockRejectedValueOnce({
      response: { status: 400, data: { meta: { error: { message: 'nope' } } } },
    })
    const w = await mountDesk()

    await rowEl(w, 'SKU-TRACKED-1').find('[data-testid="inv-untrack-btn"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="inv-stop-error"]').exists()).toBe(true)

    await w.find('[data-testid="inv-stop-error-dismiss"]').trigger('click')
    expect(w.find('[data-testid="inv-stop-error"]').exists()).toBe(false)
    w.unmount()
  })
})
