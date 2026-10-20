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

  const VIEWPORTS_ALL = [
    { name: 'desktop', w: 1280, h: 800 },
    { name: 'laptop', w: 1024, h: 768 },
    { name: 'tablet', w: 768, h: 1024 },
    { name: 'mobile', w: 375, h: 667 },
  ]
  // ★ 2026-10-20 分档（实测依据：5 页 3.0 分钟、11 页 4 视口 7.6 分钟，近似线性）
  //   fast（默认）: 2 视口（desktop + mobile）→ PR 用，约 4 分钟
  //   full        : 4 视口 → nightly / 发版前
  //   用法：E2E_TIER=full npx playwright test e2e/responsive.spec.cjs --project=chromium
  const TIER = process.env.E2E_TIER || 'fast'
  const VIEWPORTS = TIER === 'full'
    ? VIEWPORTS_ALL
    : VIEWPORTS_ALL.filter((v) => v.name === 'desktop' || v.name === 'mobile')
  const PUBLIC = [
    { name: 'Home', path: '/', sel: '.home' },
    { name: 'Products', path: '/products', sel: '.product-grid' },
    { name: 'ProductDetail', path: '/products/66', sel: 'main' },
    // ★ 2026-10-20 补：此前 R 维只覆盖 3 个公开页（全站 44 页里的 11%）
    { name: 'Search', path: '/search', sel: '.search-page' },
    { name: 'Login', path: '/login', sel: '.auth-page' },
    { name: 'Register', path: '/register', sel: '.auth-page' },
    { name: 'QuoteRequest', path: '/quote-request', sel: '.rfq-page' },
    // ★ 2026-10-21 P1：再补 5 个固定路径公开页（R 维缺口按 audit 逐页算出来的）
    { name: 'AppIndex', path: '/applications', sel: '.application-index' },
    { name: 'MethodIndex', path: '/methods', sel: '.method-index' },
    { name: 'ProtocolIndex', path: '/protocols', sel: '.protocol-index' },
    { name: 'RGIndex', path: '/research-goals', sel: '.research-goal-index' },
    { name: 'CartPage', path: '/cart', sel: '.cart-page' },
  ]
  const STAFF = [
    { name: 'AdminOrders', path: '/ops/orders', sel: '.order-table' },
    { name: 'Workspace', path: '/workspace', sel: '.workspace-layout' },
    // ★ 2026-10-20 补：workspace 下两个 P0 固定路径页
    { name: 'WorkspaceProducts', path: '/workspace/products', sel: '.products-page' },
    { name: 'ProductNew', path: '/workspace/products/new', sel: '.product-edit' },
    // ★ 2026-10-21 P1：再补 13 个（auth 页 + PO 客户页 + PO 内部审核台，admin 登录均可访问）
    { name: 'SettingsPage', path: '/settings', sel: '.settings-page' },
    { name: 'CheckoutPage', path: '/checkout', sel: '.checkout-page' },
    { name: 'OrderList', path: '/orders', sel: '.order-list-page' },
    { name: 'PoSubmit', path: '/po/submit', sel: '.po-page' },
    { name: 'PoOrderList', path: '/po/orders', sel: '.po-page' },
    { name: 'PoAddressList', path: '/po/addresses', sel: '.po-page' },
    { name: 'PoReorder', path: '/po/reorder', sel: '.po-page' },
    { name: 'PoDownloadCenter', path: '/po/downloads', sel: '.po-page' },
    { name: 'PoReviewDesk', path: '/ops/po/review', sel: '.po-page' },
    { name: 'PoShipmentDesk', path: '/ops/po/shipments', sel: '.po-page' },
    { name: 'PoInvoicingDesk', path: '/ops/po/invoicing', sel: '.po-page' },
    { name: 'PoArReport', path: '/ops/po/ar', sel: '.po-page' },
    { name: 'PoOrgManagement', path: '/ops/po/organizations', sel: '.po-page' },
    // ★ 2026-10-21 P4：补 /workspace 子页（R 维缺口集中在这里；5 个共用 entity-page 类）
    { name: 'WsGoals', path: '/workspace/goals', sel: '.entity-page' },
    { name: 'WsApplications', path: '/workspace/applications', sel: '.entity-page' },
    { name: 'WsMethods', path: '/workspace/methods', sel: '.entity-page' },
    { name: 'WsProtocols', path: '/workspace/protocols', sel: '.entity-page' },
    { name: 'WsReferences', path: '/workspace/references', sel: '.entity-page' },
    { name: 'WsKnowledgeIntake', path: '/workspace/knowledge-intake', sel: '.ki-page' },
  ]

for (const v of VIEWPORTS) {
  test.describe(`视口 ${v.name} (${v.w}x${v.h})`, { tag: ['@readonly', '@local-only'] }, () => {
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
