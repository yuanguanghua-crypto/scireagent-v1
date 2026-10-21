/**
 * D4 + D5 回归 —— 运营/客户两侧的**订单状态筛选**与**分页**
 *
 * ## 缺陷现场（2026-10-21 全站测试发现，均 P1）
 * **D4 · `/ops/orders`（运营订单管理）**
 *   - 状态下拉是**页面内联的 9 个 option**（`AdminOrdersPage.vue` 模板），只有 legacy 混搭态：
 *     draft / confirmed / invoiced / paid / processing / shipped / completed / quote_pending / quoted
 *     ⇒ **缺整套 PO 流程态**（`po_received` / `in_production` / `delivered` / `cancelled`）
 *     ⇒ 运营**筛不出待审单**（实测 `selectOption('po_received')` 报 did not find some options）。
 *   - **没有分页**：`getAdminOrders(params)` 从不传 page，后端 `PAGE_SIZE=20`
 *     ⇒ 991 单里**只能看到最新 20 单**（更早的单永久不可达）。
 *   - `statusColors` 也缺 `po_received`/`in_production`/`delivered`
 *     ⇒ 徽章样式拼出 `undefined15`（非法 CSS）。
 *
 * **D5 · `/po/orders`（客户 PO 列表）**
 *   - 筛选读 `poConstants.ORDER_STATUS_FILTERS`，该表只有 PO 流程态，
 *     **缺 legacy 的 `quote_pending` / `quoted`**（库内实有 40 + 33 单）⇒ 客户筛不出报价中的单。
 *   - `stores/poPortal.js` 的 total 读取有 D2 同款错误
 *     （读 `res.data.meta`，而分页信息在信封 `res.meta`）⇒ 恒显示"20 order(s)"。
 *   - 也没有分页控件。
 *
 * ## 判定口径
 * - 状态词表必须**与后端 `Order.Status` 一一对应**（`poConstants.js` 头注释本来就这么声称，
 *   实际没做到 —— 这就是根因层面的不一致）。
 * - 分页必须真的向后端取数（不是前端切片），且**总数取后端真实 count**。
 *
 * 运行：npx playwright test e2e/order-status-filters.spec.cjs --project=chromium
 * 前置：后端 8000 + 前端 5173；admin 登录后两页都能看到全量订单。**本 spec 只读，零写入。**
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff } = require('./helpers/auth.cjs')

const SEL = 'select[aria-label="Filter orders by status"]'

/** 取状态下拉里所有 option 的 value */
async function optionValues(page) {
  return page.locator(`${SEL} option`).evaluateAll((els) => els.map((e) => e.value))
}

/** 取分页组件显示的总数（`total` 文案里的数字） */
async function paginationTotal(page) {
  const txt = (await page.locator('.data-pagination .el-pagination__total').textContent()) || ''
  return parseInt(txt.replace(/[^\d]/g, ''), 10)
}

