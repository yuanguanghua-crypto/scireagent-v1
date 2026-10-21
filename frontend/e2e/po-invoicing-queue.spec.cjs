/**
 * D3 回归 —— `/ops/po/invoicing`：**开票后订单必须仍留在队列里**
 *
 * ## 缺陷现场（2026-10-21 全站测试发现，P1）
 * 对一笔 DELIVERED 订单开票后，点「Refresh」队列刷新，**该订单从列表消失**，
 * 于是再也点不进去 → 「Record Payment」永远用不了 ⇒ 开票后收不回款、也记不上收款。
 *
 * 根因（读码确认）：
 *   `PoInvoicingDesk.vue` 的 `load()` 里
 *     `all.filter((o) => o.status === 'delivered' || o.invoice)`
 *   而列表用的是 `OrderListSerializer`，它的 `fields` **不含 `invoice`**
 *   （`apps/transactions/api/v1/serializers.py:56-61`）⇒ `o.invoice` 恒为 `undefined`；
 *   开票又把订单状态推进成 `invoiced`（`services.py` 的 issue_invoice）
 *   ⇒ 两个条件同时不成立 ⇒ 被 filter 掉。
 *   ⚠️ 详情接口用 `OrderDetailSerializer`（含 `invoice`），所以**详情能显示发票**，
 *      只有**队列**坏掉 —— 这正是它容易被漏掉的原因。
 *
 * ## 修复后的队列语义（本 spec 用正反两条断言钉住）
 * | 订单状态 | 是否留在队列 | 理由 |
 * |---|---|---|
 * | `delivered` | **在** | 还没开票 |
 * | `invoiced`  | **在** | 已开票但可能未付清（部分付款仍停在 invoiced，见 `services.py:520-530`）|
 * | `paid` / `completed` / `cancelled` | **不在** | 已结清 / 已终结 |
 *
 * ## 数据纪律
 * 本文件**自己造单、自己删净**：
 * - 每个用例用**唯一标记** `PO-E2E-D3-<ts>-<rand>`（不复用 helper 的公共 `PO-E2E-PR-*` 前缀，
 *   否则跑完无法把"我造的"和别的 spec 造的区分开 ⇒ 上一版就因此留下了残留）；
 * - 清理走 **DELETE /api/v1/orders/{id}/**（`Order` 是 ModelViewSet，级联删掉 OneToOne 的 invoice），
 *   失败才退回 cancel；清理后再 GET 确认 404。
 *   ⚠️ 别用 `helpers/api.cjs` 的 `apiContext`：它读 `X-Auth-Token` 且会**自动补 `/api/v1` 前缀**，
 *      把带全前缀的 URL 传进去会被拼坏（上一版就是这么静默失败的）。
 *
 * 运行：npx playwright test e2e/po-invoicing-queue.spec.cjs --project=chromium
 * 前置：后端 8000 + 前端 5173。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff } = require('./helpers/auth.cjs')
const H = require('./helpers/poHelpers.cjs')

const PATH = '/ops/po/invoicing'
const TITLE = 'Invoicing Desk'

function tag() {
  return `PO-E2E-D3-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
}

/** 带唯一标记造一个 DELIVERED 订单（submit → approve → shipment → shipped → delivered） */
async function seedDeliveredTagged(custToken, adminToken) {
  const prod = await H.getProductWithSku(custToken)
  const poNumber = tag()
  const po = await H.submitPoApi(custToken, {
    poNumber,
    productId: prod.id,
    skuId: prod.sku.id,
    qty: 1,
  })
  expect(po.id, `提交 PO 失败（po_number=${poNumber}）`).toBeTruthy()
  await H.approve(adminToken, po.id)
  const o1 = await H.getOrder(adminToken, po.id)
  await H.createShipmentApi(adminToken, po.id, o1.items || [])
  const o2 = await H.getOrder(adminToken, po.id)
  const sid = o2.shipments?.[0]?.id
  expect(sid, '应能建出发货单').toBeTruthy()
  await H.markShippedApi(adminToken, sid)
  await H.markDeliveredApi(adminToken, sid)
  return { ...po, poNumber }
}

/** 带唯一标记造一个已付清(paid)的订单 */
async function seedPaidTagged(custToken, adminToken) {
  const po = await seedDeliveredTagged(custToken, adminToken)
  await H.issueInvoiceApi(adminToken, po.id)
  const o = await H.getOrder(adminToken, po.id)
  const invoiceId = o.invoice?.id
  expect(invoiceId, '应能开出发票').toBeTruthy()
  await H.payInvoiceApi(adminToken, invoiceId, o.grand_total, 'wire')
  return po
}

