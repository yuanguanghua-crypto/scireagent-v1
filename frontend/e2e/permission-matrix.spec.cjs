/**
 * 阶段 6 — 权限矩阵穷举（维度 P）
 * 4 角色 × 受限页 expected 行为（行为已用 probe-perm.cjs 实证采集）。
 *
 * 实证结论：
 *  - 匿名访问 requiresAuth / requiresAdmin → /login?redirect=<path>
 *  - customer 访问 requiresAuth → 进入（STAY）
 *  - customer 访问 requiresAdmin 页（独立 /admin/po/*、/admin/orders 及 /workspace/*）→ 前端 isStaff 拦截，redirect 到 /
 *        （全局 beforeEach 守卫统一判定 is_staff；2026-07-11 修复：原独立 requiresAdmin 页缺前端拦截的缺口已关闭）
 *  - customer 访问 /workspace/*（AdminLayout 包裹）→ 被 redirect 到 /
 *  - staff（is_staff）访问所有受限页 → 进入（STAY）
 *  - 已登录访问 /login（guest）→ staff 跳 /workspace，customer 跳 /
 */
const { test, expect } = require('@playwright/test')
const { loginAsStaff, loginAsCustomer, BASE_URL } = require('./helpers/auth.cjs')

const REQUIRES_AUTH = [
  '/settings', '/checkout', '/orders', '/orders/1',
  '/po/submit', '/po/orders', '/po/orders/1',
  '/po/addresses', '/po/reorder', '/po/downloads',
]
const REQUIRES_ADMIN_STANDALONE = [
  '/admin/po/review', '/admin/po/shipments', '/admin/po/invoicing',
  '/admin/po/ar', '/admin/po/organizations',
  '/admin/orders', '/admin/orders/1',
]
const REQUIRES_ADMIN_WORKSPACE = [
  '/workspace', '/workspace/products', '/workspace/goals',
  '/workspace/applications', '/workspace/methods', '/workspace/protocols',
  '/workspace/references', '/workspace/knowledge-intake',
  '/workspace/products/new', '/workspace/products/1/edit',
]

async function clearAuth(page) {
  await page.goto(BASE_URL + '/')
  await page.evaluate(() => localStorage.clear())
}

// ---------- 匿名：所有受限页 → /login?redirect ----------
test.describe('匿名访客', () => {
  test.beforeEach(async ({ page }) => { await clearAuth(page) })

  for (const path of [...REQUIRES_AUTH, ...REQUIRES_ADMIN_STANDALONE, ...REQUIRES_ADMIN_WORKSPACE]) {
    test(`匿名访问 ${path} → /login?redirect`, async ({ page }) => {
      await page.goto(BASE_URL + path, { waitUntil: 'domcontentloaded' })
      await page.waitForURL(/\/login/, { timeout: 8000 })
      const url = new URL(page.url())
      expect(url.pathname).toBe('/login')
      expect(url.searchParams.get('redirect')).toBe(path)
    })
  }
})

// ---------- customer（is_staff=False） ----------
test.describe('customer（非 staff）', () => {
  test.beforeEach(async ({ page }) => { await loginAsCustomer(page) })

  for (const path of REQUIRES_AUTH) {
    test(`customer 访问 ${path}（requiresAuth）→ 进入`, async ({ page }) => {
      await page.goto(BASE_URL + path, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(500)
      expect(page.url()).toContain(path)
    })
  }

  for (const path of REQUIRES_ADMIN_STANDALONE) {
    test(`customer 访问 ${path}（requiresAdmin 独立页）→ 被 redirect 到 /`, async ({ page }) => {
      await page.goto(BASE_URL + path, { waitUntil: 'domcontentloaded' })
      await page.waitForURL(BASE_URL + '/', { timeout: 8000 })
      expect(page.url()).toBe(BASE_URL + '/')
    })
  }

  for (const path of REQUIRES_ADMIN_WORKSPACE) {
    test(`customer 访问 ${path}（/workspace 经 AdminLayout）→ 被 redirect 到 /`, async ({ page }) => {
      await page.goto(BASE_URL + path, { waitUntil: 'domcontentloaded' })
      await page.waitForURL(BASE_URL + '/', { timeout: 8000 })
      expect(page.url()).toBe(BASE_URL + '/')
    })
  }
})

// ---------- staff（is_staff=True） ----------
test.describe('staff（is_staff）', () => {
  test.beforeEach(async ({ page }) => { await loginAsStaff(page) })

  for (const path of [...REQUIRES_AUTH, ...REQUIRES_ADMIN_STANDALONE, ...REQUIRES_ADMIN_WORKSPACE]) {
    test(`staff 访问 ${path} → 进入`, async ({ page }) => {
      await page.goto(BASE_URL + path, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(300)
      expect(page.url()).toContain(path)
    })
  }
})

// ---------- guest 已登录重定向 ----------
test.describe('guest 页已登录重定向', () => {
  test('staff 已登录访问 /login → 跳 /workspace', async ({ page }) => {
    await loginAsStaff(page)
    await page.goto(BASE_URL + '/login', { waitUntil: 'domcontentloaded' })
    await page.waitForURL(/\/workspace/, { timeout: 8000 })
    expect(page.url()).toContain('/workspace')
  })

  test('customer 已登录访问 /login → 跳 /', async ({ page }) => {
    await loginAsCustomer(page)
    await page.goto(BASE_URL + '/login', { waitUntil: 'domcontentloaded' })
    await page.waitForURL(BASE_URL + '/', { timeout: 8000 })
    expect(page.url()).toBe(BASE_URL + '/')
  })
})
