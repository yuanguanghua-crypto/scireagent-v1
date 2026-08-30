// 收敛类聚合浏览 E2E（Step 3 双层结构前端）
// 覆盖：RG/AP 列表页「Browse by Class」Tab → 类表格渲染真实数据 → 搜索过滤 → 进入类详情 → 成员表格。
// 前置：frontend dev server（:5173）+ backend（127.0.0.1:8000）均在运行；使用 staff 会话（admin/admin123）
// 以可见 draft 成员（匿名只返回 ACTIVE 实体，is_test_fixture 永远不可见）。
const { test, expect, login } = require('./helpers')

test.describe('收敛类聚合浏览（Step 3）', () => {
  test.beforeEach(async ({ page }) => {
    // 建立 staff 会话（login() 幂等：已登录则跳过 UI 登录）
    await login(page)
  })

  test('RG: Browse by Class Tab 渲染真实类数据、搜索 DNA 并进入类详情', async ({ page }) => {
    await page.goto('/research-goals')
    await page.waitForSelector('.el-tabs', { timeout: 15000 })

    // 切换到「Browse by Class」Tab
    await page.locator('.el-tabs__item', { hasText: 'Browse by Class' }).click()

    // 类表格出现且含真实数据（>0 行）。
    // 注意：Tab1（All Research Goals）也有 el-table，DOM 中存在但隐藏；
    // 必须限定在 .convergence-browse-tab 内定位，否则取到隐藏 pane 的第一行而超时。
    const classRows = page.locator('.convergence-browse-tab .el-table__body tr')
    await classRows.first().waitFor({ state: 'visible', timeout: 15000 })
    const rows = await classRows.count()
    expect(rows).toBeGreaterThan(0)
    console.log('REPORT: RG convergence class rows =', rows)

    // 搜索「RNA」→ 断言 RNA Analysis（rg_c001）出现。
    // 注：dev DB 中 curated 类 size=1，按 size 降序不在首屏，故通过搜索命中验证。
    await page.locator('.convergence-search input').fill('RNA')
    await expect(classRows.filter({ hasText: 'RNA Analysis' }).first()).toBeVisible({ timeout: 20000 })
    console.log('REPORT: search "RNA" → "RNA Analysis" row found')

    // 搜索「DNA」→ 表格更新且包含含 DNA 的类名
    await page.locator('.convergence-search input').fill('DNA')
    await expect(classRows.first()).toContainText('DNA', { timeout: 20000 })
    console.log('REPORT: search "DNA" → table contains a DNA class')

    // 点击含 DNA 的类 → 跳转收敛类详情页 → 断言类名标题出现
    await classRows.filter({ hasText: 'DNA' }).first().click()
    await page.waitForURL(/\/research-goals\/classes\/.+/, { timeout: 15000 })
    await expect(page.locator('.class-detail-title')).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.class-detail-title')).toContainText('DNA')
    console.log('REPORT: opened RG class detail, title =', await page.locator('.class-detail-title').innerText())
  })

  test('AP: Browse by Class Tab 进入 Contamination-Free DNA Extraction 详情并渲染成员', async ({ page }) => {
    await page.goto('/applications')
    await page.waitForSelector('.el-tabs', { timeout: 15000 })

    // 切换到「Browse by Class」Tab
    await page.locator('.el-tabs__item', { hasText: 'Browse by Class' }).click()

    // 首屏断言 Contamination-Free DNA Extraction（ap_k011，334 成员，size 降序在首屏）
    // 同样限定在 .convergence-browse-tab 内定位，避免匹配到隐藏 pane 的行
    const classRows = page.locator('.convergence-browse-tab .el-table__body tr')
    const row = classRows.filter({ hasText: 'Contamination-Free DNA Extraction' })
    await expect(row.first()).toBeVisible({ timeout: 15000 })

    // 点击该类 → 收敛类详情页
    await row.first().click()
    await page.waitForURL(/\/applications\/classes\/.+/, { timeout: 15000 })
    await expect(page.locator('.class-detail-title')).toContainText('Contamination-Free DNA Extraction', { timeout: 15000 })

    // staff 会话下成员表格至少 1 行（dev DB 中 staff 可见 draft 成员）
    // 详情页独立路由仅一张表，直接定位即可
    const memberRowsLoc = page.locator('.el-table__body tr')
    await memberRowsLoc.first().waitFor({ state: 'visible', timeout: 15000 })
    const memberRows = await memberRowsLoc.count()
    expect(memberRows).toBeGreaterThanOrEqual(1)
    console.log('REPORT: AP class member rows =', memberRows)
  })
})
