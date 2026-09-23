/**
 * P2 · Part 2 组 H —— 负向与不变量（H1–H7）
 * 规格：`2026-09-22_动作剧本×期望断言_Part2_研究员工作台产品列表页.md` §3 组 H
 * 运行：README.md §1（本机必须直调 cli.js；禁止 npm run / npx；输出重定向到文件）
 *
 *   cd src_claude/frontend
 *   node node_modules/@playwright/test/cli.js test e2e/product-list-negative.spec.cjs \
 *     --project=chromium --reporter=line --retries=0 --output=test-results-qa > ../../_qa_negative.log 2>&1
 *
 * 标签：H1 纯只读 ⇒ @readonly；H2–H7 真实写 dev 库 ⇒ @write @local-only（**不**加 @prod-ok）。
 * 判据：L0 铁律 > L1 规格（Part2 §3 组 H + 后端 views.py/models.py 的设计意图）> L2 代码现值。
 * 期望值现算：一律先跑只读探针（快照 / ORM）现取基线与目标值，不硬编码。
 * 纪律：不真跑生产；afterAll 按 `E2E-` 前缀硬删清理；不改任何应用代码。
 */
const { test, expect } = require('@playwright/test')
const { runSync } = require('./helpers/sync-spawn.cjs')
const path = require('node:path')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { snapshotDb, expectDelta, expectNoWrites } = require('./helpers/assertions.cjs')
const { cleanupByPrefix } = require('./fixtures/index.cjs')
const { BACKEND } = require('./helpers/db-snapshot.cjs')

const PY = path.join(BACKEND, 'venv', 'Scripts', 'python.exe')
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const waitLoaded = (page) => expect(page.locator('.filters-bar')).toBeVisible({ timeout: 15000 })

/** 只读 ORM/SQL 探针（子进程，只 SELECT；沿用 helpers/db-snapshot.cjs 的方式，不经 shell） */
function orm(code) {
  const out = runSync(PY, ['-B', 'manage.py', 'shell', '-c', code], {
    cwd: BACKEND,
    env: { ...process.env, DB_ENGINE: 'sqlite', PYTHONDONTWRITEBYTECODE: '1' },
    timeout: 60000, label: 'orm probe',
  })
  const line = String(out).split(/\r?\n/).find((l) => l.startsWith('__Q__'))
  if (!line) throw new Error('ORM 探针无标记行；输出前 200：' + String(out).slice(0, 200))
  return JSON.parse(line.slice('__Q__'.length))
}
const productFlags = (id) => orm(
  'import json\nfrom apps.commerce.models import Product\np=Product.objects.get(pk=' + id + ')\n' +
  "print('__Q__'+json.dumps({'status':p.status,'archived':bool(p.archived)}))")
const latestAudit = () => orm(
  'import json\nfrom apps.commerce.models import AuditLog\na=AuditLog.objects.order_by("-id").first()\n' +
  "print('__Q__'+json.dumps({'action':a.action,'snapshot':(a.snapshot or {})}))")
const seqInfo = () => orm(
  'import json\nfrom django.db import connection\nfrom apps.commerce.models import Product\n' +
  't=Product._meta.db_table\nc=connection.cursor()\nc.execute("SELECT seq FROM sqlite_sequence WHERE name=%s",[t])\n' +
  'r=c.fetchone()\nm=Product.objects.order_by("-id").values_list("id",flat=True).first() or 0\n' +
  "print('__Q__'+json.dumps({'seq':(r[0] if r else None),'max_id':m}))")

/** H2：审计必写 + snapshot 非空（一条封装两件事，失败信息自带差异定位） */
function expectLatestAudit(action, label) {
  const a = latestAudit()
  expect(a.action, `${label} 最新审计 action`).toBe(action)
  expect(Object.keys(a.snapshot || {}).length, `${label} snapshot 应非空`).toBeGreaterThan(0)
}

async function staffApi(request) {
  return apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))
}
async function fetchAll(api) {
  const r = await api.get('/products/', { params: { archived: 1, page_size: 500 } })
  return (await r.json()).data || []
}
const RUN = Date.now()
async function makeFixture(api, key, status = 'active') {
  const cat = `E2E-H-${key}-${RUN}`
  const resp = await api.post('/products/', {
    data: { name: `H ${key} ${RUN}`, catalog_no: cat, slug: `E2E-H-${key}-${RUN}`.toLowerCase(), status },
  })
  if (resp.status() !== 201) return null
  return { id: (await resp.json()).data.id, cat, status }
}