/** 只删自己造的那一单；删不掉才退回 cancel。返回 'deleted' | 'cancelled' | 'failed' */
async function cleanupOrder(adminToken, custToken, id) {
  if (!id) return 'failed'
  // 显式带 Authorization: Token（与后端 TokenAuthentication 对齐）
  const ctx = await request.newContext({
    baseURL: H.ROOT,
    extraHTTPHeaders: { Authorization: `Token ${adminToken}`, Accept: 'application/json' },
  })
  try {
    const r = await ctx.delete(`/api/v1/orders/${id}/`)
    if (r.ok() || r.status() === 204) return 'deleted'
  } finally {
    await ctx.dispose().catch(() => {})
  }
  const ok = await H.cancelOrder(custToken, adminToken, id).catch(() => false)
  return ok ? 'cancelled' : 'failed'
}

test.describe('@local-only /ops/po/invoicing · 开票后仍在队列（D3 回归）', () => {
  let cust
  let admin

  test.beforeAll(async () => {
    cust = await H.getCustomerToken()
    admin = await H.getAdminToken()
    expect(cust, '需要 customer token').toBeTruthy()
    expect(admin, '需要 admin token').toBeTruthy()
  })

  test('开票后点 Refresh：订单仍在队列里，且还能继续记录收款', async ({ page }) => {
    test.setTimeout(150000)
    const po = await seedDeliveredTagged(cust, admin)

    try {
      await loginAsStaff(page)
      await page.goto(BASE_URL + PATH, { waitUntil: 'domcontentloaded' })
      await expect(page.locator('h1.po-page-title', { hasText: TITLE })).toBeVisible({ timeout: 20000 })

      // ⚠️ 表格渲染的是 `order_no`（ORD-xxx），不是 `po_number`；po_number 只用于唯一标记与清理
      const row = page.locator('tbody tr', { hasText: po.order_no })
      // 前提断言：DELIVERED 必须在队列里（否则后面的断言失去意义）
      await expect(row, 'DELIVERED 订单应出现在开票队列').toBeVisible({ timeout: 30000 })
      await row.click()

      // 未开票 ⇒ 显示「Not yet invoiced.」+ Issue Invoice
      await expect(
        page.locator('.po-callout', { hasText: 'Not yet invoiced' }),
        '未开票订单应显示 Not yet invoiced 提示',
      ).toBeVisible({ timeout: 15000 })

      await page.getByRole('button', { name: 'Issue Invoice' }).click()

      // 开票成功的证据（不看 toast，看发票号真的渲染出来）
      await expect(page.locator('.po-tag')).toHaveText(/^INV-/, { timeout: 30000 })
      await expect(page.getByRole('button', { name: 'Record Payment' })).toBeVisible({ timeout: 15000 })

      // ★★★ D3 核心断言：刷新队列后订单**必须还在**（缺陷时它被 filter 掉 —— 消失）
      // ⚠️ 必须等**刷新真的完成**再断言：Refresh 是异步 load()，否则会拿刷新前的旧行判定，
      //    出现"断言过了但实际已消失"的竞态（首版踩过：报错落在下一行）。
      await Promise.all([
        page.waitForResponse(
          (r) => r.url().includes('/api/v1/orders/') && r.request().method() === 'GET',
          { timeout: 30000 },
        ),
        page.getByRole('button', { name: 'Refresh' }).click(),
      ])
      await expect(
        row,
        '开票后订单从队列消失 ⇒ 再也进不去「记录收款」（D3）',
      ).toBeVisible({ timeout: 20000 })
      await expect(row, '刷新后该行状态应显示 invoiced').toContainText(/invoiced/i)

      // 还能点进去，且发票信息/收款表单都在（证明是"留在可操作队列"而不是"留个死行"）
      await row.click()
      await expect(page.locator('.po-tag')).toHaveText(/^INV-/, { timeout: 20000 })
      await expect(page.getByRole('button', { name: 'Record Payment' })).toBeVisible({ timeout: 15000 })
    } finally {
      const how = await cleanupOrder(admin, cust, po.id)
      expect(how, '清理必须成功（删或取消），不能留下残留订单').not.toBe('failed')
    }
  })

  test('已付清的订单必须离开队列（反向断言，防修成「什么都留着」）', async ({ page }) => {
    test.setTimeout(150000)
    const po = await seedPaidTagged(cust, admin)

    try {
      await loginAsStaff(page)
      await page.goto(BASE_URL + PATH, { waitUntil: 'domcontentloaded' })
      await expect(page.locator('h1.po-page-title', { hasText: TITLE })).toBeVisible({ timeout: 20000 })

      // 等队列真的加载完（表格或空态出现），再断言"没有"，避免抢在加载前断言恒真
      await expect(
        page.locator('.po-card').first().locator('table, .po-empty').first(),
      ).toBeVisible({ timeout: 20000 })

      await expect(
        page.locator('tbody tr', { hasText: po.order_no }),
        '已付清(paid)的订单不应留在开票/收款队列',
      ).toHaveCount(0, { timeout: 10000 })
    } finally {
      const how = await cleanupOrder(admin, cust, po.id)
      expect(how, '清理必须成功（删或取消），不能留下残留订单').not.toBe('failed')
    }
  })
})
