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
            return `      · ${tgt}${msg ? '  ← ' + msg.slice(0, 90) : ''}`
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
