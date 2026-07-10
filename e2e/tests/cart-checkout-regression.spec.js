/**
 * Regression verification for 3 cart/checkout frontend fixes (Round 1):
 *
 * Change 1: Request Quote button → router.push('/quote-request')
 * Change 2: Checkout error handling chain (fallback chain)
 * Change 3: Submit for Approval condition (researcher only, no !isOrgAdmin)
 *
 * Uses real backend (no mocks) against the running dev stack.
 * All assertions are deterministic — no timing assumptions.
 */
const { test, expect } = require('@playwright/test')
const path = require('path')
const fs = require('fs')

const BASE = 'http://localhost:5173'
const ADMIN_USER = 'admin'
const ADMIN_PASS = 'admin123'

// ── Helpers ────────────────────────────────────────────────────────────

/** Collect page errors (console.error + pageerror) during a test. */
async function collectErrors(page) {
  const errors = { console: [], pageerror: [] }
  const ignore = /Failed to load resource|net::ERR|favicon|DevTools|\[vite\]|WebSocket/i
  page.on('console', (msg) => {
    if (msg.type() === 'error' && !ignore.test(msg.text())) {
      errors.console.push(msg.text())
    }
  })
  page.on('pageerror', (err) => {
    errors.pageerror.push(err.message)
  })
  return errors
}

/** Assert zero unexpected page errors at teardown. */
async function assertNoErrors(errors) {
  const all = []
  if (errors.pageerror.length) all.push('Uncaught JS: ' + errors.pageerror.join(' | '))
  if (errors.console.length) all.push('console.error: ' + errors.console.join(' | '))
  if (all.length) {
    console.log('REPORT: ERRORS FOUND — ' + all.join('; '))
    throw new Error(all.join('; '))
  }
  console.log('REPORT: console 0 errors ✓')
}

/**
 * Login via the UI login form. Idempotent — skips if already on workspace.
 */
async function login(page) {
  if (page.url().includes('/workspace')) return
  await page.goto('/login')

  // Wait for the login form to render
  await page.waitForSelector('#login-username', { timeout: 10000 })

  // Clear any stale session
  await page.evaluate(() => localStorage.removeItem('token'))

  // Re-navigate to ensure clean state
  await page.goto('/login')
  await page.waitForSelector('#login-username', { timeout: 10000 })

  await page.fill('#login-username', ADMIN_USER)
  await page.fill('#login-password', ADMIN_PASS)
  await page.getByRole('button', { name: 'Sign In' }).click()

  // After login the app may redirect to home or stay; wait for any authenticated page
  // Wait until the token is in localStorage
  await page.waitForFunction(() => !!localStorage.getItem('token'), { timeout: 15000 })
  console.log('REPORT: Login successful ✓')
}

/**
 * Add a product SKU to the basket via the API using the session token.
 */
async function apiAddToCart(page, skuId, quantity = 1) {
  const token = await page.evaluate(() => localStorage.getItem('token'))
  const resp = await page.request.post('/api/v1/basket/items', {
    data: { sku_id: skuId, quantity },
    headers: { Authorization: `Token ${token}` },
  })
  const body = await resp.json()
  console.log(`REPORT: addToCart(sku=${skuId}, qty=${quantity}) → status=${resp.status()}`)
  return resp.ok()
}

/**
 * Clear the basket via API.
 */
async function apiClearBasket(page) {
  const token = await page.evaluate(() => localStorage.getItem('token'))
  // Get current basket
  const getResp = await page.request.get('/api/v1/basket', {
    headers: { Authorization: `Token ${token}` },
  })
  if (!getResp.ok()) return
  const body = await getResp.json()
  const items = body?.data?.items || body?.items || []
  for (const item of items) {
    const itemId = item.id
    await page.request.delete(`/api/v1/basket/items/${itemId}/delete`, {
      headers: { Authorization: `Token ${token}` },
    })
  }
  console.log(`REPORT: Cleared ${items.length} item(s) from basket ✓`)
}

// ======================================================================
// A1. Request Quote 跳转
// ======================================================================
test.describe('A1. Request Quote redirect', () => {
  test('Login, add product to cart, click Request Quote → URL is /quote-request', async ({ page }) => {
    const errors = await collectErrors(page)

    // 1. Login
    await login(page)

    // 2. Add product to cart via API (use SKU id 446 from product 62)
    await apiClearBasket(page)
    const added = await apiAddToCart(page, 446, 1)
    expect(added).toBeTruthy()

    // 3. Navigate to /cart
    await page.goto('/cart')
    await page.waitForSelector('.cart-page', { timeout: 15000 })

    // Wait for cart items to render (not empty state)
    await page.waitForSelector('.cart-items-list', { timeout: 15000 })
    console.log('REPORT: Cart page rendered with items ✓')

    // 4. Click "Request Quote" button
    const requestQuoteBtn = page.locator('button:has-text("Request Quote")')
    await expect(requestQuoteBtn).toBeVisible({ timeout: 10000 })
    await requestQuoteBtn.click()

    // 5. Assert URL is /quote-request (not /checkout)
    await page.waitForURL(/\/quote-request/, { timeout: 15000 })
    const currentUrl = page.url()
    expect(currentUrl).toContain('/quote-request')
    expect(currentUrl).not.toContain('/checkout')
    console.log(`REPORT: URL after click = ${currentUrl} ✓`)
    console.log('REPORT: Assertion passed — navigated to /quote-request, NOT /checkout ✓')

    await assertNoErrors(errors)
  })
})

