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
]
const STAFF = [
  { name: 'AdminOrders', path: '/admin/orders', sel: '.order-table' },
  { name: 'Workspace', path: '/workspace', sel: '.workspace-layout' },
]

test('全站设计令牌一致且品牌色正确', async ({ page }) => {
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
