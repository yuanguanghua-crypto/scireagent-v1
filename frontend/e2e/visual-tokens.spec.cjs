/**
 * 阶段 9（视觉令牌部分）— 全站设计令牌 computed style 一致性（维度 V）
 * 单测试遍历所有关键页，验证 :root 设计令牌已定义、品牌色正确且跨页一致：
 *   --color-primary  emerald (rgb(5,150,105) / #059669)
 *   --color-accent   amber   (rgb(217,119,6) / #D97706)
 *   --color-bg / --color-surface / --color-text 在各关键页须一致（令牌全局定义）。
 * 中性色不硬编 hex（避免主题差异脆断），改断言跨页一致 + 非空。
 */
const { test, expect } = require('@playwright/test')
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs')

async function rootTokens(page) {
  return page.evaluate(() => {
    const cs = getComputedStyle(document.documentElement)
    const pick = (n) => cs.getPropertyValue(n).trim()
    return {
      primary: pick('--color-primary'),
      accent: pick('--color-accent'),
      bg: pick('--color-bg'),
      surface: pick('--color-surface'),
      text: pick('--color-text'),
    }
  })
}

function emerald(v) { return /^#059669$/i.test(v) || /^rgb\(5,\s*150,\s*105\)$/i.test(v) || /^#047857$/i.test(v) || /^rgb\(4,\s*120,\s*87\)$/i.test(v) }
function amber(v) { return /^#D97706$/i.test(v) || /^rgb\(217,\s*119,\s*6\)$/i.test(v) }
function isHexOrRgb(v) { return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v) || /^rgb\(/.test(v) }

const PUBLIC = [
  { name: 'Home', path: '/', sel: '.home' },
  { name: 'Products', path: '/products', sel: '.product-grid' },
  { name: 'ProductDetail', path: '/products/66', sel: 'main' },
  // ★ 2026-10-20 扩容：V 维此前只覆盖 3 个公开页
  { name: 'LoginPage', path: '/login', sel: '.auth-page' },
  { name: 'RegisterPage', path: '/register', sel: '.auth-page' },
  { name: 'SearchPage', path: '/search', sel: '.search-page' },
  { name: 'ApplicationIndex', path: '/applications', sel: '.application-index' },
  { name: 'MethodIndex', path: '/methods', sel: '.method-index' },
  { name: 'ProtocolIndex', path: '/protocols', sel: '.protocol-index' },
  { name: 'ResearchGoalIndex', path: '/research-goals', sel: '.research-goal-index' },
  { name: 'QuoteRequestPage', path: '/quote-request', sel: '.rfq-page' },
  { name: 'CartPage', path: '/cart', sel: '.cart-page' },
]
const STAFF = [
  { name: 'AdminOrders', path: '/ops/orders', sel: '.order-table' },
  { name: 'Workspace', path: '/workspace', sel: '.workspace-layout' },
  // ★ 2026-10-20 扩容
  { name: 'SettingsPage', path: '/settings', sel: '.settings-page' },
  { name: 'CheckoutPage', path: '/checkout', sel: '.checkout-page' },
  { name: 'OrderListPage', path: '/orders', sel: '.order-list-page' },
  { name: 'PoSubmit', path: '/po/submit', sel: '.po-page' },
  { name: 'PoOrderList', path: '/po/orders', sel: '.po-page' },
  { name: 'PoAddressList', path: '/po/addresses', sel: '.po-page' },
  { name: 'PoReorder', path: '/po/reorder', sel: '.po-page' },
  { name: 'PoDownloadCenter', path: '/po/downloads', sel: '.po-page' },
]

test('全站设计令牌一致且品牌色正确', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
  const collected = []
  // 公开页
  for (const p of PUBLIC) {
    await page.goto(BASE_URL + p.path, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector(p.sel, { timeout: 10000 })
    const t = await rootTokens(page)
    expect(emerald(t.primary), `${p.name} --color-primary 应为 emerald`).toBeTruthy()
    expect(amber(t.accent), `${p.name} --color-accent 应为 amber`).toBeTruthy()
    expect(isHexOrRgb(t.bg), `${p.name} --color-bg 应已定义`).toBeTruthy()
    expect(isHexOrRgb(t.surface), `${p.name} --color-surface 应已定义`).toBeTruthy()
    expect(isHexOrRgb(t.text), `${p.name} --color-text 应已定义`).toBeTruthy()
    collected.push({ name: p.name, ...t })
  }
  // staff 页
  await loginAsStaff(page)
  for (const p of STAFF) {
    await page.goto(BASE_URL + p.path, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector(p.sel, { timeout: 10000 })
    const t = await rootTokens(page)
    expect(emerald(t.primary), `${p.name} --color-primary 应为 emerald`).toBeTruthy()
    expect(amber(t.accent), `${p.name} --color-accent 应为 amber`).toBeTruthy()
    expect(isHexOrRgb(t.bg), `${p.name} --color-bg 应已定义`).toBeTruthy()
    expect(isHexOrRgb(t.surface), `${p.name} --color-surface 应已定义`).toBeTruthy()
    expect(isHexOrRgb(t.text), `${p.name} --color-text 应已定义`).toBeTruthy()
    collected.push({ name: p.name, ...t })
  }
  // ★ 2026-10-20：先断言「真的访问了每一页」。
  //   否则页面数组被误清空时，collected=[] 也会让整个 test 绿（假绿）。
  expect(collected.length, `应收集到 ${PUBLIC.length + STAFF.length} 页的令牌，实际 ${collected.length}`
  ).toBe(PUBLIC.length + STAFF.length)

  // 跨页一致性
  const base = collected[0]
  for (const t of collected) {
    expect(t.bg, `${t.name} --color-bg 应与 ${base.name} 一致`).toBe(base.bg)
    expect(t.surface, `${t.name} --color-surface 应与 ${base.name} 一致`).toBe(base.surface)
    expect(t.text, `${t.name} --color-text 应与 ${base.name} 一致`).toBe(base.text)
    expect(t.primary, `${t.name} --color-primary 应与 ${base.name} 一致`).toBe(base.primary)
    expect(t.accent, `${t.name} --color-accent 应与 ${base.name} 一致`).toBe(base.accent)
  }
})
