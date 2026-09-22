/**
 * Part 1（研究员工作台·产品新建页）· **组 H「合规 SDS / COA」（9. Compliance — COA & SDS）** —— H1–H10
 *
 * 规格来源（L1）：
 *   · 《2026-09-22_动作剧本×期望断言_Part1_研究员工作台产品新建页.md》§组 H（H1–H10）
 *   · 《src_claude/docs/COA_SDS_PRD.md》§3（P0-3/P0-4/P1-1/P1-2）、§4.3–4.4（端点/状态机）、§5（待确认）
 * 覆盖缺口（P0 矩阵 §2）：`product-edit-optimize ①–⑥` 仅覆盖 **UI 存在性**；**H2/H3/H4/H7/H8 的 DB 断言全缺**。
 * 判据层级（e2e/README.md §6）：L0 铁律 > L1 规格 > L2 代码现值；L3 不变量恒成立。
 * **期望值只取自 L1 规格 + 直读代码现值**（ProductEditPage.vue / apps/documents/**），与规格不一致处单列于文末「发现」。
 *
 * 真实 DOM（ProductEditPage.vue，非猜测）：
 *   合规节 = `section.form-section` h3「9. Compliance — COA & SDS」（:1896-2019）
 *   新建态占位 = `.compliance-placeholder`（:1900 v-if="!isEdit"）；实体块 = `.compliance-block` ×2（SDS :1907 / Batch COA :1949）
 *   SDS：`Generate SDS` 按钮（:1910）· 缺标识引导 `.sds-hint`（:1918）· 版本列表 `.sds-rev-list > .sds-rev-card`（:1923）
 *        已发布标 `.tag-sds`「Currently published」（:1927）· 动作 `Approve & Publish SDS`（:1939）/ `Withdraw`（:1940）
 *   COA：批次列表 `.sku-coa-group > .coa-card`（:1954）· 缺批次时 `.batch-create-form`（:2001，Lot number=AppInput、生产日期=input[type=date]、`Generate COA` :2011）
 *        COA 动作 `.coa-card-actions`：`Enter measurements`（:1986）/ `Approve & Publish COA`（:1987）/ `Withdraw`（:1988）
 *        QC 录入 `.qc-form`（:1969）· `Save measurements`（:1980）
 *   预览弹层 = `.preview-overlay > .preview-dialog`（CompliancePreviewModal.vue:44-45，经 openPreview 命令式挂载）
 *   反馈 toast = `.toast.toast-{type}`（:1385）；类型 warn/success/error（:352 setFeedback）
 *
 * 端点/口径（L2 现值，已对照 views/serializers/workflow）：
 *   POST /sds-revisions/generate/ {product_id} → 201（SdsRevision draft；**无 status 字段**）
 *   POST /sds-revisions/{id}/approve/ → 200（生成 PDF；`Product.current_sds` 指向该版；响应带 `compliance` 软闸门）
 *   POST /sds-revisions/{id}/withdraw/ → 200（清空 `Product.current_sds`；**旧 PDF 保留**）
 *   POST /coas/create-coa/ {sku_id,lot_number,produced_at,retest_at?} → 201（Batch + Coa draft）
 *   PUT  /coas/{id}/qc-results/ → 200（写 QC 实测字段）；POST /coas/{id}/approve/ → 200（status=published + PDF）
 *   POST /coas/{id}/withdraw/ → 200（status=draft；**旧 PDF 保留**）
 *   GET  /products/?archived=1&page_size=500（**ProductListSerializer** 含 `sds_published:bool`、`coa_published_count:int`，
 *        serializers.py:99-100/136-145）——retrieve 用 ProductDetailSerializer**不含**此二字段，故列表口径只能走 list 端点。
 *
 * 本机跑法（**必须**，见 e2e/README.md §1；输出重定向到文件，勿管道给 tail；与同伴共用 dev 库须加锁串行）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do echo "lock busy, wait..."; sleep 30; done
 *   echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test e2e/product-compliance-lifecycle.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p3e > ../../_p3e.log 2>&1
 *   rm -f ../../_pw.lock
 *
 * 前置：本地 dev 已起（Django :8000 DB_ENGINE=sqlite / Vite :5173，且 Vite 从 **E: 物理路径** 启动）。
 * 纪律：只新增本文件；不改应用代码、不 git commit；写操作只碰 `E2E-` 前缀夹具，afterAll 硬删。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext, API_BASE } = require('./helpers/api')
const { expectApi, expectDelta, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
// 触发 4xx/5xx 或 iframe 资源的用例：Chromium 把失败资源记为 console error，按语义白名单放行
const WL2 = [...WL, 'Failed to load resource']
const J = JSON.stringify
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

// ── 写请求的响应等待器（真实端点，非猜测）────────────────────────────
const byUrl = (m, re) => (r) => r.request().method() === m && re.test(r.url())
const hit = (m, frag) => (r) => r.request().method() === m && r.url().includes(frag)
const R = {
  sdsGen: hit('POST', '/sds-revisions/generate/'),
  sdsApprove: byUrl('POST', /\/sds-revisions\/\d+\/approve\//),
  sdsWithdraw: byUrl('POST', /\/sds-revisions\/\d+\/withdraw\//),
  coaCreate: hit('POST', '/coas/create-coa/'),
  coaApprove: byUrl('POST', /\/coas\/\d+\/approve\//),
  coaWithdraw: byUrl('POST', /\/coas\/\d+\/withdraw\//),
  coaQc: byUrl('PUT', /\/coas\/\d+\/qc-results\//),
}
/** 点某元素并等它触发的写请求的**真实响应** */
const apiAct = async (page, pred, fn, timeout = 60000) => {
  const [resp] = await Promise.all([page.waitForResponse(pred, { timeout }), fn()])
  return resp
}
/** 登录 → 进入编辑页 → 等合规区加载完成（`.compliance-block` = SDS + Batch COA 共 2 块） */
const openEdit = async (page, id) => {
  await loginAsStaff(page)
  await goto(page, `/workspace/products/${id}/edit`)
  await expect(page.locator('.compliance-block'), '合规区应加载完成（SDS + Batch COA）').toHaveCount(2, { timeout: 30000 })
}
// ── U-UI 选择器（真实 DOM，见文件头）────────────────────────────────
const sdsBtn = (page) => page.getByRole('button', { name: 'Generate SDS' })
const sdsListEl = (page) => page.locator('.sds-rev-list')
const coaCardEl = (page) => page.locator('.coa-card').first()
/** 走 UI 生成 SDS，返回新版本 id（并断言 201） */
const genSds = async (page) => {
  const resp = await apiAct(page, R.sdsGen, () => sdsBtn(page).click())
  await expectApi(resp, { status: 201, label: 'UI 生成 SDS' })
  return (await resp.json()).data.id
}

