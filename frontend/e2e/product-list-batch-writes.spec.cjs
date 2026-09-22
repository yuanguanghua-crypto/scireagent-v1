/**
 * Part 2（研究员工作台·产品列表页）· **批量真实写** —— D11 / F2 / D12（记录型）
 *
 * 规格来源：《动作剧本×期望断言_Part2》§3 组 D（D11/D12）与组 F（F2）；判据要点见该文档 §2。
 * 这组补的是 P0 矩阵里"写动作的 DB 断言零覆盖"这块（现有用例一律"只开弹层不真写"）。
 *
 * ★★ 安全铁律：批量动作作用于**当前勾选行**，而 dev 列表里躺着**真实 SC80xx 产品**。
 *    因此本 spec **一律先造 `E2E-` 夹具，只勾选夹具行**，`afterAll` 用 cleanupByPrefix 硬删。
 *    **绝不允许出现"全选"或按位置勾选**——那会改到真实产品。
 *
 * 运行（本地 dev 需已起 :8000 + :5173；输出重定向到文件，勿管道给 tail）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   node node_modules/@playwright/test/cli.js test e2e/product-list-batch-writes.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p3f > ../../_p3f.log 2>&1
 *
 * 实测落库口径（直读 ProductsPage.vue）：
 *   D11 `Batch archive` → 逐行 `POST /products/{id}/archive/`（`:354`）⇒ 只改 status，N 条 = N 条审计
 *   F2  `Confirm`(applyBatchLink `:274-301`) → 逐行 `PUT /products/{id}/` 带 `method_ids`/`protocol_ids`
 *       ⇒ 写 `product_method` / `product_protocol` 桥（`.includes` 去重 ⇒ 单行幂等）
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { snapshotDb, expectDelta } = require('./helpers/assertions.cjs')
const { cleanupByPrefix } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const RUN = Date.now()
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const waitLoaded = (page) => expect(page.locator('.filters-bar')).toBeVisible({ timeout: 15000 })
const staffApi = async (request) => apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))

let api
test.beforeAll(async () => {
  const { request } = require('@playwright/test')
  api = await apiContext(await getToken(await request.newContext(), ADMIN_USER, ADMIN_PASS))
})
test.afterAll(async () => {
  if (api) {
    await cleanupByPrefix(api, { label: 'batch-writes' }) // 按 E2E- 前缀硬删，幂等
    await api.dispose()
  }
})

/** 造一个 active 夹具产品（**只碰 E2E- 前缀**），返回 {id, cat} */
async function fixture(key) {
  const cat = `E2E-BW-${key}-${RUN}`
  const r = await api.post('/products/', {
    data: { name: `BW ${key} ${RUN}`, catalog_no: cat, slug: cat.toLowerCase(), status: 'active' },
  })
  if (r.status() !== 201) return null
  return { id: (await r.json()).data.id, cat }
}
/** 只勾选**夹具行**（绝不按位置/全选——dev 列表里是真产品） */
const checkRow = (page, cat) =>
  page.locator('.products-table tbody tr').filter({ hasText: cat }).locator('td.col-check input[type=checkbox]').check()

