/**
 * Part 1 · **B5 闸门（本地确定性）** —— 新建态"采纳文献"不得打到 `/products/null/`
 *
 * 背景（台账 B5，2026-09-22 修）：`ProductEditPage.vue` 曾把 Bioz 段的 `can-adopt` **硬编码为 `true`**，
 * 而组件 `BiozEvidenceSection.vue` 的设计是：
 *   - `:disabled="!canAdopt"`（两处 Adopt 按钮）
 *   - `:title="!canAdopt ? 'Save the product before adopting' : ''"`
 *   - `<p v-if="!canAdopt" class="bioz-nosave-hint">Save the product before adopting references</p>`
 * ⇒ 新建态 `productId = null` 时按钮**可点** ⇒ 必打 `/products/null/adopt-bioz-refs/` ⇒ **404**。
 * 已修：`:can-adopt="!!productId"`（按组件自身的设计意图接对）。
 *
 * 为什么本文件存在（而不是只在生产 D 组里断言）：生产 D 组跑的是**已部署**前端，
 * 修好但未部署时会红；而这里用 `page.route()` **伪造 enrich 响应**，让 Bioz 段在本地
 * **必然渲染**，从而**确定性**地验证"新建态必须 disabled + 提示 + 零 `/products/null/` 请求"。
 *
 * 运行（本地 dev 需已起 :8000 + :5173；输出重定向到文件，勿管道给 tail）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-bioz-guard.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-b5 > ../../_b5.log 2>&1
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff } = require('./helpers/auth')
const { consoleErrors } = require('./helpers/assertions.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })

/**
 * 伪造 enrich 响应：只给足让 Bioz 段渲染的字段。
 * 形状取自生产真实响应（`_probe_dgroup/enrich_D2.json` 的 `data.bioz`）。
 * 那条文献**不带 `ref_id`** ⇒ 组件会渲染 per-ref 的 `Adopt` 按钮（正是要验的目标）。
 */
const CANNED = {
  success: true,
  data: {
    chemical: { cid: null, cas_resolved: '', identity_verified: false, found: false },
    bioz: {
      queried: true,
      vendor: 'E2E-STUB',
      catalog_no: 'E2E-STUB-1',
      equivalence: 'exact',
      needs_review: false,
      disclaimer: 'E2E stub（不落库）',
      total: 1,
      references: [{
        article_title: 'E2E stub reference', authors: 'A. Author', journal: 'J. Stub',
        pub_date: '2026', doi: '10.0000/e2e-stub', pmid: '1', techniques: 'stub',
      }],
    },
  },
  meta: {},
}

test.describe('Part 1 · 新建态 Bioz 采纳守卫（B5）', () => {
  test('B5 @readonly @local-only 新建态：Adopt 必须 disabled + 显示未保存提示 + 零 /products/null/ 请求', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    const nullHits = []
    page.on('request', (r) => { if (r.url().includes('/products/null/')) nullHits.push(r.url()) })
    await page.route(/\/products\/enrich\//, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CANNED) }))

    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')
    await page.locator(`input[placeholder="e.g. 2'-Amino-ATP"]`).fill('E2E-B5-probe')
    await page.locator('.pubchem-enrich-section button.file-upload-btn').click()

    await expect(page.locator('.bioz-section'), 'Bioz 段应渲染（stub 有 1 条文献）').toBeVisible({ timeout: 15000 })
    const adoptOne = page.locator('.bioz-adopt-one')
    await expect(adoptOne, '新建态 per-ref Adopt 必须 disabled').toBeDisabled()
    await expect(page.locator('.bioz-adopt-all'), '新建态 Adopt all 必须 disabled').toBeDisabled()
    await expect(page.locator('.bioz-nosave-hint'), '应显示"先保存产品"提示').toBeVisible()
    expect(nullHits, `新建态不得请求 /products/null/，实际：${JSON.stringify(nullHits)}`).toEqual([])
    expect(errors).toEqual([])
  })
})
