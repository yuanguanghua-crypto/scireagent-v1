/**
 * #172 修复回归（TDD RED spec）
 *
 * 覆盖本轮修复：
 *   (A) 深色模式 Toast 对比度：成功提示文字应为浅色（emerald-100），
 *       不再是深绿底+中绿字的低对比糊在一起；且 Toast 应水平居中（#173，不再固定右上角）。
 *   (B) 保存草稿时自动关联 Knowledge Links：AI AUTO MATCH 拿到 enrich 结果后，
 *       直接 Save Draft（不点 Apply All）也应把 Knowledge Chain 匹配的 Methods 关联进表单。
 *
 * 运行：npx playwright test e2e/product-edit-dark-a11y-knowledge.spec.cjs --project=chromium
 * 依赖：本地后端 :8000 + 前端 :5173 已启动（staff 登录）。
 *   注意：enrich 依赖外部 PubChem/ChEMBL，本地不通，故用 page.route 拦截 mock。
 */
const { test, expect } = require('@playwright/test')
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs')

const NAME_PH = "e.g. 2'-Amino-ATP"
const CAT_PH = 'e.g. SC8043'

// 浅色预期（修复后）：emerald-100 = rgb(209, 250, 229)
const TOAST_LIGHT_COLOR = 'rgb(209, 250, 229)'

// mock enrich 响应（与后端 /products/enrich/ 业务对象结构一致）
const ENRICH_MOCK = {
  chemical: {
    found: true,
    identity_verified: true,
    cas_resolved: '12345-67-8',
    source: 'pubchem',
    cid: 12345,
    confidence: 'high',
    properties: {
      canonical_smiles: 'C1CCCCC1',
      molecular_formula: 'C6H12',
      molecular_weight: 84.16,
    },
  },
  literature: {
    matched_methods: [
      { keyword: 'PCR', matches: [{ id: 1, name: 'Polymerase Chain Reaction' }] },
    ],
    matched_apps: [],
    unmatched_method_keywords: [],
    unmatched_app_keywords: [],
  },
  protocols: [],
  jena: { matched: false },
  bioz: { evidence: [] },
}

async function gotoNewProduct(page) {
  await page.goto(`${BASE_URL}/workspace/products/new`)
}

async function fillBasic(page, name, catNo) {
  await page.locator(`input[placeholder="${NAME_PH}"]`).fill(name)
  await page.locator(`input[placeholder="${CAT_PH}"]`).fill(catNo)
}

test.describe('#172 dark toast contrast + knowledge auto-link', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page)
  })

  // (A) 深色模式 Toast 成功提示文字应为浅色
  test('(A) dark mode toast-success text is light-colored (high contrast)', async ({ page }) => {
    // 启用深色模式
    await page.evaluate(() => localStorage.setItem('scireagent_theme', 'dark'))
    await page.reload()
    await expect(page.locator('html')).toHaveClass(/dark/)

    const ts = Date.now()
    await gotoNewProduct(page)
    await fillBasic(page, `E2E Dark Toast ${ts}`, `E2E-DT-${ts}`)
    await page.getByRole('button', { name: 'Save Draft' }).click()

    const toast = page.locator('.toast-success')
    await expect(toast).toBeVisible({ timeout: 15000 })
    // 修复前：深色模式下 color 为 emerald-700（rgb(4, 120, 87)），与深绿底糊在一起 → 失败
    // 修复后：color 为 emerald-100（rgb(209, 250, 229)）→ 通过
    await expect(toast).toHaveCSS('color', TOAST_LIGHT_COLOR)

    // #173：Toast 应水平居中（不再固定右上角）。几何断言：toast 中心 x ≈ 视口中心 x。
    const box = await toast.boundingBox()
    const vw = (page.viewportSize() || { width: 1280 }).width
    expect(Math.abs(box.x + box.width / 2 - vw / 2)).toBeLessThan(3)
  })

  // (B) AI AUTO MATCH 后直接 Save Draft 自动关联 Knowledge Links
  test('(B) Save Draft auto-links Knowledge Chain methods without Apply All', async ({ page }) => {
    // mock enrich（本地外部链路不通）
    await page.route('**/products/enrich/', (route) =>
      route.fulfill({ status: 200, json: { success: true, data: ENRICH_MOCK } }),
    )
    // mock 产品创建/详情：GET 回显 POST payload 中的 method_ids，
    // 这样才能真实反映 saveDraft 是否自动把 Knowledge Links 传给了后端。
    let savedMethodIds = []
    await page.route('**/products/', (route) => {
      const url = route.request().url()
      if (url.includes('/enrich/')) return route.fallback()
      const method = route.request().method()
      if (method === 'POST') {
        const body = route.request().postData()
        try { savedMethodIds = JSON.parse(body).method_ids || [] } catch { /* ignore */ }
        return route.fulfill({ status: 200, json: { success: true, data: { id: 999, slug: 'e2e-999' } } })
      }
      if (method === 'GET') {
        return route.fulfill({
          status: 200,
          json: {
            success: true,
            data: {
              id: 999,
              method_ids: savedMethodIds,
              protocol_ids: [],
              name: 'E2E KL',
              catalog_no: 'E2E-KL',
              status: 'draft',
              skus: [],
            },
          },
        })
      }
      return route.fallback()
    })

    const ts = Date.now()
    await gotoNewProduct(page)
    await fillBasic(page, `E2E Knowledge ${ts}`, `E2E-KL-${ts}`)

    // 触发 AI AUTO MATCH（mock 返回）
    await page.getByRole('button', { name: /AI AUTO MATCH/i }).click()
    // enrich 完成后面板会出现两个 word-ok（Found / 已验证），用 first 避免 strict 冲突
    await expect(page.locator('.word-status.word-ok').first()).toBeVisible({ timeout: 15000 })

    // 直接 Save Draft（不点 Apply All）
    await page.getByRole('button', { name: 'Save Draft' }).click()

    // 5. Knowledge Links → Methods 区块应出现关联 chip（不是 "None"）
    const methodsGroup = page.locator('.chip-group').filter({ hasText: 'Methods:' })
    await expect(methodsGroup.locator('.chip')).toBeVisible({ timeout: 15000 })
    await expect(methodsGroup.locator('.chip-none')).toHaveCount(0)
  })
})
