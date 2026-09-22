/**
 * Part 1（研究员工作台·产品新建页）· **组 I「保存与发布」** —— I1 / I2 / I3 / I4 / I6 / I7
 *
 * 规格来源：《2026-09-22_动作剧本×期望断言_Part1_研究员工作台产品新建页.md》§组 I（I1–I7）；
 *          覆盖缺口定性见《2026-09-22_P0_动作剧本覆盖矩阵.md》§2（I1 ◐ / I2 ✗ / I3 ◐ / I4 ✅ / I5 ✗ / I6 ✗ / I7 ✗）。
 * 判据层级（e2e/README.md §6）：L0 铁律 > L1 规格 > L2 代码现值；L3 不变量恒成立。
 * **期望值只取自 L1 规格 + 直读代码现值**（ProductEditPage.vue / commerce/api/v1/views.py / commerce/models.py），
 * 与规格不一致处单列于文末「发现」。
 * **I5（唯一冲突）已由 product-new-form-validation.spec.cjs 覆盖 ⇒ 本文件不重复。**
 *
 * 真实 DOM（ProductEditPage.vue，非猜测）：
 *   Save Draft / Publish = `.form-actions button`（:2023 / :2026），saving 期间 `:disabled="saving"`
 *   发布确认框 = `.dialog-overlay .dialog` #publish-title + `.dialog-warn li`=incompleteItems（:2035-2043）
 *   错误 toast = `.toast.toast-error`（:1385 + :2104）；非白屏证据 = `form.edit-form`（:1678）
 *   身份行状态 = `.page-identity-status`（:1392）
 * 审计（L2 现值）：perform_create → CREATE + build_snapshot（SNAPSHOT_FIELDS 11 字段，models.py:365-368,views.py:154-156）；
 *   perform_update → UPDATE + snapshot={before,after}（views.py:158-165）。
 *
 * 本机跑法（**必须**，见 e2e/README.md §1；输出重定向到文件，勿管道给 tail；与同伴共用 dev 库须加锁串行）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do echo "lock busy, wait..."; sleep 30; done
 *   echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-save-publish.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p3d > ../../_p3d.log 2>&1
 *   rm -f ../../_pw.lock
 *
 * 前置：本地 dev 已起（Django :8000 DB_ENGINE=sqlite / Vite :5173，且 Vite 从 **E: 物理路径** 启动）。
 * 纪律：只新增本文件；不改应用代码、不 git commit；写操作只碰 `E2E-` 前缀夹具，afterAll 硬删。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, snapshotDb, expectDelta, expectNoWrites, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { catalogNo, slug, RUN_TS, cleanupByPrefix } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
// 触发 4xx/5xx 的用例：Chromium 把失败资源记为 console error，按语义白名单放行
const WL2 = [...WL, 'Failed to load resource']
const J = JSON.stringify
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

// ★ 选择器全部来自真实 DOM（ProductEditPage.vue），非猜测。
const SEL = {
  name: `input[placeholder="e.g. 2'-Amino-ATP"]`,   // :1684
  catalog: `input[placeholder="e.g. SC8043"]`,      // :1688
  save: '.form-actions button',                     // :2023（Save Draft）/ :2026（Publish）
}
const saveBtn = (page) => page.locator(SEL.save, { hasText: /Save Draft|Saving/ })
const publishBtn = (page) => page.locator(SEL.save, { hasText: 'Publish' })
const dialog = (page) => page.locator('.dialog-overlay .dialog')

const fillNew = async (page, cat) => {
  await page.locator(SEL.name).fill('E2E 保存发布 probe')
  await page.locator(SEL.catalog).first().fill(cat)
}
/** 点 Save Draft 并等对应写请求的**真实响应**（raw body = envelope，故 `.data.id` 可直接取） */
const save = async (page, method) => {
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === method && r.url().includes('/api/v1/products/')),
    saveBtn(page).click(),
  ])
  return resp
}
/** D-DB 只读取一条审计：action + snapshot（audit_log 有 object_id/action，models.py:323-327） */
const auditOf = (objectId, action) => dbQuery(
  `import json\nfrom apps.commerce.models import AuditLog\n` +
  `l = AuditLog.objects.filter(object_id=${objectId}, action=${J(action)}).order_by('-id').first()\n` +
  `print('__SNAP__' + json.dumps({'action': l.action if l else None, 'snapshot': l.snapshot if l else None}))`)
