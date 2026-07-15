/**
 * ProductEdit AI 面板澄清回归（Tier1 + Tier2, TDD RED spec）
 *
 * 覆盖本轮修复：
 *   ① 未验证时 AI 面板顶部显示警告横条（不会自动写入化学属性）
 *   ② Apply All to Form 按钮移到顶部且唯一（删除底部重复块）
 *   ③ Category 必填错误具体化（含"三级分类"）
 *   ④ 页面身份行：保存后显示 catalog_no · status（不依赖路由 meta 时机）
 *   ⑤ SEO 第 8 节标题简化为 "8. SEO"
 *   ⑥ AI 高级区（Lipinski/Jena/Bioz/文献/协议）默认折叠
 *
 * 运行：npx playwright test e2e/product-edit-aipanel.spec.cjs --project=chromium
 * 依赖：本地后端 :8000 + 前端 :5173 已启动（staff 登录）。
 */
const { test, expect } = require('@playwright/test')
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs')

const NAME_PH = "e.g. 2'-Amino-ATP"
const CAT_PH = 'e.g. SC8043'
const CAS_PH = 'e.g. 1927-31-7'
const SMILES_PH = 'e.g. C1=CC=C(C=C1)N'

// SC8007 真实值（截图复现：CID 245、未验证、单匹配）——用于稳定触发 unverified 状态
const SC8007_NAME = `2'-amino-2'-deoxyuridine 5'-(trihydrogen diphosphate)`
const SC8007_CAS = '33008-21-8'

async function fillBasicAndSave(page, name, catNo, { cas = '', smiles = '' } = {}) {
  await page.goto(`${BASE_URL}/workspace/products/new`)
  await page.locator(`input[placeholder="${NAME_PH}"]`).fill(name)
  await page.locator(`input[placeholder="${CAT_PH}"]`).fill(catNo)
  if (cas) await page.locator(`input[placeholder="${CAS_PH}"]`).fill(cas)
  if (smiles) await page.locator(`textarea[placeholder="${SMILES_PH}"]`).fill(smiles)
  await page.getByRole('button', { name: 'Save Draft' }).click()
  await expect(page.locator('.toast-success')).toContainText(/Product saved/i, { timeout: 15000 })
}

test.describe('ProductEdit AI panel clarity (Tier1+Tier2)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page)
  })

  // ③ Category 必填错误具体化（保存后才标红，符合"先填后报错"UX）
  test('③ Category required error mentions 三级分类', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E Cat ${ts}`, `E2E-CAT-${ts}`)
    await expect(page.locator('.field-error', { hasText: /三级分类/i })).toBeVisible()
  })

  // ④ 页面身份行：保存后显示 catalog_no
  test('④ page identity row shows catalog_no after save', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E Id ${ts}`, `E2E-ID-${ts}`)
    await expect(page.locator('.page-identity')).toContainText(`E2E-ID-${ts}`, { timeout: 15000 })
  })

  // ⑤ SEO 第 8 节标题简化
  test('⑤ SEO section title is "8. SEO"', async ({ page }) => {
    const ts = Date.now()
    await fillBasicAndSave(page, `E2E SEO ${ts}`, `E2E-SEO-${ts}`)
    await expect(page.locator('section.form-section h3', { hasText: /^8\. SEO$/ })).toBeVisible()
  })

  // ⑥ 高级区折叠默认闭合（需先让 AI 面板渲染：填 name）
  test('⑥ advanced match details collapsed by default', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/products/new`)
    await page.locator(`input[placeholder="${NAME_PH}"]`).fill('E2E Details Test')
    const details = page.locator('details.ai-advanced')
    await expect(details).toBeVisible()
    await expect(details).not.toHaveAttribute('open')
  })

  // 注：① 未验证警告横条 / ② Apply All 顶部去重 这两个用例依赖 AI AUTO MATCH 的 enrich 链路
  // （需 PubChem/ChEMBL 外部服务，仅生产环境可用）。本地 dev 环境 enrich 不渲染结果，故不在此
  // 跑 E2E；其正确性由以下两点保证：
  //   - 代码审查：横条 v-if="enrichChemical?.found && !chemAutoVerified && !enrichChemical.candidates?.length"；
  //     顶部按钮 v-if="enrichChemical?.found && !pubchemEnrichResult?.applied && !enrichChemical.candidates?.length"；
  //     底部重复块已删除。
  //   - 生产环境截图证据：SC8007（CID 245）导入后显示 "⚠ 未验证" 横条 + 单 "Apply All to Form" 按钮。
})
