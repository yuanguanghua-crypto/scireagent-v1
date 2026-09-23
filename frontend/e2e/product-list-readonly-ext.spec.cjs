/**
 * P2 · Part 2 其余 ✗/◐ 缺口（只读扩展集）—— **全部 @readonly**
 * 覆盖：A8 · B1/B2（6 列真实排序） · B3（nulls_last） · B4 · B5 · B6 · B7 · B9 ·
 *       C1 · C5 · D8 · D10 · F4 · G1 · G4 · G5
 * 规格：`2026-09-22_动作剧本×期望断言_Part2_研究员工作台产品列表页.md` §3 组 A/B/C/D/F/G
 *
 *   cd src_claude/frontend
 *   node node_modules/@playwright/test/cli.js test e2e/product-list-readonly-ext.spec.cjs \
 *     --project=chromium --reporter=line --retries=0 --output=test-results-qa > ../../_qa_ext.log 2>&1
 *
 * 判据：期望值**现算** —— 一律先调 A-API（`?archived=1&page_size=500`）算三层集合
 *       （allProducts / products / filteredProducts），再与 U-UI 比对；前置不满足则 test.skip。
 * 不变量：只读用例不发任何 POST/PUT/PATCH/DELETE（登录 POST /auth/login 除外，与示范用例同口径）。
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectNoWrites } = require('./helpers/assertions.cjs')

const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const waitLoaded = (page) => expect(page.locator('.filters-bar')).toBeVisible({ timeout: 15000 })

async function staffApi(request) {
  return apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))
}
async function fetchAll(api) {
  const r = await api.get('/products/', { params: { archived: 1, page_size: 500 } })
  return (await r.json()).data || []
}
async function domCodes(page) {
  return (await page.locator('.products-table tbody td.col-code').allInnerTexts()).map((s) => s.trim())
}

/** 复刻 ProductsPage.vue:90-114 的 sortedProducts 比较器（含 rel 数值列 nulls_last） */
function sortAsApp(list, field, dir) {
  const arr = [...list]
  if (field === 'aggregate_relevance_score') {
    const toNum = (v) => (v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v))) ? null : Number(v)
    arr.sort((a, b) => {
      const an = toNum(a[field]), bn = toNum(b[field])
      if (an === null && bn === null) return 0
      if (an === null) return 1
      if (bn === null) return -1
      const cmp = an - bn
      return dir === 'asc' ? cmp : -cmp
    })
  } else {
    arr.sort((a, b) => {
      const cmp = String(a[field] ?? '').localeCompare(String(b[field] ?? ''), undefined, { numeric: true, sensitivity: 'base' })
      return dir === 'asc' ? cmp : -cmp
    })
  }
  return arr
}

/** B1/B2：点表头两次（升降各一次），每次读图标定方向，再断言 DOM 行序 == 期望序 */
async function assertSort(page, live, name, field) {
  const th = page.locator('.products-table thead th.sortable', { hasText: name }).first()
  for (const _ of [0, 1]) {
    await th.click()
    const dir = (await th.innerText()).includes('▼') ? 'desc' : 'asc'
    expect(await domCodes(page), `${name} ${dir} 行序`).toEqual(sortAsApp(live, field, dir).map((p) => p.catalog_no))
  }
}
async function openArchiveDialog(page, row) {
  await row.locator('.menu-trigger').click()
  await row.locator('.menu-popover').getByRole('button', { name: 'Unpublish', exact: true }).click()
  await expect(page.locator('#archive-title')).toBeVisible()
}
const SORT_FIELDS = [
  ['Catalog No', 'catalog_no'], ['Name', 'name'], ['CAS', 'cas'],
  ['Status', 'status'], ['Category', 'category_l1'], ['Knowledge Link', 'aggregate_relevance_score'],
]
const AND_CASES = [
  ['active', 'no-cas', (p) => p.status === 'active' && !p.cas],
  ['draft', 'complete', (p) => p.status === 'draft' && p.is_complete],
  ['all', 'no-smiles', (p) => !p.smiles],
]

