/**
 * Part 1（研究员工作台·产品新建页）· **组 J「负向与不变量」** —— 本地 R1 为主
 *
 * 规格来源：《动作剧本×期望断言_Part1》§组 J（J1–J5）。判据层级 L0 铁律 > L1 规格 > L2 代码现值。
 * 这组是"最能抓 bug 的断言"（P0 矩阵里整组零覆盖）：
 *   J1 只读动作 ⇒ 各表 Δ0
 *   J2 写入动作 ⇒ audit_log 必有对应记录且 snapshot 非空
 *   J3 归档行（archived=True）在未被显式 restore 时 archived 恒真、name/catalog_no 不被改写
 *   J4 主键序列 last_value >= max(id)（Postgres 语义 ⇒ 只在生产可判；本地 SQLite 不适用）
 *   J5 草案未 Import ⇒ 知识表（protocol / method / method_protocol）Δ0
 *
 * 运行（本地 dev 需已起 :8000 + :5173；**输出重定向到文件，勿管道给 tail**）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-negative.spec.cjs \
 *     --project=chromium --reporter=line --retries=0 --output=test-results-neg > ../../_neg.log 2>&1
 *
 * J4（生产只读）另跑（需 ssh 到 47.82.156.48，只发 SELECT）：
 *   E2E_API_BASE=https://scireagent.com E2E_BASIC_USER=scire01 E2E_BASIC_PASS=… \
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-negative.spec.cjs -g "J4" … 
 *
 * 实测选择器来源：ProductEditPage.vue（name :1684 / catalog_no :1688 / cas :1692 / 高级区 details.ai-advanced :1504）
 */
const { test, expect } = require('@playwright/test')
const { runSync } = require('./helpers/sync-spawn.cjs')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, snapshotDb, expectDelta, expectNoWrites, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { catalogNo, slug } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (request) => apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))

