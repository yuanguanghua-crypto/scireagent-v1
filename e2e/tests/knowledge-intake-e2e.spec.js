// KnowledgeIntake E2E — covers gap ①: sidebar entry → /workspace/knowledge-intake,
// filling the intake form (goal/app/method chips, references, notes, confidence) and
// saving successfully, with full DB cleanup (product + any get_or_create orphans).
//
// NOTE: the backing product is created via the API (not the ProductEditPage UI) so this
// spec stays independent of the chemical-structure editor and its React-in-Vue Ketcher.
const {
  test, expect, login, gotoWorkspace, cleanupE2EProduct,
  getToken, cleanupKnowledgeIntakeOrphans,
} = require('./helpers')

// Create a minimal E2E product via the API (slug is required by the serializer).
async function createE2EProductViaApi(page, token) {
  const ts = Date.now()
  const name = `E2E_TEST_KI_${ts}`
  const catNo = `E2E_TEST_KI_${ts}`
  const r = await page.request.post('/api/v1/products/', {
    headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' },
    data: {
      name,
      catalog_no: catNo,
      slug: `e2e-test-ki-${ts}`,
      cas: '1234-56-7',
      smiles: 'C1=CC=C(C=C1)N',
      category_l1: 'Small Molecule',
      status: 'draft',
    },
    failOnStatusCode: false,
  })
  const j = await r.json().catch(() => ({}))
  const id = (j.data && j.data.id) || (j.id)
  return { id, catNo, name }
}

// Chip option names selected in this test. These English option names are NOT present in
// the seeded (Chinese) DB, so get_or_create would create orphans — we remove them on cleanup.
const SELECTED = {
  research_goals: ['RNA Analysis'],
  applications: ['RNA Fluorescent Labeling'],
  methods: ['CuAAC Click Chemistry'],
}

test.describe('KnowledgeIntake (gap ①)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('enter from sidebar, fill intake form, save successfully, and clean up', async ({ page }) => {
    const token = await getToken(page)
    const { id, catNo, name } = await createE2EProductViaApi(page, token)
    expect(Number(id)).toBeGreaterThan(0)
    console.log(`REPORT: KI backing product id=${id} catNo=${catNo}`)

    try {
      // ── Navigate from the sidebar "Knowledge Intake" entry ──
      await gotoWorkspace(page, '/workspace/knowledge-intake')
      await expect(page.locator('.ki-page')).toBeVisible()
      await expect(page.locator('.ki-title')).toHaveText('Knowledge Content Intake')

      // Wait for the product list to load (left sidebar).
      await expect(page.locator('.ki-product-item').first()).toBeVisible({ timeout: 15000 })

      // ── Select the backing product from the list ──
      const productItem = page.locator('.ki-product-item', { hasText: catNo }).first()
      await expect(productItem).toBeVisible()
      await productItem.click()
      await expect(page.locator('.ki-form-area')).toBeVisible()

      // ── Toggle chips (goals / applications / methods) ──
      for (const g of SELECTED.research_goals) {
        const chip = page.locator('.ki-chip', { hasText: g }).first()
        await chip.click()
        await expect(chip).toHaveClass(/ki-chip-active/)
      }
      for (const a of SELECTED.applications) {
        const chip = page.locator('.ki-chip', { hasText: a }).first()
        await chip.click()
        await expect(chip).toHaveClass(/ki-chip-active/)
      }
      for (const m of SELECTED.methods) {
        const chip = page.locator('.ki-chip', { hasText: m }).first()
        await chip.click()
        await expect(chip).toHaveClass(/ki-chip-active/)
      }

      // ── Fill references + notes + confidence ──
      await page.locator('input[placeholder="24151973, 25959142"]').fill('24151973, 25959142')
      await page.locator('input[placeholder="10.1038/nprot.2014.001"]').fill('10.1038/nprot.2014.001')
      await page.locator('textarea[placeholder="High specificity; Bioorthogonal"]').fill('High specificity; Bioorthogonal')
      await page.locator('textarea[placeholder="Copper toxicity; Needs modified substrates"]').fill('Copper toxicity; Needs modified substrates')
      // Confidence defaults to 'high'; click to assert the control works.
      const confChip = page.locator('.ki-chip', { hasText: 'high' }).first()
      await confChip.click()
      await expect(confChip).toHaveClass(/ki-chip-active/)

      // ── Save ──
      await page.getByRole('button', { name: 'Save' }).click()

      // Success toast confirms persistence.
      const toast = page.locator('.ki-toast.ok')
      await expect(toast).toBeVisible({ timeout: 15000 })
      await expect(toast).toContainText(`Saved knowledge for ${catNo}`)
      console.log('REPORT: KnowledgeIntake save succeeded (toast shown)')
    } finally {
      // Always remove the backing product (UI Products page → API fallback) + any orphans.
      try {
        if (id) await cleanupE2EProduct(page, id, catNo)
      } catch (e) {
        console.log('REPORT: KI product cleanup threw:', e.message)
      }
      try {
        await cleanupKnowledgeIntakeOrphans(page, token, SELECTED)
      } catch (e) {
        console.log('REPORT: KI orphan cleanup threw:', e.message)
      }
    }
  })
})
