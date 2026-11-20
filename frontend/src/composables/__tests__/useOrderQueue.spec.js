/**
 * `fetchOrderQueue` —— 服务端状态筛 + 翻页取全（S5 P-2 的核心逻辑）。
 *
 * ## 钉住的是什么
 * 原实现 `getOrders({page_size:200})` + 客户端 `filter(status)` ⇒ 队列**越过 200 单即静默漏单**
 * （本地实测 confirmed 全库 94、最新 200 内 24 ⇒ 漏 70）。本文件用**纯单测**钉住三件事：
 *   ① 请求真的带上了 `status__in`（队列语义在服务端，不在浏览器里）；
 *   ② 总数超过单页时会**继续翻页**，最终取到的条数 = 队列真值（不再有 200 天花板）；
 *   ③ 翻页上限与"空页"两种终点都必须**停得住**（不能死循环），且截断要如实上报。
 *
 * 真闸门在服务端：`backend/apps/transactions/tests/test_order_status_in_filter.py`。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const api = vi.hoisted(() => ({ getOrders: vi.fn() }))
vi.mock('@/api/adminPo', () => api)

const { fetchOrderQueue, fetchAllOrderPages, QUEUE_PAGE_SIZE, QUEUE_MAX_PAGES } =
  await import('@/composables/useOrderQueue')

/** 造一个后端信封：`{success, data:[...], meta:{pagination:{count, next}}}` */
function envelope(total, page, pageSize) {
  const start = (page - 1) * pageSize
  const rows = []
  for (let i = start; i < Math.min(start + pageSize, total); i += 1) rows.push({ id: i + 1 })
  const hasNext = start + rows.length < total
  return {
    success: true,
    data: rows,
    meta: { pagination: { count: total, page, page_size: pageSize, next: hasNext ? `?page=${page + 1}` : null } },
  }
}

/** 按请求里的 page/status__in 直接算出该页，模拟服务端。 */
function mockServer(total) {
  api.getOrders.mockImplementation(async (params) => {
    return envelope(total, params.page || 1, params.page_size || QUEUE_PAGE_SIZE)
  })
}

beforeEach(() => {
  api.getOrders.mockReset()
})

describe('fetchOrderQueue', () => {
  it('请求带上 status__in，且队列语义交给服务端', async () => {
    mockServer(2)
    await fetchOrderQueue(['confirmed', 'shipped'])
    expect(api.getOrders).toHaveBeenCalledTimes(1)
    const params = api.getOrders.mock.calls[0][0]
    expect(params.status__in).toBe('confirmed,shipped')
    // 客户端不再自己 filter（旧实现在这里做 filter）—— 取回什么就是什么
    expect(params.page).toBe(1)
  })

  it('★ 队列超过 200 张也能取全（原来 200 是天花板）', async () => {
    mockServer(437)
    const { orders, total, truncated } = await fetchOrderQueue(['confirmed'])
    expect(orders.length, '437 张 confirmed 必须一张不少地取到').toBe(437)
    expect(total).toBe(437)
    expect(truncated).toBe(false)
    // 437 / 500 单页 ⇒ 1 趟就够；这里真正要证明的是"没有 200 的硬上限"
    expect(api.getOrders.mock.calls.length).toBe(1)
  })

  it('总数大于单页时继续翻页，直到凑满 count', async () => {
    mockServer(1200)
    const { orders, total, truncated } = await fetchOrderQueue(['delivered', 'invoiced'], { pageSize: 500 })
    expect(orders.length).toBe(1200)
    expect(total).toBe(1200)
    expect(truncated).toBe(false)
    expect(api.getOrders.mock.calls.length).toBe(3) // 500 + 500 + 200
    // 每页参数逐趟递增，且状态集合不变
    expect(api.getOrders.mock.calls.map((c) => c[0].page)).toEqual([1, 2, 3])
    expect(api.getOrders.mock.calls.every((c) => c[0].status__in === 'delivered,invoiced')).toBe(true)
  })

  it('超过翻页上限时停下并如实上报 truncated', async () => {
    mockServer(100000)
    const { orders, total, truncated } = await fetchOrderQueue(['confirmed'], { pageSize: 10, maxPages: 3 })
    expect(truncated, '超上限必须显式上报，不能假装取全').toBe(true)
    expect(orders.length).toBe(30)
    expect(total).toBe(100000)
    expect(api.getOrders.mock.calls.length).toBe(3)
  })

  it('空页即停（count 与实际不一致时也不会死循环）', async () => {
    // count 说 999，但服务端只给得出 2 条 ⇒ 第二趟是空页
    api.getOrders.mockImplementation(async (params) => {
      if (params.page === 1) {
        return { success: true, data: [{ id: 1 }, { id: 2 }], meta: { pagination: { count: 999, next: '?page=2' } } }
      }
      return { success: true, data: [], meta: { pagination: { count: 999, next: null } } }
    })
    const { orders, truncated } = await fetchOrderQueue(['confirmed'], { pageSize: 2 })
    expect(orders.length).toBe(2)
    expect(truncated).toBe(false)
    expect(api.getOrders.mock.calls.length).toBe(2)
  })

  it('兼容旧信封形状（data.results + data.count）', async () => {
    api.getOrders.mockResolvedValue({
      success: true,
      data: { count: 1, next: null, results: [{ id: 9 }] },
      meta: {},
    })
    const { orders, total } = await fetchOrderQueue(['confirmed'])
    expect(orders).toEqual([{ id: 9 }])
    expect(total).toBe(1)
  })

  it('缺 count 时退化为"只取到的这些"，不至于死循环', async () => {
    api.getOrders.mockResolvedValue({ success: true, data: [{ id: 1 }], meta: {} })
    const { orders, total, truncated } = await fetchOrderQueue(['confirmed'])
    expect(orders.length).toBe(1)
    expect(total).toBe(1)
    expect(truncated).toBe(false)
    expect(api.getOrders.mock.calls.length).toBe(1)
  })

  it('默认上限常量与后端分页上限一致（防止两处漂移）', () => {
    expect(QUEUE_PAGE_SIZE).toBe(500) // backend/apps/core/pagination.py max_page_size
    expect(QUEUE_MAX_PAGES).toBe(40)
  })
})

