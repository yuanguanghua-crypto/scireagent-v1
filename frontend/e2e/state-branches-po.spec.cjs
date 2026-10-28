/**
 * 阶段 7 · 维度 S（状态分支）—— PO 域 **按页面** 的状态穷举
 *
 * ## 与 state-matrix.spec.cjs 的分工
 * `state-matrix.spec.cjs` 把所有 PO 态都压在一个页面（`/ops/orders/:id`）上按态穷举；
 * 审计脚本 `scripts/audit_7d_auto.py` 判 S 维的依据是「该页出现在状态矩阵 spec 里」
 * ⇒ 其余 PO 页面一律判 ✗。本文件把这 8 个页面**各自真实存在的状态分支**走一遍。
 *
 * ## 覆盖的页面（`path:` 字面量同时是 goto 依据，也是审计的数据源）
 *   /po/submit            PoSubmit          未加行项目 / 行项目缺 SKU / 成功横幅 / reorder 预填 vs 空表单
 *   /po/orders            PoOrderList       空态（in_production 死态筛选）/ 有数据 / 筛选生效
 *   /po/orders/:id        PoOrderDetail     无发货单 vs 有发货单 / 未开票 vs 已开票 / 时间线空与非空
 *   /ops/orders           AdminOrdersPage   空态（搜索无命中）/ 有数据 / 状态筛选
 *   /ops/orders/:id       AdminOrderDetail  .ship-form vs .pay-form 的表单级分支（按钮集已由 state-matrix 覆盖）
 *   /ops/po/review        PoReviewDesk      待审卡片 / 缺货高亮 / Appove 后离场（已审）
 *   /ops/po/shipments     PoShipmentDesk    无发货单 → 已建发货单 → 已发货（Mark Delivered 出现）
 *   /ops/po/invoicing     PoInvoicingDesk   未开票 → 已开票（Record Payment 表单出现）
 *
 * ## 纪律
 *  - 拟人化：页面上的状态迁移一律从 UI 点（Approve / Create Shipment / Mark Shipped / Issue Invoice）；
 *    只有**造夹具的前置状态**走 API，且每处都标了「夹具前置，不属于被测路径」。
 *  - 禁止断言绝对数量、禁止 snapshotDb() 的 Δ 断言；只断言我自己造的那一单（PO 号前缀 `E2E-ST-<ts>`）。
 *  - 选择器均来自源码，注释里给 `文件:行号`。
 *  - **quoted 是粘性态**（`quoted → cancelled` 状态机不允许，实测 400 INVALID_TRANSITION），
 *    本文件不使用 quoted 夹具；用到的态（po_received/confirmed/delivered/invoiced）都可取消 ⇒ 零残留。
 *
 * ## 运行
 *   cd frontend
 *   npx playwright test e2e/state-branches-po.spec.cjs --project=chromium \
 *     --reporter=line --output=/tmp/pw-stB > /tmp/pw-stB.log 2>&1; echo "EXIT=$?"
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, ADMIN_USER, ADMIN_PASS, CUST_USER, CUST_PASS } = require('./helpers/auth.cjs')
const { apiContext, getToken, getSession } = require('./helpers/api.cjs')
const { dbExec } = require('./helpers/db-write.cjs')
const h = require('./helpers/poHelpers.cjs')

const RUN_TS = Date.now()
const MARK = `E2E-ST-${RUN_TS}` // 本轮唯一标记：所有夹具 PO 号 = `${MARK}-<k>`

/**
 * 页面清单 —— `path` 必须是字面量：审计脚本用 `re.findall(r"path:\s*'([^']+)'")` 扫描。
 */
const PAGES = {
  poSubmit: { name: 'PoSubmit', path: '/po/submit' },
  poOrders: { name: 'PoOrderList', path: '/po/orders' },
  poOrderDetail: { name: 'PoOrderDetail', path: '/po/orders/:id', base: '/po/orders' },
  opsOrders: { name: 'AdminOrdersPage', path: '/ops/orders' },
  opsOrderDetail: { name: 'AdminOrderDetail', path: '/ops/orders/:id', base: '/ops/orders' },
  poReview: { name: 'PoReviewDesk', path: '/ops/po/review' },
  poShipments: { name: 'PoShipmentDesk', path: '/ops/po/shipments' },
  poInvoicing: { name: 'PoInvoicingDesk', path: '/ops/po/invoicing' },
}

const createdOrderIds = []
let adminToken = null
let custToken = null
let prod = null
let reqCtx = null

test.beforeAll(async () => {
  reqCtx = await request.newContext()
  // getToken 按 username 缓存（DRF token 不过期）⇒ 整轮只真正登录 1 次/账号，
  // 不撞后端 LoginRateThrottle = 5 次/分钟/IP（helpers/api.cjs:129-133）。
  adminToken = await getToken(reqCtx, ADMIN_USER, ADMIN_PASS)
  custToken = await getToken(reqCtx, CUST_USER, CUST_PASS)
  prod = await h.getProductWithSku(custToken)
  expect(prod?.id && prod?.sku?.id, '需要至少一个带 SKU 的真实产品做 PO 夹具').toBeTruthy()
})

