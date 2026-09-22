/**
 * Part 1（研究员工作台·产品新建页）· **组 E「知识关联」（5. Knowledge Links）** —— E1–E6
 *
 * 规格来源：《2026-09-22_动作剧本×期望断言_Part1_研究员工作台产品新建页.md》§组 E（E1–E6）；
 *          覆盖缺口定性见《2026-09-22_P0_动作剧本覆盖矩阵.md》§2（E1–E5 ✗ 零覆盖；E6 ◐）。
 * 判据层级（e2e/README.md §6）：L0 铁律 > L1 规格 > L2 代码现值；L3 不变量恒成立。
 * **期望值只取自 L1 规格 + 直读代码现值**（ProductEditPage.vue / utils/protocolLinks.js /
 * commerce/api/v1/serializers.py / bridges.services.relevance），与规格不一致处单列于文末「发现」。
 *
 * 真实 DOM（ProductEditPage.vue，非猜测）：
 *   Methods chips   : `.chip-group`(含 `.chip-label` "Methods:") > `.chip` / `.chip-remove` / `.chip-none`  :1784-1791
 *   Protocols chips : 同类，`.chip-protocol`(强) / `.chip-weak`(弱) / `显示全部 (N)` / `收起` / `.weak-toggle` :1794-1817
 *   下拉 Link       : `.entity-select-row` 两个 AppSelect(Element Plus `.el-select`) + 两个 `Link`（:disabled="!linkMethodSelect"）:1820-1826
 *   内联新建        : `.inline-buttons` `+ New Method` → 弹层 `.dialog-overlay .dialog` #inline-title + `Save & Link` :1831-1835/:2059-2072
 * 桥落库时机（L2 现值）：chips/Link/内联新建**只改本地数组**（toggleMethodId :406-416 / addSelectedMethod :421-428 /
 *   saveInlineEntity :430-451），**真正写桥表发生在产品保存**（payload.method_ids/protocol_ids → serializers.py:347-352/:419-424）。
 *
 * 本机跑法（**必须**，见 e2e/README.md §1；输出重定向到文件，勿管道给 tail；与同伴共用 dev 库须加锁串行）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do echo "lock busy, wait..."; sleep 30; done
 *   echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-knowledge-links.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p3d > ../../_p3d.log 2>&1
 *   rm -f ../../_pw.lock
 *
 * 前置：本地 dev 已起（Django :8000 DB_ENGINE=sqlite / Vite :5173，且 Vite 从 **E: 物理路径** 启动）。
 * 纪律：只新增本文件；不改应用代码、不 git commit；写操作只碰 `E2E-` 前缀夹具（产品）/`E2E-MTH-` 前缀知识实体，
 *      afterAll 硬删产品并按捕获的 id 删除自建 Method。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, snapshotDb, expectDelta, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { catalogNo, slug, RUN_TS, cleanupByPrefix } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const WL2 = [...WL, 'Failed to load resource']
const J = JSON.stringify
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

const SEL = {
  name: `input[placeholder="e.g. 2'-Amino-ATP"]`,      // :1684
  catalog: `input[placeholder="e.g. SC8043"]`,         // :1688
  save: '.form-actions button',                        // :2023
  enrichBtn: '.pubchem-enrich-section button.file-upload-btn',   // :1426（限 section，避开 Word Import 同名按钮）
}
const saveBtn = (page) => page.locator(SEL.save, { hasText: /Save Draft|Saving/ })
const dialog = (page) => page.locator('.dialog-overlay .dialog')
const chips = (page, label) => page.locator('.chip-group')
  .filter({ has: page.locator('.chip-label', { hasText: `${label}:` }) })

const fillNew = async (page, cat) => {
  await page.locator(SEL.name).fill('E2E 知识关联 probe')
  await page.locator(SEL.catalog).first().fill(cat)
}
// 点击前先 scrollIntoView：本页 save 按钮在视口外，且 Knowledge Links 的 el-select 残留 popper
// 可能短暂遮挡 ⇒ 不滚动就点会因「hit-target 不符」重试到超时（2026-09-22 实测）。
const save = async (page, method) => {
  const btn = saveBtn(page)
  await btn.scrollIntoViewIfNeeded()
  // 保存若带 method_ids 会同步重算派生协议（`_refresh_inherited_bridges` serializers.py:444-470 →
  // `recompute_product` relevance.py:437-487），实测可达 ~28s，而前端 axios 上限仅 15s（http.js:11）
  // ⇒ 重的链法保存会客户端 abort（见「发现」#6/#7）。此处给 60s 上限：够现行夹具（皆轻）通过，
  // 且比套件默认更快暴露 abort（abort 时无响应可等待）。
  const respP = page.waitForResponse(
    (r) => r.request().method() === method && r.url().includes('/api/v1/products/'),
    { timeout: 60_000 })
  await btn.click()
  return respP
}
/** 打开 Element Plus 下拉并选第一个真实项（跳过 `— Link existing … —` 占位，:1821/:1824），再等 popper 收起 */
async function linkFirstOption(page, elSelect) {
  await elSelect.click()
  await page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    .filter({ hasNotText: '— Link existing' }).first().click()
  await page.keyboard.press('Escape')
  await expect(page.locator('.el-select-dropdown:visible'), '选完后 popper 应收起（不遮挡后续按钮）').toHaveCount(0)
}

