/**
 * Part 1（研究员工作台·产品新建页）· **组 F「SKU」（7. SKUs）** —— F1–F6
 * 外加任务书追加：`sku_code` 留空兜底 · SKU 规格字段落库 · 编辑态增/删 SKU · 非法/重复 `sku_code` · 新建态 SKU 区行为。
 *
 * 规格来源：《2026-09-22_动作剧本×期望断言_Part1_研究员工作台产品新建页.md》§组 F（F1–F6）；
 *          缺口定性见《2026-09-22_P0_动作剧本覆盖矩阵.md》§2/§4（F 组整组 ✗，零覆盖）。
 * 判据层级（e2e/README.md §6）：L0 铁律 > L1 规格 > L2 代码现值；L3 不变量恒成立。
 * **期望值只取自 L1 规格 + 直读代码现值**（ProductEditPage.vue / commerce/models.py / serializers.py），
 * 与规格不一致处单列于文末「发现」。
 *
 * 真实 DOM（ProductEditPage.vue，非猜测）：
 *   `.sku-table tbody tr` 9 列 = Code(1) · Pack Size(2) · Pack Unit(3) · Concn(4) · Conc Unit(5) · Price(6) · Curr(7) · Default radio(8) · ✕(9)  :1852,1856-1873
 *   `+ Add SKU` = button.btn-ghost.btn-sm（:1877）；重复警告 `.sku-warning`（:1879）；缺默认 `.field-error`（:1878）
 *   发布弹窗 `.dialog-overlay .dialog` #publish-title + `.dialog-warn` li=incompleteItems（:2035-2043）
 *   `sku_code` 兜底：saveDraft `s.sku_code || \`${catNo}-${i+1}\``（:1266）
 *
 * 本机跑法（**必须**，见 e2e/README.md §1；输出重定向到文件，勿管道给 tail；与同伴共用 dev 库须加锁串行）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do echo "lock busy, wait..."; sleep 30; done
 *   echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-sku.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p3c > ../../_p3c.log 2>&1
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
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
// 触发 4xx 的用例：Chromium 把失败资源记为 console error，按语义白名单放行
const WL2 = [...WL, 'Failed to load resource']
const J = JSON.stringify
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))
const say = (label, obj) => console.log(`__E2E__ ${label} ${typeof obj === 'string' ? obj : JSON.stringify(obj)}`)

// ── D-DB：`sku` 表不在 db-snapshot.cjs 默认 7 表内 ⇒ 用只读 dbQuery 现算 ──────
const skuCount = () => dbQuery(`import json\nfrom apps.commerce.models import SKU\nprint('__SNAP__' + json.dumps(SKU.objects.count()))`)
// ⚠ 坑：`.values('price')` 返回 Decimal ⇒ json.dumps 直接 TypeError（见文末发现 #7）。故不取 price。
const skusOf = (cat) => dbQuery(
  `import json\nfrom apps.commerce.models import SKU\n` +
  `qs = SKU.objects.filter(product__catalog_no=${J(cat)}).order_by('price')` +
  `.values('id','sku_code','pack_size','concentration','lead_time','is_default','product_id')\n` +
  `print('__SNAP__' + json.dumps(list(qs)))`)
const productIdOf = (cat) => dbQuery(
  `import json\nfrom apps.commerce.models import Product\n` +
  `print('__SNAP__' + json.dumps(Product.objects.get(catalog_no=${J(cat)}).id))`)

// ── U-UI：SKU 表格元素（真实 DOM，见文件头）─────────────────────────────
const skuRows = (page) => page.locator('.sku-table tbody tr')
const addSku = (page) => page.locator('button', { hasText: '+ Add SKU' }).click()
const cellIn = (row, n) => row.locator(`td:nth-child(${n}) input`)
const codeIn = (row) => cellIn(row, 1)
const packIn = (row) => cellIn(row, 2)
const concIn = (row) => cellIn(row, 4)
const defRadio = (row) => cellIn(row, 8)
const delBtn = (row) => row.locator('td:nth-child(9) button')

const fillNew = async (page, cat) => {                       // 只填 name + catalog_no（其余留空，够 Save Draft）
  await page.locator(`input[placeholder="e.g. 2'-Amino-ATP"]`).fill('E2E SKU probe')      // :1684
  await page.locator(`input[placeholder="e.g. SC8043"]`).first().fill(cat)                // :1688
}
const save = async (page, method) => {                        // 点 Save Draft 并等对应写请求
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === method && r.url().includes('/api/v1/products/')),
    page.locator('.form-actions button', { hasText: 'Save Draft' }).click(),                // :2023
  ])
  return resp
}
/** 建 E2E- 夹具产品（可带 skus）；返回 {id, catalog_no} */
async function fixtureProduct(api, pfx, skus = []) {
  const cat = catalogNo(pfx)
  const resp = await api.post('/products/', { data: { name: `E2E ${pfx}`, catalog_no: cat, slug: slug(pfx), skus } })
  await expectApi(resp, { status: 201, label: `夹具 ${pfx}` })
  return { id: (await resp.json()).data.id, catalog_no: cat }
}

