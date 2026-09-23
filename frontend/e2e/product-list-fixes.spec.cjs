/**
 * 产品列表页 7 项修复的定向回归（Q1 / Q2 / Q3 / Q5 / Q6 · Y2 · Y5）
 *
 * 运行前提：本地 dev 已启动（Django :8000 + Vite :5173）。
 *   cd src_claude/frontend && node node_modules/@playwright/test/cli.js test \
 *     e2e/product-list-fixes.spec.cjs --project=chromium
 *
 * 对应改动（本轮）：
 *   Q1 空态分 4 场景（none-at-all / all-in-recycle / recycle-empty / filtered-out）+ 动作出口
 *   Q2 Unpublish 仅对 active|draft 显示（deprecated 行不再出现"再下架"）
 *   Q3 No Knowledge Link = aggregate_relevance_score 为空（不再靠后端中文文案匹配）
 *   Q5 读 meta.pagination.count，超 500 时显示截断告警（此前 count 被丢弃）
 *   Q6 Restore selected 改走幂等端点 POST /products/batch-restore/（替代逐条 restore/）
 *   Y5 加 watch(route.query.view) 使 URL 与视图双向对齐（**防御性**，见下方注释）
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { attachConsoleErrorCollector } = require('./helpers/console')
const { apiContext, getToken } = require('./helpers/api')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })

// 经 /auth/login 取 token（不依赖 localStorage 的键名），再建带 Token 的 API 上下文。
// 注：helpers/api.cjs 已于 2026-09-22 修正 URL 解析 bug（此前 '/products/' 会被解析到
// http://host/products/ ⇒ 404 HTML ⇒ 所有 API 断言静默失效）。
async function staffApi(request) {
  const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
  return apiContext(token)
}

test.describe('产品列表页 7 项修复', { tag: ['@write', '@local-only'] }, () => {

  // ── Q2：菜单按状态互斥 ─────────────────────────────
  test('Q2: 各 status 的菜单动作互斥（deprecated 行不得出现 Unpublish）', async ({ page, request }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: WL })
    await loginAsStaff(page)
    const ctx = await staffApi(request)
    const ts = Date.now()
    const made = []
    try {
      // 造 3 条夹具（active / archived-status / deprecated），确保三种分支都被覆盖 —— dev 库
      // 未必天然存在 status='archived' 或 'deprecated' 的行。
      for (const st of ['active', 'archived', 'deprecated']) {
        const cat = `E2E-Q2-${st}-${ts}`
        const resp = await ctx.post('/products/', {
          data: { name: `Q2 ${st} ${ts}`, catalog_no: cat, slug: `e2e-q2-${st}-${ts}`, status: st },
        })
        if (resp.status() === 201) made.push({ id: (await resp.json()).data.id, cat, st })
      }
      test.skip(made.length < 3, `夹具创建不全（${made.length}/3），跳过：可能 slug/货号冲突`)

      await goto(page, '/workspace/products')
      await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 })

      // 每条的分支断言：Unpublish 仅 active|draft；Republish 仅 archived；Discontinue 非 deprecated；Reopen 仅 deprecated
      const expectMap = {
        active: { has: ['Unpublish', 'Discontinue'], not: ['Republish', 'Reopen'] },
        archived: { has: ['Republish', 'Discontinue'], not: ['Unpublish', 'Reopen'] },
        deprecated: { has: ['Reopen'], not: ['Unpublish', 'Republish', 'Discontinue'] },
      }
      for (const f of made) {
        const row = page.locator('.products-table tbody tr').filter({ hasText: f.cat })
        await expect(row).toHaveCount(1)
        await row.locator('.menu-trigger').click()
        const menu = row.locator('.menu-popover')
        for (const name of expectMap[f.st].has) {
          await expect(menu.getByRole('button', { name, exact: true }),
            `${f.st} 行应显示 ${name}`).toBeVisible()
        }
        for (const name of expectMap[f.st].not) {
          await expect(menu.getByRole('button', { name, exact: true }),
            `${f.st} 行不应显示 ${name}`).toHaveCount(0)
        }
        await page.keyboard.press('Escape')
        await row.locator('.menu-trigger').click().catch(() => {})
        // 关闭菜单（点击空白）
        await page.locator('.filters-bar').click({ position: { x: 5, y: 5 } }).catch(() => {})
      }
      expect(errors).toEqual([])
    } finally {
      // 清理：硬删（admin 为超管）——避免在 dev 库留下夹具
      for (const f of made) {
        await ctx.post(`/products/${f.id}/hard-delete/`).catch(() => {})
      }
      await ctx.dispose()
    }
  })

  // ── Q3 / Y2：筛选口径与列同源 ───────────────────────
  test('Q3: No Knowledge Link 筛选 ⇒ 每行 Knowledge Link 单元均为 —', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: WL })
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await page.locator('.filter-select').nth(1).selectOption('no-link')
    const rows = page.locator('.products-table tbody tr')
    const n = await rows.count()
    test.skip(n === 0, '当前数据下无「无知识链接」产品，无法验证筛选口径')
    const cap = Math.min(n, 10)
    for (let i = 0; i < cap; i++) {
      // 修复点：口径 = aggregate_relevance_score 为空 ⇒ 该列必显示 .rel-none（— 占位）
      await expect(rows.nth(i).locator('.col-rel .rel-none')).toHaveCount(1)
      await expect(rows.nth(i).locator('.col-rel .rel-score')).toHaveCount(0)
    }
    expect(errors).toEqual([])
  })

  // ── Q5：截断告警 ───────────────────────────────────
  test('Q5: 未超 500 上限时不显示截断告警（正例需 >500 条，见下方注释）', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // dev 当前 < 500 ⇒ 不应出现告警。正例（count>500）需要构造 501 条数据，
    // 留给 P3 的真实写剧本（用 E2E- 前缀批量造数）覆盖。
    await expect(page.locator('.truncate-notice')).toHaveCount(0)
  })

  // ── Y5：URL ↔ 视图对齐（**防御性**）───────────────────
  test('Y5: 深链 ?view=recycle → 视图正确；toggle 与 URL 双向同步', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: WL })
    await loginAsStaff(page)
    await goto(page, '/workspace/products?view=recycle')
    const recycleBtn = page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' })
    const productsBtn = page.locator('.view-toggle__btn', { hasText: 'Products' })
    await expect(recycleBtn).toHaveClass(/is-active/, { timeout: 10000 })
    await expect(page.locator('.recycle-banner')).toBeVisible()

    // 切回 Products：URL 的 query 应被移除
    await productsBtn.click()
    await expect(productsBtn).toHaveClass(/is-active/)
    await expect(page).not.toHaveURL(/view=recycle/)

    // 再切回收站：URL 应带回 query
    await recycleBtn.click()
    await expect(recycleBtn).toHaveClass(/is-active/)
    await expect(page).toHaveURL(/view=recycle/)

    // ★ 承重断言（setView 改 push 后成立）：历史栈此时为
    //    [ …A:?view=recycle(深链) → B:/products(点 Products) → C:?view=recycle(点 Recycle) ]
    //    故 goBack() 应回到 **B（无 query ⇒ Products 视图）**，goForward() 回到 C。
    //    若 setView 仍是 replace，这里根本不会留下 B/C 两条历史 ⇒ 断言必失败。
    await page.goBack()
    await expect(page).not.toHaveURL(/view=recycle/)
    await expect(productsBtn).toHaveClass(/is-active/, { timeout: 5000 })
    await page.goForward()
    await expect(page).toHaveURL(/view=recycle/)
    await expect(recycleBtn).toHaveClass(/is-active/, { timeout: 5000 })
    expect(errors).toEqual([])
  })

  // ── Q1：空态分场景 ─────────────────────────────────
  test('Q1: 筛选到 0 行 ⇒ filtered-out 空态 + Clear filters 可复位', async ({ page, request }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: WL })
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 })

    // 动态挑一个「当前在售视图内 0 行」的 status 值，确保必定触发 filtered-out
    const ctx = await staffApi(request)
    const resp = await ctx.get('/products/', { params: { archived: 1, page_size: 500 } })
    const body = await resp.json()
    const live = (body?.data || []).filter(p => p.archived !== true)
    await ctx.dispose()
    const counts = {}
    for (const p of live) counts[p.status] = (counts[p.status] || 0) + 1
    const emptyStatus = ['deprecated', 'draft', 'archived', 'active'].find(s => !counts[s])
    test.skip(!emptyStatus, '当前数据下 4 个 status 均有产品，无法构造 filtered-out 空态')

    await page.locator('.filter-select').first().selectOption(emptyStatus)
    await expect(page.locator('.empty-state')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.empty-title')).toHaveText('No products match the current filters')
    // 修复点：空态带"清除筛选"出口
    const clearBtn = page.getByRole('button', { name: 'Clear filters' })
    await expect(clearBtn).toBeVisible()
    await clearBtn.click()
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 5000 })
    expect(errors).toEqual([])
  })

  // ── Q6：批量恢复走幂等端点（真实写 + 清理）────────────
  test('Q6: Restore selected → POST /products/batch-restore/（非逐条 restore/）+ 清理', async ({ page, request }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: WL })
    await loginAsStaff(page)
    const posts = []
    page.on('request', r => { if (r.method() === 'POST') posts.push(r.url()) })

    await goto(page, '/workspace/products?view=recycle')
    const row = page.locator('.products-table tbody tr').first()
    await expect(row).toBeVisible({ timeout: 10000 })
    const code = (await row.locator('.col-code').innerText()).trim()

    await row.locator('td.col-check input[type=checkbox]').check()
    await page.getByRole('button', { name: /Restore selected/ }).click()
    const dlg = page.locator('.dialog-overlay').filter({ has: page.locator('#restore-title') })
    await expect(dlg).toBeVisible()
    await dlg.getByRole('button', { name: /^Restore$/ }).click()

    await expect(page.locator('.el-message--success, .el-message--warning').first())
      .toBeVisible({ timeout: 15000 })

    // ★ 修复点断言：调用了批量端点，且**没有**调用单条 restore/
    expect(posts.some(u => u.includes('/products/batch-restore/')),
      `应调用 batch-restore，实际 POST: ${JSON.stringify(posts)}`).toBe(true)
    expect(posts.some(u => /\/products\/\d+\/restore\/$/.test(u)),
      '不应再逐条调用单条 restore/').toBe(false)

    // 清理：把它放回回收站（本地 dev 库，允许真实写）
    const ctx = await staffApi(request)
    const listResp = await ctx.get('/products/', { params: { archived: 1, page_size: 500 } })
    const all = (await listResp.json())?.data || []
    const target = all.find(p => p.catalog_no === code)
    if (target) await ctx.delete(`/products/${target.id}/`).catch(() => {})
    await ctx.dispose()
    expect(errors).toEqual([])
  })
})
