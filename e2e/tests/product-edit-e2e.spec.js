// ProductEdit AI AUTO MATCH E2E。
//
// 历史背景：2026-07-17 commit f324de0 将 AI Tools（Validate / Recommend Protocols /
// Recommend Literature）合并进「AI AUTO MATCH」one-stop enrich，独立的
// /validate、/recommend-protocols、/recommend-literature 端点与面板已从产品编辑页删除。
// 旧 spec 的 3 个失败用例断言的是已删除的按钮（getByRole /Validate/ 等超时），根因即
// 此。故本文件重写为断言当前真实存在的 AI AUTO MATCH 面板
// （frontend/src/views/workspace/ProductEditPage.vue 的 .pubchem-enrich-section）：
//   - AI AUTO MATCH 按钮（.file-upload-btn，文案 `AI AUTO MATCH "..."`）
//   - loading 态（按钮文案 "Searching & matching…" + .ai-loading-spinner）
//   - 成功态（.pubchem-preview / .source-badge / "Found: ... CID" / Apply All to Form）
//   - 错误态（.word-status.word-err）
// 注意：enrich 真实调用依赖外部 LLM API（backend/.env 的 SCIREAGENT_LLM_API_KEY），
// 真实触发会消耗 token，故所有 AI AUTO MATCH 交互一律 mock（helpers.mockEnrich），
// 不真实触发 AI 调用。
// 原「Recommend Literature」相关用例已删除：独立端点已不存在，亦无对应新功能
// （literature 已并入 enrich 返回的 literature.references，当前无独立按钮）。
const {
  test, expect, login, gotoWorkspace, cleanupE2EProduct, selectFirstCascader,
  mockEnrich,
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

test.describe('ProductEdit AI AUTO MATCH — edit mode', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('AI AUTO MATCH 面板/按钮存在，enrich 成功（mocked）渲染结果区', async ({ page }) => {
    const { id, catNo } = await createProductUI(page)
    try {
      await gotoWorkspace(page, `/workspace/products/${id}/edit`)
      await page.waitForSelector('.product-edit', { timeout: 15000 })

      // ── 面板与按钮真实存在（不再有旧的 Validate / Recommend 按钮）──
      await expect(page.locator('h3', { hasText: 'AI AUTO MATCH' })).toBeVisible()
      const matchBtn = page.getByRole('button', { name: /AI AUTO MATCH/ })
      await expect(matchBtn).toBeVisible()

      // ── mock enrich + 1500ms 延迟以观察 loading 态；不真实触发外部 LLM ──
      await mockEnrich(page, { delay: 1500 })
      await matchBtn.click()
      // loading 态：spinner 出现（aria-label="loading"）
      await expect(page.locator('.ai-loading-spinner[aria-label="loading"]')).toBeVisible({ timeout: 5000 })
      // 成功态：结果预览区 + 来源徽标 + Found 状态 + Apply All 按钮
      await expect(page.locator('.pubchem-preview').first()).toBeVisible({ timeout: 20000 })
      await expect(page.locator('.source-badge').first()).toContainText('PubChem')
      // Found 状态：页面上有两个 .word-status.word-ok（Found 与 身份已验证），按文本过滤
      await expect(page.locator('.word-status.word-ok', { hasText: 'Found: PubChem CID' })).toBeVisible()
      await expect(page.locator('.word-status.word-ok', { hasText: 'Found: PubChem CID' })).toContainText('999999')
      await expect(page.getByRole('button', { name: 'Apply All to Form' })).toBeVisible()
      console.log('REPORT: AI AUTO MATCH → loading + success 态均渲染（enrich 已 mock）')
    } finally {
      await cleanupE2EProduct(page, id, catNo)
    }
  })

  test('AI AUTO MATCH 失败（mocked）展示错误横幅', async ({ page }) => {
    const { id, catNo } = await createProductUI(page)
    try {
      await gotoWorkspace(page, `/workspace/products/${id}/edit`)
      await page.waitForSelector('.product-edit', { timeout: 15000 })

      await mockEnrich(page, { failure: true })
      await page.getByRole('button', { name: /AI AUTO MATCH/ }).click()

      const err = page.locator('.word-status.word-err')
      await expect(err).toBeVisible({ timeout: 20000 })
      await expect(err).toContainText('Enrich failed')
      console.log('REPORT: AI AUTO MATCH error → 错误横幅展示')
    } finally {
      await cleanupE2EProduct(page, id, catNo)
    }
  })
})

test.describe('ProductEdit AI AUTO MATCH — new / unsaved mode', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('unsaved variant: AI AUTO MATCH（mocked）成功渲染 enrich 结果', async ({ page }) => {
    await gotoWorkspace(page, '/workspace/products/new')
    await page.waitForSelector('.product-edit', { timeout: 15000 })

    const ts = Date.now()
    await page.locator('input[placeholder="e.g. 2\'-Amino-ATP"]').fill(`E2E_UNSAVED_${ts}`)
    await page.locator('input[placeholder="e.g. 1927-31-7"]').fill('62-53-3')
    await page.locator('textarea[placeholder="e.g. C1=CC=C(C=C1)N"]').fill('C1=CC=C(C=C1)N')

    await mockEnrich(page)
    await page.getByRole('button', { name: /AI AUTO MATCH/ }).click()
    await expect(page.locator('.pubchem-preview').first()).toBeVisible({ timeout: 20000 })
    await expect(page.locator('.source-badge').first()).toContainText('PubChem')
    console.log('REPORT: unsaved AI AUTO MATCH → enrich 结果渲染')
    // 未保存产品 → 无需清理
  })
})