// ── 行内菜单动作封装（供 H2/H3/H4/H5 复用，让每条用例本体 ≤15 行）──
async function clickMenuItem(page, row, name) {
  await row.locator('.menu-trigger').click()
  await row.locator('.menu-popover').getByRole('button', { name, exact: true }).click()
}
async function confirmDialog(page, titleId, name) {
  const dlg = page.locator('.dialog-overlay', { has: page.locator('#' + titleId) })
  await expect(dlg).toBeVisible()
  await dlg.getByRole('button', { name, exact: true }).click()
}
async function doUnpublish(page, row) {
  await clickMenuItem(page, row, 'Unpublish')
  await confirmDialog(page, 'archive-title', 'Unpublish')
}
async function doRecycle(page, row) {
  await clickMenuItem(page, row, 'Move to Recycle Bin')
  const dlg = page.locator('.dialog-overlay', { has: page.locator('#delete-title') })
  await dlg.locator('.confirm-check input[type=checkbox]').check()
  await dlg.getByRole('button', { name: 'Move to recycle bin', exact: true }).click()
}
async function doRestore(page, row) {
  await clickMenuItem(page, row, 'Restore')
  await confirmDialog(page, 'restore-title', 'Restore')
}

test.describe('Part 2 · 组 H 负向与不变量', () => {
  let api
  test.beforeAll(async () => {
    const { request } = require('@playwright/test')
    // ⚠️ apiContext() 是 async —— 漏 await 会让 api 变成 Promise（.post/.dispose 全 undefined）
    api = await apiContext(await getToken(await request.newContext(), ADMIN_USER, ADMIN_PASS))
  })
  test.afterAll(async () => {
    if (!api) return
    await cleanupByPrefix(api, { label: 'H' })  // 按 E2E- 前缀硬删，幂等
    await api.dispose()
  })

  // ── H1 只读动作 ⇒ product / product_protocol / product_method / audit_log Δ0 ──
  test('H1a @readonly 进入列表：product·bridges·audit_log 全 Δ0', async ({ page }) => {
    await loginAsStaff(page)
    await expectNoWrites(async () => {
      await goto(page, '/workspace/products')
      await waitLoaded(page)
    }, 'H1a 进入列表')
  })

  test('H1b @readonly 切换视图（双向）：Δ0', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    await expectNoWrites(async () => {
      await page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' }).click()
      await expect(page.locator('.recycle-banner')).toBeVisible()
      await page.locator('.view-toggle__btn', { hasText: 'Products' }).click()
      await expect(page.locator('.recycle-banner')).toHaveCount(0)
    }, 'H1b 切视图')
  })

  test('H1c @readonly 排序：Δ0', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    await expectNoWrites(async () => {
      await page.locator('.products-table thead th.sortable', { hasText: 'Name' }).click()
      await page.locator('.products-table thead th.sortable', { hasText: 'Catalog No' }).click()
    }, 'H1c 排序')
  })

  test('H1d @readonly 筛选（状态 + 完整性）：Δ0', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    await expectNoWrites(async () => {
      await page.locator('.filters-bar select').first().selectOption('active')
      await page.locator('.filters-bar select').nth(1).selectOption('no-cas')
      await page.locator('.filters-bar select').first().selectOption('all')
    }, 'H1d 筛选')
  })

  test('H1e @readonly 表头全选 / 取消全选：Δ0', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    await expectNoWrites(async () => {
      const cb = page.locator('.products-table thead .col-check input[type=checkbox]')
      await cb.check()
      await cb.uncheck()
    }, 'H1e 全选')
  })

  test('H1f @readonly 打开 Batch Link 弹层：Δ0', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    await expectNoWrites(async () => {
      await page.locator('.products-table tbody td.col-check input[type=checkbox]').first().check()
      await page.getByRole('button', { name: 'Batch Link', exact: true }).click()
      await expect(page.locator('#batch-title')).toBeVisible()
      await page.getByRole('button', { name: 'Cancel', exact: true }).click()
      await expect(page.locator('#batch-title')).toHaveCount(0)
    }, 'H1f 打开弹层')
  })

  // ✅ 2026-09-22 B10 已修（`ProductsPage.vue:236-239`）⇒ 本闸门 fixme 翻回 test。
  //   此前 Batch Link 四下拉恒空 ⇒ 选不到 Method ⇒ "预览不写库"这条不变量无法被触发。
  test('H1g @readonly Batch Link 预览：Δ0（预览不写库）', async ({ page }) => {
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    await page.locator('.products-table tbody td.col-check input[type=checkbox]').first().check()
    await page.getByRole('button', { name: 'Batch Link', exact: true }).click()
    await expect(page.locator('#batch-title')).toBeVisible()
    // ★ 定位 Method 下拉：**不要用 `hasText: 'Method'`**（`hasText` 会连 `<option>` 文本一起算，
    //   别的 label 名字里含 "Method" 时会匹配到 2 个 ⇒ strict mode violation）。
    //   改用「必填占位项 `— Required —`」锚定，与位置/名称解耦（模板见 ProductsPage.vue:655-658）。
    const mSel = page.locator('.batch-link-form select')
      .filter({ has: page.locator('option', { hasText: '— Required —' }) })
    await expect(mSel.locator('option')).not.toHaveCount(1, { timeout: 20000 })
    await mSel.selectOption(await mSel.locator('option').nth(1).getAttribute('value'))
    await expectNoWrites(async () => {
      await page.getByRole('button', { name: 'Preview', exact: true }).click()
      await expect(page.locator('.batch-preview')).toContainText('Will link')
    }, 'H1g 预览')
  })

  // ── H2 每个成功写动作 ⇒ audit_log Δ+1/条 且 snapshot 非空 ──
  test('H2a @write @local-only Unpublish(archive) ⇒ audit Δ+1、snapshot 非空', async ({ page }) => {
    const fx = await makeFixture(api, 'h2a', 'active')
    test.skip(!fx, '夹具创建失败（货号/slug 冲突）')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const before = snapshotDb()
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await doUnpublish(page, row)
    await expect(row.locator('.status-archived')).toBeVisible({ timeout: 10000 })
    expectDelta(before, snapshotDb(), { product: 0, audit_log: +1 }, 'H2a Unpublish')
    expectLatestAudit('UPDATE', 'H2a')
  })

  test('H2b @write @local-only Discontinue ⇒ audit Δ+1、snapshot 非空', async ({ page }) => {
    const fx = await makeFixture(api, 'h2b', 'active')
    test.skip(!fx, '夹具创建失败')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const before = snapshotDb()
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await clickMenuItem(page, row, 'Discontinue')
    await expect(row.locator('.status-deprecated')).toBeVisible({ timeout: 10000 })
    expectDelta(before, snapshotDb(), { product: 0, audit_log: +1 }, 'H2b Discontinue')
    expectLatestAudit('UPDATE', 'H2b')
  })

  test('H2c @write @local-only Recycle(DELETE) ⇒ audit Δ+1、snapshot 非空', async ({ page }) => {
    const fx = await makeFixture(api, 'h2c', 'active')
    test.skip(!fx, '夹具创建失败')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const before = snapshotDb()
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await doRecycle(page, row)
    await expect(row).toHaveCount(0, { timeout: 10000 })
    expectDelta(before, snapshotDb(), { product: 0, audit_log: +1 }, 'H2c Recycle')
    expectLatestAudit('DELETE', 'H2c')
  })

  test('H2d @write @local-only Restore ⇒ audit Δ+1、snapshot 非空', async ({ page }) => {
    const fx = await makeFixture(api, 'h2d', 'active')
    test.skip(!fx, '夹具创建失败')
    await api.delete(`/products/${fx.id}/`)
    await loginAsStaff(page)
    await goto(page, '/workspace/products?view=recycle')
    await waitLoaded(page)
    const before = snapshotDb()
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await doRestore(page, row)
    await expect(row).toHaveCount(0, { timeout: 10000 })
    expectDelta(before, snapshotDb(), { product: 0, audit_log: +1 }, 'H2d Restore')
    expectLatestAudit('RESTORE', 'H2d')

    // ── **E4**（覆盖矩阵 P1 最后一条）：Restore 后**切回 Products 视图**，该产品应重新出现在列表中 ──
    //   判据来自剧本：恢复的语义是"回到在售视图可见"，故不能只看回收站里那行消失（H2d 原断言）。
    //   夹具是 `status='active'` 的归档行 ⇒ 恢复后 archived=false ⇒ 应出现在 Products 视图。
    await page.locator('.view-toggle__btn', { hasText: 'Products' }).click()
    await waitLoaded(page)
    await expect(
      page.locator('.products-table tbody tr').filter({ hasText: fx.cat }),
      'E4 恢复后切回 Products 视图 ⇒ 该产品应出现在列表'
    ).toHaveCount(1, { timeout: 10000 })
    await expect(page, 'E4 切回后 URL 不应再带 view=recycle').not.toHaveURL(/view=recycle/)
  })

  // ── H3 Unpublish 只改 status；Recycle 只改 archived ──
  test('H3a @write @local-only Unpublish 只改 status、不改 archived', async ({ page }) => {
    const fx = await makeFixture(api, 'h3a', 'active')
    test.skip(!fx, '夹具创建失败')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    expect(productFlags(fx.id), 'Unpublish 前置').toEqual({ status: 'active', archived: false })
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await doUnpublish(page, row)
    await expect(row.locator('.status-archived')).toBeVisible({ timeout: 10000 })
    expect(productFlags(fx.id), 'Unpublish 后').toEqual({ status: 'archived', archived: false })
  })

  test('H3b @write @local-only Recycle(DELETE) 只改 archived、不改 status', async ({ page }) => {
    const fx = await makeFixture(api, 'h3b', 'active')
    test.skip(!fx, '夹具创建失败')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await doRecycle(page, row)
    await expect(row).toHaveCount(0, { timeout: 10000 })
    expect(productFlags(fx.id), 'DELETE 后').toEqual({ status: 'active', archived: true })
  })

  // ── H4 Restore 只改 archived、不改 status ──
  test('H4 @write @local-only Restore 只改 archived、不改 status', async ({ page }) => {
    const fx = await makeFixture(api, 'h4', 'active')
    test.skip(!fx, '夹具创建失败')
    await api.delete(`/products/${fx.id}/`)
    expect(productFlags(fx.id).archived, '前置已归档').toBe(true)
    await loginAsStaff(page)
    await goto(page, '/workspace/products?view=recycle')
    await waitLoaded(page)
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await doRestore(page, row)
    await expect(row).toHaveCount(0, { timeout: 10000 })
    expect(productFlags(fx.id), 'Restore 后').toEqual({ status: 'active', archived: false })
  })

  // ── H5 批量 N 条 ⇒ N 条审计（与 P-3 前端循环逐条调一致）──
  test('H5 @write @local-only 批量 Unpublish 3 条 ⇒ audit_log Δ+3', async ({ page }) => {
    const fxs = []
    for (const k of ['a', 'b', 'c']) fxs.push(await makeFixture(api, `h5${k}`, 'active'))
    test.skip(fxs.some((f) => !f), '夹具创建不全')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    const before = snapshotDb()
    for (const f of fxs) await page.locator('.products-table tbody tr').filter({ hasText: f.cat }).locator('td.col-check input[type=checkbox]').check()
    await page.getByRole('button', { name: 'Batch archive', exact: true }).click()
    await confirmDialog(page, 'archive-title', 'Unpublish')
    await expect(page.locator('.el-message').first()).toBeVisible({ timeout: 10000 })
    expectDelta(before, snapshotDb(), { product: 0, audit_log: +3 }, 'H5 批量 Unpublish')
    for (const f of fxs) expect(productFlags(f.id).status, `${f.cat} status`).toBe('archived')
  })

  // ── H6 恢复后 recycleCount == ?archived=1 里 archived===true 的条数 ──
  test('H6 @write @local-only 恢复后 recycleCount == API 中 archived===true 条数', async ({ page }) => {
    const fx = await makeFixture(api, 'h6', 'active')
    test.skip(!fx, '夹具创建失败')
    await api.delete(`/products/${fx.id}/`)
    await loginAsStaff(page)
    await goto(page, '/workspace/products?view=recycle')
    await waitLoaded(page)
    const badge = page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' })
    const apiArchived = async () => (await fetchAll(api)).filter((p) => p.archived === true).length
    await expect(badge).toContainText(new RegExp(`\\(${await apiArchived()}\\)`))
    const row = page.locator('.products-table tbody tr').filter({ hasText: fx.cat })
    await doRestore(page, row)
    await expect(row).toHaveCount(0, { timeout: 10000 })
    await expect(badge).toContainText(new RegExp(`\\(${await apiArchived()}\\)`))
  })

  // ── H7 批量写后主键序列 last_value >= max(id) ──
  test('H7 @write @local-only 批量写后主键序列 last_value >= max(id)', async () => {
    for (const k of ['a', 'b', 'c']) await makeFixture(api, `h7${k}`, 'active')
    const { seq, max_id } = seqInfo()
    test.skip(seq === null || seq === undefined, 'sqlite_sequence 无 product 条目 ⇒ 序列不适用')
    expect(seq, `序列 ${seq} 应 >= max(id) ${max_id}`).toBeGreaterThanOrEqual(max_id)
  })
})