/** D-DB 只读产品某字段现值（禁止硬编码期望） */
const productField = (id, field) => dbQuery(
  `import json\nfrom apps.commerce.models import Product\n` +
  `print('__SNAP__' + json.dumps(getattr(Product.objects.get(id=${id}), ${J(field)})))`)
const firstClassId = () => dbQuery(
  `import json\nfrom apps.commerce.models import ProductClass\n` +
  `print('__SNAP__' + json.dumps(ProductClass.objects.order_by('id').values_list('id', flat=True).first()))`)

/** 建 E2E- 夹具产品（可带额外字段）；返回 {id, catalog_no} */
async function fixtureProduct(api, pfx, extra = {}) {
  const cat = catalogNo(pfx)
  const resp = await api.post('/products/', { data: { name: `E2E ${pfx}`, catalog_no: cat, slug: slug(pfx), ...extra } })
  await expectApi(resp, { status: 201, label: `夹具 ${pfx}` })
  return { id: (await resp.json()).data.id, catalog_no: cat }
}

test.describe('Part 1 · 组 I 保存与发布', () => {
  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    const r = await cleanupByPrefix(api, { label: 'I-group' })
    console.log(`__E2E__ I_CLEANUP ${J(r)}`)   // found / deleted / failed 必须可见
    await ctx.dispose(); await api.dispose()
  })

  // ── I1：Save Draft（新建）⇒ product Δ+1 + audit_log Δ+1 CREATE + snapshot 11 字段 ──
  test('I1 @write @local-only Save Draft(新建) ⇒ product Δ+1；audit_log Δ+1 CREATE、snapshot 非空(11)', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await fillNew(page, catalogNo('I1'))
    const before = snapshotDb()
    const resp = await save(page, 'POST')
    await expectApi(resp, { status: 201, label: 'I1 新建' })
    expectDelta(before, snapshotDb(), { product: +1, audit_log: +1 }, 'I1 新建产品')
    const log = auditOf((await resp.json()).data.id, 'CREATE')
    expect(log.action, 'I1 审计 action 应为 CREATE').toBe('CREATE')
    expect(Object.keys(log.snapshot || {}), 'I1 snapshot = SNAPSHOT_FIELDS 11 白名单字段').toHaveLength(11)
    expect(errors).toEqual([])
  })

  // ── I2：Save Draft（编辑）⇒ audit_log Δ+1 UPDATE，snapshot 同时含 before/after（S3）──
  test('I2 @write @local-only Save Draft(编辑) ⇒ audit_log Δ+1 UPDATE、snapshot 含 before/after', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'I2')                       // 初始 name='E2E I2'
    await loginAsStaff(page); await goto(page, `/workspace/products/${f.id}/edit`)
    const before = snapshotDb()
    const edited = `E2E I2 edited ${RUN_TS}`
    await page.locator(SEL.name).fill(edited)
    await expectApi(await save(page, 'PUT'), { status: 200, label: 'I2 编辑保存' })
    expectDelta(before, snapshotDb(), { audit_log: +1, product: 0 }, 'I2 编辑保存')
    const log = auditOf(f.id, 'UPDATE')
    expect(log.action, 'I2 审计 action 应为 UPDATE').toBe('UPDATE')
    expect([log.snapshot?.before?.name, log.snapshot?.after?.name], 'I2 before/after 各取变更前后值')
      .toEqual([`E2E I2`, edited])
    expect(Object.keys(log.snapshot?.before || {}), 'I2 before 亦为 11 字段').toHaveLength(11)
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── I3：Publish（不完整）⇒ 弹层列全部缺项、可取消、Δ0、status 不变（告知式不硬阻断）──
  test('I3 @readonly @local-only Publish(不完整) ⇒ 弹层列缺项、取消后 Δ0、status 不变', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await fillNew(page, catalogNo('I3'))                            // 只填 name+catalog_no ⇒ 缺 4 项
    await expectNoWrites(async () => { await publishBtn(page).click() }, 'I3 点 Publish 只开弹层')
    const dlg = dialog(page)
    await expect(dlg.locator('#publish-title')).toHaveText('Confirm Publish')
    await expect(dlg.locator('.dialog-warn li'), 'I3 应列出全部缺项 CAS/SMILES/Category/Default SKU').toHaveCount(4)
    await expect(dlg.locator('.dialog-warn')).toContainText('Default SKU')
    await expectNoWrites(async () => { await dlg.locator('button', { hasText: 'Cancel' }).click() }, 'I3 取消零写入')
    await expect(dlg).toHaveCount(0)
    await expect(page.locator('.page-identity-status')).toHaveText('draft')
    expect(errors).toEqual([])
  })

  // ── I4：Publish（完整）⇒ DB product.status 变 active（**加强版：断 DB 而非只断 UI**）──
  test('I4 @write @local-only Publish(完整) ⇒ DB product.status=active（加强版断 DB）', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'I4', {                 // 满足 5 条完成度（name/cat/cas/smiles/class/default sku）
      cas: '50-78-2', smiles: 'CC(=O)OC1=CC=CC=C1C(=O)O', product_class_id: firstClassId(),
      skus: [{ sku_code: `${catalogNo('I4')}-A`, is_default: true, price: '10.00' }],
    })
    await loginAsStaff(page); await goto(page, `/workspace/products/${f.id}/edit`)
    await expect(page.locator('.completeness-bar'), 'I4 夹具应满足 5 条完成度').toContainText('✓ Complete')
    await publishBtn(page).click()
    const dlg = dialog(page)
    await expect(dlg.locator('.dialog-warn'), 'I4 完整 ⇒ 无缺项警示').toHaveCount(0)
    const [resp] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes('/api/v1/products/')),
      dlg.locator('button', { hasText: 'Confirm Publish' }).click(),
    ])
    // ★ 断言 PUT 本身成功 —— 原实现接受**任意**状态码 ⇒ 若 PUT 失败，
    //   失败会**伪装**成"DB status 没变"，无法区分"接口挂了"与"读库过早"。
    //   （2026-09-22 合并跑时 I4 曾失败而单独跑通过，此断言用于自证根因。）
    console.log('__E2E__ I4_PUT ' + JSON.stringify({ status: resp.status(), url: resp.url() }))
    expect(resp.status(), 'I4 Publish 的 PUT 应 2xx（否则 DB 不会变 active）').toBeLessThan(300)
    expect(productField(f.id, 'status'), 'I4 DB status 应变 active（L1 §I4）').toBe('active')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── I6：连点 Save ⇒ saving 期间按钮 disabled（去抖）+ 只落 1 行（product Δ+1 而非 Δ+n）──
  test('I6 @write @local-only 连点 Save ⇒ saving 期间 disabled（去抖）、product Δ+1（非 Δ+n）', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    // 延后 POST 响应 1.2s，让「保存中」窗口可观测（route.continue ⇒ 仍是**真实写入**）
    await page.route('**/api/v1/products/', async (route) => {
      if (route.request().method() === 'POST') await new Promise((r) => setTimeout(r, 1200))
      await route.continue()
    })
    await fillNew(page, catalogNo('I6'))
    const before = snapshotDb()
    const respP = page.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/api/v1/products/'))
    await saveBtn(page).click()
    await expect(saveBtn(page), 'I6 保存进行中按钮应 disabled（:2023 saving 去抖）').toBeDisabled()
    await expectApi(await respP, { status: 201, label: 'I6 首次保存' })
    expectDelta(before, snapshotDb(), { product: +1, audit_log: +1 }, 'I6 连点只落 1 行')
    await page.unroute('**/api/v1/products/')
    expect(errors).toEqual([])
  })

  // ── I7：保存失败（page.route 造 500）⇒ 可读错误态、非白屏、Δ0（formatSaveError :1228）──
  test('I7 @write @local-only 保存失败(500) ⇒ 可读错误 toast、非白屏、product/audit_log Δ0', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await page.route('**/api/v1/products/', (route) => route.fulfill({
      status: 500, contentType: 'application/json',
      body: J({ success: false, data: null, meta: { error: { code: 'server_error', message: 'E2E injected 500' } } }),
    }))
    await fillNew(page, catalogNo('I7'))
    const before = snapshotDb()
    await saveBtn(page).click()
    const toast = page.locator('.toast.toast-error')
    await expect(toast, 'I7 应显示可读错误（formatSaveError :1228-1244）').toContainText('HTTP 500')
    await expect(toast).toContainText('E2E injected 500')
    await expect(page.locator('form.edit-form'), 'I7 不得白屏、不得跳转').toBeVisible()
    expectDelta(before, snapshotDb(), { product: 0, audit_log: 0 }, 'I7 失败不得落库')
    await page.unroute('**/api/v1/products/')
    expect(errors).toEqual([])
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（纠错 / 纠偏 / 记录） —— 与 L1 规格或真实网站不一致处，带 文件:行号
 *
 * #1【记录】I3 的「弹层列出全部缺项」为**前端 incompleteItems**（4 项），非后端 _incomplete_items
 *    · `ProductEditPage.vue:2038-2042` 用 `incompleteItems`（:214-222），文案 `Name/Catalog No`·`CAS`·
 *      `SMILES`·`Category`·`Default SKU`；
 *    · 后端 `_incomplete_items` 用另一套文案（`serializers.py:80-94`）**不出现在本页**（L1 §1.6 已注）。
 *    · ⇒ 断言按前端文案（4 项：name/cat 已填）。
 *
 * #2【记录】I6 的「去抖」实现是 **`saving` ref ⇒ 按钮 disabled**，不是请求层幂等
 *    · `saveDraft()`（`ProductEditPage.vue:1246-1317`）**开头没有 `if (saving.value) return` 守卫**，
 *      唯一屏障是模板 `:disabled="saving"`（:2023）。
 *    · ⇒ 同一 event-loop tick 内两次同步 `.click()`（人不可能做到）会绕过禁用并发两次 POST。
 *      真实双击（间隔 ≫ 一次 microtask）安全。本 spec 以「保存中 disabled + 只落 1 行」为判据，
 *      未把「同步双发」当缺陷断言（属不可达的人为场景）；如需请求层硬幂等须用户拍板。
 *
 * #3【记录】I4 的激活副作用未在本 spec 断言
 *    · `update()` 在 draft→active 时触发 `CommerceService.activate_product`（`serializers.py:429-441`），
 *      会重算派生 `product_method_relation`；该管线的落库语义属 L1 §I4/§6.5 的「可能 Δ+」，非确定值
 *      ⇒ 本 spec 只断 `status=active`（确定项），不作 Δ 断言。
 *
 * #4【记录】审计快照字段数 = **11**（取自代码，非硬编码）
 *    · `AuditLog.SNAPSHOT_FIELDS`（`commerce/models.py:365-368`）恰 11 项；
 *      `build_snapshot` 逐项 `hasattr` 收集（:382-392）⇒ Product 全命中 ⇒ 长度恒 11。
 *
 * #5【记录/性能隐患】`Save Draft` 若携带 `method_ids`，保存会**同步**重算派生协议 ⇒ 时延与
 *    所链方法的派生协议数成正比（实测 method54/752 条 ≈27.7s；method35/268 条 ≈13.1s）。
 *    · 链路 `serializers.py:444-470 _refresh_inherited_bridges` → `bridges/services/relevance.py:437-487
 *      recompute_product`；详见姊妹 spec「发现」#6（`product-new-knowledge-links.spec.cjs`）。
 *    · 本 spec 的 I1/I2/I4/I6/I7 夹具**均不带 method_ids**（不触发该重算），故不受影响；
 *      但生产"Save Draft"用户体验会随编辑页所链方法数退化 ⇒ 记此，供用户判定是否需异步化/加进度反馈。
 * ──────────────────────────────────────────────────────────────────────── */