/**
 * `fetchAllOrderPages` —— 同一套取数骨架，供**非状态队列**的调用方复用
 * （机构管理台的按机构查单、下载中心的"有发票/附件"）。
 *
 * 这两处原先都是「拉一页 + 客户端筛」的受害者：
 *   - `PoOrgManagement`：`page_size:100` 且无翻页 ⇒ 本地 org 4 有 1123 单，漏 1023；
 *   - `PoDownloadCenter`：`page_size:100` 再筛 ⇒ 全库 267 张有发票的单，
 *     落在最新 100 单之外的客户根本看不到。
 */
describe('fetchAllOrderPages', () => {
  it('参数原样透传，且不会凭空注入 status__in', async () => {
    mockServer(3)
    await fetchAllOrderPages({ has_documents: 1 })
    const params = api.getOrders.mock.calls[0][0]
    expect(params.has_documents).toBe(1)
    expect(params).not.toHaveProperty('status__in')
    expect(params.page).toBe(1)
    expect(params.page_size).toBe(QUEUE_PAGE_SIZE)
  })

  it('按机构查单：1123 单必须全取到（原来只取 100）', async () => {
    mockServer(1123)
    const { orders, total, truncated } = await fetchAllOrderPages({ organization_id: 4 })
    expect(orders.length).toBe(1123)
    expect(total).toBe(1123)
    expect(truncated).toBe(false)
    expect(api.getOrders.mock.calls.map((c) => c[0].page)).toEqual([1, 2, 3])
    expect(api.getOrders.mock.calls.every((c) => c[0].organization_id === 4)).toBe(true)
  })

  it('下载中心：267 张有文档的单取全（原来只看最新 100 单里碰运气）', async () => {
    mockServer(267)
    const { orders, total } = await fetchAllOrderPages({ has_documents: 1 })
    expect(orders.length).toBe(267)
    expect(total).toBe(267)
    expect(api.getOrders.mock.calls.every((c) => c[0].has_documents === 1)).toBe(true)
  })

  it('超上限同样如实上报 truncated', async () => {
    mockServer(1000)
    const { orders, truncated } = await fetchAllOrderPages({ has_documents: 1 }, { pageSize: 10, maxPages: 2 })
    expect(orders.length).toBe(20)
    expect(truncated).toBe(true)
  })
})