// ── D-DB 只读现算（禁止硬编码期望值）─────────────────────────────────
const methodCount = () => dbQuery(`import json\nfrom apps.knowledge.models import Method\nprint('__SNAP__' + json.dumps(Method.objects.count()))`)
/** 现算「无派生协议」的最轻 method id：E6b 用它做夹具，避开 E2b 已记录的 15s 客户端超时缺陷（见「发现」#7） */
const lightestMethodId = () => dbQuery(
  `import json\nfrom apps.knowledge.models import Method\nfrom apps.bridges.models import MethodProtocol\n` +
  `used = set(MethodProtocol.objects.values_list('method_id', flat=True))\n` +
  `print('__SNAP__' + json.dumps(Method.objects.exclude(id__in=used).order_by('id').values_list('id', flat=True).first()))`)
/** 详情节点的只读取数（含 protocol_links 与 protocol_ids，E4 需两者现算） */
const detailOf = async (api, pid) => (await (await api.get(`/products/${pid}/`)).json()).data
/** 现算「协议链接最多的产品」id（用于 E4/E5 的折叠/排序只读断言；不写库） */
const heaviestProtocolProduct = () => dbQuery(
  `import json\nfrom django.db.models import Count\nfrom apps.bridges.models import ProductProtocol\n` +
  `r = ProductProtocol.objects.values('product').annotate(c=Count('id')).order_by('-c').first()\n` +
  `print('__SNAP__' + json.dumps(r['product'] if r else None))`)

// 排序契约复刻自 `utils/protocolLinks.js:69-89`（weak 沉底 → chem_specific 置顶 → TIER_RANK 升 → relevance/score_c 降 → id 升）
const TIER_RANK = { literature: 0, document: 1, featured: 2, weak: 3 }
const cmpProtocol = (a, b) => {
  const w = (r) => (r.tier === 'weak' ? 1 : 0)
  if (w(a) !== w(b)) return w(a) - w(b)
  const c = (r) => (r.chem_specific ? 1 : 0)
  if (c(a) !== c(b)) return c(b) - c(a)
  const ra = TIER_RANK[a.tier] ?? 2, rb = TIER_RANK[b.tier] ?? 2
  if (ra !== rb) return ra - rb
  const rel = (Number(b.relevance_score) || 0) - (Number(a.relevance_score) || 0)
  if (rel) return rel
  const sc = (Number(b.score_c) || 0) - (Number(a.score_c) || 0)
  return sc || Number(a.id) - Number(b.id)
}
/** 读 chip 序列的协议 id（真实 DOM：`a.chip-link` href=`/protocols/<id>`） */
const linkIds = (loc) => loc.evaluateAll((els) => els.map((a) => Number(String(a.getAttribute('href')).split('/').pop())))
const strongChips = (g) => g.locator('.chip-protocol:not(.chip-weak)')

