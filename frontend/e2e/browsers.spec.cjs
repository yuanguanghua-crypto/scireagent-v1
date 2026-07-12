/**
 * 阶段 9（跨浏览器部分）— 关键路径跨浏览器冒烟（维度 V 跨引擎）
 * 在 chromium / firefox / webkit 三个引擎上各跑一遍最小关键路径，
 * 验证核心渲染与导航不依赖单一引擎：
 *   1) 首页加载 + 产品网格可见
 *   2) 导航到 /products 并渲染
 *   3) 打开产品详情 (66)
 * 不覆盖写操作（避免跨引擎状态污染），仅验证渲染/导航稳定。
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL } = require('./helpers/auth.cjs')

test('首页加载且产品网格可见', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  await page.goto(BASE_URL + '/', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.home')).toBeVisible({ timeout: 10000 })
  await expect(page.locator('.product-grid .product-card').first()).toBeVisible({ timeout: 10000 })
  expect(errors, '首页无运行时报错').toHaveLength(0)
})

test('产品列表页渲染', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  await page.goto(BASE_URL + '/products', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.product-grid')).toBeVisible({ timeout: 10000 })
  expect(errors, '产品列表无运行时报错').toHaveLength(0)
})

test('产品详情页渲染', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  await page.goto(BASE_URL + '/products/66', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('main')).toBeVisible({ timeout: 10000 })
  expect(errors, '产品详情无运行时报错').toHaveLength(0)
})
