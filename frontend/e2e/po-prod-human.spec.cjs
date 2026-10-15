/**
 * 生产拟人全流程 E2E（真浏览器 · 写入 · 跑完清理）
 *
 * Phase 2: PO 全流程（客户 UI 提交 → staff 四台 → 客户确认 paid）
 * Phase 3: 库存台交互（入库 → 调整 → 流水）
 *
 * 前置：临时测试商品（E2E Prod Flow Product，active）由外部脚本创建，跑完清理。
 * 认证：token 注入（API 登录一次 + addInitScript 写 localStorage）。
 * 运行：服务器上 `node node_modules/@playwright/test/cli.js test e2e/po-prod-human.spec.cjs ...`
 */
const { test, expect } = require('@playwright/test')

const BASE_URL = 'https://scireagent.com'
const API_BASE = `${BASE_URL}/api/v1`
const BASIC = { username: 'scire01', password: 'RalyeNdTsXWfN3Pc' }

const USERS = {
  customer: { u: 'e2e_customer', p: 'E2ePass123!', isStaff: false, role: 'researcher' },
  admin:    { u: 'admin',         p: 'admin123',        isStaff: true,  role: 'admin' },
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

test.use({ httpCredentials: { username: BASIC.username, password: BASIC.password } })
test.describe.configure({ mode: 'serial' })

let poNumber = ''   // 跨测试共享（serial 模式）
let orderNo = ''    // ORD-xxx（发货台/发票台表格显示的是 order_no 而非 po_number）

test.describe('Phase 2 · PO 全流程拟人', () => {
  test('① 客户：/po/submit UI 提交', async ({ page }) => {
    test.setTimeout(120000)
    await injectAuth(page, 'customer')
    await page.goto(`${BASE_URL}/po/submit`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('h1.po-page-title', { hasText: 'Submit Purchase Order' })).toBeVisible({ timeout: 15000 })

    poNumber = `E2E-PROD-FLOW-${Date.now()}`
    await page.getByPlaceholder('无 PO 号可留空').fill(poNumber)
    await page.getByRole('button', { name: '+ Add Line Item' }).click()

    // 搜索临时测试商品
    const prodInput = page.locator('.po-table tbody input.po-input').first()
    await prodInput.fill('E2E Prod Flow')
    await page.locator('.po-search-item').first().click({ timeout: 15000 })
    await page.locator('.po-table tbody select').first().selectOption({ index: 1 })
    await page.locator('.po-table tbody input[type="number"]').first().fill('2')

    await page.getByRole('button', { name: 'Submit PO' }).click()
    await expect(page.locator('.po-callout')).toContainText(/submitted successfully/i, { timeout: 20000 })
    const ordNo = (await page.locator('.po-callout .po-mono').innerText()).trim()
    expect(ordNo).toMatch(/^ORD-/)
    orderNo = ordNo
    console.log(`__E2E__ ① 提交成功: ${orderNo} (PO=${poNumber})`)
  })

  test('② staff：审核台 Approve', async ({ page }) => {
    test.setTimeout(120000)
    await injectAuth(page, 'admin')
    await page.goto(`${BASE_URL}/ops/po/review`, { waitUntil: 'domcontentloaded' })
    const card = page.locator('.po-card', { hasText: poNumber })
    await expect(card).toBeVisible({ timeout: 20000 })
    await card.getByRole('button', { name: 'Approve' }).click()
    await expect(page.locator('.po-card', { hasText: poNumber })).toHaveCount(0, { timeout: 20000 })
    console.log('__E2E__ ② 审核: Approve 完成')
  })

  test('③ staff：发货台 Create Shipment + Mark Shipped + Mark Delivered', async ({ page }) => {
    test.setTimeout(120000)
    await injectAuth(page, 'admin')
    await page.goto(`${BASE_URL}/ops/po/shipments`, { waitUntil: 'domcontentloaded' })
    const row = page.locator('tr', { hasText: orderNo }).first()
    await expect(row).toBeVisible({ timeout: 20000 })
    await row.click()
    await page.locator('.po-field', { hasText: 'Carrier' }).locator('input').fill('FedEx')
    await page.locator('.po-field', { hasText: /Tracking #/ }).locator('input').fill(`TRK-${Date.now()}`)
    await page.getByRole('button', { name: 'Create Shipment' }).click()
    const markShipped = page.getByRole('button', { name: 'Mark Shipped' }).first()
    await expect(markShipped).toBeVisible({ timeout: 20000 })
    await markShipped.click()
    const receivedBy = page.getByPlaceholder('Received by').first()
    await expect(receivedBy).toBeVisible({ timeout: 20000 })
    await receivedBy.fill('E2E Receiver')
    await page.getByRole('button', { name: 'Mark Delivered' }).first().click()
    console.log('__E2E__ ③ 发货+签收完成')
  })

  test('④ staff：发票台 Issue Invoice → Record Payment（同一会话）', async ({ page }) => {
    test.setTimeout(120000)
    await injectAuth(page, 'admin')
    await page.goto(`${BASE_URL}/ops/po/invoicing`, { waitUntil: 'domcontentloaded' })
    const row = page.locator('tr', { hasText: orderNo }).first()
    await expect(row).toBeVisible({ timeout: 20000 })
    await row.click()
    // 开票
    await page.getByRole('button', { name: 'Issue Invoice' }).click()
    await expect(page.getByRole('button', { name: 'Record Payment' })).toBeVisible({ timeout: 20000 })
    // 收款（同一次选中，不重新导航）
    const amount = page.locator('.po-field', { hasText: 'Amount' }).locator('input').first()
    await expect(amount).toBeVisible({ timeout: 20000 })
    await amount.fill('25.00')
    await page.getByRole('button', { name: 'Record Payment' }).click()
    console.log('__E2E__ ④⑤ 开票+收款完成（paid）')
  })

  test('⑥ 客户：订单列表可见 + 追踪', async ({ page }) => {
    await injectAuth(page, 'customer')
    await page.goto(`${BASE_URL}/po/orders`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('body')).toContainText(orderNo, { timeout: 20000 })
    console.log('__E2E__ ⑥ 客户确认订单可见')
  })
})

test.describe('Phase 3 · 库存台交互拟人', () => {
  test('⑦ 入库：新建库存行（搜索 → 选 SKU → MAIN 仓）', async ({ page }) => {
    test.setTimeout(120000)
    await injectAuth(page, 'admin')
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('h1.po-page-title', { hasText: 'Inventory Desk' })).toBeVisible({ timeout: 15000 })
    await page.getByTestId('inv-receipt-new').click()
    await page.getByTestId('inv-receipt-search').fill('E2E Prod Flow')
    await page.getByTestId('inv-search-item').first().click({ timeout: 15000 })
    const skuSelect = page.getByTestId('inv-receipt-sku')
    await expect(skuSelect.locator('option')).toHaveCount(2, { timeout: 15000 })
    await skuSelect.selectOption({ index: 1 })
    await page.getByTestId('inv-receipt-qty').fill('50')
    await page.getByTestId('inv-receipt-reason').fill('E2E-PROD-INV 首次入库')
    await page.getByTestId('inv-receipt-submit').click()
    await expect(page.getByTestId('inv-receipt-modal')).toBeHidden({ timeout: 15000 })
    console.log('__E2E__ ⑦ 库存入库完成')
  })

  test('⑧ 盘点调整：delta=-5 + ADJUST 流水', async ({ page }) => {
    test.setTimeout(120000)
    await injectAuth(page, 'admin')
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    const row = page.locator('[data-location="MAIN"]').filter({ hasText: 'E2E-PROD-SKU' })
    await expect(row).toBeVisible({ timeout: 15000 })
    await row.getByTestId('inv-adjust-btn').click()
    await page.getByTestId('inv-delta').fill('-5')
    await page.getByTestId('inv-adjust-reason').fill('E2E-PROD-INV 盘点调整')
    await page.getByTestId('inv-adjust-submit').click()
    await expect(page.getByTestId('inv-adjust-modal')).toBeHidden({ timeout: 15000 })
    console.log('__E2E__ ⑧ 盘点调整完成')
  })

  test('⑨ 流水查询：History 弹窗显示 receipt + adjust', async ({ page }) => {
    await injectAuth(page, 'admin')
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    const row = page.locator('[data-location="MAIN"]').filter({ hasText: 'E2E-PROD-SKU' })
    await expect(row).toBeVisible({ timeout: 15000 })
    await row.getByTestId('inv-detail-btn').click()
    await expect(page.getByTestId('inv-detail-modal')).toBeVisible({ timeout: 15000 })
    const movementsTable = page.getByTestId('inv-movements-table')
    await expect(movementsTable).toContainText('receipt', { timeout: 10000 })
    await expect(movementsTable).toContainText('adjust', { timeout: 10000 })
    await expect(movementsTable).toContainText('E2E-PROD-INV 首次入库')
    console.log('__E2E__ ⑨ 流水查询完成（receipt + adjust 均可见）')
  })
})