test.afterAll(async () => {
  // 先走产品自己的清理路径（cancel），再按 id + 本轮标记硬删（cancel 只改状态、行仍留库）
  let cancelled = 0
  for (const id of createdOrderIds) {
    if (await h.cancelOrder(custToken, adminToken, id)) cancelled += 1
  }
  if (createdOrderIds.length) {
    const py =
      "import json\nfrom django.db import models\nfrom apps.transactions.models import Order\n" +
      `ids = ${JSON.stringify(createdOrderIds)}\nm = ${JSON.stringify(MARK)}\n` +
      "q1 = Order.objects.filter(id__in=ids)\nn1 = q1.count(); q1.delete()\n" +
      "q2 = Order.objects.filter(models.Q(po_number__startswith=m) | models.Q(shipping_name__startswith=m))\n" +
      "n2 = q2.count(); q2.delete()\n" +
      "print('__SNAP__' + json.dumps({'deletedById': n1, 'deletedByMarker': n2}))"
    console.log('__E2E__ CLEANUP_ORDERS ' + JSON.stringify({ created: createdOrderIds.length, cancelled, ...dbExec(py, 'cleanup-orders') }))
  }
  if (reqCtx) await reqCtx.dispose().catch(() => {})
})

/* ── 通用小工具 ──────────────────────────────────────────────────────── */

const go = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })

/** 注入会话（同 helpers/auth.cjs:73-108；前端只认 localStorage 的 token/is_staff/role） */
async function asUser(page, username, password) {
  const session = await getSession(page.request, username, password)
  await page.addInitScript((s) => {
    try {
      localStorage.setItem('token', s.token)
      localStorage.setItem('is_staff', String(s.isStaff))
      localStorage.setItem('role', s.role || '')
    } catch {
      /* about:blank ⇒ 忽略 */
    }
  }, session)
  await go(page, '/')
  await page.waitForFunction(() => !!(localStorage.getItem('token') || '').trim(), null, { timeout: 30000 })
  return session
}
const asStaff = (page) => asUser(page, ADMIN_USER, ADMIN_PASS)
const asCustomer = (page) => asUser(page, CUST_USER, CUST_PASS)

/** 夹具：API 建一个指定状态的 PO（**夹具前置，不属于被测路径**）；返回 { id, order_no } */
async function fixturePo(key, { qty = 1 } = {}) {
  const po = await h.submitPoApi(custToken, {
    poNumber: `${MARK}-${key}`,
    productId: prod.id,
    skuId: prod.sku.id,
    qty,
    price: '12.00',
  })
  expect(po?.id, `夹具 PO ${key} 应建成功`).toBeTruthy()
  createdOrderIds.push(po.id)
  return po
}

