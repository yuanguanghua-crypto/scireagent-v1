/**
 * 阶段 10（a11y）— 关键页可访问性扫描（维度 A）
 * 用 @axe-core/playwright 扫描关键页，硬断言 critical / serious 违规为 0。
 *
 * 修复历史（2026-07-11 a11y 整改 pass）：
 *   - 主色 emerald-600→emerald-700；成功色文本（on 浅绿底）统一改为 emerald-800
 *     （--color-primary-active），满足 WCAG AA 4.5:1（实测 ~6.8:1）。
 *   - AdminOrders：图标按钮加 aria-label、<select> 加可访问名、表头/状态徽章改深令牌。
 *   - Workspace：.nav-item.active 与 .status-tag.status-active 改 emerald-800。
 *   - 仅扫描 wcag2a + wcag2aa 标签（AA 4.5:1 阈值），不含 enhanced 7:1。
 *
 * 扫描页：公开（Home / Products / ProductDetail）+ staff（AdminOrders / Workspace）。
 */
const { test, expect } = require('@playwright/test')
const { AxeBuilder } = require('@axe-core/playwright')
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs')

async function scan(page, label) {
  // 等待瞬时加载态（.spinner-text Loading...）消失，只对稳定 DOM 做扫描。
  // 否则 axe 会在 spinner 重绘的那一帧抓到不稳定的计算色，产生伪 serious 违规。
  await page
    .waitForSelector('.spinner-text', { state: 'detached', timeout: 15000 })
    .catch(() => {})
  // 冻结过渡/动画：本项目的 .el-tag / page-enter 等带 transition:all，
  // axe 若在过渡帧采样会抓到中间色（如 Element 默认 #7d8795），造成伪 serious。
  // 冻结后元素立即落在最终（合规）色，扫描结果稳定可复现。
  await page
    .addStyleTag({
      content:
        '*,*::before,*::after{transition:none !important;animation:none !important;transition-duration:0s !important;animation-duration:0s !important;}',
    })
    .catch(() => {})
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()
  const critical = results.violations.filter((v) => v.impact === 'critical')
  const serious = results.violations.filter((v) => v.impact === 'serious')
  const total = results.violations.length
  console.log(`A11Y[${label}] total=${total} critical=${critical.length} serious=${serious.length}`)
    if (critical.length || serious.length) {
      const detail = [...critical, ...serious]
        .map((v) => {
          // ★ 2026-10-20：原来只打处数，看不出是哪个元素。补上 axe 给的 target/failureSummary。
          const nodes = (v.nodes || []).slice(0, 5).map((n) => {
            const tgt = Array.isArray(n.target) ? n.target.join(' ') : String(n.target)
            const msg = (n.failureSummary || '').split('\n').filter(Boolean).slice(-1)[0] || ''
            // ★ 2026-10-21：加元素 HTML 片段 —— 只有 selector（如 #el-id-1-82）时无法定位到组件源码，
            //   axe 的 n.html 能看出是什么控件（Element Plus 的自动 id 尤其需要这个）。
            const html = (n.html || '').replace(/\s+/g, ' ').slice(0, 110)
            return `      · ${tgt}\n        HTML: ${html}${msg ? '\n        ← ' + msg.slice(0, 80) : ''}`
          }).join('\n')
          const more = (v.nodes || []).length > 5 ? `\n      · …还有 ${v.nodes.length - 5} 处` : ''
          return `  - [${v.impact}] ${v.id}: ${v.help} (${(v.nodes || []).length} 处)\n${nodes}${more}`
        })
        .join('\n')
      console.log(`A11Y[${label}] 违规:\n${detail}`)
    }
  // a11y 整改 pass（2026-07-11）后清零已知债，回归不得回退。
  expect(critical, `A11Y[${label}] 不应存在 critical 级可访问性违规`).toHaveLength(0)
  expect(serious, `A11Y[${label}] 不应存在 serious 级可访问性违规`).toHaveLength(0)
}

  const PUBLIC = [
    { name: 'Home', path: '/', sel: '.home' },
    { name: 'Products', path: '/products', sel: '.product-grid' },
    { name: 'ProductDetail', path: '/products/66', sel: 'main' },
    // ★ 2026-10-20 扩容：A 维此前只覆盖 3 个公开页（全站 44 页里 11%）
    { name: 'LoginPage', path: '/login', sel: '.auth-page' },
    { name: 'RegisterPage', path: '/register', sel: '.auth-page' },
    { name: 'SearchPage', path: '/search', sel: '.search-page' },
    { name: 'ApplicationIndex', path: '/applications', sel: '.application-index' },
    { name: 'MethodIndex', path: '/methods', sel: '.method-index' },
    { name: 'ProtocolIndex', path: '/protocols', sel: '.protocol-index' },
    { name: 'ResearchGoalIndex', path: '/research-goals', sel: '.research-goal-index' },
    { name: 'QuoteRequestPage', path: '/quote-request', sel: '.rfq-page' },
    { name: 'CartPage', path: '/cart', sel: '.cart-page' },
  ]
  const STAFF = [
    { name: 'AdminOrders', path: '/ops/orders', sel: '.order-table' },
    { name: 'Workspace', path: '/workspace', sel: '.workspace-layout' },
    // ★ 2026-10-20 扩容
    { name: 'SettingsPage', path: '/settings', sel: '.settings-page' },
    { name: 'CheckoutPage', path: '/checkout', sel: '.checkout-page' },
    { name: 'OrderListPage', path: '/orders', sel: '.order-list-page' },
    { name: 'PoSubmit', path: '/po/submit', sel: '.po-page' },
    { name: 'PoOrderList', path: '/po/orders', sel: '.po-page' },
    { name: 'PoAddressList', path: '/po/addresses', sel: '.po-page' },
    { name: 'PoReorder', path: '/po/reorder', sel: '.po-page' },
    { name: 'PoDownloadCenter', path: '/po/downloads', sel: '.po-page' },
    // ★ 2026-10-21 P3：补 5 个 PO 内部审核台（A 维缺口按 audit 逐页算出来的）
    { name: 'PoReviewDesk', path: '/ops/po/review', sel: '.po-page' },
    { name: 'PoShipmentDesk', path: '/ops/po/shipments', sel: '.po-page' },
    { name: 'PoInvoicingDesk', path: '/ops/po/invoicing', sel: '.po-page' },
    { name: 'PoArReport', path: '/ops/po/ar', sel: '.po-page' },
    { name: 'PoOrgManagement', path: '/ops/po/organizations', sel: '.po-page' },
    // ★ 2026-10-21 P4：补 /workspace 子页 + products 两页（A 维缺口集中在这里）
    { name: 'WorkspaceProducts', path: '/workspace/products', sel: '.products-page' },
    { name: 'ProductNew', path: '/workspace/products/new', sel: '.product-edit' },
    { name: 'WsGoals', path: '/workspace/goals', sel: '.entity-page' },
    { name: 'WsApplications', path: '/workspace/applications', sel: '.entity-page' },
    { name: 'WsMethods', path: '/workspace/methods', sel: '.entity-page' },
    { name: 'WsProtocols', path: '/workspace/protocols', sel: '.entity-page' },
    { name: 'WsReferences', path: '/workspace/references', sel: '.entity-page' },
    { name: 'WsKnowledgeIntake', path: '/workspace/knowledge-intake', sel: '.ki-page' },
  ]