// ── D-DB：documents 三表 + 字段现值（只读 dbQuery；禁止硬编码期望）──────
const docSnap = () => dbQuery(
  `import json\nfrom apps.documents.models import SdsRevision, Batch, Coa\n` +
  `print('__SNAP__' + json.dumps({'sds_revision': SdsRevision.objects.count(),` +
  ` 'batch': Batch.objects.count(), 'coa': Coa.objects.count()}))`)
const fieldOf = (model, mod, id, f) => dbQuery(
  `import json\nfrom ${mod} import ${model}\n` +
  `print('__SNAP__' + json.dumps(getattr(${model}.objects.get(id=${id}), ${J(f)})))`)
const productField = (id, f) => fieldOf('Product', 'apps.commerce.models', id, f)   // 含 current_sds_id
const sdsField = (id, f) => fieldOf('SdsRevision', 'apps.documents.models', id, f)
const coaField = (id, f) => fieldOf('Coa', 'apps.documents.models', id, f)
const skuIdOf = (cat) => dbQuery(
  `import json\nfrom apps.commerce.models import SKU\n` +
  `print('__SNAP__' + json.dumps(SKU.objects.get(product__catalog_no=${J(cat)}).id))`)
/** 列表口径：ProductListSerializer 的 sds_published / coa_published_count（现算，不硬编码） */
const listItem = async (api, cat) => {
  const r = await api.get('/products/', { params: { archived: 1, page_size: 500, ordering: '-created_at' } })
  await expectApi(r, { status: 200, label: `列表口径 ${cat}` })
  return (await r.json()).data.find((p) => p.catalog_no === cat)
}

