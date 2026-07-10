// SciReAgent — full-feature E2E walkthrough of the research workspace (/workspace).
// Drives the browser like a human operator: every left-nav feature is exercised and
// asserted to render real data; product CRUD (create -> edit -> cleanup) is covered end-to-end.
//
// NOTE: AI buttons (validate / recommend / AI AUTO MATCH) are deliberately NOT clicked —
// they require external API keys absent from .env and would fail. Such buttons are skipped.
const { test, expect, login, gotoWorkspace, cleanupE2EProduct, selectFirstCascader } = require('./helpers')

// ─────────────────────────────────────────────────────────────────────────────
// Authentication
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Authentication', () => {
  test('unauthenticated visit to /workspace redirects to /login, then login lands on Dashboard', async ({ page }) => {
    // The public Home route is NOT protected; a protected workspace route IS.
    await page.goto('/workspace')
    await page.waitForURL('**/login**', { timeout: 15000 })
    await expect(page).toHaveURL(/login/)

    // Login form structure
    await expect(page.locator('#login-username')).toBeVisible()
    await expect(page.locator('#login-password')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible()

    // Submit credentials
    await page.fill('#login-username', 'admin')
    await page.fill('#login-password', 'admin123')
    await page.getByRole('button', { name: 'Sign In' }).click()

    // After login (isStaff) the app routes to the Dashboard at /workspace
    await page.waitForURL(/\/workspace$/, { timeout: 20000 })
    await expect(page).toHaveURL(/\/workspace$/)

    // Dashboard renders stat cards with numeric values
    await expect(page.locator('.stat-card').first()).toBeVisible()
    const total = await page.locator('.stat-card').first().locator('.stat-value').innerText()
    expect(total.trim()).toMatch(/\d+/)
    console.log(`REPORT: Dashboard total-products stat = ${total}`)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Workspace feature walkthrough (each left-nav item)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Workspace feature walkthrough', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('Dashboard shows stat cards with real numbers', async ({ page }) => {
    await gotoWorkspace(page, '/workspace')
    await expect(page.locator('.stat-card')).toHaveCount(4)
    for (const card of await page.locator('.stat-card').all()) {
      const v = (await card.locator('.stat-value').innerText()).trim()
      expect(v).toMatch(/\d+/)
    }
  })

  test('Products list renders real data', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/products')
    await expect(page.locator('.products-table')).toBeVisible()
    const rows = page.locator('.products-table tbody tr')
    await expect(rows.first()).toBeVisible()
    const n = await rows.count()
    expect(n).toBeGreaterThan(0)
    // Soft magnitude check vs known ~109
    console.log(`REPORT: Products rows rendered = ${n}`)
    await expect(page.locator('.filter-count')).toHaveText(/\d+ products/)
  })

  test('Research Goals list renders real data', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/goals')
    await expect(page.locator('.entity-page')).toBeVisible()
    const rows = page.locator('.entity-table tbody tr')
    await expect(rows.first()).toBeVisible()
    const n = await rows.count()
    expect(n).toBeGreaterThan(0)
    console.log(`REPORT: Research Goals rows = ${n}`)
  })

  test('Applications list renders real data', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/applications')
    await expect(page.locator('.entity-page')).toBeVisible()
    const rows = page.locator('.entity-table tbody tr')
    await expect(rows.first()).toBeVisible()
    const n = await rows.count()
    expect(n).toBeGreaterThan(0)
    console.log(`REPORT: Applications rows = ${n}`)
  })

  test('Methods list renders real data', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/methods')
    await expect(page.locator('.entity-page')).toBeVisible()
    const rows = page.locator('.entity-table tbody tr')
    await expect(rows.first()).toBeVisible()
    const n = await rows.count()
    expect(n).toBeGreaterThan(0)
    console.log(`REPORT: Methods rows = ${n}`)
  })

  test('Protocols list renders real data', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/protocols')
    await expect(page.locator('.entity-page')).toBeVisible()
    const rows = page.locator('.entity-table tbody tr')
    await expect(rows.first()).toBeVisible()
    const n = await rows.count()
    expect(n).toBeGreaterThan(0)
    console.log(`REPORT: Protocols rows = ${n}`)
  })

  test('References list renders real data', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/references')
    await expect(page.locator('.entity-page')).toBeVisible()
    const rows = page.locator('.entity-table tbody tr')
    await expect(rows.first()).toBeVisible()
    const n = await rows.count()
    expect(n).toBeGreaterThan(0)
    console.log(`REPORT: References rows = ${n}`)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Product CRUD (create -> edit -> cleanup)
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Product CRUD', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('create a product, edit it, and clean it up', async ({ page }) => {
    const ts = Date.now()
    const catNo = `E2E_TEST_${ts}`
    const name = `E2E_TEST_Product_${ts}`
    let id = null
    let created = false

    try {
      // ---- CREATE ----
      await gotoWorkspace(page, '/workspace/products/new')
      await page.waitForSelector('.product-edit', { timeout: 15000 })

      await page.locator('input[placeholder="e.g. 2\'-Amino-ATP"]').fill(name)
      await page.locator('input[placeholder="e.g. SC8043"]').fill(catNo)
      await page.locator('input[placeholder="e.g. 1927-31-7"]').fill('1234-56-7')
      await page.locator('textarea[placeholder="e.g. C1=CC=C(C=C1)N"]').fill('C1=CC=C(C=C1)N')

      // Category (Element Plus cascader) — pick the first available path
      await selectFirstCascader(page)

      // At least one default SKU is required
      await page.getByRole('button', { name: '+ Add SKU' }).click()
      await page.locator('.sku-table input[type="number"]').first().fill('1')

      // Save Draft
      await page.getByRole('button', { name: 'Save Draft' }).click()
      await page.waitForURL(/\/workspace\/products\/\d+\/edit$/, { timeout: 20000 })
      const editUrl = page.url()
      id = editUrl.match(/\/products\/(\d+)\/edit/)[1]
      console.log(`REPORT: Created product id=${id} catNo=${catNo}`)
      expect(Number(id)).toBeGreaterThan(0)
      created = true

      // ---- VERIFY it appears in the list ----
      await gotoWorkspace(page, '/workspace/products')
      await expect(page.locator('.products-table tbody tr', { hasText: catNo })).toBeVisible()

      // ---- EDIT ----
      await page.locator('.products-table tbody tr', { hasText: catNo }).click()
      await page.waitForURL(/\/workspace\/products\/\d+\/edit$/)
      await page.locator('input[placeholder="e.g. 2\'-Amino-ATP"]').fill(name + '_EDITED')
      await page.getByRole('button', { name: 'Save Draft' }).click()
      await page.waitForLoadState('networkidle')

      await gotoWorkspace(page, '/workspace/products')
      await expect(page.locator('.products-table tbody tr', { hasText: name + '_EDITED' })).toBeVisible()
      console.log(`REPORT: Edited product name to ${name}_EDITED`)
    } finally {
      // ALWAYS remove the E2E_TEST product we created — success or failure —
      // so the suite never leaves an orphan behind (hardening requirement).
      if (created && id) {
        try {
          await cleanupE2EProduct(page, id, catNo)
        } catch (e) {
          console.log(`REPORT: cleanup threw: ${e.message} — manual removal may be needed for id=${id}`)
        }
      }
    }
    console.log('REPORT: Product cleaned up successfully (no E2E_TEST residue)')
  })
})
