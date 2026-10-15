/**
 * 库存管理台 · 完整 E2E（v4.1 DEV-1）—— procurement/admin/customer/anonymous 四角色 + 全功能面
 *
 * 覆盖：页面渲染 · 入库（既有行/累加/新行全流程搜索选品/空原因报错）· 调整（正/超提取）·
 *       筛选（搜索/库位/低库存）· 详情流水（含 RESERVED 占用联动）· 权限（匿名/researcher/admin）
 *
 * ★ 行定位纪律：同一 SKU 会有多行（EU/MAIN/US 多库位，location 排序 EU<MAIN<US）——
 *   一切行定位必须按库位 scope（`filter({ hasText: location })`），裸 `inv-row-<sku>` 会 strict 违规。
 * ★ 认证策略：token 注入（API 登录一次 + addInitScript 写 localStorage）—— 规避 5/min 登录限流。
 * 前置：dev 后端 :8000 + 前端 :5173 + fixture（E2E-PO-SKU-001，e2e_po_fixture.json）
 */
const { test, expect } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const { BASE_URL } = require('./helpers/auth.cjs')

const API_BASE = process.env.API_BASE || 'http://localhost:8000/api/v1'
const FIXTURE = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', '..', 'e2e_po_fixture.json'), 'utf8'))
const SKU_CODE = FIXTURE.sku_code

const USERS = {
  proc: { u: process.env.E2E_PROC_USER || 'e2e_proc', p: process.env.E2E_PROC_PASS || 'E2ePass123!',
          isStaff: false, role: 'procurement' },
  admin: { u: process.env.E2E_USER || 'admin', p: process.env.E2E_PASS || 'admin123',
           isStaff: true, role: 'admin' },
  customer: { u: process.env.E2E_CUSTOMER_USER || 'e2e_customer',
              p: process.env.E2E_CUSTOMER_PASS || 'E2ePass123!', isStaff: false, role: 'researcher' },
}
const _tokens = {}

async function token(request, who) {
  if (!_tokens[who]) {
    const res = await request.post(`${API_BASE}/auth/login`, {
      data: { username: USERS[who].u, password: USERS[who].p },
    })
    expect(res.status(), `login ${who}`).toBe(200)
    _tokens[who] = (await res.json()).data.token
  }
  return _tokens[who]
}

async function injectAuth(page, who) {
  const t = await token(page.request, who)
  const { isStaff, role } = USERS[who]
  await page.addInitScript(([tk, is, r]) => {
    localStorage.setItem('token', tk)
    localStorage.setItem('is_staff', String(is))
    localStorage.setItem('role', r)
  }, [t, isStaff, role])
}

async function gotoDesk(page) {
  await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('inv-table')).toBeVisible({ timeout: 15000 })
}

/** 行定位（必须带库位）：⚠️ 不用 hasText —— 'US' 会大小写不敏感匹配到每行的 "Adjust" 按钮。
 *  改用组件行上的 data-location 属性 + CSS 属性选择器，精确定位。 */
const rowBy = (page, location) =>
  page.locator(`[data-testid="inv-row-${SKU_CODE}"][data-location="${location}"]`)

async function openHistory(page, location) {
  await rowBy(page, location).getByTestId('inv-detail-btn').click()
  await expect(page.getByTestId('inv-detail-modal')).toBeVisible({ timeout: 10000 })
}