// ── 夹具（只碰 E2E- 前缀；不挂 ProductReagentClass 桥 ⇒ hard-delete 可正常删）──
async function mkProduct(api, pfx, extra = {}) {
  const cat = catalogNo(pfx)
  const resp = await api.post('/products/', { data: { name: `E2E ${pfx}`, catalog_no: cat, slug: slug(pfx), ...extra } })
  await expectApi(resp, { status: 201, label: `夹具 ${pfx}` })
  return { id: (await resp.json()).data.id, cat }
}
/** 带 1 个默认 SKU 的产品（COA 需 SKU） */
async function mkProductSku(api, pfx, extra = {}) {
  const cat = catalogNo(pfx)
  const sku_code = `${cat}-A`
  const resp = await api.post('/products/', {
    data: { name: `E2E ${pfx}`, catalog_no: cat, slug: slug(pfx), skus: [{ sku_code, is_default: true, price: '10.00' }], ...extra },
  })
  await expectApi(resp, { status: 201, label: `夹具 ${pfx}` })
  return { id: (await resp.json()).data.id, cat, skuId: await skuIdOf(cat) }
}
async function draftCoa(api, f) {
  const r = await api.post('/coas/create-coa/', {
    data: { sku_id: f.skuId, lot_number: `${f.cat}-L1`, produced_at: '2026-01-15' },
  })
  await expectApi(r, { status: 201, label: 'COA 夹具(draft)' })
  return (await r.json()).data.id
}
async function approvedCoa(api, f) {
  const id = await draftCoa(api, f)
  await expectApi(await api.post(`/coas/${id}/approve/`), { status: 200, label: 'COA 夹具(published)' })
  return id
}
async function approvedSds(api, productId) {
  const g = await api.post('/sds-revisions/generate/', { data: { product_id: productId } })
  await expectApi(g, { status: 201, label: 'SDS 夹具(generate)' })
  const id = (await g.json()).data.id
  await expectApi(await api.post(`/sds-revisions/${id}/approve/`), { status: 200, label: 'SDS 夹具(approve)' })
  return id
}

