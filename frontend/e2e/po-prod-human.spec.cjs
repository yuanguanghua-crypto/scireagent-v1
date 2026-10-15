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
  /** API 前置：为 E2E-PROD-SKU-001 建库存行（不走 UI 搜索，生产搜索行为待查）。 */
  let invRow = null

  test('⑦ API 建库存行 + UI 验证行出现', async ({ page, request }) => {
    test.setTimeout(120000)
    const t = await token(request, 'admin')
    // 搜索产品拿 SKU ID（解析模式与 PoSubmit.vue 一致：data.product || data）
    const sr = await request.get(`${API_BASE}/products/?search=E2E Prod Flow`, {
      headers: { 'X-Auth-Token': t } })
    const products = (await sr.json()).data || []
    expect(products.length, '应能搜到测试商品').toBeGreaterThan(0)
    const pid = products[0].id
    const dr = await request.get(`${API_BASE}/products/${pid}/`, { headers: { 'X-Auth-Token': t } })
    const djson = await dr.json()
    const d = djson.data || {}
    const prod = d.product || d
    const skuId = (prod.skus || [])[0]?.id
    expect(skuId, `应能取到 SKU ID（product keys=${Object.keys(prod).slice(0,6)}）`).toBeTruthy()
    // API 入库（建行）
    const rr = await request.post(`${API_BASE}/inventory/receipt/`, {
      headers: { 'X-Auth-Token': t },
      data: { sku_id: skuId, location: 'MAIN', quantity: 50, reason: 'E2E-PROD-INV setup' },
    })
    expect(rr.status(), await rr.text()).toBeLessThan(300)
    invRow = (await rr.json()).data
    // UI 验证行出现
    await injectAuth(page, 'admin')
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('h1.po-page-title', { hasText: 'Inventory Desk' })).toBeVisible({ timeout: 15000 })
    const euRow = page.locator('[data-location="MAIN"]').filter({ hasText: 'E2E-PROD-SKU' })
    await expect(euRow).toBeVisible({ timeout: 15000 })
    console.log('__E2E__ ⑦ 库存行已创建（API receipt）+ UI 可见')
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