test.describe('@inv-desk 库存管理台 · 完整 E2E', () => {
  test.describe('页面与权限', () => {
    test('procurement：页面渲染（标题/表格/筛选/MAIN 行）', async ({ page }) => {
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      await expect(page.locator('h1.po-page-title', { hasText: 'Inventory Desk' })).toBeVisible()
      await expect(page.getByTestId('inv-receipt-new')).toBeVisible()
      await expect(rowBy(page, 'MAIN')).toBeVisible()
    })

    test('匿名：访问 /ops/inventory → 落 /login', async ({ page }) => {
      await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
      await page.waitForURL(/\/login/, { timeout: 10000 })
    })

    test('researcher（客户）：被守卫拦下，不停留在内部台', async ({ page }) => {
      await injectAuth(page, 'customer')
      await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(1200)
      expect(page.url()).not.toMatch(/\/ops\/inventory/)
    })

    test('admin：可进入并可执行调整（staff 正对照）', async ({ page }) => {
      await injectAuth(page, 'admin')
      await gotoDesk(page)
      await rowBy(page, 'MAIN').getByTestId('inv-adjust-btn').click()
      await page.getByTestId('inv-delta').fill('1')
      await page.getByTestId('inv-adjust-reason').fill('E2E admin 盘盈')
      await page.getByTestId('inv-adjust-submit').click()
      await expect(page.getByTestId('inv-adjust-modal')).toBeHidden({ timeout: 10000 })
      await openHistory(page, 'MAIN')
      await expect(page.getByTestId('inv-movements-table')).toContainText('E2E admin 盘盈')
    })
  })

  test.describe('入库', () => {
    test('既有行入库：available 精确累加 + RECEIPT 流水含原因', async ({ page }) => {
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      const row = rowBy(page, 'MAIN')
      const before = parseInt(await row.locator('td').nth(4).innerText(), 10)
      await row.getByTestId('inv-receipt-btn').click()
      await page.getByTestId('inv-receipt-qty').fill('5')
      await page.getByTestId('inv-receipt-reason').fill('E2E 入库测试')
      await page.getByTestId('inv-receipt-submit').click()
      await expect(page.getByTestId('inv-receipt-modal')).toBeHidden({ timeout: 10000 })
      await expect(rowBy(page, 'MAIN').locator('td').nth(4))
        .toHaveText(String(before + 5), { timeout: 10000 })
      await openHistory(page, 'MAIN')
      await expect(page.getByTestId('inv-movements-table')).toContainText('E2E 入库测试')
    })

    test('空原因入库 → 弹窗不关闭（校验拦截）', async ({ page }) => {
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      await rowBy(page, 'MAIN').getByTestId('inv-receipt-btn').click()
      await page.getByTestId('inv-receipt-qty').fill('5')
      await page.getByTestId('inv-receipt-reason').fill('   ')
      await page.getByTestId('inv-receipt-submit').click()
      await expect(page.getByTestId('inv-receipt-modal')).toBeVisible()
    })

    test('新建库存行全流程：搜索产品 → 选 SKU → EU 仓 → EU 行出现', async ({ page }) => {
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      await page.getByTestId('inv-receipt-new').click()
      await page.getByTestId('inv-receipt-search').fill('E2E PO Test')
      await page.getByTestId('inv-search-item').first().click({ timeout: 10000 })
      const skuSelect = page.getByTestId('inv-receipt-sku')
      await expect(skuSelect.locator('option')).toHaveCount(2, { timeout: 10000 }) // 占位 + 夹具 SKU
      await skuSelect.selectOption({ index: 1 })
      await page.getByTestId('inv-receipt-location').selectOption('EU')
      await page.getByTestId('inv-receipt-qty').fill('3')
      await page.getByTestId('inv-receipt-reason').fill('E2E 新建 EU 行')
      await page.getByTestId('inv-receipt-submit').click()
      await expect(page.getByTestId('inv-receipt-modal')).toBeHidden({ timeout: 10000 })
      // EU 行出现（该 SKU 在 EU 仓唯一一行，receipt 累加幂等）
      const euRow = page.locator('[data-testid^="inv-row-"]').filter({ hasText: 'EU' })
      await expect(euRow).toHaveCount(1, { timeout: 10000 })
      await expect(euRow.locator('td').nth(4)).not.toHaveText('0')
    })
  })

  test.describe('调整', () => {
    test('超提取（delta 超过 available）→ 弹窗不关闭且库存不变', async ({ page }) => {
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      const row = rowBy(page, 'MAIN')
      const before = await row.locator('td').nth(4).innerText()
      await row.getByTestId('inv-adjust-btn').click()
      await page.getByTestId('inv-delta').fill('-999999')
      await page.getByTestId('inv-adjust-reason').fill('E2E 超提取')
      await page.getByTestId('inv-adjust-submit').click()
      await expect(page.getByTestId('inv-adjust-modal')).toBeVisible({ timeout: 10000 })
      await page.getByTestId('inv-adjust-modal').getByRole('button', { name: 'Cancel' }).click()
      await expect(rowBy(page, 'MAIN').locator('td').nth(4))
        .toHaveText(before, { timeout: 10000 })
    })
  })

  test.describe('筛选', () => {
    test('搜索：可见行均匹配 SKU', async ({ page }) => {
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      await page.getByTestId('inv-search').fill(SKU_CODE)
      await page.getByRole('button', { name: 'Apply' }).click()
      const rows = page.getByTestId('inv-table').locator('tbody tr')
      await expect(rows.first()).toContainText(SKU_CODE, { timeout: 10000 })
      const n = await rows.count()
      expect(n, '搜索后应有结果行').toBeGreaterThan(0)
      for (let i = 0; i < n; i++) {
        await expect(rows.nth(i)).toContainText(SKU_CODE)
      }
    })

    test('低库存筛选：自适配阈值 + 高亮', async ({ page, request }) => {
      const t = await token(request, 'proc')
      const lr = await request.get(
        `${API_BASE}/inventory/?search=${SKU_CODE}&location=US`,
        { headers: { 'X-Auth-Token': t } })
      const ldata = (await lr.json()).data
      const lrows = ldata.results || ldata || []
      expect(lrows.length, 'US 行应存在').toBeGreaterThan(0)
      const usAvail = parseInt(lrows[0].available, 10)
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      // 阈值 = usAvail ⇒ US 行可见且带低库存高亮
      await page.getByTestId('inv-low-stock').fill(String(usAvail))
      await page.getByRole('button', { name: 'Apply' }).click()
      const usRow = rowBy(page, 'US')
      await expect(usRow).toBeVisible({ timeout: 10000 })
      await expect(usRow).toHaveClass(/po-row-low/, { timeout: 10000 })
      // 阈值 = usAvail-1 ⇒ US 行被过滤隐藏
      await page.getByTestId('inv-low-stock').fill(String(usAvail - 1))
      await page.getByRole('button', { name: 'Apply' }).click()
      await expect(usRow).toBeHidden({ timeout: 10000 })
    })
  })

  test.describe('与订单联动', () => {
    test('API 建单→审核→备货后：History 显示 RESERVED 占用 + allocate 流水', async ({ page, request }) => {
      test.setTimeout(120000)
      // ① 客户下单
      const ct = await token(request, 'customer')
      const po = `E2E-INV-${Date.now()}`
      let r = await request.post(`${API_BASE}/orders/po/`, {
        headers: { 'X-Auth-Token': ct }, data: {
          po_number: po, shipping_name: 'E2E Lab', shipping_address: '1 Test St',
          items: [{ sku_id: FIXTURE.sku_id, quantity: 2, unit_price: FIXTURE.unit_price }],
        },
      })
      expect(r.status(), await r.text()).toBe(201)
      // ② staff 审核确认
      const at = await token(request, 'admin')
      const orders = await (await request.get(`${API_BASE}/orders/`, {
        headers: { 'X-Auth-Token': ct } })).json()
      const rows = orders.data.results || orders.data
      const order = rows.find((o) => o.po_number === po)
      expect(order, '下单后应能查到订单').toBeTruthy()
      r = await request.post(`${API_BASE}/orders/${order.id}/approve/`, {
        headers: { 'X-Auth-Token': at } })
      expect(r.status()).toBe(200)
      // ③ 备货占用夹具库存（MAIN）
      const detail = await (await request.get(`${API_BASE}/orders/${order.id}/`, {
        headers: { 'X-Auth-Token': ct } })).json()
      const item = (detail.data.items || [])[0]
      r = await request.post(`${API_BASE}/orders/${order.id}/allocate/`, {
        headers: { 'X-Auth-Token': at }, data: {
          lines: [{ order_item_id: item.id, inventory_id: FIXTURE.inventory_id, quantity: 2 }] },
      })
      expect(r.status(), await r.text()).toBeLessThan(300)
      // ④ UI：History（MAIN 行）显示 RESERVED 占用 + allocate 流水
      await injectAuth(page, 'proc')
      await gotoDesk(page)
      await openHistory(page, 'MAIN')
      await expect(page.getByTestId('inv-detail-modal').locator('.po-table').first())
        .toContainText('reserved', { timeout: 10000 })
      await expect(page.getByTestId('inv-movements-table')).toContainText('allocate', { timeout: 10000 })
      // 注：RESERVED 占用保留在 dev 夹具库存上（available 充足）；如需清理走后台
    })
  })
})