test.describe('@local-only D4 · /ops/orders 状态筛选 + 分页', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page)
    await page.goto(`${BASE_URL}/ops/orders`, { waitUntil: 'domcontentloaded' })
    // 用页面根类限定：裸 `h1.page-title` 会命中 2 个元素（strict mode 冲突）
    await expect(page.locator('.admin-orders-page h1.page-title', { hasText: 'Order Management' }))
      .toBeVisible({ timeout: 20000 })
  })

  test('状态下拉必须覆盖后端 PO 流程态（po_received / in_production / delivered / cancelled）', async ({ page }) => {
    const values = await optionValues(page)
    expect(values.length, '下拉应至少有 All + 若干状态').toBeGreaterThan(1)
    for (const v of ['po_received', 'in_production', 'delivered', 'cancelled']) {
      expect(values, `运营侧状态下拉缺 PO 流程态「${v}」⇒ 筛不出对应订单`).toContain(v)
    }
  })

  test('选 po_received ⇒ 列表只剩 PO Received 且非空', async ({ page }) => {
    // ⚠️ 必须等**筛选后的响应**回来再断言：否则会拿筛选前的旧行判定（首版踩过）
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/api/v1/admin/orders/') && r.url().includes('status=po_received'),
        { timeout: 30000 },
      ),
      page.locator(SEL).selectOption('po_received'),
    ])
    await expect
      .poll(async () => page.locator('.order-row').count(), { timeout: 20000 })
      .toBeGreaterThan(0)

    const badges = await page.locator('.order-row .status-badge').allTextContents()
    expect(badges.length).toBeGreaterThan(0)
    for (const b of badges) {
      expect(b.trim(), '筛选 po_received 后不应出现其它状态的单').toBe('PO Received')
    }
  })

  test('分页：总数取后端真实 count（>20），且能翻到第 2 页看到不同的单', async ({ page }) => {
    await page.waitForSelector('.order-row', { timeout: 20000 })

    // ① 分页控件必须存在（缺陷时完全没有）
    await expect(page.locator('.data-pagination'), '运营订单列表必须有分页（缺陷时只看得到最新 20 单）')
      .toBeVisible({ timeout: 10000 })

    // ② 总数必须 > 一页的量
    const total = await paginationTotal(page)
    expect(Number.isFinite(total), '总数文案应含数字').toBe(true)
    expect(total, `总数应显示后端真实 count（>20），实际 ${total}`).toBeGreaterThan(20)

    // ③ 第 2 页内容必须不同（真分页，不是前端切片重渲染）
    const first1 = ((await page.locator('.order-row .mono').first().textContent()) || '').trim()
    await page.locator('.data-pagination .el-pager li').nth(1).click()
    await expect
      .poll(async () => ((await page.locator('.order-row .mono').first().textContent()) || '').trim(), {
        timeout: 20000,
      })
      .not.toBe(first1)
  })
})

test.describe('@local-only D5 · /po/orders 状态筛选 + 分页', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page)
    await page.goto(`${BASE_URL}/po/orders`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.po-page h1.po-page-title', { hasText: 'My Purchase Orders' }))
      .toBeVisible({ timeout: 20000 })
  })

  test('状态下拉必须含 legacy 报价态（quote_pending / quoted）', async ({ page }) => {
    const values = await optionValues(page)
    for (const v of ['quote_pending', 'quoted']) {
      expect(values, `客户 PO 列表下拉缺「${v}」⇒ 客户筛不出报价中的单（库内实有 40+33 单）`).toContain(v)
    }
  })

  test('选 quoted ⇒ 列表只剩 Quoted，总数显示真实 count（不是当前页条数）', async ({ page }) => {
    // ⚠️ 等筛选后的响应（`/orders/?status=quoted`）回来再断言，避免拿旧行误判
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/api/v1/orders/') && r.url().includes('status=quoted'),
        { timeout: 30000 },
      ),
      page.locator(SEL).selectOption('quoted'),
    ])
    await expect
      .poll(async () => page.locator('.po-table tbody tr').count(), { timeout: 20000 })
      .toBeGreaterThan(0)

    // ⚠️ PO 侧用的是 StatusBadge 组件，根类名是 `.po-badge`（不是 `.status-badge`）
    const badges = await page.locator('.po-table tbody tr .po-badge').allTextContents()
    for (const b of badges) {
      expect(b.trim(), '筛选 quoted 后不应出现其它状态的单').toBe('Quoted')
    }

    // 总数：缺陷时 store 读错位置，恒等于当前页条数（20）
    const subtitle = (await page.locator('.po-page-subtitle').textContent()) || ''
    const shown = parseInt(subtitle.replace(/[^\d]/g, ''), 10)
    expect(Number.isFinite(shown), `副标题应含单数，实际「${subtitle}」`).toBe(true)
    expect(shown, `总单数应显示后端真实 count（库内 quoted 33 单），实际 ${shown}`).toBeGreaterThan(20)
  })

  test('分页：能翻到第 2 页看到不同的单', async ({ page }) => {
    await page.waitForSelector('.po-table tbody tr', { timeout: 20000 })
    await expect(page.locator('.data-pagination'), '客户 PO 列表必须有分页').toBeVisible({ timeout: 10000 })

    const first1 = ((await page.locator('.po-table tbody tr .po-mono').first().textContent()) || '').trim()
    await page.locator('.data-pagination .el-pager li').nth(1).click()
    await expect
      .poll(
        async () => ((await page.locator('.po-table tbody tr .po-mono').first().textContent()) || '').trim(),
        { timeout: 20000 },
      )
      .not.toBe(first1)
  })
})