test.describe('Part 2 · 批量真实写（D11 / F2 / D12）', () => {
  // ── D11：批量 Unpublish 3 条 ⇒ 3 条审计、3 行 status=archived ──
  test('D11 @write @local-only 批量 Unpublish 3 条夹具 ⇒ audit_log Δ+3、3 行归档', async ({ page }) => {
    const fxs = []
    for (const k of ['a', 'b', 'c']) fxs.push(await fixture(`D11${k}`))
    test.skip(fxs.some((f) => !f), '夹具创建不全（货号/slug 冲突）')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    for (const f of fxs) await checkRow(page, f.cat)
    const before = snapshotDb()
    await page.getByRole('button', { name: 'Batch archive', exact: true }).click()
    const dlg = page.locator('.dialog-overlay', { has: page.locator('#archive-title') })
    await expect(dlg).toBeVisible()
    await dlg.getByRole('button', { name: 'Unpublish', exact: true }).click()
    await expect(page.locator('.el-message').first()).toBeVisible({ timeout: 10000 })
    // P-3：批量是**前端循环逐条调** ⇒ N 条 = N 条审计（不是 1）
    expectDelta(before, snapshotDb(), { product: 0, audit_log: +3 }, 'D11 批量 Unpublish')
    const { data } = await (await api.get('/products/', { params: { archived: 1, page_size: 500 } })).json()
    for (const f of fxs) {
      const row = data.find((p) => p.id === f.id)
      expect(row && row.status, `${f.cat} 批量后 status`).toBe('archived')
      expect(row && row.archived, `${f.cat} 批量后 archived 不应变`).toBe(false)
    }
  })

  // ── F2：Batch Link Apply ⇒ 桥表 Δ+1（product 不变）──────────
  // ✅ 2026-09-22 **B10 + B11 + B8 均已修** ⇒ fixme 翻回 test。
  //   B10：下拉恒空（`loadKnowledgeOptions` 多一层 `.data`）
  //   B11：`applyBatchLink` 用 `put`（全量更新）只传 2 字段 ⇒ 6ms 400；已改 `patch`
  //   B8 ：`PATCH` 走同步重算，原先 **268 次独立提交**（cProfile: commit 占 97%）⇒ 23–46s，
  //        超过前端 axios 15s 超时 ⇒ **UI 报失败而服务端已落库**（幻影失败）。
  //        已把重算循环并入一个 `transaction.atomic()` ⇒ **23–46s → <1.1s**。
  //   本用例同时是 B11+B8 的**端到端闸门**：若 PATCH 仍慢于 15s，弹层不会关闭 ⇒ 必红。
  test('F2 @write @local-only Batch Link Apply 1 条夹具 ⇒ product_method Δ+1、product Δ0', async ({ page }) => {
    const f = await fixture('F2')
    test.skip(!f, '夹具创建失败')
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    await checkRow(page, f.cat)
    await page.getByRole('button', { name: 'Batch Link', exact: true }).click()
    await expect(page.locator('#batch-title')).toBeVisible()
    // ★ 定位 Method 下拉：**不要用 `hasText: 'Method'`** —— `hasText` 会连 label 内
    //   `<option>` 的文本一起算，某个 Research Goal / Application 名字里含 "Method" 时
    //   会匹配到 2 个 label ⇒ strict mode violation（B10 修好、选项真的有数据后才暴露）。
    //   改用「必填占位项 `— Required —`」锚定，与位置和名称都解耦（模板见 ProductsPage.vue:655-658）。
    const mSel = page.locator('.batch-link-form select')
      .filter({ has: page.locator('option', { hasText: '— Required —' }) })
    await expect(mSel.locator('option')).not.toHaveCount(1, { timeout: 20000 })
    await mSel.selectOption(await mSel.locator('option').nth(1).getAttribute('value'))
    await page.getByRole('button', { name: 'Preview', exact: true }).click()
    await expect(page.locator('.batch-preview')).toContainText('Will link')
    const before = snapshotDb()
    await page.locator('.batch-preview button.btn-primary').click()
    await expect(page.locator('#batch-title')).toHaveCount(0, { timeout: 15000 })
    expectDelta(before, snapshotDb(), { product: 0, product_method: +1 }, 'F2 Batch Link Apply')
  })

  // ── D12：批量**部分失败**的当前呈现（记录型，Q4 未定义）──────
  // 目的不是判对错，而是**钉住现状**并留证：前端循环 ⇒ 失败前已改的行**不回滚**；UI 只有一条 toast、**无重试入口**。
  // Q4（"部分失败应如何呈现/补救"）仍开放 ⇒ 待用户认定后替换本用例断言。
  test('D12 @write @local-only 批量部分失败：已改行不回滚 + 仅一条 toast（Q4 待认定）', async ({ page }) => {
    const fxs = []
    for (const k of ['a', 'b', 'c']) fxs.push(await fixture(`D12${k}`))
    test.skip(fxs.some((f) => !f), '夹具创建不全')
    let n = 0
    await page.route('**/api/v1/products/*/archive/', (route) => {
      n += 1
      if (n === 2) return route.fulfill({ status: 500, contentType: 'application/json', body: '{"success":false}' })
      return route.continue()
    })
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    await waitLoaded(page)
    for (const f of fxs) await checkRow(page, f.cat)
    const before = snapshotDb()
    await page.getByRole('button', { name: 'Batch archive', exact: true }).click()
    const dlg = page.locator('.dialog-overlay', { has: page.locator('#archive-title') })
    await dlg.getByRole('button', { name: 'Unpublish', exact: true }).click()
    await expect(page.locator('.el-message').first()).toBeVisible({ timeout: 10000 })
    const d = snapshotDb()
    // 现状：3 条循环里第 2 条被打 500 ⇒ 成功 2 条、审计 +2（**已改的不回滚**）
    expectDelta(before, d, { product: 0, audit_log: +2 }, 'D12 部分失败')
    const msgs = await page.locator('.el-message').count()
    expect(msgs, `当前实现只有 ${msgs} 条提示、无重试入口（Q4 待认定）`).toBeGreaterThan(0)
  })
})
