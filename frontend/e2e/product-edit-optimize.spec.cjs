/**
 * ProductEdit 优化回归（①~⑥，TDD RED spec）
 *
 * 覆盖确认任务：
 *   ① Compliance 节常显 + 未保存占位横幅
 *   ② SDS 生成：缺标识时按钮「不静默禁用」，点击/常显给出引导
 *   ③ 生命周期状态步进器 + 文档批准按钮更名为 "Approve & Publish SDS/COA"
 *   ④ 生成后 Toast 明确引导（"Approve & Publish"）
 *   ⑤ 合并 Batch+COA 为单一 "Generate COA" 入口（无重复 per-batch 按钮）
 *   ⑥ 首次保存后不跳离 + 解锁提示（Toast 提及 SDS/COA/SEO）
 *
 * 运行：npx playwright test e2e/product-edit-optimize.spec.cjs
 * 依赖：本地后端 :8000 + 前端 :5173 已启动（staff 登录）。
 */
const { test, expect } = require('@playwright/test')
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs')

const NAME_PH = "e.g. 2'-Amino-ATP"
const CAT_PH = 'e.g. SC8043'
const CAS_PH = 'e.g. 1927-31-7'
const SMILES_PH = 'e.g. C1=CC=C(C=C1)N'

async function fillBasicAndSave(page, name, catNo, { cas = '', smiles = '' } = {}) {
  await page.goto(`${BASE_URL}/workspace/products/new`)
  await page.locator(`input[placeholder="${NAME_PH}"]`).fill(name)
  await page.locator(`input[placeholder="${CAT_PH}"]`).fill(catNo)
  if (cas) await page.locator(`input[placeholder="${CAS_PH}"]`).fill(cas)
  if (smiles) await page.locator(`textarea[placeholder="${SMILES_PH}"]`).fill(smiles)
  await page.getByRole('button', { name: 'Save Draft' }).click()
  await expect(page.locator('.toast-success')).toContainText(/Product saved/i, { timeout: 15000 })
}

test.describe('ProductEdit optimization (①~⑥)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page)
  })

  // ① 新建产品：Compliance 节可见 + 占位横幅
  test('① new product: Compliance section visible + save-first placeholder', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/products/new`)
    await expect(page.locator('section.form-section', { hasText: 'Compliance' })).toBeVisible()
    await expect(page.locator('.compliance-placeholder')).toContainText(/Save the product first/i)
  })

  // ② 缺化学标识：SDS 按钮「不禁用」+ 常显引导（点击也给引导）
  test('② SDS generate: enabled without identifiers; guidance shown', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E Opt NoChem ${ts}`, `E2E-NOCHEM-${ts}`)
    const sdsBtn = page.getByRole('button', { name: 'Generate SDS' })
    await expect(sdsBtn).toBeVisible()
    await expect(sdsBtn).toBeEnabled()
    // 常显引导
    await expect(page.locator('.sds-hint')).toContainText(/CAS|SMILES|InChI/i)
    // 点击也给引导
    await sdsBtn.click()
    await expect(page.locator('.toast-warn')).toContainText(/CAS|SMILES|InChI/i, { timeout: 10000 })
  })

  // ③ 生命周期步进器 + 文档批准按钮更名
  test('③ lifecycle stepper + SDS approve button renamed', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E Opt Chem ${ts}`, `E2E-CHEM-${ts}`, { cas: '123-45-6', smiles: 'C1=CC=C(C=C1)N' })
    await expect(page.locator('.lifecycle-stepper')).toBeVisible()
    // 生成 SDS（后端生成可能较慢，放宽等待；用稳定后置条件而非 toast 时序）
    await page.getByRole('button', { name: 'Generate SDS' }).click()
    await expect(page.locator('.sds-rev-card').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('button', { name: /Approve & Publish SDS/i })).toBeVisible()
  })

  // ④ 生成 SDS 后 Toast 引导「Approve & Publish」
  test('④ SDS generated toast guides to Approve & Publish', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E Opt Guide ${ts}`, `E2E-GUIDE-${ts}`, { cas: '123-45-6', smiles: 'C1=CC=C(C=C1)N' })
    await page.getByRole('button', { name: 'Generate SDS' }).click()
    await expect(page.locator('.toast-success')).toContainText(/Approve & Publish SDS/i, { timeout: 30000 })
  })

  // ⑤ 单一 "Generate COA" 入口（含一个 SKU 且无批次）
  test('⑤ single Generate COA entry (no duplicate per-batch button)', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E Opt COA ${ts}`, `E2E-COA-${ts}`)
    // 添加一个默认 SKU 并再次保存（编辑态）
    await page.getByRole('button', { name: '+ Add SKU' }).click()
    await page.getByRole('button', { name: 'Save Draft' }).click()
    // 重新保存后，该 SKU 应仅出现一个 "Generate COA" 入口（无 per-batch 重复按钮）
    const coaBtns = page.getByRole('button', { name: 'Generate COA' })
    await expect(coaBtns).toHaveCount(1)
  })

  // ⑥ 首次保存解锁提示（Toast 提及 SDS/COA/SEO）
  test('⑥ first save unlock hint mentions SDS/COA/SEO', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E Opt Unlock ${ts}`, `E2E-UNLOCK-${ts}`)
    await expect(page.locator('.toast-success')).toContainText(/SDS/i, { timeout: 10000 })
    await expect(page.locator('.toast-success')).toContainText(/COA/i, { timeout: 10000 })
    await expect(page.locator('.toast-success')).toContainText(/SEO/i, { timeout: 10000 })
  })
})