test.describe('Part 2 · 其余缺口（只读扩展集）', () => {
  // ── A8 ──
  test('A8 @readonly recycle 视图无 + New Product；Products 视图有', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products?view=recycle')
    await expect(page.locator('.recycle-banner')).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('link', { name: '+ New Product', exact: true })).toHaveCount(0)
    await page.locator('.view-toggle__btn', { hasText: 'Products' }).click()
    await expect(page.getByRole('link', { name: '+ New Product', exact: true })).toHaveCount(1)
    // ── **A7↑**（覆盖矩阵 P2 升级）：点 `+ New Product` ⇒ 应**真的跳转**到新建页 ──
    //   原断言只查"链接存在"，与剧本「点击 ⇒ 跳 /workspace/products/new」差一半。
    await page.getByRole('link', { name: '+ New Product', exact: true }).click()
    await expect(page, 'A7↑ 点 + New Product 应跳转到新建页').toHaveURL(/\/workspace\/products\/new$/)
  })

  // ── B1/B2：6 个可排序列，每列升降各验一次真实行序 ──
  for (const [name, field] of SORT_FIELDS) {
    test(`B2 @readonly 排序「${name}」：DOM 行序 == 按 ${field} 期望序`, async ({ page, request }) => {
      await loginAsStaff(page)
      const api = await staffApi(request)
      const live = (await fetchAll(api)).filter((p) => p.archived !== true)
      await api.dispose()
      await goto(page, '/workspace/products')
      await waitLoaded(page)
      test.skip(live.length < 2, '在售行不足 2，无法验证排序')
      await assertSort(page, live, name, field)
    })
  }

  // ── B3 ──
  test('B3 @readonly Knowledge Link 排序：null 恒沉底（升/降都验）', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const live = (await fetchAll(api)).filter((p) => p.archived !== true)
    await api.dispose()
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    test.skip(live.length < 2, '在售行不足 2')
    const th = page.locator('.products-table thead th.sortable', { hasText: 'Knowledge Link' }).first()
    for (const _ of [0, 1]) {
      await th.click()
      const dir = (await th.innerText()).includes('▼') ? 'desc' : 'asc'
      expect(await domCodes(page), `Knowledge Link ${dir}`).toEqual(sortAsApp(live, 'aggregate_relevance_score', dir).map((p) => p.catalog_no))
      const rels = (await page.locator('.products-table tbody td.col-rel').allInnerTexts()).map((t) => t.trim())
      const firstNull = rels.findIndex((t) => t === '—')
      if (firstNull !== -1) expect(rels.slice(firstNull).every((t) => t === '—'), 'null 之后不应再有数值行').toBe(true)
    }
  })

  // ── B4 ──
  test('B4 @readonly statusFilter 5 值逐个收窄行集合 + 计数文案同步', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const live = (await fetchAll(api)).filter((p) => p.archived !== true)
    await api.dispose()
    await goto(page, '/workspace/products')
    for (const v of ['all', 'active', 'draft', 'deprecated', 'archived']) {
      await page.locator('.filters-bar select').first().selectOption(v)
      const n = v === 'all' ? live.length : live.filter((p) => p.status === v).length
      await expect(page.locator('.filter-count')).toHaveText(`${n} products`)
      await expect(page.locator('.products-table tbody tr')).toHaveCount(n)
    }
  })

  // ── B5 ──
  test('B5 @readonly completenessFilter 7 值逐个收窄行集合', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const live = (await fetchAll(api)).filter((p) => p.archived !== true)
    await api.dispose()
    const pred = {
      all: () => true, complete: (p) => p.is_complete, incomplete: (p) => !p.is_complete,
      'no-cas': (p) => !p.cas, 'no-smiles': (p) => !p.smiles,
      'no-link': (p) => p.aggregate_relevance_score == null, 'no-category': (p) => !p.product_class_id,
    }
    await goto(page, '/workspace/products')
    for (const v of Object.keys(pred)) {
      await page.locator('.filters-bar select').nth(1).selectOption(v)
      const n = live.filter(pred[v]).length
      await expect(page.locator('.filter-count')).toHaveText(`${n} products`)
      await expect(page.locator('.products-table tbody tr')).toHaveCount(n)
    }
  })

  // ── B6 ──
  test('B6 @readonly status + completeness 叠加为 AND', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const live = (await fetchAll(api)).filter((p) => p.archived !== true)
    await api.dispose()
    await goto(page, '/workspace/products')
    for (const [st, cp, fn] of AND_CASES) {
      await page.locator('.filters-bar select').first().selectOption(st)
      await page.locator('.filters-bar select').nth(1).selectOption(cp)
      const n = live.filter(fn).length
      await expect(page.locator('.filter-count')).toHaveText(`${n} products`)
      await expect(page.locator('.products-table tbody tr')).toHaveCount(n)
    }
  })

  // ── B7 ──
  test('B7 @readonly 排序在筛选结果内生效', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const live = (await fetchAll(api)).filter((p) => p.archived !== true)
    await api.dispose()
    const subset = live.filter((p) => p.status === 'active')
    test.skip(subset.length < 2, 'active 在售行不足 2')
    await goto(page, '/workspace/products')
    await page.locator('.filters-bar select').first().selectOption('active')
    await waitLoaded(page)
    const th = page.locator('.products-table thead th.sortable', { hasText: 'Catalog No' }).first()
    await th.click()
    const dir = (await th.innerText()).includes('▼') ? 'desc' : 'asc'
    expect(await domCodes(page), 'B7 筛选内排序').toEqual(sortAsApp(subset, 'catalog_no', dir).map((p) => p.catalog_no))
  })

  // ── B9 ──
  test('B9 @readonly 计数文案 == filtered 条数（非总数、非视图总数）', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const all = await fetchAll(api)
    await api.dispose()
    const live = all.filter((p) => p.archived !== true)
    const active = live.filter((p) => p.status === 'active').length
    test.skip(active === 0 || active === all.length || active === live.length, '无合适的 status 值可区分三层口径')
    await goto(page, '/workspace/products')
    await page.locator('.filters-bar select').first().selectOption('active')
    await expect(page.locator('.filter-count')).toHaveText(`${active} products`)
    await expect(page.locator('.filter-count')).not.toHaveText(`${all.length} products`)
  })

  // ── C1 ──
  test('C1 @readonly 表头全选 == 当前 filtered 行', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const boxes = page.locator('.products-table tbody td.col-check input[type=checkbox]')
    const n = await boxes.count()
    test.skip(n === 0, '无可见行，无法验证全选')
    await page.locator('.products-table thead .col-check input[type=checkbox]').check()
    for (let i = 0; i < n; i++) await expect(boxes.nth(i), `第 ${i} 行应被全选`).toBeChecked()
  })

  // ── C5 ──
  test('C5 @readonly 筛选后全选只选可见行', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const live = (await fetchAll(api)).filter((p) => p.archived !== true)
    await api.dispose()
    const active = live.filter((p) => p.status === 'active').length
    test.skip(active === 0 || active === live.length, '需存在可区分的可见子集')
    await goto(page, '/workspace/products')
    await page.locator('.filters-bar select').first().selectOption('active')
    await page.locator('.products-table thead .col-check input[type=checkbox]').check()
    await expect(page.locator('.products-table tbody td.col-check input[type=checkbox]')).toHaveCount(active)
    await page.locator('.filters-bar select').first().selectOption('all')
    expect(await page.locator('.products-table tbody td.col-check input:checked').count(), '清筛选后仍只勾选原 active 子集').toBe(active)
  })

  // ── D8 ──
  test('D8 @readonly recycle 视图行内菜单只有 Restore', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products?view=recycle')
    await waitLoaded(page)
    const rows = page.locator('.products-table tbody tr')
    test.skip((await rows.count()) === 0, '回收站为空，无法验证行内菜单')
    await rows.first().locator('.menu-trigger').click()
    const menu = rows.first().locator('.menu-popover')
    await expect(menu.locator('.menu-item')).toHaveCount(1)
    await expect(menu.locator('.menu-item')).toHaveText('Restore')
  })

  // ── D10 ──
  test('D10 @readonly 菜单开启后 Esc / 点页面空白 ⇒ 关闭', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const rows = page.locator('.products-table tbody tr')
    test.skip((await rows.count()) === 0, '无可见行')
    await rows.first().locator('.menu-trigger').click()
    await expect(rows.first().locator('.menu-popover')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(rows.first().locator('.menu-popover')).toHaveCount(0)
    await rows.first().locator('.menu-trigger').click()
    await page.evaluate(() => document.body.click())
    await expect(rows.first().locator('.menu-popover')).toHaveCount(0)
  })

  // ── F4 ──
  test('F4 @readonly 弹层 Esc / 点遮罩 ⇒ 关闭', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const row = page.locator('.products-table tbody tr').filter({ has: page.locator('.status-active') }).first()
    test.skip((await row.count()) === 0, '无 active 行（Unpublish 入口不可达）')
    const dlg = page.locator('.dialog-overlay', { has: page.locator('#archive-title') })
    await openArchiveDialog(page, row)
    await page.keyboard.press('Escape')
    await expect(dlg).toHaveCount(0)
    await openArchiveDialog(page, row)
    await dlg.click({ position: { x: 5, y: 5 } })
    await expect(dlg).toHaveCount(0)
  })

  // ── G1 ──
  test('G1 @readonly 列表接口 500 ⇒ 渲染 .error 文案（非白屏）', async ({ page }) => {
    await loginAsStaff(page)
    await page.route('**/api/v1/products/**', (route) => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ success: false, meta: { error: { message: 'boom' } } }),
    }))
    await goto(page, '/workspace/products')
    await expect(page.locator('.error')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('.error')).toContainText('Failed to load products')
  })

  // ── G4 ──
  test('G4 @readonly 单条动作失败（PATCH 500）⇒ toast 提示失败（不真写）', async ({ page }) => {
    await loginAsStaff(page)
    await page.route('**/api/v1/products/*/', (route) => route.request().method() === 'PATCH'
      ? route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ meta: { error: { message: 'boom' } } }) })
      : route.continue())
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const row = page.locator('.products-table tbody tr').filter({ has: page.locator('.status-active') }).first()
    test.skip((await row.count()) === 0, '无 active 行，无法触发 Discontinue')
    await row.locator('.menu-trigger').click()
    await row.locator('.menu-popover').getByRole('button', { name: 'Discontinue', exact: true }).click()
    await expect(page.locator('.el-message--error').filter({ hasText: 'Discontinue failed' })).toBeVisible({ timeout: 10000 })
  })

  // ── G5 ──
  test('G5 @readonly status=archived 行：Unpublish 菜单不可达（记录）', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const target = (await fetchAll(api)).find((p) => p.archived !== true && p.status === 'archived')
    await api.dispose()
    test.skip(!target, 'dev 库无 status=archived 且未归档的行，无法验证可达性')
    await goto(page, '/workspace/products')
    await page.locator('.filters-bar select').first().selectOption('archived')
    await waitLoaded(page)
    const row = page.locator('.products-table tbody tr').filter({ hasText: target.catalog_no })
    await expect(row).toHaveCount(1)
    await row.locator('.menu-trigger').click()
    await expect(row.locator('.menu-popover').getByRole('button', { name: 'Unpublish', exact: true })).toHaveCount(0)
  })

  // ── 以下 4 条：覆盖矩阵 §3.2（P2 抽样批）──────────────────────────
  // 代码事实（已 Read 核实，勿凭剧本行号）：`ProductsPage.vue:556` 批量条 `v-if="selectedCount > 0"`，
  // 且 `v-if="viewMode === 'active'"` 才渲染 Batch Link / Batch archive / Batch delete 三颗，
  // 否则渲染 `Restore selected`（`:562` 的 v-else）；行勾选 = `tbody td.col-check input[type=checkbox]`。

  // ── C3：勾选 1 行 ⇒ 三个批量按钮**同时出现** ─────────────────────────
  test('C3 @readonly 勾选 1 行 ⇒ Batch Link / Batch archive / Batch delete 三按钮同时出现', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const boxes = page.locator('.products-table tbody td.col-check input[type=checkbox]')
    test.skip((await boxes.count()) === 0, '无可见行，无法勾选')
    const names = ['Batch Link', 'Batch archive', 'Batch delete']
    for (const n of names) {
      await expect(page.getByRole('button', { name: n, exact: true }), `未勾选时不应出现 ${n}`).toHaveCount(0)
    }
    await boxes.first().check()
    for (const n of names) {
      await expect(page.getByRole('button', { name: n, exact: true }),
        `勾选 1 行后应出现 ${n}`).toBeVisible({ timeout: 10000 })
    }
  })

  // ── C2：取消全选 ⇒ 全部取消 + 批量按钮消失 ──────────────────────────
  test('C2 @readonly 取消全选 ⇒ 各行取消勾选 + 批量按钮消失', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const boxes = page.locator('.products-table tbody td.col-check input[type=checkbox]')
    const n = await boxes.count()
    test.skip(n === 0, '无可见行，无法验证全选')
    const head = page.locator('.products-table thead .col-check input[type=checkbox]')
    await head.check()
    await expect(page.locator('.products-table tbody td.col-check input:checked'),
      '全选后应勾满当前 filtered 行').toHaveCount(n)
    await head.uncheck()
    expect(await page.locator('.products-table tbody td.col-check input:checked').count(),
      '取消全选后应一格不剩').toBe(0)
    await expect(page.getByRole('button', { name: 'Batch archive', exact: true }),
      '无选中 ⇒ 批量按钮应消失').toHaveCount(0)
  })

  // ── C4：切换视图 ⇒ 选中被清空 + 批量按钮消失 ────────────────────────
  // ⚠️ 这条防的是一个**具体故障**：若切视图不清选中，recycle 视图会显示 `Restore selected`
  //    ⇒ 用户可能在**新视图**里对**旧选中**误操作。仅断"active 批量按钮消失"是不够的
  //    （那可能只是视图分支不同），所以**同时**断 recycle 侧不出现 `Restore selected`。
  test('C4 @readonly 勾选后切视图 ⇒ 选中清空（recycle 不得出现 Restore selected）', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const boxes = page.locator('.products-table tbody td.col-check input[type=checkbox]')
    test.skip((await boxes.count()) === 0, '无可见行，无法勾选')
    await boxes.first().check()
    await expect(page.getByRole('button', { name: 'Batch archive', exact: true })).toBeVisible({ timeout: 10000 })

    await page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' }).click()
    await expect(page).toHaveURL(/view=recycle/)
    await expect(page.getByRole('button', { name: 'Batch archive', exact: true }),
      'active 视图的批量按钮应消失').toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Restore selected', exact: true }),
      '切视图后不得残留选中（否则会冒出 Restore selected）').toHaveCount(0)
  })

  // ── D1：行内 `Edit` ⇒ 跳编辑页 + 零写入 ─────────────────────────────
  test('D1 @readonly 行内菜单 Edit ⇒ 跳 /workspace/products/{id}/edit 且零写入', async ({ page, request }) => {
    await loginAsStaff(page)
    const api = await staffApi(request)
    const target = (await fetchAll(api)).find((p) => p.archived !== true)
    await api.dispose()
    test.skip(!target, 'dev 库无可见产品，无法验证 Edit 跳转')
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const row = page.locator('.products-table tbody tr').filter({ hasText: target.catalog_no })
    await expect(row).toHaveCount(1)
    await expectNoWrites(async () => {
      await row.locator('.menu-trigger').click()
      await row.locator('.menu-popover').getByRole('button', { name: 'Edit', exact: true }).click()
      await expect(page, 'D1 Edit 应跳到该产品的编辑页').toHaveURL(
        new RegExp(`/workspace/products/${target.id}/edit$`)
      )
    }, 'D1 Edit 跳转')
  })
})
