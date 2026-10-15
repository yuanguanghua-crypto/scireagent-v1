/**
 * 库存管理台 E2E（v4.1 DEV-1）—— procurement 角色走真 UI：
 * 页面渲染 → 入库（弹窗）→ 调整（弹窗）→ 流水可见。
 *
 * 前置：dev 后端 :8000 + 前端 :5173；dev 库存在 E2E 夹具 SKU（E2E-PO-SKU-001）行。
 * 运行：剥代理 + workers=1 --project=chromium --output=<独立目录> -g "@inv-desk"
 */
const { test, expect } = require('@playwright/test')
const { loginAsProcurement, loginAsCustomer, logout, BASE_URL } = require('./helpers/auth.cjs')

test.describe('@inv-desk 库存管理台（procurement）', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsProcurement(page)
  })

  test('页面渲染：标题 + 表格 + 操作按钮', async ({ page }) => {
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('h1.po-page-title', { hasText: 'Inventory Desk' })).toBeVisible()
    await expect(page.getByTestId('inv-table')).toBeVisible()
    await expect(page.getByTestId('inv-receipt-new')).toBeVisible()
  })

  test('入库：对新 SKU 搜索选择并创建行，流水含 receipt', async ({ page, request }) => {
    test.setTimeout(120000)
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    // 用夹具 SKU 的定位：搜索 E2E-PO-SKU-001
    await page.getByTestId('inv-search').fill('E2E-PO-SKU-001')
    await page.getByRole('button', { name: 'Apply' }).click()
    const rowBtn = page.getByTestId('inv-receipt-btn').first()
    await expect(rowBtn).toBeVisible({ timeout: 10000 })
    await rowBtn.click()
    await page.getByTestId('inv-receipt-qty').fill('5')
    await page.getByTestId('inv-receipt-reason').fill('E2E 入库测试')
    await page.getByTestId('inv-receipt-submit').click()
    await expect(page.getByTestId('inv-receipt-modal')).toBeHidden({ timeout: 10000 })
    // History：流水应含 receipt
    await page.getByTestId('inv-detail-btn').first().click()
    await expect(page.getByTestId('inv-detail-modal')).toBeVisible()
    await expect(page.getByTestId('inv-movements-table')).toContainText('receipt', { timeout: 10000 })
  })

  test('调整：delta=+2 写入 ADJUST 流水', async ({ page }) => {
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    const btn = page.getByTestId('inv-adjust-btn').first()
    await expect(btn).toBeVisible({ timeout: 10000 })
    await btn.click()
    await page.getByTestId('inv-delta').fill('2')
    await page.getByTestId('inv-adjust-reason').fill('E2E 盘盈 +2')
    await page.getByTestId('inv-adjust-submit').click()
    await expect(page.getByTestId('inv-adjust-modal')).toBeHidden({ timeout: 10000 })
    await page.getByTestId('inv-detail-btn').first().click()
    await expect(page.getByTestId('inv-movements-table')).toContainText('adjust', { timeout: 10000 })
  })

  test('权限回归：researcher 访问 /ops/inventory → 被守卫拦下', async ({ page }) => {
    // ★ beforeEach 已登录 procurement ⇒ 切角色必须先 logout（否则 /login 被守卫弹走）
    await logout(page)
    await loginAsCustomer(page)
    await page.goto(`${BASE_URL}/ops/inventory`, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1000)
    expect(page.url()).not.toMatch(/\/ops\/inventory/)
  })
})