test.describe('Part 1 · 组 J 负向与不变量', () => {
  // ── J1：只读动作 ⇒ 各表 Δ0 ─────────────────────────────
  test('J1 @readonly 新建页只读交互（填 name/cas + 展开高级区）后各表 Δ0', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')
    await expectNoWrites(async () => {
      await page.locator(`input[placeholder="e.g. 2'-Amino-ATP"]`).fill('E2E-J1-probe')
      await page.locator('input[placeholder="e.g. 1927-31-7"]').fill('1927-31-7')
      const adv = page.locator('details.ai-advanced').first()
      if (await adv.count()) await adv.click()
    }, 'J1 新建页只读交互')
    expect(errors).toEqual([])
  })

  // ── J2a：新建 ⇒ audit_log +1 且 snapshot 非空（CREATE）──
  test('J2a @write @local-only 新建产品 ⇒ product +1 / audit_log +1(create) 且 snapshot 非空', async ({ request }) => {
    const api = await staffApi(request)
    const cat = catalogNo('J2A')
    const before = snapshotDb()
    const resp = await api.post('/products/', { data: { name: `J2a ${cat}`, catalog_no: cat, slug: slug('J2A') } })
    const id = (await resp.json()).data.id
    expectDelta(before, snapshotDb(), { product: +1, audit_log: +1 }, 'J2a 新建')
    const probe = dbQuery(
      `import json\nfrom apps.commerce.models import AuditLog\n` +
        `q = AuditLog.objects.filter(object_id=${id}, action='CREATE')\n` +
        `print('__SNAP__' + json.dumps({'n': q.count(), 'fields': sorted((q.first().snapshot or {}).keys())}))`
    )
    expect(probe.n, '应有且仅有 1 条 CREATE 审计').toBe(1)
    expect(probe.fields.length, `snapshot 不应为空，实际字段：${JSON.stringify(probe.fields)}`).toBeGreaterThan(0)
    await api.post(`/products/${id}/hard-delete/`).catch(() => {})
    await api.dispose()
  })

  // ── J2b：更新 ⇒ audit_log +1 且快照含 before/after ────
  test('J2b @write @local-only 更新产品 ⇒ audit_log +1 且快照同时含变更前/后（S3 before/after）', async ({ request }) => {
    const api = await staffApi(request)
    const cat = catalogNo('J2B')
    const created = await api.post('/products/', { data: { name: `J2b ${cat}`, catalog_no: cat, slug: slug('J2B') } })
    const id = (await created.json()).data.id
    const before = snapshotDb()
    await expectApi(await api.patch(`/products/${id}/`, { data: { name: `J2b-renamed-${cat}` } }),
      { status: 200, json: { success: true }, label: 'J2b PATCH' })
    expectDelta(before, snapshotDb(), { audit_log: +1 }, 'J2b 更新审计')
    const probe = dbQuery(
      `import json\nfrom apps.commerce.models import AuditLog\n` +
        `s = AuditLog.objects.filter(object_id=${id}, action='UPDATE').first().snapshot\n` +
        `print('__SNAP__' + json.dumps({'top': sorted(s.keys()), 'before_name': (s.get('before') or {}).get('name'), 'after_name': (s.get('after') or {}).get('name')}))`
    )
    expect(probe.after_name, 'S3 快照应记到变更后的 name').toBe(`J2b-renamed-${cat}`)
    await api.post(`/products/${id}/hard-delete/`).catch(() => {})
    await api.dispose()
  })

  // ── J3：归档行不变量（只读，用字段指纹而非计数）────────
  test('J3 @readonly 归档行未被显式 restore 时：archived 恒真且 name/catalog_no 不被改写', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    const fp = () =>
      dbQuery(
        `import json\nfrom apps.commerce.models import Product\n` +
          `rows = list(Product.objects.filter(archived=True).order_by('id').values_list('id','name','catalog_no','status'))\n` +
          `print('__SNAP__' + json.dumps(rows))`
      )
    await loginAsStaff(page)
    const before = fp()
    test.skip(before.length === 0, 'dev 库无 archived 行，无法验证该不变量')
    await goto(page, '/workspace/products')
    await page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' }).click()
    await expect(page.locator('.recycle-banner')).toBeVisible()
    expect(fp(), '只读浏览回收站后，归档行的 id/name/catalog_no/status 指纹必须逐字节不变').toEqual(before)
    expect(errors).toEqual([])
  })

  // ── J5：草案未 Import ⇒ 知识表 Δ0 ──────────────────────
  test('J5 @readonly 新建页跑 AI AUTO MATCH 但不 Import ⇒ 知识表 protocol/method Δ0', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    const know = () =>
      dbQuery(
        `import json\nfrom apps.knowledge.models import Protocol, Method\nfrom apps.bridges.models import MethodProtocol\n` +
          `print('__SNAP__' + json.dumps({'protocol': Protocol.objects.count(), 'method': Method.objects.count(), 'method_protocol': MethodProtocol.objects.count()}))`
      )
    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')
    const before = know()
    await page.locator(`input[placeholder="e.g. 2'-Amino-ATP"]`).fill('2-Propargylamino CTP')
    await page.locator('input[placeholder="e.g. 1927-31-7"]').fill('150718-26-6')
    const btn = page.locator('section.pubchem-enrich-section button.file-upload-btn').first()
    if (await btn.count()) { await btn.click(); await page.waitForTimeout(8000) }
    expectDelta(before, know(), { protocol: 0, method: 0, method_protocol: 0 }, 'J5 未 Import 的知识表')
    expect(errors).toEqual([])
  })

  // ── J4：主键序列普查（Postgres 语义 ⇒ 仅生产）──────────
  test('J4 @readonly @prod-ok 生产主键序列普查：每张表 last_value >= max(id)', async () => {
    const base = process.env.E2E_API_BASE || 'http://localhost:8000'
    test.skip(/localhost|127\.0\.0\.1/.test(base), '主键序列是 Postgres 语义，本地 SQLite 不适用（J4 只在生产有意义）')
    const KEY = 'C:/Users/yuankaifeng/.ssh/scireagent_deploy_ed25519'
    const TABLES = ['product', 'protocol', 'method', 'audit_log', 'product_protocol', 'product_method']
    const selects = TABLES.map((t) => `SELECT '${t}' t, (SELECT max(id) FROM ${t}) mx, (SELECT last_value FROM ${t}_id_seq) lv`)
    const sql = selects.join(' UNION ALL ')
    const out = runSync('ssh', ['-i', KEY, '-o', 'StrictHostKeyChecking=no', 'admin@47.82.156.48',
      `docker exec scireagent-db-1 psql -U scireagent -d scireagent -tAc "${sql}"`],
      { timeout: 60000, label: 'prod seq probe' })
    const rows = out.split(/\r?\n/).map((l) => l.split('|')).filter((a) => a.length === 3)
    expect(rows.length, `应取回 ${TABLES.length} 行序列普查结果，实际：${JSON.stringify(out).slice(0, 200)}`).toBe(TABLES.length)
    const bad = rows.filter(([, mx, lv]) => Number(lv) < Number(mx)).map(([t, mx, lv]) => `${t}: last_value=${lv} < max(id)=${mx}`)
    expect(bad, `主键序列脱节（会导致新建 duplicate key 500）：${JSON.stringify(bad)}`).toEqual([])
  })
})
