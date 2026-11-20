/**
 * 运营台 / 门户「服务端筛选 + 翻页取全」取数。
 *
 * ## 为什么需要它（S5 P-2，2026-11-20）
 * 两个运营台（Shipment Desk / Invoicing Desk）此前都是：
 * ```
 * const res = await getOrders({ page_size: 200 })
 * orders.value = all.filter(o => QUEUE_STATUSES.includes(o.status))
 * ```
 * 即 **拉一页、再在客户端按状态筛**。`status` 精确匹配一次只能筛一个状态，
 * 所以只能整页拉回来自己筛 —— 于是埋了一个**静默漏单**：
 *
 *   本地 dev 库只读实测（`Order` 全库 1124 条）：
 *     confirmed 全库 94、最新 200 条内 24 ⇒ **被挤出 200 的 70 单**
 *
 * 这 70 单既进不了待发货队列、也进不了待开票队列，**页面还不会提示"只显示最近 200 单"**。
 * 只要历史累计单量越过 `page_size` 就开始漏，而且**越用越漏**。
 *
 * ## 同族缺陷（同日一并修）
 * - `PoOrgManagement.vue`：`getOrgOrders(org.id, {page_size:100})` 无翻页
 *   ⇒ 本地 org 4 有 **1123** 单，按机构查单**漏 1023**。
 * - `PoDownloadCenter.vue`：`page_size:100` 后再客户端筛 `invoice || attachments`
 *   ⇒ 全库有发票的 267 单里，落在最新 100 单之外的**根本不出现**，
 *   页面还显示 "No downloadable documents yet"（看起来像"确实没有文档"）。
 *
 * 三处的病根是同一个：**把"全量"交给了一页**。
 *
 * ## 现在的做法
 * 队列语义交回服务端：`?status__in=a,b`（后端 `OrderFilter` 逐值校验）/
 * `?has_documents=1` / `?organization_id=`，再按页循环取到「已取条数 ≥ 总数」为止。
 * 判据用 `count` 而不是 `next` URL：`count` 是队列真值，`all.length >= count` 语义更直白。
 *
 * `truncated`：极端情况下（单队列超过 `maxPages × pageSize`）会停下并**如实上报**，
 * 由页面显示"仅显示前 N 条" —— 宁可说清楚，也不再静默截断。
 */
import { getOrders } from '@/api/adminPo'

/** 单页条数：后端 `StandardPagination.max_page_size = 500`，取满以少跑几趟。 */
export const QUEUE_PAGE_SIZE = 500
/** 翻页上限：40 × 500 = 20,000 条；超过则停并置 `truncated`。 */
export const QUEUE_MAX_PAGES = 40

/** 兼容两种信封形状（P2-1 已知：分页 meta 有 3 套写法并存）。 */
function unwrap(res) {
  const body = res || {}
  const data = body.data
  const rows = Array.isArray(data) ? data : (data?.results || [])
  const pag = body.meta?.pagination || (Array.isArray(data) ? {} : (data || {})) || {}
  const count = typeof pag.count === 'number' ? pag.count : rows.length
  return { rows, count }
}

/**
 * 按任意查询参数把订单**取全**（服务端筛选 + 翻页）。
 *
 * ⚠️ `getOrders` / `getMyOrders`（`api/poPortal`）/ `getOrgOrders`（`api/adminPo`）
 * 打的都是同一个 `/orders/`，区别只是预置参数不同；这里统一走 `getOrders`，
 * 把「谁的订单」交给 `get_queryset()`（客户只在自己的单里筛，不构成提权面）。
 *
 * @param {object} [params] 透传给列表接口的查询参数（`status__in` / `has_documents` / `organization_id` …）
 * @param {{pageSize?:number, maxPages?:number}} [opts]
 * @returns {Promise<{orders:Array, total:number, truncated:boolean}>}
 */
export async function fetchAllOrderPages(params = {}, opts = {}) {
  const pageSize = opts.pageSize || QUEUE_PAGE_SIZE
  const maxPages = opts.maxPages || QUEUE_MAX_PAGES
  const all = []
  let total = 0

  for (let page = 1; page <= maxPages; page += 1) {
    // eslint-disable-next-line no-await-in-loop
    const res = await getOrders({ ...params, page_size: pageSize, page })
    const { rows, count } = unwrap(res)
    total = count
    all.push(...rows)
    // 空页 = 服务端没有更多（也防 count 与实际不一致时死循环）
    if (rows.length === 0 || all.length >= total) {
      return { orders: all, total, truncated: false }
    }
  }
  return { orders: all, total, truncated: true }
}

/**
 * 取某个状态集合的**全部**订单。
 *
 * @param {string[]} statuses 状态集合，如 `['confirmed','shipped','in_production']`
 * @param {{pageSize?:number, maxPages?:number}} [opts]
 * @returns {Promise<{orders:Array, total:number, truncated:boolean}>}
 */
export async function fetchOrderQueue(statuses, opts = {}) {
  return fetchAllOrderPages({ status__in: (statuses || []).join(',') }, opts)
}