test.describe('a11y 公开页扫描（硬断言 0 critical/0 serious）', { tag: ['@readonly', '@local-only'] }, () => {
  for (const p of PUBLIC) {
    test(`${p.name} 扫描完成`, async ({ page }) => {
      await page.goto(BASE_URL + p.path, { waitUntil: 'domcontentloaded' })
      await page.waitForSelector(p.sel, { timeout: 10000 })
      await scan(page, p.name)
    })
  }
})

/**
 * ★ 2026-10-21 补：**表单态**的结算页扫描（这是此前的一个扫描漏洞）
 *
 * 原来的 35 页扫描里，`/checkout` 是在**购物车为空**时扫的 ⇒ 页面显示空态、**表单根本不渲染**。
 * 而 CheckoutPage 有 7 个带 `label` 的 `AppInput` —— 它们从来没被扫到过。
 * 组件单测顺带发现：那些 `label[for="v-x"]` 指向的 id **不存在**（EP 的 el-input 吞 id）
 * ⇒ 真实表单一旦渲染，无障碍关联本应不成立。补上这条用例，把"表单态"纳入闸门。
 *
 * 顺带覆盖：加购 → 结算 → 清空购物车（保证零残留）。
 */
test.describe('a11y 表单态扫描（有商品才渲染的页）', { tag: ['@readonly', '@local-only'] }, () => {
  test('CheckoutPage（购物车非空）扫描完成', async ({ page }) => {
    test.setTimeout(90000)
    await loginAsStaff(page)

    // ① 真加购（走 UI，不直接 POST）
    await page.goto(BASE_URL + '/products/66', { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.pd-sku-row', { timeout: 20000 })
    await page.locator('.pd-sku-row').first().getByRole('button', { name: 'Add to Cart' }).click()
    await page.waitForSelector('.cart-badge', { timeout: 10000 })

    // ② 进结算页，确认表单真的渲染了（不能只等 .checkout-page 这个外壳）
    await page.goto(BASE_URL + '/checkout', { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.checkout-page', { timeout: 20000 })
    await page.waitForSelector('.checkout-page input', { timeout: 20000 })

    await scan(page, 'CheckoutPage(有商品)')

    // ★ 比 axe 更严格的断言：可访问名必须是 **label 文案**，不能被 placeholder 顶替。
    //   实测背景：这 7 个 AppInput 原本 `label[for="v-x"]` 指向**不存在**的 id（EP 的 el-input 吞 id），
    //   而 input 恰好有 placeholder ⇒ **axe 不报 critical**（axe 允许 placeholder 作可访问名）。
    //   但真实影响是：屏幕阅读器只听到 placeholder（"Dr. John Smith"），
    //   **听不到 label 里的必填标记**（"Recipient Name *"）⇒ 必填信息对读屏用户丢失。
    //   所以这里按可访问名精确定位，而不是只靠 axe 的 0 违规。
    await expect(
      page.getByRole('textbox', { name: 'Recipient Name *' }),
      '收货人输入的可访问名应为 label 文案（含必填星号），而不是 placeholder',
    ).toBeVisible({ timeout: 10000 })

    // ③ 清空购物车，保证零残留（这条用例会真加购）
    await page.goto(BASE_URL + '/cart', { waitUntil: 'domcontentloaded' })
    for (let i = 0; i < 10; i++) {
      const n = await page.locator('.cart-item').count()
      if (n === 0) break
      await page.locator('.cart-item').first()
        .getByRole('button', { name: /remove|delete|×/i }).click()
      await page.waitForTimeout(200)
    }
  })
})

test.describe('a11y staff 页扫描（硬断言 0 critical/0 serious）', { tag: ['@readonly', '@local-only'] }, () => {
  test.beforeEach(async ({ page }) => { await loginAsStaff(page) })
  for (const p of STAFF) {
    test(`${p.name} 扫描完成`, async ({ page }) => {
      await page.goto(BASE_URL + p.path, { waitUntil: 'domcontentloaded' })
      await page.waitForSelector(p.sel, { timeout: 10000 })
      await scan(page, p.name)
    })
  }
})
