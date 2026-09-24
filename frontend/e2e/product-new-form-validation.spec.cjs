/**
 * Part 1（研究员工作台·产品新建页）· **组 C「表单字段」与唯一性冲突** + I5 + A5
 *
 * 规格来源：《2026-09-22_动作剧本×期望断言_Part1》§组C（C1–C11）、§组I 的 I5、§组A 的 A5。
 * 判据层级（e2e/README.md §6）：L0 铁律 > L1 规格 > L2 代码现值；L3 不变量恒成立。
 * **本 spec 的期望值全部取自 L1 规格 + 直读代码现值，未凭感觉编写**；与规格不一致处单列于文末「发现」。
 *
 * 本机跑法（**必须**，见 e2e/README.md §1；输出重定向到文件，勿管道给 tail）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do echo "lock busy, wait..."; sleep 30; done   # 与同伴共用 dev 库，串行
 *   echo $$ > ../../_pw.lock
 *   E2E_BASIC_USER= node node_modules/@playwright/test/cli.js test e2e/product-new-form-validation.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p3a > ../../_p3a.log 2>&1
 *   rm -f ../../_pw.lock
 *
 * 前置：本地 dev 已起（Django :8000 DB_ENGINE=sqlite / Vite :5173，且 Vite 从 **E: 物理路径** 启动）。
 * 纪律：只写 `E2E-` 前缀夹具，`afterAll` 用 cleanupByPrefix() 硬删；**不改应用代码、不 git commit**。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, snapshotDb, expectDelta, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')

const API_HOST = process.env.E2E_API_BASE || 'http://localhost:8000'
const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
// 触发 4xx 的用例：Chromium 会把 4xx 资源记为 console error，按语义白名单放行
const WL2 = [...WL, 'Failed to load resource']

const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

/** 建一个 E2E- 夹具产品（在售），返回 {id, catalog_no, slug} */
async function newFixture(api, pfx, extra = {}) {
  const cat = catalogNo(pfx)
  const resp = await api.post('/products/', { data: { name: `E2E ${pfx}`, catalog_no: cat, slug: slug(pfx), ...extra } })
  return { id: (await resp.json()).data.id, catalog_no: cat, slug: slug(pfx) }
}

// 非法枚举值：均为**真实自由文本**；合法集见 backend/apps/commerce/models.py:55-91,141
const ENUM_CASES = [
  ['C5', 'purity', '>99%'],
  ['C6', 'concentration', '12345 nM'],
  ['C7', 'storage', 'frozen somewhere odd'],
  ['C7', 'shipping', 'Teleport'],
  ['C10', 'molecular_weight', 'abc'],
]

const SELECTORS = {
  name: `input[placeholder="e.g. 2'-Amino-ATP"]`,   // ProductEditPage.vue:1684
  catalog: `input[placeholder="e.g. SC8043"]`,      // :1688
  save: '.form-actions button',                     // :2022-2025
  toastErr: '.toast.toast-error',                   // :1385 + :2104
}

