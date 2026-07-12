/**
 * 阶段 8 — 响应式视口矩阵（维度 R）
 * 4 视口（桌面/笔记本/平板/移动）× 关键页：加载不崩 + 无 pageerror。
 * 桌面视口额外验证主导航交互可用（点击 Products 链接跳转）。
 *
 * 视口：desktop 1280×800 / laptop 1024×768 / tablet 768×1024 / mobile 375×667
 * 关键页：公开 Home(.home) / Products(.product-grid) / ProductDetail(/products/66, main)
 *         staff AdminOrders(.order-table) / Workspace(.workspace-layout)
 */
const { test, expect } = require('@playwright/test')
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs')

const VIEWPORTS = [
  { name: 'desktop', w: 1280, h: 800 },
  { name: 'laptop', w: 1024, h: 768 },
  { name: 'tablet', w: 768, h: 1024 },
  { name: 'mobile', w: 375, h: 667 },
]
const PUBLIC = [
  { name: 'Home', path: '/', sel: '.home' },
  { name: 'Products', path: '/products', sel: '.product-grid' },
  { name: 'ProductDetail', path: '/products/66', sel: 'main' },
]
const STAFF = [
  { name: 'AdminOrders', path: '/admin/orders', sel: '.order-table' },
  { name: 'Workspace', path: '/workspace', sel: '.workspace-layout' },
]

for (const v of VIEWPORTS) {
  test.describe(`视口 ${v.name} (${v.w}x${v.h})`, () => {
    test.use({ viewport: { width: v.w, height: v.h } })
    test.beforeEach(async ({ page }) => {
      page._errors = []
      page.on('pageerror', (e) => page._errors.push(e.message))
    })

    for (const p of PUBLIC) {
      test(`${p.name} 加载不崩`, async ({ page }) => {
        await page.goto(BASE_URL + p.path, { waitUntil: 'domcontentloaded' })
        await page.waitForSelector(p.sel, { timeout: 10000 })
        expect(page._errors, '页面崩溃级 error 应为空').toEqual([])
      })
    }

    test.describe('staff 页', () => {
      test.beforeEach(async ({ page }) => { await loginAsStaff(page) })
      for (const p of STAFF) {
        test(`${p.name} 加载不崩`, async ({ page }) => {
          await page.goto(BASE_URL + p.path, { waitUntil: 'domcontentloaded' })
          await page.waitForSelector(p.sel, { timeout: 10000 })
          expect(page._errors, '页面崩溃级 error 应为空').toEqual([])
        })
      }
    })

    // 仅桌面视口（汉堡未启用）验证主导航交互可用
    if (v.name === 'desktop' || v.name === 'laptop') {
      test('Home 主导航交互可用（点击 Products 跳转）', async ({ page }) => {
        await page.goto(BASE_URL + '/', { waitUntil: 'domcontentloaded' })
        await page.waitForSelector('.home', { timeout: 10000 })
        await page.getByRole('link', { name: 'Products', exact: true }).first().click()
        await page.waitForURL(/\/products/, { timeout: 8000 })
        await page.waitForSelector('.product-grid', { timeout: 10000 })
        expect(page._errors).toEqual([])
      })
    }
  })
}