/* ══════════════════════════════════════════════════════════════════════
 * 1) /po/submit
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@po-submit PO 提交页的状态分支', { tag: ['@local-only'] }, () => {
  test('未加行项目 ⇒ 原生 alert「Add at least one line item.」，无成功横幅、零写入', { tag: ['@readonly'] }, async ({ page }) => {
    await asCustomer(page)
    await go(page, PAGES.poSubmit.path)
    await expect(page.getByRole('button', { name: 'Submit PO' })).toBeVisible({ timeout: 30000 })
    // 空表单态：PoSubmit.vue:326 `<p v-else class="po-muted">No line items yet.</p>`
    await expect(page.getByText('No line items yet.')).toBeVisible()

    // PoSubmit.vue:147-150 —— items 为空时 alert 并 return（不发请求）
    let msg = null
    const onDialog = async (d) => {
      msg = d.message()
      await d.dismiss()
    }
    page.on('dialog', onDialog)
    let posted = 0
    const onReq = (r) => {
      if (/\/api\/v1\/orders\/po\/?$/.test(r.url())) posted += 1
    }
    page.on('request', onReq)
    await page.getByRole('button', { name: 'Submit PO' }).click()
    await expect.poll(() => msg, { timeout: 10000 }).toBe('Add at least one line item.')
    page.off('dialog', onDialog)
    page.off('request', onReq)
    expect(posted, '空行项目不应发出提交请求').toBe(0)
    await expect(page.locator('.po-callout')).toHaveCount(0)
  })

  test('有行项目但未选 SKU ⇒ alert「Each line item requires a SKU, quantity and unit price.」', { tag: ['@readonly'] }, async ({ page }) => {
    await asCustomer(page)
    await go(page, PAGES.poSubmit.path)
    await page.locator('.po-btn', { hasText: '+ Add Line Item' }).click() // PoSubmit.vue:327
    await expect(page.locator('.po-table tbody tr')).toHaveCount(1)

    // PoSubmit.vue:151-155 —— skuId/quantity/unitPrice 任一为空即 alert 并 return
    let msg = null
    const onDialog = async (d) => {
      msg = d.message()
      await d.dismiss()
    }
    page.on('dialog', onDialog)
    await page.getByRole('button', { name: 'Submit PO' }).click()
    await expect.poll(() => msg, { timeout: 10000 }).toBe('Each line item requires a SKU, quantity and unit price.')
    page.off('dialog', onDialog)
    await expect(page.locator('.po-callout')).toHaveCount(0)
  })

  test('reorder 预填态 vs 空表单态：?reorder=<id> 带入行项目与收货信息，不带则空', { tag: ['@write'] }, async ({ page }) => {
    const po = await fixturePo('REORDER', { qty: 2 }) // 夹具前置
    const detail = await h.getOrder(adminToken, po.id)

    await asCustomer(page)

    // ① 空表单态（不带到 reorder）：无行项目
    await go(page, PAGES.poSubmit.path)
    await expect(page.getByText('No line items yet.')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.po-table tbody tr')).toHaveCount(0)

    // ② 预填态：PoSubmit.vue:18-24 onMounted 读 route.query.reorder → loadReorder（:118-144）
    await go(page, `${PAGES.poSubmit.path}?reorder=${po.id}`)
    await expect(page.locator('.po-table tbody tr').first()).toBeVisible({ timeout: 30000 })
    // :123 明确把 PO Number 清空（换单必须重填）
    await expect(page.locator('#po-f1')).toHaveValue('')
    // 收货信息按原单带入（:126-127）
    if (detail.shipping_name) await expect(page.locator('#po-f6')).toHaveValue(detail.shipping_name)
    // 行项目数量与原单一致（只断言我自己的夹具：1 行）
    await expect(page.locator('.po-table tbody tr')).toHaveCount(1)
    await expect(page.locator('.po-table tbody tr input[type="number"]').first()).toHaveValue('2')
  })

  test('真实提交成功 ⇒ 成功横幅出现并带 order_no（随后取消清理）', { tag: ['@write'] }, async ({ page }) => {
    await asCustomer(page)
    await go(page, PAGES.poSubmit.path)

    // UI 全流程：加行 → 搜产品 → 选产品 → 选 SKU → 提交（PoSubmit.vue:59-99 / :290-318）
    await page.locator('.po-btn', { hasText: '+ Add Line Item' }).click()
    const row = page.locator('.po-table tbody tr').first()
    const searchInput = row.locator('input.po-input').first() // :292-296（placeholder = 'Search product…'）
    await searchInput.fill(prod.name.slice(0, 12))
    const hit = page.locator('.po-search-item').first() // :298-308
    await expect(hit).toBeVisible({ timeout: 20000 })
    await hit.click()

    const skuSelect = row.locator('select.po-select') // :312-318
    await expect(skuSelect).toBeEnabled({ timeout: 20000 })
    await skuSelect.selectOption({ index: 1 })
    // onSkuChange 带出单价（:101-104）⇒ 第 3 个 po-input（Price）应被填上；数量保持默认 1
    await expect(row.locator('input.po-input').nth(2)).not.toHaveValue('')

    await page.locator('#po-f1').fill(`${MARK}-UI`) // PO Number
    await page.locator('#po-f6').fill('E2E Recipient')
    await page.locator('#po-f8').fill('1 E2E Way, Test City')
    await page.locator('#po-f9').fill('e2e@lab.edu')

    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && /\/api\/v1\/orders\/po\/?$/.test(r.url()),
        { timeout: 45000 },
      ),
      page.getByRole('button', { name: 'Submit PO' }).click(),
    ])
    console.log('__E2E__ POSUBMIT ' + JSON.stringify({ status: resp.status() }))
    expect(resp.status(), '真实提交应 2xx').toBeLessThan(300)

    // 成功态：PoSubmit.vue:196-201 成功横幅 + order_no
    const callout = page.locator('.po-callout')
    await expect(callout).toBeVisible({ timeout: 20000 })
    await expect(callout).toContainText('PO submitted successfully')
    await expect(callout.locator('.po-mono')).toHaveText(/^ORD-[0-9A-Za-z]+(-[0-9A-Za-z]+)*$/)
    await expect(page.getByRole('link', { name: 'View My Orders' })).toBeVisible()

    // 记录 id 供清理（按 PO 号回查，只认我自己填的唯一 PO 号）
    const id = await h.findOrderIdByPo(adminToken, `${MARK}-UI`)
    expect(id, '提交后应能按 PO 号回查到订单').toBeTruthy()
    createdOrderIds.push(id)
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 2) /po/orders
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@po-orders PO 列表页的状态分支', { tag: ['@local-only'] }, () => {
  test('筛选 in_production（后端死态）⇒ 空态「No purchase orders found.」；切回 All ⇒ 我造的单可见（反向）', { tag: ['@write'] }, async ({ page }) => {
    const po = await fixturePo('LIST') // 夹具前置：po_received
    const order = await h.getOrder(adminToken, po.id)

    await asCustomer(page)
    await go(page, PAGES.poOrders.path)
    const row = page.locator('.po-table tbody tr', { hasText: order.order_no })
    await expect(row).toHaveCount(1, { timeout: 30000 }) // 有数据态

    // 空态：PoOrderList.vue:75-76 `v-else` ⇒ `.po-empty` "No purchase orders found."
    //   选 in_production 的理由（确定性）：后端**没有任何端点**能把订单推进到 in_production
    //   （见 state-matrix.spec.cjs:6-8 的实证），该态永远 0 条 ⇒ 空态可复现，且不会因为
    //   别人并发造单而假失败。
    const filter = page.locator('select[aria-label="Filter orders by status"]') // :38
    await filter.selectOption({ label: 'In Production' })
    await expect(page.locator('.po-empty')).toHaveText('No purchase orders found.')
    await expect(page.locator('.po-table')).toHaveCount(0)

    // 反向：切回 All（PoOrderList.vue:16 传空 params）⇒ 我的单回来了
    await filter.selectOption({ label: 'All' })
    await expect(page.locator('.po-table tbody tr', { hasText: order.order_no })).toHaveCount(1, { timeout: 20000 })
  })

  test('状态筛选真的生效：选 PO Received ⇒ 我的行保留且全部可见行都是 po received；选 Cancelled ⇒ 我的行消失（反向）', { tag: ['@write'] }, async ({ page }) => {
    const po = await fixturePo('FILTER') // 夹具前置：po_received
    const order = await h.getOrder(adminToken, po.id)

    await asCustomer(page)
    await go(page, PAGES.poOrders.path)
    await expect(page.locator('.po-table tbody tr', { hasText: order.order_no })).toHaveCount(1, { timeout: 30000 })

    const filter = page.locator('select[aria-label="Filter orders by status"]')
    await filter.selectOption({ label: 'PO Received' })
    // StatusBadge 文案 = formatStatus(status)（PoOrderList.vue:62；poConstants.js:47-49）
    const myRow = page.locator('.po-table tbody tr', { hasText: order.order_no })
    await expect(myRow).toHaveCount(1, { timeout: 20000 })
    await expect(myRow.locator('.po-badge')).toHaveText('Po Received')
    // 筛选生效：当前页所有徽章都应是 Po Received（不断数量，只断「没有别的状态混进来」）
    const all = page.locator('.po-table tbody tr .po-badge')
    const n = await all.count()
    for (let i = 0; i < n; i++) await expect(all.nth(i)).toHaveText('Po Received')

    // 反向：切到 Cancelled ⇒ 我的 po_received 单必须消失（状态筛选没写错）
    await filter.selectOption({ label: 'Cancelled' })
    await expect(page.locator('.po-table tbody tr', { hasText: order.order_no })).toHaveCount(0, { timeout: 20000 })
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 3) /po/orders/:id
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@po-order-detail PO 详情页的状态分支', { tag: ['@local-only'] }, () => {
  test('无发货单 ⇒ 无 Shipments 区块、无 Invoice 区块；已发货 ⇒ Shipments(1)；已开票 ⇒ Invoice 区块（三态对比）', { tag: ['@write'] }, async ({ page }) => {
    // 夹具前置（三种状态，均非被测路径）：
    const poNew = await fixturePo('D-NEW') // po_received：无发货、无发票
    const poShipped = await h.seedDelivered(custToken, adminToken) // 已建发货单 + 已签收，未开票
    createdOrderIds.push(poShipped.id)
    const poInvoiced = await h.seedInvoiced(custToken, adminToken) // 已开票
    createdOrderIds.push(poInvoiced.id)

    await asCustomer(page)
    const shipTitle = page.locator('.po-section-title', { hasText: /^Shipments \(\d+\)$/ }) // PoOrderDetail.vue:127-128
    const invTitle = page.locator('.po-section-title', { hasText: 'Invoice' }) // :115-116

    // ① 新单：两个区块都不存在（反向）
    await go(page, `${PAGES.poOrderDetail.base}/${poNew.id}`)
    await expect(page.locator('.po-page-title')).toContainText('Order ORD-', { timeout: 30000 })
    await expect(shipTitle).toHaveCount(0)
    await expect(invTitle).toHaveCount(0)
    // 顶部状态徽章 = order.status 原样（下划线换空格，PoOrderDetail.vue:49）
    await expect(page.locator('.po-page-header .po-badge')).toHaveText('Po Received')
    // 时间线：至少 1 条（PoOrderDetail.vue:170-181；提交即产生 StatusLog）
    await expect(page.locator('.po-timeline-item').first()).toBeVisible()

    // ② 已发货未开票：Shipments 区块在、Invoice 区块仍不在（反向）
    const shipped = await h.getOrder(adminToken, poShipped.id)
    expect(shipped.shipments?.length, '夹具应有发货单').toBeGreaterThan(0)
    await go(page, `${PAGES.poOrderDetail.base}/${poShipped.id}`)
    await expect(shipTitle).toHaveText(`Shipments (${shipped.shipments.length})`, { timeout: 30000 })
    await expect(page.locator('.po-shipment').first()).toBeVisible()
    await expect(invTitle).toHaveCount(0)

    // ③ 已开票：Invoice 区块在（含发票号 + Download PDF）
    const invoiced = await h.getOrder(adminToken, poInvoiced.id)
    expect(invoiced.invoice, '夹具应已开票').toBeTruthy()
    await go(page, `${PAGES.poOrderDetail.base}/${poInvoiced.id}`)
    await expect(invTitle).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.po-tag').first()).toHaveText(invoiced.invoice.invoice_no)
    await expect(page.getByRole('button', { name: 'Download PDF' })).toBeVisible()
    await expect(shipTitle).toBeVisible()
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 4) /ops/orders
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@ops-orders 订单管理列表页的状态分支', { tag: ['@local-only'] }, () => {
  test('搜索无命中 ⇒ 空态「No orders found」；清空搜索 ⇒ 我的单回来（反向）', { tag: ['@write'] }, async ({ page }) => {
    const po = await fixturePo('OPS-EMPTY') // 夹具前置
    const order = await h.getOrder(adminToken, po.id)

    await asStaff(page)
    await go(page, PAGES.opsOrders.path)

    // 有数据：我的单在列表（AdminOrdersPage.vue:90-103）
    await expect(page.locator('.order-row', { hasText: order.order_no })).toHaveCount(1, { timeout: 30000 })

    // 空态：搜索一个必然不存在的单号（后端 search 走 order_no/po_number icontains，admin_order_views.py:32-35）
    // AdminOrdersPage.vue:66-68 搜索框 + :106 EmptyState title="No orders found"
    await page.locator('.filters input.search-input').fill(`E2E-NOPE-${RUN_TS}`)
    await page.locator('.filters button.search-btn').click()
    await expect(page.locator('.empty-state .empty-title')).toHaveText('No orders found')
    await expect(page.locator('.order-row')).toHaveCount(0)

    // 反向：清空搜索 ⇒ 行回来
    await page.locator('.filters input.search-input').fill('')
    await page.locator('.filters button.search-btn').click()
    await expect(page.locator('.order-row', { hasText: order.order_no })).toHaveCount(1, { timeout: 20000 })
  })

  test('状态筛选：我的 confirmed 单在 Confirmed 下出现、在 Quote Pending 下消失（反向），徽章文案随状态', { tag: ['@write'] }, async ({ page }) => {
    // ★ 为什么用 confirmed 而不是 po_received：
    //   本用例写于 **D4 修复之前**：当时 `AdminOrdersPage.vue` 的状态下拉只有 legacy 那 9 个值，
    //   没有 po_received / delivered / cancelled / in_production ⇒ 无法按 PO 流程态筛选。
    //   D4 已于 2026-10-21 修好（下拉改由 `poConstants` 统一提供，已含全部 PO 流程态，
    //   正向/反向筛选的验证见 `order-status-filters.spec.cjs`）。
    //   这里仍用 confirmed 做**状态分支**（confirmed 是 PO 流程里的一环），断言不变。
    const po = await h.seedApproved(custToken, adminToken) // 夹具前置：po_received → confirmed
    createdOrderIds.push(po.id)
    const order = await h.getOrder(adminToken, po.id)
    expect(order.status).toBe('confirmed')

    await asStaff(page)
    await go(page, PAGES.opsOrders.path)
    const filter = page.locator('select[aria-label="Filter orders by status"]') // :53
    const row = page.locator('.order-row', { hasText: order.order_no })

    await filter.selectOption('confirmed')
    await expect(row).toHaveCount(1, { timeout: 20000 })
    // getStatusLabel：下划线→空格+首字母大写（:20-22）
    await expect(row.locator('.status-badge')).toHaveText('Confirmed')

    await filter.selectOption('quote_pending')
    await expect(row, 'confirmed 单不应出现在 Quote Pending 筛选下').toHaveCount(0, { timeout: 20000 })
    // 反向再回来，确认不是「筛选后列表整体空白」
    await filter.selectOption('confirmed')
    await expect(row).toHaveCount(1, { timeout: 20000 })
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 5) /ops/orders/:id —— 只补 state-matrix 没断的「表单级」分支
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@ops-order-detail 内部订单详情页的表单级状态分支', { tag: ['@local-only'] }, () => {
  test('confirmed ⇒ .ship-form 在、.pay-form 不在；invoiced ⇒ .pay-form 在；quote_pending ⇒ .quote-form 在（三种表单块互斥）', { tag: ['@write'] }, async ({ page }) => {
    const poConfirmed = await h.seedApproved(custToken, adminToken) // 夹具前置
    createdOrderIds.push(poConfirmed.id)
    const poInvoiced = await h.seedInvoiced(custToken, adminToken) // 夹具前置
    createdOrderIds.push(poInvoiced.id)
    const poQuote = await h.seedQuotePending(custToken) // 夹具前置：legacy checkout(payment_method=quote)
    expect(poQuote?.id, 'quote_pending 夹具应建成功').toBeTruthy()
    createdOrderIds.push(poQuote.id)

    await asStaff(page)

    // confirmed：AdminOrderDetail.vue:131-146 的 ship-form（v-if status==='confirmed'||'in_production'）
    await go(page, `${PAGES.opsOrderDetail.base}/${poConfirmed.id}`)
    await expect(page.locator('.status-badge')).toHaveText('Confirmed', { timeout: 30000 })
    await expect(page.locator('.ship-form')).toBeVisible()
    await expect(page.locator('.ship-form').getByText('Create Shipment')).toBeVisible()
    await expect(page.locator('.pay-form')).toHaveCount(0)
    await expect(page.locator('.quote-form')).toHaveCount(0)
    // 可取消态才有 Cancel（:29-33 CANCELABLE）
    await expect(page.locator('.btn-cancel')).toBeVisible()

    // invoiced：:152-169 的 pay-form
    await go(page, `${PAGES.opsOrderDetail.base}/${poInvoiced.id}`)
    await expect(page.locator('.status-badge')).toHaveText('Invoiced', { timeout: 30000 })
    await expect(page.locator('.pay-form')).toBeVisible()
    await expect(page.locator('.pay-form').getByText('Record Payment').first()).toBeVisible()
    await expect(page.locator('.ship-form')).toHaveCount(0)
    await expect(page.locator('textarea[placeholder="Admin-only notes..."]')).toBeVisible()

    // quote_pending：:173-186 的 quote-form（Enter Quote：Total Price / Valid Until / Submit Quote）
    await go(page, `${PAGES.opsOrderDetail.base}/${poQuote.id}`)
    await expect(page.locator('.status-badge')).toHaveText('Quote Pending', { timeout: 30000 })
    await expect(page.locator('.quote-form')).toBeVisible()
    await expect(page.locator('.quote-form').getByText('Enter Quote')).toBeVisible()
    await expect(page.locator('.quote-form').getByRole('button', { name: 'Submit Quote' })).toBeVisible()
    await expect(page.locator('.ship-form')).toHaveCount(0)
    await expect(page.locator('.pay-form')).toHaveCount(0)
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 6) /ops/po/review —— 待审 / 缺货 / 已审离场
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@po-review 订单审核台的状态分支', { tag: ['@local-only'] }, () => {
  test('待审卡片可展开；超量行显示缺货徽章；UI Approve 后该卡片离场（已审，反向）', { tag: ['@write'] }, async ({ page }) => {
    // 夹具前置：qty 需**大于该 SKU 的可用量**才会触发缺货分支（PoReviewDesk.vue:108-117）。
    // ⚠ `PoSubmitItemSerializer.quantity` 有 `max_value=10000`（serializers.py:264）⇒ 不能瞎填大数。
    //   先建 1 件探针单读真实的 `sku_available`（详情序列化字段），再按需补建一张缺货单。
    const probe = await fixturePo('REVIEW-PROBE', { qty: 1 })
    const probeDetail = await h.getOrder(adminToken, probe.id)
    const skuAvail = Number(probeDetail?.items?.[0]?.sku_available ?? 0)
    let po = probe
    if (skuAvail >= 1) {
      // 1 件可满足 ⇒ 另造一张必然缺货的单（可用量 + 1，且不超过序列化上限）
      po = await fixturePo('REVIEW', { qty: Math.min(10000, skuAvail + 1) })
    }
    const order = await h.getOrder(adminToken, po.id)
    expect(order.status).toBe('po_received')
    console.log('__E2E__ REVIEW_FIXTURE ' + JSON.stringify({ po: po.id, qty: order.items?.[0]?.quantity, sku_available: order.items?.[0]?.sku_available }))
    expect(
      Number(order.items?.[0]?.quantity) > Number(order.items?.[0]?.sku_available ?? 0),
      '夹具数量必须大于可用量，才能走缺货分支',
    ).toBe(true)

    await asStaff(page)
    await go(page, PAGES.poReview.path)

    const card = page.locator('.po-card', { hasText: order.order_no }) // :73-122
    await expect(card).toHaveCount(1, { timeout: 30000 })
    // 卡片状态徽章：status.replace(/_/g,' ')（:77）
    await expect(card.locator('.po-badge').first()).toHaveText('Po Received')
    await expect(card.getByRole('button', { name: 'Approve' })).toBeVisible()
    await expect(card.getByRole('button', { name: 'Reject' })).toBeVisible()
    await expect(card.getByRole('button', { name: 'Assign Rep' })).toBeVisible()

    // 展开态：View Items → Hide Items（:95-97）+ 缺货行高亮（:109）/ 缺货徽章（:115）
    await expect(card.locator('.po-shortage')).toHaveCount(0)
    await card.getByRole('button', { name: 'View Items' }).click()
    await expect(card.locator('.po-shortage')).toHaveCount(1, { timeout: 20000 })
    await expect(card.locator('.po-shortage-badge')).toContainText('缺货')
    await expect(card.getByRole('button', { name: 'Hide Items' })).toBeVisible()

    // 已审：UI Approve（po_views.py ApproveOrderView：po_received → confirmed）
    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && /\/api\/v1\/orders\/\d+\/approve\/$/.test(r.url()),
        { timeout: 30000 },
      ),
      card.getByRole('button', { name: 'Approve' }).click(),
    ])
    expect(resp.status(), 'Approve 应 2xx').toBeLessThan(300)

    // 反向：已审单不再出现在待审台（列表按 status=po_received 拉，getPendingReviews）
    await expect(page.locator('.po-card', { hasText: order.order_no })).toHaveCount(0, { timeout: 20000 })
    const after = await h.getOrder(adminToken, po.id)
    expect(after.status, 'Approve 后状态应为 confirmed').toBe('confirmed')
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 7) /ops/po/shipments —— 无发货单 → 建发货单 → 已发货 → 已签收
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@po-shipments 发货台的状态分支', { tag: ['@local-only'] }, () => {
  test('选中订单 ⇒「No shipments yet.」；建发货单 ⇒ 出现发货块+Mark Shipped；标记发货 ⇒ Mark Delivered 出现、Mark Shipped 消失；标记签收 ⇒ 操作按钮全消失', { tag: ['@write'] }, async ({ page }) => {
    const po = await h.seedApproved(custToken, adminToken) // 夹具前置：confirmed（发货台只列 confirmed/shipped/in_production，:31）
    createdOrderIds.push(po.id)
    const order = await h.getOrder(adminToken, po.id)

    await asStaff(page)
    await go(page, PAGES.poShipments.path)

    // 选中订单行 → 右侧详情面板
    const row = page.locator('.po-table tbody tr', { hasText: order.order_no }) // :82-87
    await expect(row).toHaveCount(1, { timeout: 30000 })
    await row.click()
    await expect(page.locator('.po-section-title', { hasText: `Order ${order.order_no}` })).toBeVisible()

    // 态 A：无发货单（:133）
    await expect(page.getByText('No shipments yet.')).toBeVisible()
    await expect(page.locator('.po-shipment')).toHaveCount(0)

    // 态 B：建发货单（:99-113）：Carrier + Tracking # + Create Shipment
    await page.locator('.po-field input.po-input').first().fill('DHL') // Carrier（:99）
    await page.locator('.po-field input.po-input').nth(1).fill(`TRK${RUN_TS}`) // Tracking #（:100）
    const [respCreate] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && /\/api\/v1\/orders\/\d+\/shipments\/$/.test(r.url()),
        { timeout: 30000 },
      ),
      page.getByRole('button', { name: 'Create Shipment' }).click(),
    ])
    expect(respCreate.status(), 'Create Shipment 应 2xx').toBeLessThan(300)
    await expect(page.getByText('No shipments yet.')).toHaveCount(0, { timeout: 20000 })
    await expect(page.locator('.po-shipment')).toHaveCount(1)
    await expect(page.locator('.po-shipment').getByRole('button', { name: 'Mark Shipped' })).toBeVisible() // :125

    // 态 C：标记发货 ⇒ Mark Delivered（需要 Received by 输入）+ Mark Shipped 消失（反向）
    const [respShip] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && /\/api\/v1\/shipments\/\d+\/mark-shipped\/$/.test(r.url()),
        { timeout: 30000 },
      ),
      page.locator('.po-shipment').getByRole('button', { name: 'Mark Shipped' }).click(),
    ])
    expect(respShip.status(), 'Mark Shipped 应 2xx').toBeLessThan(300)
    const box = page.locator('.po-shipment')
    await expect(box.getByRole('button', { name: 'Mark Delivered' })).toBeVisible({ timeout: 20000 }) // :126-129
    await expect(box.getByRole('button', { name: 'Mark Shipped' })).toHaveCount(0)
    await expect(box.locator('input[placeholder="Received by"]')).toBeVisible()
    await expect(box.locator('.po-badge').first()).toHaveText('Shipped') // 2026-10-28: 组件默认 Title Case（已去掉 :label）

    // 态 D：标记签收 ⇒ 两条操作按钮都消失（delivered 无可执行动作，:125/:126 条件均为假）
    await box.locator('input[placeholder="Received by"]').fill('E2E')
    const [respDeliver] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && /\/api\/v1\/shipments\/\d+\/mark-delivered\/$/.test(r.url()),
        { timeout: 30000 },
      ),
      box.getByRole('button', { name: 'Mark Delivered' }).click(),
    ])
    expect(respDeliver.status(), 'Mark Delivered 应 2xx').toBeLessThan(300)
    const box2 = page.locator('.po-shipment')
    await expect(box2.locator('.po-badge').first()).toHaveText('Delivered', { timeout: 20000 })
    await expect(box2.getByRole('button', { name: 'Mark Shipped' })).toHaveCount(0)
    await expect(box2.getByRole('button', { name: 'Mark Delivered' })).toHaveCount(0)
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 8) /ops/po/invoicing —— 未开票 → 已开票
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@po-invoicing 开票台的状态分支', { tag: ['@local-only'] }, () => {
  test('delivered 订单 ⇒「Not yet invoiced.」+ Issue Invoice；UI 开票后 ⇒ 发票号出现、callout 消失、Record Payment 表单出现（反向）', { tag: ['@write'] }, async ({ page }) => {
    const po = await h.seedDelivered(custToken, adminToken) // 夹具前置：delivered，无发票
    createdOrderIds.push(po.id)
    const order = await h.getOrder(adminToken, po.id)
    expect(order.invoice, '夹具此时不应有发票').toBeFalsy()

    await asStaff(page)
    await go(page, PAGES.poInvoicing.path)

    const row = page.locator('.po-table tbody tr', { hasText: order.order_no }) // :67-75
    await expect(row).toHaveCount(1, { timeout: 30000 })
    await row.click()
    await expect(page.locator('.po-section-title', { hasText: `Order ${order.order_no}` })).toBeVisible()

    // 态 A：未开票（:84-92）
    const callout = page.locator('.po-callout')
    await expect(callout).toContainText('Not yet invoiced.')
    await expect(page.getByRole('button', { name: 'Issue Invoice' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Record Payment' })).toHaveCount(0)

    // 态 B：开票（:90 Issue Invoice；后端 /orders/{id}/invoice/）
    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && /\/api\/v1\/orders\/\d+\/invoice\/$/.test(r.url()),
        { timeout: 30000 },
      ),
      page.getByRole('button', { name: 'Issue Invoice' }).click(),
    ])
    expect(resp.status(), 'Issue Invoice 应 2xx').toBeLessThan(300)

    // 已开票：callout 消失（反向）、发票号 + 状态徽章 + Record Payment 表单出现（:94-113）
    await expect(page.locator('.po-callout')).toHaveCount(0, { timeout: 20000 })
    const after = await h.getOrder(adminToken, po.id)
    expect(after.invoice?.invoice_no, '开票后应有发票号').toBeTruthy()
    await expect(page.locator('.po-tag').first()).toHaveText(after.invoice.invoice_no)
    await expect(page.getByRole('button', { name: 'Record Payment' })).toBeVisible()
    await expect(page.locator('input[placeholder="0.00"]')).toBeVisible()
    // 记录 Payment 表单的 Method 下拉也已渲染（:105-109）
    await expect(page.locator('.po-field select.po-select').first()).toBeVisible()
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（走状态分支时发现的**真缺陷**） —— 均带 文件:行号 + 实测证据
 *
 * #1【✅ 已修 2026-10-21 · 原缺陷】`/ops/orders` 的状态筛选**缺 PO 流程态**，运营筛不出「待审 / 已签收 / 已取消」
 *    · 修法：状态词表统一到 `config/poConstants.js`（All + 9 个 PO 流程态 + 6 个 legacy 态），
 *      `AdminOrdersPage.vue` 改为引用该常量（含 optgroup 分组），并补 `statusColors` 缺失的 3 态；
 *      同时补上分页（此前 991 单只能看到最新 20 单）。回归：`order-status-filters.spec.cjs`。
 *    · `AdminOrdersPage.vue:54-64` 的下拉只有 legacy 那 9 个值：
 *      draft / confirmed / invoiced / paid / processing / shipped / completed / quote_pending / quoted
 *      —— **没有** po_received / delivered / cancelled / in_production。
 *    · 但本页点进去的 `AdminOrderDetail.vue:129-188` 与审核台/发货台/开票台用的都是
 *      **PO 状态机**（po_received → confirmed → shipped → delivered → invoiced → paid → completed）。
 *    · 实测（本文件首轮）：`selectOption('po_received')` 在 45s 内始终
 *      "did not find some options" ⇒ 无法筛出待审单。
 *    · ⇒ 运营在"订单管理"列表里按「待审」批量查看订单的路径**不存在**（只能靠审核台）。
 *      本文件的筛选用例因此改用下拉里真实存在的 `confirmed`（并在用例里写明了原因）。
 *
 * #2【✅ 已修 2026-10-21 · 原缺陷】`/ops/po/invoicing` 一旦开票，订单就**从列表消失**，再也进不去「记录收款」
 *    · 修法：队列过滤改为只看状态 `['delivered','invoiced']`（不再依赖列表 payload 里的 `invoice`）。
 *      回归：`po-invoicing-queue.spec.cjs`。
 *    · `PoInvoicingDesk.vue:21`：`orders.value = all.filter(o => o.status === 'delivered' || o.invoice)`
 *    · 但列表接口用的 `OrderListSerializer`（`apps/transactions/api/v1/serializers.py:56-61`）
 *      字段只有 `id/order_no/status/payment_method/po_number/grand_total/currency/items_count/created_at`
 *      —— **没有 `invoice`**（实测：50 行里含 invoice 键的 = 0 行）。
 *    · ⇒ `|| o.invoice` 恒为假 ⇒ 列表里**只有 delivered**；开票后订单变 invoiced ⇒ 刷新即消失。
 *    · 后果：开完票当场不录收款，之后在该页面**无法再找到这张单**（Record Payment 路径丢失）。
 *
 * #3【缺陷】`/po/orders/:id` 的 "For Research Use Only" 免责声明**恒显示**（与产品是否 RUO 无关）
 *    · `PoOrderDetail.vue:105`：`v-if="order.items?.some(it => it.is_ruo !== false)"`
 *    · 但明细用的是 `OrderItemSerializer`（`serializers.py:24-35`），字段
 *      `id/product_id/product_name/sku_id/sku_code/pack_size/quantity/unit_price/subtotal/sku_available`
 *      —— **不含 `is_ruo`**（实测明细 items 键无该字段）。
 *    · ⇒ `undefined !== false` 恒真 ⇒ 每个订单都显示该声明（即使产品未标 RUO）。
 *
 * #4【✅ 已修 2026-10-21 · 原缺陷·次要】`/po/orders` 的状态筛选缺 `quote_pending` / `quoted`
 *    · 修法：`poConstants.js` 补 `LEGACY_STATUS_FILTERS`（6 个 legacy 态）并在两页用 optgroup 渲染；
 *      顺带修 `stores/poPortal.js` 的 total 读取（此前恒显示 20 单）并补分页。
 *      回归：`order-status-filters.spec.cjs`。
 *    · `config/poConstants.js:38-49` 的 `ORDER_STATUS_FILTERS` 只有 9 项（All + 8 个 PO 态），
 *      而库中真实存在 `quote_pending`(40 单) 与 `quoted`(33 单)（实测 DB 计数）。
 *    · ⇒ 客户无法在"我的采购订单"里筛选「待报价 / 已报价」的订单。
 * ──────────────────────────────────────────────────────────────────────── */
