// ProductEdit AI Tools E2E — covers gap ④.
// Three buttons (🧠 AI Tools): Validate / Recommend Protocols / Recommend Literature.
//   - Validate  & Recommend Protocols run against the OFFLINE real backend (no mock).
//   - Recommend Literature is an OUTBOUND (PubMed) endpoint → MUST be mocked.
// We cover edit mode (pk variants) and new/unsaved mode (unsaved variants), plus the
// loading / success / error states.
const {
  test, expect, login, gotoWorkspace, cleanupE2EProduct, selectFirstCascader,
  mockRecommendLiterature, delayRoute,
} = require('./helpers')

// Create a minimal product via the UI; returns { id, catNo, name }.
async function createProductUI(page) {
  const ts = Date.now()
  const name = `E2E_TEST_AI_${ts}`
  const catNo = `E2E_TEST_AI_${ts}`
  await gotoWorkspace(page, '/workspace/products/new')
  await page.waitForSelector('.product-edit', { timeout: 15000 })
  await page.locator('input[placeholder="e.g. 2\'-Amino-ATP"]').fill(name)
  await page.locator('input[placeholder="e.g. SC8043"]').fill(catNo)
  await page.locator('input[placeholder="e.g. 1927-31-7"]').fill('62-53-3')
  await page.locator('textarea[placeholder="e.g. C1=CC=C(C=C1)N"]').fill('C1=CC=C(C=C1)N')
  await selectFirstCascader(page)
  await page.getByRole('button', { name: '+ Add SKU' }).click()
  await page.locator('.sku-table input[type="number"]').first().fill('1')
  await page.getByRole('button', { name: 'Save Draft' }).click()
  await page.waitForURL(/\/workspace\/products\/\d+\/edit$/, { timeout: 20000 })
  const id = page.url().match(/\/products\/(\d+)\/edit/)[1]
  return { id, catNo, name }
}

test.describe('ProductEdit AI Tools (gap ④) — edit mode', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('Validate (loading + success), Recommend Protocols (success), Recommend Literature (mocked success)', async ({ page }) => {
    const { id, catNo } = await createProductUI(page)
    try {
      await gotoWorkspace(page, `/workspace/products/${id}/edit`)
      await page.waitForSelector('.product-edit', { timeout: 15000 })

      // ── Validate: delay the (real, offline) request to observe the LOADING state ──
      await delayRoute(page, '**/products/**/validate/**', 1500)
      const validateBtn = page.getByRole('button', { name: /Validate/ })
      await validateBtn.click()
      // loading state: button switches to "Validating…" while the request is in flight
      await expect(page.getByRole('button', { name: /Validating/ })).toBeVisible({ timeout: 5000 })
      // success state: validation result block renders with the overall match badge
      await expect(page.locator('.ai-result-block').first()).toBeVisible({ timeout: 20000 })
      await expect(page.locator('.ai-badge', { hasText: 'Overall Match' })).toBeVisible()
      console.log('REPORT: Validate → result block rendered (Overall Match badge present)')

      // ── Recommend Protocols: real offline backend ──
      await page.getByRole('button', { name: /Recommend Protocols/ }).click()
      const protBlock = page.locator('.ai-result-block', { hasText: 'Recommended Protocols' })
      await expect(protBlock).toBeVisible({ timeout: 20000 })
      await expect(page.locator('.ai-rec-item').first()).toBeVisible()
      await expect(page.locator('.ai-rec-item').first().locator('.ai-badge', { hasText: 'Relevance' })).toBeVisible()
      console.log('REPORT: Recommend Protocols → ' + (await page.locator('.ai-rec-item').count()) + ' item(s) with relevance score')

      // ── Recommend Literature: OUTBOUND → mocked ──
      await mockRecommendLiterature(page, {
        refs: [
          { pmid: '24151973', title: 'E2E Mock Literature A', authors: 'Doe J', journal: 'Nature', year: 2020 },
          { pmid: '25959142', title: 'E2E Mock Literature B', authors: 'Lee K', journal: 'Cell', year: 2021 },
        ],
      })
      await page.getByRole('button', { name: /Recommend Literature/ }).click()
      const litBlock = page.locator('.ai-result-block', { hasText: 'Recommended Literature' })
      await expect(litBlock).toBeVisible({ timeout: 20000 })
      // Scope the count to the LITERATURE block — the Protocols block also renders
      // `.ai-rec-item`, so an unscoped count would include those too.
      await expect(litBlock.locator('.ai-rec-item')).toHaveCount(2)
      await expect(litBlock.locator('.ai-rec-item').first()).toContainText('E2E Mock Literature A')
      console.log('REPORT: Recommend Literature (mocked) → 2 items rendered')
    } finally {
      await cleanupE2EProduct(page, id, catNo)
    }
  })

  test('Recommend Literature error state shows the error banner (mocked failure)', async ({ page }) => {
    const { id, catNo } = await createProductUI(page)
    try {
      await gotoWorkspace(page, `/workspace/products/${id}/edit`)
      await page.waitForSelector('.product-edit', { timeout: 15000 })

      await mockRecommendLiterature(page, { failure: true })
      await page.getByRole('button', { name: /Recommend Literature/ }).click()

      const err = page.locator('.word-status.word-err')
      await expect(err).toBeVisible({ timeout: 20000 })
      await expect(err).toContainText(/recommend literature failed/i)
      console.log('REPORT: Recommend Literature error → banner shown')
    } finally {
      await cleanupE2EProduct(page, id, catNo)
    }
  })
})

test.describe('ProductEdit AI Tools (gap ④) — new / unsaved mode', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('unsaved variants: Validate, Recommend Protocols, Recommend Literature (mocked)', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/products/new')
    await page.waitForSelector('.product-edit', { timeout: 15000 })

    const ts = Date.now()
    await page.locator('input[placeholder="e.g. 2\'-Amino-ATP"]').fill(`E2E_UNSAVED_${ts}`)
    await page.locator('input[placeholder="e.g. 1927-31-7"]').fill('62-53-3')
    await page.locator('textarea[placeholder="e.g. C1=CC=C(C=C1)N"]').fill('C1=CC=C(C=C1)N')

    // Validate (unsaved variant, real offline backend)
    await page.getByRole('button', { name: /Validate/ }).click()
    await expect(page.locator('.ai-result-block').first()).toBeVisible({ timeout: 20000 })
    await expect(page.locator('.ai-badge', { hasText: 'Overall Match' })).toBeVisible()
    console.log('REPORT: unsaved Validate → result block rendered')

    // Recommend Protocols (unsaved variant, real offline backend)
    await page.getByRole('button', { name: /Recommend Protocols/ }).click()
    await expect(page.locator('.ai-result-block', { hasText: 'Recommended Protocols' })).toBeVisible({ timeout: 20000 })
    console.log('REPORT: unsaved Recommend Protocols → block rendered')

    // Recommend Literature (unsaved variant, mocked)
    await mockRecommendLiterature(page, {
      refs: [{ pmid: '99999999', title: 'E2E Unsaved Lit', authors: 'Mock A', journal: 'Mock J', year: 2022 }],
    })
    await page.getByRole('button', { name: /Recommend Literature/ }).click()
    await expect(page.locator('.ai-result-block', { hasText: 'Recommended Literature' })).toBeVisible({ timeout: 20000 })
    console.log('REPORT: unsaved Recommend Literature (mocked) → block rendered')
    // No product was saved → nothing to clean up.
  })
})