// ======================================================================
// A2. CartPage 结构验证
// ======================================================================
test.describe('A2. CartPage structure verification', () => {
  test('Code check: handleRequestQuote routes to /quote-request', async () => {
    // Read the CartPage.vue source and verify the handleRequestQuote function
    const cartPagePath = path.resolve(__dirname, '../../frontend/src/views/CartPage.vue')
    const source = fs.readFileSync(cartPagePath, 'utf-8')

    // Extract the handleRequestQuote function
    const match = source.match(/function\s+handleRequestQuote\s*\(\s*\)\s*\{[^}]*\}/)
    expect(match).not.toBeNull()
    const fnBody = match[0]
    expect(fnBody).toContain("'/quote-request'")
    expect(fnBody).not.toContain("'/checkout'")
    console.log('REPORT: handleRequestQuote route check ✓ (routes to /quote-request)')
  })

  test('Code check: showSubmitApproval computed uses role === researcher only', async () => {
    const cartPagePath = path.resolve(__dirname, '../../frontend/src/views/CartPage.vue')
    const source = fs.readFileSync(cartPagePath, 'utf-8')

    // Extract the showSubmitApproval computed
    const match = source.match(/const\s+showSubmitApproval\s*=\s*computed\s*\(\s*\(\)\s*=>\s*\{[\s\S]*?\}\s*\)/)
    expect(match).not.toBeNull()
    const fnBody = match[0]

    // Must use role === 'researcher'
    expect(fnBody).toContain("role === 'researcher'")
    // Must NOT use !isOrgAdmin
    expect(fnBody).not.toContain('isOrgAdmin')
    console.log('REPORT: showSubmitApproval condition check ✓ (role === researcher, no !isOrgAdmin)')
  })

  test('Code check: CheckoutPage error handling chain has fallbacks', async () => {
    const checkoutPath = path.resolve(__dirname, '../../frontend/src/views/CheckoutPage.vue')
    const source = fs.readFileSync(checkoutPath, 'utf-8')

    // Find the catch block with error message chain
    // The chain should include response?.data?.meta?.error?.message
    expect(source).toContain('err?.response?.data?.meta?.error?.message')
    expect(source).toContain("err?.data?.meta?.error?.message")
    expect(source).toContain("err?.message")
    expect(source).toContain("Checkout failed")

    console.log('REPORT: CheckoutPage error handling chain check ✓ (has fallback chain)')
  })

  test('Cart page renders correctly with items', async ({ page }) => {
    const errors = await collectErrors(page)

    // Login and add items
    await login(page)
    await apiClearBasket(page)
    const added = await apiAddToCart(page, 446, 2)
    expect(added).toBeTruthy()

    // Navigate to cart
    await page.goto('/cart')
    await page.waitForSelector('.cart-page', { timeout: 15000 })
    await page.waitForSelector('.cart-items-list', { timeout: 15000 })

    // Assert cart structure elements are present
    await expect(page.locator('.cart-title')).toBeVisible()
    await expect(page.locator('.cart-items-list .cart-item')).toHaveCount(1)
    await expect(page.locator('.cart-summary')).toBeVisible()
    await expect(page.locator('button:has-text("Place Order")')).toBeVisible()
    await expect(page.locator('button:has-text("Request Quote")')).toBeVisible()

    console.log('REPORT: Cart page structure renders correctly ✓')

    await assertNoErrors(errors)
  })
})

// ======================================================================
// A3. 前端构建验证
// ======================================================================
test.describe('A3. Frontend build verification', () => {
  test('npm run build succeeds with 0 errors', async () => {
    const frontendDir = path.resolve(__dirname, '../../frontend')
    const { execSync } = require('child_process')

    let stdout, stderr, exitCode
    try {
      const result = execSync('npm run build -- --emptyOutDir false', {
        cwd: frontendDir,
        timeout: 120000,
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf-8',
      })
      stdout = result.stdout || ''
      stderr = result.stderr || ''
      exitCode = 0
    } catch (e) {
      stdout = e.stdout || ''
      stderr = e.stderr || ''
      exitCode = e.status || 1
    }

    // Log build output for diagnostics
    console.log(`BUILD exit code: ${exitCode}`)
    if (stdout) {
      const lines = stdout.split('\n').filter(l => l.trim())
      const relevant = lines.filter(l => l.includes('error') || l.includes('ERROR') || l.includes('vite') || l.includes('build'))
      if (relevant.length) console.log('BUILD relevant output:', relevant.join('\n'))
    }
    if (stderr && exitCode !== 0) {
      console.log('BUILD stderr:', stderr.substring(0, 1000))
    }

    expect(exitCode).toBe(0)
    console.log('REPORT: Frontend build succeeded with exit code 0 ✓')
  })
})