test.describe('Part 1 · 组 H 合规 SDS / COA（9. Compliance）', () => {
  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    const r = await cleanupByPrefix(api, { label: 'H-group' })
    console.log(`__E2E__ H_CLEANUP ${J(r)}`)   // found / deleted / failed 必须可见
    await ctx.dispose(); await api.dispose()
  })

  // ── H1：缺 CAS/SMILES/InChI ⇒ 常显引导 + 点击不静默禁用（给警告）；零写入 ──
  test('H1 @readonly @local-only 缺标识 ⇒ SDS 引导(不静默禁用)、点击零写入(sds_revision Δ0)', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(req)
    const f = await mkProduct(api, 'H1')                                  // 无 cas/smiles/inchi
    await openEdit(page, f.id)
    await expect(page.locator('.sds-hint'), 'H1 常态引导（:1918）').toContainText(/CAS|SMILES|InChI/i)
    await expect(sdsBtn(page), 'H1 按钮不静默禁用，而是给引导').toBeEnabled()
    const before = docSnap()
    await sdsBtn(page).click()                                            // :1071 缺标识 → 前端早退
    await expect(page.locator('.toast-warn')).toContainText(/CAS|SMILES|InChI/i, { timeout: 10000 })
    expectDelta(before, docSnap(), { sds_revision: 0 }, 'H1 缺标识不得生成 SDS')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H2：Generate SDS ⇒ 201、sds_revision Δ+1、**无 status 字段**、current_sds 仍空（DB）──
  test('H2 @write @local-only Generate SDS ⇒ 201、sds_revision Δ+1、无 status 字段、current_sds 仍空', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProduct(api, 'H2', { cas: '62-53-3' })
    await openEdit(page, f.id)
    const before = docSnap()
    const resp = await apiAct(page, R.sdsGen, () => sdsBtn(page).click())
    await expectApi(resp, { status: 201, label: 'H2 生成 SDS' })
    expectDelta(before, docSnap(), { sds_revision: +1 }, 'H2 sds_revision Δ+1')
    const data = (await resp.json()).data
    expect(Object.keys(data), 'H2 SDS **无 status 字段**（L1 §29：SDS 无状态机）').not.toContain('status')
    expect(productField(f.id, 'current_sds_id'), 'H2 生成仅 draft，不发布').toBeNull()
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H3：Approve & Publish SDS ⇒ current_sds 指向该版、sds_published=true；无 CAS 仅软告警 ──
  test('H3 @write @local-only Approve & Publish SDS ⇒ current_sds 指向该版、sds_published=true；无 CAS 软闸门', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProduct(api, 'H3', { smiles: 'C1=CC=C(C=C1)N' })    // 有 smiles 无 cas ⇒ 打开前端 gate
    await openEdit(page, f.id)
    const sdsId = await genSds(page)
    const resp = await apiAct(page, R.sdsApprove, () => sdsListEl(page).getByRole('button', { name: /Approve & Publish SDS/ }).click())
    await expectApi(resp, { status: 200, label: 'H3 审批 SDS' })
    expect(productField(f.id, 'current_sds_id'), 'H3 current_sds 指向该版本（DB）').toBe(sdsId)
    expect(sdsField(sdsId, 'pdf_path'), 'H3 PDF 已生成').toBeTruthy()
    expect((await resp.json()).data.compliance, 'H3 无 CAS 软闸门：仅告警不阻断（L1 §P0-3）').toMatchObject({ compliant: false, reason: 'no_cas' })
    expect((await listItem(api, f.cat)).sds_published, 'H3 列表口径 sds_published').toBe(true)
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H4：Withdraw SDS ⇒ current_sds 清空、sds_published=false；旧 PDF 保留（DB）──
  test('H4 @write @local-only Withdraw SDS ⇒ current_sds 清空、sds_published=false；旧 PDF 保留', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProduct(api, 'H4', { cas: '62-53-3' })
    const sdsId = await approvedSds(api, f.id)
    const pdf = sdsField(sdsId, 'pdf_path')
    await openEdit(page, f.id)
    const resp = await apiAct(page, R.sdsWithdraw, () => sdsListEl(page).getByRole('button', { name: 'Withdraw' }).click())
    await expectApi(resp, { status: 200, label: 'H4 撤回 SDS' })
    expect(productField(f.id, 'current_sds_id'), 'H4 撤回清空 current_sds（DB）').toBeNull()
    expect(sdsField(sdsId, 'pdf_path'), 'H4 旧 PDF 保留（L1 COA_SDS_PRD §238）').toBe(pdf)
    expect((await listItem(api, f.cat)).sds_published, 'H4 撤回后 sds_published=false').toBe(false)
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H5：新建批次 + Generate COA ⇒ batch Δ+1、coa Δ+1、status=draft、计数=0（DB）──
  test('H5 @write @local-only 新建批次+Generate COA ⇒ batch Δ+1、coa Δ+1、status=draft、计数=0', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProductSku(api, 'H5')
    await openEdit(page, f.id)
    const form = page.locator('.batch-create-form')                        // :2001（无批次时渲染）
    await form.locator('input[type="date"]').first().fill('2026-01-15')    // Production date
    const before = docSnap()
    const resp = await apiAct(page, R.coaCreate, () => form.getByRole('button', { name: /Generate COA/ }).click())
    await expectApi(resp, { status: 201, label: 'H5 生成 COA' })
    expectDelta(before, docSnap(), { batch: +1, coa: +1 }, 'H5 batch + coa 落库')
    expect(coaField((await resp.json()).data.id, 'status'), 'H5 草稿态').toBe('draft')
    expect((await listItem(api, f.cat)).coa_published_count, 'H5 未发布计数=0').toBe(0)
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H6：Enter measurements → Save measurements ⇒ coa QC 字段写入 DB ──
  test('H6 @write @local-only Enter/Save measurements ⇒ coa QC 实测字段写入 DB', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProductSku(api, 'H6')
    const coaId = await draftCoa(api, f)
    await openEdit(page, f.id)
    await coaCardEl(page).getByRole('button', { name: 'Enter measurements' }).click()   // :1986
    const qc = page.locator('.qc-form')                                                   // :1969
    await qc.locator('input').first().fill('White powder')                                // Appearance
    const resp = await apiAct(page, R.coaQc, () => qc.getByRole('button', { name: 'Save measurements' }).click())
    await expectApi(resp, { status: 200, label: 'H6 保存实测' })
    expect(coaField(coaId, 'appearance_result'), 'H6 实测落库（DB）').toBe('White powder')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H7：Approve & Publish COA ⇒ status=published + PDF、计数=1；重复 approve 幂等（DB，铁律级状态机）──
  test('H7 @write @local-only Approve & Publish COA ⇒ status=published+PDF、计数=1；重复 approve 幂等', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProductSku(api, 'H7')
    const coaId = await draftCoa(api, f)
    await openEdit(page, f.id)
    const resp = await apiAct(page, R.coaApprove, () => coaCardEl(page).getByRole('button', { name: /Approve & Publish COA/ }).click())
    await expectApi(resp, { status: 200, label: 'H7 审批 COA' })
    expect(coaField(coaId, 'status'), 'H7 状态转 published（L1 §P0-4 铁律级状态机）').toBe('published')
    expect(coaField(coaId, 'pdf_path'), 'H7 PDF 已生成').toBeTruthy()
    expect((await listItem(api, f.cat)).coa_published_count, 'H7 已发布计数=1').toBe(1)
    await expectApi(await api.post(`/coas/${coaId}/approve/`), { status: 200, label: 'H7 幂等 approve' })
    expect(coaField(coaId, 'status'), 'H7 幂等：重复 approve 仍 published').toBe('published')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H8：Withdraw COA ⇒ status 回 draft、旧 PDF 保留、计数=0（DB）──
  test('H8 @write @local-only Withdraw COA ⇒ status 回 draft、旧 PDF 保留、计数=0', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProductSku(api, 'H8')
    const coaId = await approvedCoa(api, f)                               // 造 published 夹具
    const pdf = coaField(coaId, 'pdf_path')
    await openEdit(page, f.id)
    const resp = await apiAct(page, R.coaWithdraw, () => coaCardEl(page).getByRole('button', { name: 'Withdraw' }).click())
    await expectApi(resp, { status: 200, label: 'H8 撤回 COA' })
    expect(coaField(coaId, 'status'), 'H8 状态回 draft（L1 §4.4）').toBe('draft')
    expect(coaField(coaId, 'pdf_path'), 'H8 旧 PDF 保留（L1 §238）').toBe(pdf)
    expect((await listItem(api, f.cat)).coa_published_count, 'H8 撤回后计数=0').toBe(0)
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H9a：Preview ⇒ 打开合规预览弹层（SDS / COA 均走同一 modal）──
  test('H9a @write @local-only Preview ⇒ 打开合规预览弹层（SDS / COA）', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await mkProductSku(api, 'H9A', { cas: '62-53-3' })
    await approvedSds(api, f.id); await approvedCoa(api, f)
    await openEdit(page, f.id)
    await sdsListEl(page).getByRole('button', { name: 'Preview' }).first().click()          // :1941
    await expect(page.locator('.preview-overlay .preview-dialog')).toBeVisible()
    await page.locator('.preview-close').click()
    await expect(page.locator('.preview-overlay')).toHaveCount(0)
    await coaCardEl(page).getByRole('button', { name: 'Preview' }).click()                  // :1989
    await expect(page.locator('.preview-overlay .preview-dialog')).toBeVisible()
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── H9b：下载端点 GET 匿名可访问（已发布文档 ⇒ 200 application/pdf）──
  test('H9b @write @local-only 下载端点匿名可访问（已发布 SDS/COA ⇒ 200）', async ({ request }) => {
    const api = await staffApi(request)
    const f = await mkProductSku(api, 'H9B', { cas: '62-53-3' })
    const sdsId = await approvedSds(api, f.id)
    const coaId = await approvedCoa(api, f)
    await expectApi(await request.get(`${API_BASE}/sds-revisions/${sdsId}/download/`), { status: 200, label: 'H9b SDS 匿名下载' })
    await expectApi(await request.get(`${API_BASE}/coas/${coaId}/download/`), { status: 200, label: 'H9b COA 匿名下载' })
    await api.dispose()
  })

  // ── H9b2：✅ 2026-09-22 B9 已修（`documents/api/v1/views.py` download() 加发布状态门控）──
  //   口径：对外一律 404；**staff 仍可下载**（内部复核/审计留痕，故不删 pdf、只加门控）。
  //   此前下载端点只判 `pdf_path` 是否存在 ⇒ 已撤回(draft) 的 COA 可被匿名下载（200 + PDF）。
  test('H9b2 @write @local-only 已撤回(draft) COA 的 PDF 不应可匿名下载（L1 COA_SDS_PRD :80）', async ({ request }) => {
    const api = await staffApi(request)
    const f = await mkProductSku(api, 'H9C')
    const coaId = await approvedCoa(api, f)
    await api.post(`/coas/${coaId}/withdraw/`)                            // 撤回 → draft，但 pdf_path 保留
    await expectApi(await request.get(`${API_BASE}/coas/${coaId}/download/`), { status: 404, label: 'H9b2 draft COA 匿名下载应被拒' })
    await api.dispose()
  })

  // ── H10：新建态 ⇒ 整块合规区不渲染实体块，仅常显占位（必须先保存）──
  test('H10 @readonly @local-only 新建态 ⇒ 合规区不渲染实体块、仅常显占位（必须先保存）', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await expect(page.locator('.compliance-placeholder'), 'H10 常显占位（:1900）').toContainText(/Save the product first/i)
    await expect(page.locator('.compliance-block'), 'H10 新建态不得渲染 SDS/Batch COA 实体块').toHaveCount(0)
    await expect(sdsBtn(page), 'H10 不得出现 Generate SDS').toHaveCount(0)
    await expect(page.locator('.batch-create-form')).toHaveCount(0)
    await expect(sdsListEl(page)).toHaveCount(0)
    expect(errors).toEqual([])
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（纠错 / 纠偏 / 记录） —— 带 文件:行号
 *
 * #1【记录】H2 的「SDS 无 status 字段」为 L1 明示、L2 已对齐
 *    · L1《COA_SDS_PRD.md:29》：「COA 有 status（DRAFT/APPROVED/PUBLISHED）；**SDS 无 status 字段**——
 *      其"已发布"状态由 `Product.current_sds` 外键指针表示」；Part1 组 H · H2 同义。
 *    · L2：`SdsRevision` 模型无 status（`apps/documents/models.py:146-233`）；`SdsRevisionSerializer.fields`
 *      无 status（`apps/documents/api/v1/serializers.py:96-109`）；发布 = `approve_sds` 置 `product.current_sds`
 *      （`apps/documents/services/workflow.py:316-322`）。⇒ 断言按「无 status 键 + current_sds 指针」。
 *
 * #2【纠错候选｜已 fixme，须用户拍板】已撤回(draft)的 COA PDF 仍可**匿名下载**
 *    · L1 说：详情页/列表「仅对 `status=PUBLISHED` 的 COA 展示与允许下载」（`COA_SDS_PRD.md:80`、§4.4:188）。
 *    · L2 实测（本机探针）：
 *        - 下载端点**无发布状态校验**且 `IsAdminOrReadOnly` 放行匿名 GET
 *          （`apps/documents/api/v1/views.py:49-53` 权限 + `:117-140` download 仅判 `pdf_path` 存在）
 *        - `withdraw_coa` **保留** `pdf_path`（`apps/documents/services/workflow.py:118-128`）
 *        - UI 在 draft 态**仍显示 Download**（`ProductEditPage.vue:1990` 条件仅 `item.coa.pdf_path`）
 *        - ⇒ 探针实测：published→撤回为 draft 后，匿名 `GET /coas/{id}/download/` ⇒ **HTTP 200 application/pdf**
 *    · ⇒ **L1 ≠ L2（功能定义偏差）**：本 spec 将该条独立标 `test.fixme`（断言 L1：应 404），
 *      **不放宽断言博绿灯**；是否收紧下载门控（校验 status=published / 撤回即清 pdf 引用）请用户判定。
 *
 * #3【记录】本机 PubChem 不可达 ⇒ `generate_sds` 恒落到 L4，测试**不得依赖 `data_confidence` 等级**
 *    · `generate_sds` 四级降级链（`workflow.py:191-284`）；本机探针实测：带 cas/smiles 的产品
 *      `POST /sds-revisions/generate/` ⇒ 201、1.7s、`data_confidence="very_low"`、
 *      `data_source_detail="Generic safety notes (no identifier matched)"`。
 *    · ⇒ 断言只取「是否落库 / 指针 / 计数」等确定性事实，不硬编码 confidence（随网络环境漂移）。
 *    · 另：无 CAS 时 `approve_sds` 返回 `compliance={compliant:false,reason:'no_cas',note:…}`
 *      但**仍 200 且置 current_sds** ⇒ 印证「软闸门：告知非硬阻断」（`workflow.py:287-322`）。
 *
 * #4【纠偏】任务书把 H8 描述为「拒绝 / 驳回路径」—— 代码与 L1 均无 reject/驳回态
 *    · L1 §4.4 状态机仅 `DRAFT →(approve) PUBLISHED →(withdraw) DRAFT`（`COA_SDS_PRD.md:177-189`）；
 *      迁移 `0004_fix_coa_approved_to_published` 已把 APPROVED 废弃（approve 直接写 PUBLISHED）。
 *    · 与 `documents/views.py:101-125` 一致：COA 只有 `approve` / `withdraw` 两个动作，无 reject。
 *    · ⇒ 本 spec 按 L1 以 **withdraw（H8）** 覆盖「非 approve 路径 → 回 draft」，并在报告注明该纠偏。
 *
 * #5【记录】`sds_published` / `coa_published_count` **只在 list 端点**，retrieve 不带
 *    · 定义：`ProductListSerializer`（`apps/commerce/api/v1/serializers.py:99-100,136-145`）——
 *      `sds_published = current_sds_id is not None`；`coa_published_count = 已 published 的批次数`。
 *    · `ProductDetailSerializer`（同文件 :473+）**不含**二者 ⇒ 列表口径断言只能走 `GET /products/`。
 *    · 用法：`?archived=1&page_size=500&ordering=-created_at` 取最新页再按 `catalog_no` 定位（现算，不硬编码）。
 *
 * #6【记录/测试坑】`?search=` 走**自定义选择器**，对含连字符的长货号不命中
 *    · `ProductViewSet.get_queryset`：`search` → `selectors.filter_products(query, base_qs=qs)`
 *      （`apps/commerce/api/v1/views.py:93-97`），非 DRF 原生 `SearchFilter`。
 *    · 本机探针实测 `?search=E2E-PROBE2-<ts>` 返回空 ⇒ 夹具定位**不可**用 search，改用 #5 的排序+前缀匹配。
 *
 * #7【记录】COA `doc_id` 序号口径按 (catalog_number, year) 计数，非全局（`workflow.py:44-50`）
 *    · 故本 spec 断言 `status` 而非 `doc_id` 具体值（避免跨用例串号假失败）。
 *
 * #8【记录】清理：夹具**不挂分类桥** ⇒ `hard-delete` 可正常删（绕开台账 B1 的 500 坑）
 *    · 探针实测：本 spec 产物 `POST /products/{id}/hard-delete/` ⇒ 200。
 *    · `afterAll` 用 `cleanupByPrefix(api,{label:'H-group'})` 按 `E2E-` 前缀幂等硬删；
 *      COA/Batch/SDS 经 FK CASCADE 随产品一并删除。
 * ──────────────────────────────────────────────────────────────────────── */