test.describe('Part 1 · 组 F SKU（7. SKUs）', () => {
  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    const r = await cleanupByPrefix(api, { label: 'F-group' })
    console.log(`__E2E__ F_CLEANUP ${JSON.stringify(r)}`)   // found / deleted / failed 必须可见
    await ctx.dispose(); await api.dispose()
  })

  // ── F0：新建态 SKU 区行为（L1 §1.2 ⑩ + §组A 顶条）──────────────
  test('F0 @readonly @local-only 新建态 SKU 区：无表格、仅 +Add SKU、顶条含 Default SKU', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await expect(page.locator('.completeness-bar')).toContainText('Default SKU')   // :1362 + incompleteItems:220
    await expect(page.locator('.sku-table'), '无 SKU ⇒ 表格不渲染（:1850 v-if）').toHaveCount(0)
    await expect(page.locator('button', { hasText: '+ Add SKU' })).toBeVisible()
    expect(errors).toEqual([])
  })

  // ── F1：+Add SKU ⇒ 行新增；保存后 sku Δ+1 且关联到该产品（L1 §F1）──
  test('F1 @write @local-only +Add SKU ⇒ 新增一行；保存后 sku 表 Δ+1 且关联该产品', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req); const cat = catalogNo('F1')
    await loginAsStaff(page); await goto(page, '/workspace/products/new'); await fillNew(page, cat)
    await expect(skuRows(page)).toHaveCount(0)
    await addSku(page)
    await expect(skuRows(page), 'L1 F1：U 新增一行').toHaveCount(1)
    await codeIn(skuRows(page).first()).fill(`${cat}-A`)
    const before = skuCount()
    await expectApi(await save(page, 'POST'), { status: 201, label: 'F1 保存' })
    expectDelta({ sku: before }, { sku: skuCount() }, { sku: +1 }, 'F1 sku Δ+1')
    expect(skusOf(cat).map((r) => [r.sku_code, r.product_id]), 'F1 关联落库')
      .toEqual([[`${cat}-A`, (await api.get(`/products/?search=${cat}`)).ok() ? skusOf(cat)[0].product_id : -1]])
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── F1b：sku_code 留空 ⇒ 兜底 `${catalog_no}-1`（L1 §C11 同源派生；:1266）──
  test('F1b @write @local-only sku_code 留空 ⇒ 兜底生成 `${catalog_no}-1`', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req); const cat = catalogNo('F1B')
    await loginAsStaff(page); await goto(page, '/workspace/products/new'); await fillNew(page, cat)
    await addSku(page)                                        // 刻意不填 sku_code
    const before = skuCount()
    await expectApi(await save(page, 'POST'), { status: 201, label: 'F1b 保存' })
    expectDelta({ sku: before }, { sku: skuCount() }, { sku: +1 }, 'F1b sku Δ+1')
    expect(skusOf(cat).map((r) => r.sku_code), 'F1b 兜底应基于 catalog_no（:1266）').toEqual([`${cat}-1`])
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── F1c：SKU 规格字段（pack_size/concentration）随保存落库 ──────────
  test('F1c @write @local-only SKU 规格字段(pack_size/concentration)随保存落库', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req); const cat = catalogNo('F1C')
    await loginAsStaff(page); await goto(page, '/workspace/products/new'); await fillNew(page, cat)
    await addSku(page)
    const row = skuRows(page).first()
    await codeIn(row).fill(`${cat}-A`); await packIn(row).fill('10'); await concIn(row).fill('100')
    const before = skuCount()
    await expectApi(await save(page, 'POST'), { status: 201, label: 'F1c 保存' })
    expectDelta({ sku: before }, { sku: skuCount() }, { sku: +1 }, 'F1c sku Δ+1')
    const r = skusOf(cat)[0]
    expect([r.pack_size, r.concentration], 'F1c 规格字段落库（joinValueUnit 拼单位 :266）').toEqual(['10 mg', '100 mM'])
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── F2：编辑态删 SKU ⇒ 该 SKU 消失、sku 表 Δ-1（L1 §F2）──────────
  test('F2 @write @local-only 编辑态删 SKU ⇒ 该 SKU 消失、sku 表 Δ-1', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req); const cat = catalogNo('F2')
    const { id } = await fixtureProduct(api, 'F2', [
      { sku_code: `${cat}-A`, price: '10.00', pack_size: '10mg' },
      { sku_code: `${cat}-B`, price: '20.00', pack_size: '20mg' },
    ])                                                        // ordering=price ⇒ nth(1)=B（models.py:263）
    await loginAsStaff(page); await goto(page, `/workspace/products/${id}/edit`)
    await expect(skuRows(page)).toHaveCount(2)
    const before = skuCount()
    await delBtn(skuRows(page).nth(1)).click()
    await expectApi(await save(page, 'PUT'), { status: 200, label: 'F2 保存' })
    expectDelta({ sku: before }, { sku: skuCount() }, { sku: -1 }, 'F2 sku Δ-1')
    expect(skusOf(cat).map((r) => r.sku_code), 'F2 仅剩 cat-A').toEqual([`${cat}-A`])
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── F2b：编辑态 +Add SKU ⇒ 保存后 sku Δ+1（任务书「编辑态增删」）──
  test('F2b @write @local-only 编辑态 +Add SKU ⇒ 保存后 sku 表 Δ+1', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req); const cat = catalogNo('F2B')
    const { id } = await fixtureProduct(api, 'F2B', [{ sku_code: `${cat}-A`, price: '10.00' }])
    await loginAsStaff(page); await goto(page, `/workspace/products/${id}/edit`)
    await expect(skuRows(page)).toHaveCount(1)
    await addSku(page); await expect(skuRows(page)).toHaveCount(2)
    await codeIn(skuRows(page).nth(1)).fill(`${cat}-B`)
    const before = skuCount()
    await expectApi(await save(page, 'PUT'), { status: 200, label: 'F2b 保存' })
    expectDelta({ sku: before }, { sku: skuCount() }, { sku: +1 }, 'F2b sku Δ+1')
    expect(skusOf(cat).map((r) => r.sku_code).sort(), 'F2b 新增只落一行').toEqual([`${cat}-A`, `${cat}-B`].sort())
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── F3：勾 is_default ⇒ 该 SKU 落 true、旧默认转 false（L1 §F3）────
  test('F3 @write @local-only 勾 is_default ⇒ 该 SKU 落 true 且旧默认转 false', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req); const cat = catalogNo('F3')
    const { id } = await fixtureProduct(api, 'F3', [
      { sku_code: `${cat}-A`, price: '10.00', is_default: true },
      { sku_code: `${cat}-B`, price: '20.00' },
    ])
    await loginAsStaff(page); await goto(page, `/workspace/products/${id}/edit`)
    await expect(skuRows(page)).toHaveCount(2)
    await defRadio(skuRows(page).nth(1)).click()              // 单选语义：:1871 清其余
    await expectApi(await save(page, 'PUT'), { status: 200, label: 'F3 保存' })
    const out = Object.fromEntries(skusOf(cat).map((r) => [r.sku_code, r.is_default]))
    expect(out, 'F3 仅 B 为默认').toEqual({ [`${cat}-A`]: false, [`${cat}-B`]: true })
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── F4：两行同 pack_size+concentration ⇒ 重复警告（纯前端，L1 §F4）──
  test('F4 @readonly @local-only 两行同 pack_size+concentration ⇒ 出现重复警告（纯前端）', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await expectNoWrites(async () => {
      await addSku(page); await addSku(page)
      await expect(skuRows(page)).toHaveCount(2)
      await expect(page.locator('.sku-warning')).toHaveCount(0)
      await packIn(skuRows(page).nth(0)).fill('10'); await packIn(skuRows(page).nth(1)).fill('10')  // :235 key=size::conc
      await expect(page.locator('.sku-warning')).toContainText('Duplicate pack size + concentration')  // :1879
    }, 'F4 纯前端态零写入')
    expect(errors).toEqual([])
  })

  // ── F5：重复 sku_code ⇒ L1 期望 400（unique 约束 models.py:247）────
  // ✅ 2026-09-22 B6 已修（`serializers.py` create 里把"建产品 + 建 SKU"放进 `transaction.atomic()`，
  //   并把 IntegrityError 按字段归属分流：命中 sku_code ⇒ 400）⇒ fixme 翻回 test。
  test('F5 @write @local-only 重复 sku_code ⇒ 400（不再是 500）', async ({ request: req }) => {
    const api = await staffApi(req); const dup = `${catalogNo('F5')}-DUP`
    await fixtureProduct(api, 'F5', [{ sku_code: dup }])      // 占位：先落一个 DUP
    const resp = await api.post('/products/', {
      data: { name: 'E2E F5 dup', catalog_no: catalogNo('F5B'), slug: slug('F5B'), skus: [{ sku_code: dup }] },
    })
    say('F5_DUP', { status: resp.status(), body: (await resp.text()).slice(0, 300) })
    await expectApi(resp, { status: 400, json: { 'meta.error.code': 'validation_error' }, label: 'F5 重复 sku_code' })
    await api.dispose()
  })

  // ── F5c：★ B6 的**原子性**闸门 —— 冲突失败后不得留下"0-SKU 产品行" ──
  //   原先 `SKU.objects.create` 在 try 之外且无事务 ⇒ 产品行已落库却无 SKU（非原子）。
  test('F5c @write @local-only 重复 sku_code 失败后 ⇒ product 计数不变（无 0-SKU 残留）', async ({ request: req }) => {
    const api = await staffApi(req); const dup = `${catalogNo('F5C')}-DUP`
    await fixtureProduct(api, 'F5C', [{ sku_code: dup }])
    const before = snapshotDb()
    const resp = await api.post('/products/', {
      data: { name: 'E2E F5C dup', catalog_no: catalogNo('F5D'), slug: slug('F5D'), skus: [{ sku_code: dup }] },
    })
    await expectApi(resp, { status: 400, label: 'F5c 冲突应 400' })
    expectDelta(before, snapshotDb(), { product: 0, sku: 0 }, 'F5c 事务回滚（不留 0-SKU 产品行）')
    await api.dispose()
  })

  // ── F5b：空 sku_code ⇒ L1 期望 400（模型 blank=False ⇒ 必填）──────
  test('F5b @write @local-only 空 sku_code ⇒ L1 期望 400（模型 blank=False）', async ({ request: req }) => {
    const api = await staffApi(req)
    const resp = await api.post('/products/', {
      data: { name: 'E2E F5b blank', catalog_no: catalogNo('F5C'), slug: slug('F5C'), skus: [{ sku_code: '' }] },
    })
    say('F5B_EMPTY', { status: resp.status(), body: (await resp.text()).slice(0, 300) })
    await expectApi(resp, { status: 400, json: { 'meta.error.code': 'validation_error' }, label: 'F5b 空 sku_code' })
    await api.dispose()
  })

  // ── F6：无 SKU 就 Publish ⇒ 弹窗列出 Default SKU 缺项（L1 §F6）────
  test('F6 @readonly @local-only 无 SKU 点 Publish ⇒ 弹窗列出 Default SKU 缺项', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await expectNoWrites(async () => {
      await fillNew(page, catalogNo('F6'))
      await page.locator('.form-actions button', { hasText: 'Publish' }).click()      // :2026 → handlePublish:1326
    }, 'F6 点 Publish 只开弹窗')
    const dlg = page.locator('.dialog-overlay .dialog')                                // :2035-2043
    await expect(dlg.locator('#publish-title')).toHaveText('Confirm Publish')
    await expect(dlg.locator('.dialog-warn')).toContainText('Default SKU')
    expect(errors).toEqual([])
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（纠错 / 纠偏 / 记录） —— 与 L1 规格或真实网站不一致处，带 文件:行号
 *
 * #1【纠偏】任务书说 SKU 有「purity / storage / shipping」规格字段 —— 与实现不符
 *    · `SKU` 模型（`backend/apps/commerce/models.py:231-263`）字段仅：
 *      `sku_code / pack_size / price / currency / inventory_status / concentration / lead_time / is_default`；
 *      **无** purity / storage / shipping。
 *    · `purity` / `storage` / `shipping` 是 **Product 级**字段（`models.py:143-149`，页面 §3 Scientific Parameters）。
 *    · ⇒ 任务书把产品级规格字段误并入 SKU。本 spec 按真实 SKU 字段断言（F1c），并在此记录。
 *
 * #2【记录】SKU 的 `lead_time`（模型 + serializer 均有）在 SKU 表格**无输入列**
 *    · `SKU.lead_time` 存在于 `models.py:256` 与 `SKUCreateSerializer.fields`（`serializers.py:36`），
 *      但 SKU 表格 9 列（`ProductEditPage.vue:1852`）没有 lead_time 输入 ⇒ 只能由 Word 导入/API 写入。
 *    · 页面里可编辑的 `lead_time` 属于 **Product 表单**（`sanitizeChoiceFields` 的 `leadTimeOpts`，`:1205`）。
 *
 * #3【记录】F5「重复 sku_code ⇒ 400」在代码现值下**大概率不可达**，需实跑判定
 *    · `SKU.sku_code` 有 DB 级 `unique=True`（`models.py:247`），但 `SKUCreateSerializer`
 *      **主动移除了 UniqueValidator**（`serializers.py:37-44`），故 `is_valid()` 不拦重复。
 *    · 真正落库在 `ProductCreateUpdateSerializer.create()`（`serializers.py:343-345`）：
 *      `SKU.objects.create(...)` **未**包 try/except IntegrityError（只有 `Product.objects.create` 被包，`:337-342`）。
 *      且 settings 无 `ATOMIC_REQUESTS`（`config/settings/base.py` 未设）⇒ 重复 sku_code 预期会以 **500** 收场，
 *      并可能**遗留一个 0-SKU 的产品行**（非原子）。
 *    · L1 §F5 判据写「unique 约束 → 400」⇒ 本 spec 按 L1 断言 400；实测值见日志 `__E2E__ F5_DUP`。
 *      **若实跑为 500 + 残留产品，即为「纠错」候选（改代码须用户拍板）。**
 *
 * #4【记录】F5b「空 sku_code」的期望取自代码现值（L1 未定义）
 *    · `SKU.sku_code = CharField(max_length=100, unique=True)`（`models.py:247`）**未设** `blank=True`
 *      ⇒ DRF 侧 `allow_blank=False, required=True` ⇒ 空串预期 400。实测见 `__E2E__ F5B_EMPTY`。
 *
 * #5【记录】新建态 SKU 区的「缺默认」标红**首次保存前不出现**
 *    · SKU 区 `.field-error`（`:1878`）由 `isFieldMissing('default_sku')` 驱动，而 `missingFields`
 *      只在 `saveDraft` 内 `collectMissing()` 后才填充（`:1256-1257`）；
 *      未保存前只有顶条 `.completeness-bar`（用实时 `incompleteItems`，`:220`）提示 `Default SKU`。
 *    · ⇒ F0 断言顶条；若期望"进页即见 SKU 区标红"需用户拍板（属告知模式的呈现选择）。
 *
 * #6【记录】SKU 行顺序契约 = `SKU.Meta.ordering = ['product','price']`（`models.py:263`）
 *    · 前端保存走 id 原地更新（`serializers.py:392-408`），id 稳定；F2/F2b/F3 用 price 制造确定性行序。
 *
 * #7【记录/测试坑】`dbQuery` 的 Python 片段里对 SKU 取 `.values('price')` 会**直接抛错**
 *    · `SKU.price = DecimalField`（`models.py:249`）⇒ `json.dumps` 报
 *      `TypeError: Object of type Decimal is not JSON serializable`（`db-snapshot.cjs:95` 抛 execFileSync 失败）。
 *    · 首跑因此 6 条误报 FAIL；本 spec 已改为不取 `price`（排序仍用 `.order_by('price')`）。
 *    · 供后续写 SKU/订单相关 D-DB 断言者避坑：Decimal 字段需 `str()` 或 `float()` 后再 dumps。
 * ──────────────────────────────────────────────────────────────────────── */