test.describe('Part 1 · 组 C 表单字段与唯一性冲突（+ I5 / A5）', () => {
  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    await cleanupByPrefix(api, { label: 'C-group' })
    await ctx.dispose()
    await api.dispose()
  })

  // ── C1a：name 必填 → 前端标红（L1 :1685 / 顶条 :1362）──────────
  test('C1a @write @local-only 新建页留空点 Save Draft ⇒ Name 标红 + 顶条缺项', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')
    await expect(page.locator('.completeness-bar')).toContainText('Name/Catalog No')
    const nameErr = page.locator('label', { has: page.locator(SELECTORS.name) }).locator('.field-error')
    await expect(nameErr, '未点保存前不应标红').toHaveCount(0)
    await page.locator(SELECTORS.save, { hasText: 'Save Draft' }).click()
    await expect(nameErr, '点保存后应标红').toContainText('Required field unfilled')
    await expect(page).toHaveURL(/\/workspace\/products\/new/)
    expect(errors).toEqual([])
  })

  // ── C1b：name 必填 → 后端 400 且不落库（L1「不得产生产品行」）──
  test('C1b @write @local-only API 缺 name ⇒ 400 validation_error 且 product Δ0', async ({ request: req }) => {
    const api = await staffApi(req)
    const before = snapshotDb()
    const resp = await api.post('/products/', { data: { catalog_no: catalogNo('C1B'), slug: slug('C1B') } })
    await expectApi(resp, { status: 400, json: { 'meta.error.code': 'validation_error' }, label: 'C1b' })
    expect((await resp.json()).meta.error.message, 'C1b 文案应指向 name').toContain('name')
    expectDelta(before, snapshotDb(), { product: 0 }, 'C1b 缺 name 不得落库')
    await api.dispose()
  })

  // ── C4：SMILES 前端标红（L1 :1712）──────────────────────────
  test('C4 @write @local-only 新建页留空点 Save Draft ⇒ SMILES 标红（L1 :1712）', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')
    await expect(page.locator('.completeness-bar')).toContainText('SMILES')
    await page.locator(SELECTORS.save, { hasText: 'Save Draft' }).click()
    await expect(page.locator('#smiles-missing')).toContainText('Required field unfilled')
    expect(errors).toEqual([])
  })

  // ── C4b：[记录] 后端实际不强制 smiles（与任务书"C4⇒400"不符，见文末发现#2）──
  test('C4b @write @local-only [记录] API 不传 smiles ⇒ 201（后端不强制）', async ({ request: req }) => {
    const api = await staffApi(req)
    const resp = await api.post('/products/', {
      data: { name: 'E2E C4b', catalog_no: catalogNo('C4B'), slug: slug('C4B') },
    })
    await expectApi(resp, { status: 201, label: 'C4b 建库成功=后端不强制 smiles' })
    await api.post(`/products/${(await resp.json()).data.id}/hard-delete/`).catch(() => {})
    await api.dispose()
  })

  // ── C5/C6/C7/C10：非法枚举 / 非数值 ⇒ 400 ────────────────────
  for (const [lbl, field, bad] of ENUM_CASES) {
    test(`${lbl} @write @local-only ${field} 非法值 ⇒ 400 validation_error`, async ({ request: req }) => {
      const api = await staffApi(req)
      const cat = catalogNo(`${lbl}-${field.slice(0, 3)}`)
      const resp = await api.post('/products/', {
        data: { name: 'E2E enum probe', catalog_no: cat, slug: cat.toLowerCase(), [field]: bad },
      })
      await expectApi(resp, { status: 400, json: { 'meta.error.code': 'validation_error' }, label: `${lbl} ${field}` })
      expect((await resp.json()).meta.error.message, `${lbl} 文案应指向 ${field}`).toContain(field)
      await api.dispose()
    })
  }

  // ── C2：catalog_no 命中【在售】行 ⇒ 400（真重复，不含三条出路）──
  test('C2 @write @local-only catalog_no 命中在售行 ⇒ 400 且文案不含回收站出路', async ({ request: req }) => {
    const api = await staffApi(req)
    const f = await newFixture(api, 'C2')
    const before = snapshotDb()
    const resp = await api.post('/products/', { data: { name: 'E2E C2 dup', catalog_no: f.catalog_no, slug: slug('C2DUP') } })
    await expectApi(resp, { status: 400, json: { 'meta.error.code': 'validation_error' }, label: 'C2' })
    const msg = (await resp.json()).meta.error.message
    // ★ 2026-09-24：`54c4dc5`（R7「用户可见文案去技术细节」）已把文案改为
    //   `货号「…」已被另一个产品占用（内部编号 #<id>）——请换一个货号。`
    //   （原为 `product id=<id>`）。断言随之更新，并**反向钉住"不得再泄露技术细节"**。
    expect(msg, 'C2 应指向占用者（内部编号）').toContain(`内部编号 #${f.id}`)
    expect(msg, 'C2 是"真重复"，不得出现回收站出路').not.toMatch(/回收站|还原/)
    expect(msg, 'C2 不得泄露技术细节（R7：端点路径/端点名/内部字段名）').not.toMatch(/restore\/|hard-delete|product id=/)
    expectDelta(before, snapshotDb(), { product: 0 }, 'C2 真重复不得新增行')
    await api.dispose()
  })

  // ── C2b：catalog_no 命中【回收站】行 ⇒ 409 conflict + 三条出路 + 归档行零改动 ──
  test('C2b @write @local-only catalog_no 命中回收站 ⇒ 409 conflict + 三条出路', async ({ request: req }) => {
    const api = await staffApi(req)
    const f = await newFixture(api, 'C2B')
    await api.delete(`/products/${f.id}/`)   // 软删 → 回收站（占位，不释放编号）
    const fp = () => dbQuery(`import json\nfrom apps.commerce.models import Product\np = Product.objects.get(id=${f.id})\nprint('__SNAP__' + json.dumps({'name': p.name, 'catalog_no': p.catalog_no, 'slug': p.slug, 'archived': p.archived}))`)
    const before = snapshotDb(); const rowBefore = fp()
    const resp = await api.post('/products/', { data: { name: 'E2E C2b dup', catalog_no: f.catalog_no, slug: slug('C2BDUP') } })
    await expectApi(resp, { status: 409, json: { 'meta.error.code': 'conflict' }, label: 'C2b' })
    const msg = (await resp.json()).meta.error.message
    // ★ 2026-09-24：R7（`54c4dc5`）后三条出路改为**研究员语言**，不再是端点名：
    //   ① 想继续用这个编号 → 先到「回收站」把它还原；② 这是另一个产品 → 请换一个货号；
    //   ③ 需要彻底删除旧记录 → 请联系管理员。（原断言在要 `restore/`、`请改用新的`、`hard-delete`）
    expect(msg, 'C2b 应指向归档行（内部编号）').toContain(`内部编号 #${f.id}`)
    expect(msg, 'C2b ① 出路：去回收站还原').toMatch(/回收站/)
    expect(msg, 'C2b ① 出路：还原动作').toMatch(/还原/)
    expect(msg, 'C2b ② 出路：换一个货号').toMatch(/请换一个货号/)
    expect(msg, 'C2b ③ 出路：联系管理员').toMatch(/请联系管理员/)
    expect(msg, 'C2b 不得泄露技术细节（R7）').not.toMatch(/restore\/|hard-delete|product id=/)
    expectDelta(before, snapshotDb(), { product: 0 }, 'C2b 冲突不得新增行')
    expect(fp(), 'C2b 归档行必须零改动').toEqual(rowBefore)
    await api.dispose()
  })

  // ── C2c：slug 命中【回收站】行 ⇒ 409 conflict（同体例）──────
  test('C2c @write @local-only slug 命中回收站 ⇒ 409 conflict + 三条出路', async ({ request: req }) => {
    const api = await staffApi(req)
    const f = await newFixture(api, 'C2C')
    await api.delete(`/products/${f.id}/`)
    const resp = await api.post('/products/', { data: { name: 'E2E C2c dup', catalog_no: catalogNo('C2CNEW'), slug: f.slug } })
    await expectApi(resp, { status: 409, json: { 'meta.error.code': 'conflict' }, label: 'C2c' })
    const msg = (await resp.json()).meta.error.message
    // ★ 2026-09-24：同 C2b，R7 后的三条出路为研究员语言（此字段 label 为 `slug`）。
    expect(msg, 'C2c ① 出路：去回收站还原').toMatch(/回收站/)
    expect(msg, 'C2c ① 出路：还原动作').toMatch(/还原/)
    expect(msg, 'C2c ② 出路：换一个 slug').toMatch(/请换一个slug/)
    expect(msg, 'C2c ③ 出路：联系管理员').toMatch(/请联系管理员/)
    expect(msg, 'C2c 不得泄露技术细节（R7）').not.toMatch(/restore\/|hard-delete|product id=/)
    await api.dispose()
  })

  // ── I5：唯一冲突的前端呈现：可读 toast、非白屏、不静默、Δ0 ──
  test('I5 @write @local-only 前端唯一冲突呈现：可读 toast、非白屏、product Δ0', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await newFixture(api, 'I5')
    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')
    const before = snapshotDb()
    await page.locator(SELECTORS.name).fill('E2E I5 conflict')
    await page.locator(SELECTORS.catalog).first().fill(f.catalog_no)
    await page.locator(SELECTORS.save, { hasText: 'Save Draft' }).click()
    const toast = page.locator(SELECTORS.toastErr)
    await expect(toast).toBeVisible({ timeout: 8000 })
    await expect(toast).toContainText(/HTTP 400/)
    await expect(page.locator('form.edit-form')).toBeVisible()
    expectDelta(before, snapshotDb(), { product: 0 }, 'I5 冲突不得落库')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── A5：深链不存在的 id ⇒ 错误态、非白屏（L1 组A 缺口）──────
  test('A5 @readonly 深链不存在 id 的编辑页 ⇒ 错误态非白屏', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page)
    await goto(page, '/workspace/products/999999/edit')
    await expect(page.locator('div.error')).toContainText('Failed to load product')
    await expect(page.locator('.completeness-bar')).toBeVisible()
    expect(errors).toEqual([])
  })

  // ── C8：`research_use_only` 默认 **true**；**不变更时保存不得被写 false** ──────
  //   规格依据：`models.py:157` `research_use_only = BooleanField(default=True, …)`（已 Read 核实）。
  //   覆盖矩阵点名此条**未覆盖**：「无脚本断言默认 true、且保存不得被写 false」。
  //   注：断言走 API+DB 层 —— 直接验的是**模型默认与保存语义**（这正是剧本的判据），
  //       不受前端表单是否勾选影响；UI 勾选框的表现另由表单类用例覆盖。
  test('C8 @write @local-only research_use_only 默认 true；只改 name 的保存不得把它写 false', async ({ request: req }) => {
    const api = await staffApi(req)
    const code = catalogNo('C8')
    // ① 建产品时**完全不传**该字段 ⇒ 应落模型默认 true
    const created = await api.post('/products/', {
      data: { name: `E2E C8 ${code}`, catalog_no: code, slug: slug('C8') },
    })
    await expectApi(created, { status: 201, label: 'C8 建产品（不传 research_use_only）' })
    const id = (await created.json()).data.id
    const readFlag = () =>
      dbQuery(
        `import json\nfrom apps.commerce.models import Product\n` +
          `print('__SNAP__' + json.dumps(Product.objects.get(id=${id}).research_use_only))`
      )
    expect(await readFlag(), 'C8 未传该字段 ⇒ 必须取模型默认 true').toBe(true)

    // ② 只改 name 保存（请求体**不含** research_use_only）⇒ 该字段必须保持 true，不得被写 false
    const patched = await api.patch(`/products/${id}/`, { data: { name: `E2E C8 renamed ${code}` } })
    await expectApi(patched, { status: 200, label: 'C8 只改 name 保存' })
    expect(await readFlag(), 'C8 不变更该字段的保存**不得**把它写成 false').toBe(true)

    await api.dispose()
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（纠错 / 纠偏 / 记录） —— 与 L1 规格或任务书不一致处，带 文件:行号
 *
 * #1【记录】409 的错误码是 `conflict`，而非 `product_number_conflict`
 *    · `backend/apps/commerce/api/v1/serializers.py:158` 定义
 *      `ProductNumberConflict.default_code = 'product_number_conflict'`；
 *    · 但全局异常处理器 `backend/core/exceptions.py:26-36` 的 `_get_error_code()`
 *      在 409 时**硬写** `'conflict'`，覆盖了 APIException 的 default_code；
 *    · 实测（真实请求）C2b/C2c：`meta.error.code == 'conflict'`。
 *    · L1 规格 Part1 §C2b 的判据行本来就写 `code=conflict` ⇒ 断言取 `conflict`。
 *      ⇒ `product_number_conflict` 是**不可达码**；若前端/文档/监控依赖它，需用户拍板（纠错候选）。
 *
 * #2【纠偏/记录】C4「smiles 必填 ⇒ 400」不成立
 *    · `backend/apps/commerce/models.py:133` `smiles = TextField(blank=True, default='')`
 *      ⇒ 后端不强制；实测：不传 smiles 的 POST ⇒ **201（产品被创建）**；
 *    · L1 规格 §C4 只要求**前端标红**（`ProductEditPage.vue:1712` `#smiles-missing`），
 *      **未**要求后端 400——与"告知模式"（草稿可不完整，见 `:1246-1259`）一致；
 *    · ⇒ 任务书 C4 的"400"与 L1/L2 均不符。本 spec 按 L1 断言前端标红（C4），
 *      并附 `C4b [记录]` 断言后端实际 201 留证。
 *
 * #3【记录】C5/C6 的 400 仅 API 可达，UI 不会触发
 *    · 后端：`purity`/`concentration` 为 choices（`models.py:143,145`），非法值 ⇒ 400（实测）；
 *    · 前端：`ProductEditPage.vue:1199-1211` `sanitizeChoiceFields()` 在 POST 前把非法 choices
 *      值**置空** ⇒ UI 永不发非法枚举，研究员看不到 400；`purity` 的 free 输入框（`:1737`）亦然。
 *
 * #4【记录】C7「归一化规则」vs 400 —— 两层各自成立，不冲突
 *    · 后端：`storage`/`shipping` 亦为 choices（`models.py:147,149`），非法值 ⇒ 400（实测）；
 *    · 前端：`normalizeStorage`/`normalizeShipping`（`:1170/:1187`）把 docx/enrich 原文
 *      归一化为枚举；UI 的 storage/shipping 是 `AppSelect`（`:1742-1747`，无自由输入）
 *      ⇒ UI 不会发非法值。⇒ L1 C7 与 L2 是**不同层**的表述，均正确。
 *
 * #5【记录】C2「真重复」文案不含回收站出路（符合 L1）
 *    · 实测：`catalog_no: 货号「X」已被现有产品占用（product id=N）。`（400 validation_error）。
 *
 * #6【记录】409 的 `meta.error.details` 为空
 *    · 409 由 `serializers.py:316` 抛 APIException，`core/exceptions.py:15` 的 details
 *      过滤 `detail` 后为空 ⇒ 可操作文案只在 `meta.error.message`；
 *    · 前端 `formatSaveError`（`ProductEditPage.vue:1236-1237`）恰好读 `meta.error.message`
 *      ⇒ 三系出路可在 toast 显示（I5 依赖此路径）。
 *
 * #7【记录】A5 错误态文案取 L2 现值
 *    · `ProductEditPage.vue:948` `loadError = 'Failed to load product'`，`:1350` 渲染为
 *      `div.error`；L1 §组A 列 A5 为"缺口/文案待认定"，此处按 L2 断言。
 * ──────────────────────────────────────────────────────────────────────── */