/** 建 E2E- 夹具产品（可带额外字段）；返回 {id, catalog_no} */
async function fixtureProduct(api, pfx, extra = {}) {
  const cat = catalogNo(pfx)
  const resp = await api.post('/products/', { data: { name: `E2E ${pfx}`, catalog_no: cat, slug: slug(pfx), ...extra } })
  await expectApi(resp, { status: 201, label: `夹具 ${pfx}` })
  return { id: (await resp.json()).data.id, catalog_no: cat }
}

const createdMethods = []   // 内联新建的 Method id（afterAll 硬删，避免 dev 库残留）

test.describe('Part 1 · 组 E 知识关联（5. Knowledge Links）', () => {
  // E4/E5 载入「协议链接最多」产品 + 各用例含多次 spawn Python 取数 ⇒ 超时给足（默认 45s 偏紧）
  test.describe.configure({ timeout: 120_000 })

  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    const r = await cleanupByPrefix(api, { label: 'E-group' })
    for (const mid of createdMethods) await api.delete(`/methods/${mid}/`).catch(() => {})
    console.log(`__E2E__ E_CLEANUP ${J(r)} createdMethods=${J(createdMethods)}`)
    await ctx.dispose(); await api.dispose()
  })

  // ── E1：移除 Methods chip ⇒ 保存后 product_method Δ-1（_sync_method_bridges :201-215）──
  test('E1 @write @local-only 移除 Method chip ⇒ 保存后 product_method Δ-1', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'E1', { method_ids: [lightestMethodId()] })   // 最轻方法：夹具更快（「发现」#7）
    await loginAsStaff(page); await goto(page, `/workspace/products/${f.id}/edit`)
    const g = chips(page, 'Methods')
    await expect(g.locator('.chip'), 'E1 夹具应已有 1 个 method chip').toHaveCount(1)
    const before = snapshotDb()
    await g.locator('.chip-remove').click()
    await expect(g.locator('.chip'), 'E1 chip 应消失').toHaveCount(0)
    await expectApi(await save(page, 'PUT'), { status: 200, label: 'E1 保存' })
    expectDelta(before, snapshotDb(), { product_method: -1 }, 'E1 桥表 Δ-1')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── E2（L1 §E2，仅 `U` 契约）：下拉 Link 已有 Method ⇒ 未选时 Link disabled、选后 chip 出现 ──
  //    ⚠ L1 §E2 原文只有 `U`（chip 出现 / Link 未选 disabled）；「保存后 product_method Δ+1」是
  //    任务书的加强项，但经真实 UI **不可达**（客户端 15s 超时 < 服务端同步重算 ~28s，见「发现」#6/#7）
  //    ⇒ 加强断言单列 E2b 为 `test.fixme`，本用例只守住 L1 契约。
  test('E2 @write @local-only 下拉 Link 已有 Method ⇒ Link 未选时 disabled、选后 chip 出现', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'E2')
    await loginAsStaff(page); await goto(page, `/workspace/products/${f.id}/edit`)
    const row = page.locator('.entity-select-row')
    const linkBtn = row.locator('button', { hasText: 'Link' }).first()
    await expect(linkBtn, 'E2 未选时 Link 应 disabled（:1822）').toBeDisabled()
    await linkFirstOption(page, row.locator('.el-select').first())
    await expect(chips(page, 'Methods').locator('.chip'), 'E2 chip 应出现').toHaveCount(1)
    await expect(linkBtn, 'E2 link 后 select 已清空 ⇒ Link 回到 disabled（:423）').toBeDisabled()
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── E2b【缺陷 · fixme】任务书加强项：下拉 Link 后「保存」⇒ product_method Δ+1 ──
  //    经真实 UI **不可达**（非测试问题）：`utils/http.js:11` axios `timeout:15000` < 服务端同步重算
  //    （实测 UI 首项 method54 含 752 条 MethodProtocol ⇒ PUT ≈28s）⇒ 请求被客户端 abort
  //    （`net::ERR_ABORTED`），UI 报 `Save failed: timeout of 15000ms exceeded`。缺陷修复（重算异步化
  //    或该请求放宽超时）后本用例即应转正。证据与文件:行号见文末「发现」#6/#7。
  test.fixme('E2b @write @local-only [缺陷] 下拉 Link 已有 Method ⇒ 保存后 product_method Δ+1', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'E2B')
    await loginAsStaff(page); await goto(page, `/workspace/products/${f.id}/edit`)
    const row = page.locator('.entity-select-row')
    await linkFirstOption(page, row.locator('.el-select').first())
    await expect(chips(page, 'Methods').locator('.chip'), 'E2b chip 应出现').toHaveCount(1)
    const before = snapshotDb()
    await expectApi(await save(page, 'PUT'), { status: 200, label: 'E2b 保存' })  // ← 当前必失败：15s abort
    expectDelta(before, snapshotDb(), { product_method: +1 }, 'E2b 桥表 Δ+1')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── E3：内联新建 Method ⇒ method Δ+1 + chip 挂上 + 保存后产品被链上 ──
  test('E3 @write @local-only 内联新建 Method ⇒ method Δ+1、chip 挂上、保存后产品被链上', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'E3')
    await loginAsStaff(page); await goto(page, `/workspace/products/${f.id}/edit`)
    const before = snapshotDb(); const mBefore = methodCount()
    await page.locator('.inline-buttons button', { hasText: '+ New Method' }).click()
    const dlg = dialog(page)
    await expect(dlg.locator('#inline-title')).toHaveText('New Method')
    await dlg.locator('input').first().fill(`E2E-MTH-${RUN_TS}`)                 // POST /methods/{name}（:430-437）
    const respP = page.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes('/api/v1/methods/'))
    await dlg.locator('button', { hasText: 'Save & Link' }).click()
    createdMethods.push((await (await respP).json()).data.id)
    await expect(dlg, 'E3 弹层应关闭').toHaveCount(0)
    await expect(chips(page, 'Methods').locator('.chip'), 'E3 chip 自动挂上').toHaveCount(1)
    expectDelta({ method: mBefore }, { method: methodCount() }, { method: +1 }, 'E3 知识表 Δ+1')
    await expectApi(await save(page, 'PUT'), { status: 200, label: 'E3 保存' })
    expectDelta(before, snapshotDb(), { product_method: +1 }, 'E3 产品被链上 Δ+1')
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── E4：Protocols 折叠（强相关 TopN=10 + 显示全部）+ 弱相关独立折叠区 ──
  //    期望值全部现场推导：强相关 = server protocol_links 中 tier!=weak；
  //    弱相关 = union(protocol_links, protocol_ids) 去重后 − 强相关（前端 unionProtocolRows 把本地 id 记为 weak）
  test('E4 @readonly @local-only Protocols 折叠：强相关 TopN10 + 显示全部；弱相关独立折叠区', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(req)
    const pid = heaviestProtocolProduct()
    const d = await detailOf(api, pid)
    const rows = d.protocol_links || []
    const strong = rows.filter((r) => r.tier !== 'weak').length
    const weak = new Set([...rows.map((r) => r.id), ...(d.protocol_ids || [])]).size - strong
    await loginAsStaff(page); await goto(page, `/workspace/products/${pid}/edit`)
    const g = chips(page, 'Protocols')
    if (strong <= 10 && weak === 0) test.skip(true, `E4 不可达（规格沉默）：strong=${strong} weak=${weak}，无折叠/弱相关条件`)
    await expect(strongChips(g), 'E4 默认只显 10 条强相关（buildFolded topN=10）').toHaveCount(Math.min(strong, 10))
    if (strong > 10) {
      await expect(g.locator('button', { hasText: `显示全部 (${strong - 10})` })).toBeVisible()
      await g.locator('button', { hasText: '显示全部' }).click()
      await expect(strongChips(g), 'E4 折叠≠删除：展开后强相关全显').toHaveCount(strong)
    }
    if (weak > 0) {
      await expect(g.locator('.weak-toggle'), 'E4 弱相关独立折叠区（:1807）').toContainText(`弱相关 (${weak})`)
      await g.locator('.weak-toggle').click()
      await expect(g.locator('.chip-weak'), 'E4 展开后弱相关全显').toHaveCount(weak)
    }
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── E5：协议排序 —— DOM 次序 == 服务端 protocol_links 按契约排序后的次序 ──
  test('E5 @readonly @local-only 协议排序：强相关区次序 == 按 sortProtocolLinks 契约复排的次序', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(req)
    const pid = heaviestProtocolProduct()
    const rows = (await detailOf(api, pid)).protocol_links || []
    const expected = rows.filter((r) => r.tier !== 'weak').sort(cmpProtocol).map((r) => r.id)
    if (expected.length < 2) test.skip(true, `E5 不可达（规格沉默）：可见强相关协议 <2（links=${rows.length}）`)
    await loginAsStaff(page); await goto(page, `/workspace/products/${pid}/edit`)
    const g = chips(page, 'Protocols')
    await expect(strongChips(g), 'E5 强相关区应已渲染（默认折叠）').toHaveCount(Math.min(expected.length, 10))
    if (expected.length > 10) await g.locator('button', { hasText: '显示全部' }).click()
    await expect(strongChips(g), 'E5 展开后强相关数 == 服务端强相关数').toHaveCount(expected.length)
    expect(await linkIds(strongChips(g).locator('.chip-link')), 'E5 次序必须与 protocolLinks.js:69-89 契约一致（weak 沉底）').toEqual(expected)
    await api.dispose(); expect(errors).toEqual([])
  })

  // ── E6：全新产品（未 enrich 未手连）保存 ⇒ 三桥表 Δ0（不凭空自动关联）──
  test('E6 @write @local-only 新建产品 0 链接保存 ⇒ product_method/protocol/relation Δ0', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await fillNew(page, catalogNo('E6'))
    const before = snapshotDb()
    await expectApi(await save(page, 'POST'), { status: 201, label: 'E6 保存' })
    expectDelta(before, snapshotDb(),
      { product: +1, product_method: 0, product_protocol: 0, product_method_relation: 0 }, 'E6 零链接')
    expect(errors).toEqual([])
  })

  // ── E6b：**加强版**（原 dark-a11y-knowledge(B) 只断 UI）—— enrich 命中方法 → Save Draft ⇒ DB 桥表 Δ+1 ──
  test('E6b @write @local-only [加强] enrich 命中方法→Save Draft ⇒ DB product_method Δ+1（自动关联落库）', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    const mid = lightestMethodId()   // 夹具取最轻方法（无派生协议）⇒ 避开 15s 客户端超时缺陷（「发现」#7）
    if (mid == null) test.skip(true, 'E6b 不可达（规格沉默）：库中不存在无派生协议的 Method')
    await page.route('**/products/enrich/', (route) => route.fulfill({ status: 200, json: { success: true, data: {
      chemical: { found: true, cid: 12345, confidence: 'high', identity_verified: false, properties: {} },
      literature: { matched_methods: [{ keyword: 'PCR', matches: [{ id: mid, name: 'E2E auto method' }] }],
        matched_apps: [], unmatched_method_keywords: [], unmatched_app_keywords: [] },
      protocols: [], jena: { matched: false }, bioz: { evidence: [] },
    } } }))
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await fillNew(page, catalogNo('E6B'))
    await page.locator(SEL.enrichBtn).click()
    await expect(page.locator('.pubchem-enrich-section .word-ok').first(), 'E6b enrich 应完成').toBeVisible()
    const before = snapshotDb()
    await expectApi(await save(page, 'POST'), { status: 201, label: 'E6b 保存' })
    expectDelta(before, snapshotDb(), { product_method: +1 }, 'E6b 自动关联落库 Δ+1')
    await page.unroute('**/products/enrich/')
    expect(errors).toEqual([])
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（纠错 / 纠偏 / 记录） —— 与 L1 规格或真实网站不一致处，带 文件:行号
 *
 * #1【纠偏/记录】L1 §E2/E3 的「桥表 Δ+1」在**纯 UI 交互时刻并不成立**——桥落库被推迟到产品保存
 *    · chips 的增删（`toggleMethodId` `ProductEditPage.vue:406-410`）、下拉 Link（`addSelectedMethod`
 *      `:421-424`）、内联新建（`saveInlineEntity` `:430-442`）**都只改本地数组**；
 *      真正写 `ProductMethod` 的是产品保存路径 `_sync_method_bridges`（`serializers.py:201-215`，
 *      由 create/update `:347-352`/`:419-424` 触发）。
 *    · ⇒ 本 spec 的 E1/E2/E3 均以「**保存后**桥表 Δ」为判据（与 L1 原文 E1「保存后」一致）；
 *      E3 的「知识表 Δ+1」在 `POST /methods/` 返回即成立（`Method` 表，非桥表），故即时断言。
 *    · ⚠ 规格把「下拉 Link ⇒ Δ+1」写成即时效果，与实现（需 Save）不同层 ⇒ 记此，供用户判定是否需改文案。
 *
 * #2【记录】E3 的内联新建只支持 **Method / Protocol** 两型（L1 §E3 小注与此一致）
 *    · 模板 `+ New Method` / `+ New Protocol`（`ProductEditPage.vue:1833-1834`）→ `openInlineNew('method'|'protocol')`
 *      （`:400-404`）；`apiEndpoints` 另含 goal/app/reference（`:380-383`）但**无入口按钮**。
 *    · ⇒ 组 E 的「内联新建」范围按 method/protocol 断言。
 *
 * #3【记录/风险】内联新建会**遗留知识实体**，`cleanupByPrefix`（`fixtures/index.cjs:31-58`）只清产品
 *    · 本 spec 以 `E2E-MTH-<ts>` 命名 + 捕获 POST 返回 id，在 afterAll 用 `DELETE /methods/{id}/`
 *      （`MethodViewSet` = ModelViewSet + `IsAdminOrReadOnly`，`knowledge/api/v1/views.py:76-79`）硬删。
 *    · 若 DELETE 失败，dev 库会残留 1 个 E2E-MTH- 方法（日志 `__E2E__ E_CLEANUP` 可见 createdMethods）。
 *
 * #4【记录】E4 的「弱相关」桶 = server weak 行 ∪ **本地 protocol_ids**（由前端记为 weak），
 *      **不等于** `protocol_links` 里的 weak 数
 *    · `unionProtocolRows`（`utils/protocolLinks.js:155-180`）把 server 行之外的本地 `protocolIds`
 *      赋予 `tier='weak'`/`link_source='queued'` ⇒ 归入弱相关折叠区；且 `protocolIds` 来自
 *      `get_protocol_ids`（`serializers.py:533-536`，走 MethodProtocol），**与 `protocol_links` 不同源**。
 *    · 实测（2026-09-22，id=70）：`protocol_links` 245 行（literature 169 / weak 76），但 `protocol_ids`
 *      另含 74 个不在 server 行的 id ⇒ 页面弱相关实际 **150**。首版断言按 76 会误报 FAIL。
 *    · ⇒ 期望值改为「`union(protocol_links, protocol_ids)` 去重 − 强相关」，即按真实渲染口径现算（非放宽）。
 *
 * #5【记录/测试坑】产品保存按钮在视口外，且 el-select 残留 popper 会短暂遮挡 ⇒ 点击本身不稳
 *    · 2026-09-22 实测：按钮 rect.y≈1249 > 视口 720，不 `scrollIntoViewIfNeeded()` 直接点会因
 *      hit-target 不符而重试；链接下拉选完后残留的 `.el-select-dropdown` 亦会遮挡后续按钮。
 *      ⇒ `save()` 先滚动、`linkFirstOption()` 选后 `Escape` 并断言 popper 收起。属**测试驱动问题**。
 *
 * #6【纠错 · E2 超时真因】先前的「点击/hit-target」判断（#5）**只对了一半**：点击可达、PUT 确已发出，
 *     真正的阻塞是**保存接口同步重算派生协议 > 前端 axios 超时上限**。
 *    · 链路：`ProductViewSet.perform_update`（`commerce/api/v1/views.py:158-165`）→ `ProductWriteSerializer.update`
 *      （`commerce/api/v1/serializers.py:361-442`）→ `_refresh_inherited_bridges`（`:444-470`）→
 *      `recompute_product`（`bridges/services/relevance.py:437-487`）逐协议算三轴分并 upsert `ProductProtocol`。
 *    · 实测（2026-09-22，sqlite，直连 API）：UI 知识下拉首项 = **method 54「Genomic DNA Extraction」**
 *      （`GET /methods/?page_size=200` 首项；前端加载 `ProductEditPage.vue:390`、渲染 `:1821`），
 *      含 **752** 条 MethodProtocol ⇒ 该次 PUT **≈27.7s**（对照 method35/268 条 ≈13.1s；
 *      清空 method_ids 不触发重算 ≈0.15s）⇒ 时延与服务端派生协议数**成正比**。
 *    · 前端 `frontend/src/utils/http.js:11` axios `timeout: 15000` ⇒ **客户端 15s 先 abort**。
 *    · ⇒ L1 §组 I「`Save Draft`（编辑）⇒ `PUT /products/{id}/` **200**」对"带 method 的产品"在
 *      UI 上**不可达成** ⇒ 属**应用缺陷（纠错）**，非测试问题。诉求：重算异步化或该请求单独放宽超时。
 *
 * #7【纠错 · 假失败（高优先）】UI 报「保存失败」，服务端却已落库
 *    · 浏览器实测探针（2026-09-22，product 2571）：点 `Save Draft` 后 **15.18s** 弹出
 *      `Save failed: timeout of 15000ms exceeded`（`http.js:11`），网络层 `FAILED PUT net::ERR_ABORTED`；
 *      但随后 DB 快照显示 **已写入**：`product_method Δ+1`、`product_protocol Δ+752`、
 *      `ProductMethod = [54]`（服务端 WSGI 视图未被中断，执行到底）。
 *    · ⇒ 用户被告知失败、数据却已变更 ⇒ 重试即**二次提交**（幂等与信任受损）。**需用户拍板**：
 *      重算异步化 / 保存结果以服务端为准 / 请求单独放宽超时；本 spec **不改应用代码**。
 *    · 落地方式：E2 只保留 L1 的 `U` 契约（可通过）；Δ+1 加强断言单列为 **`E2b` `test.fixme`**。
 *    · 连带：E6b（原链 method35 ≈13s）离 15s 超时仅 ~2s 余量 ⇒ 夹具改用**无派生协议**的最轻方法
 *      （`lightestMethodId()` 现算 ⇒ method 45）。**仅换夹具，断言不变**（Δ+1 照旧）。
 * ──────────────────────────────────────────────────────────────────────── */
