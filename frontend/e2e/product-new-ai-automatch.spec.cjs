/**
 * Part 1 · 研究员工作台·**产品新建页** 组 D「AI AUTO MATCH」—— **生产只读 E2E 剧本**
 *
 * 权威规格：`2026-09-22_动作剧本×期望断言_Part1_研究员工作台产品新建页.md` 组 D（D1–D16）
 * 面板实现：`src/views/workspace/ProductEditPage.vue`（+ MultiSourceMatchSection / BiozEvidenceSection）
 *
 * ── 覆盖与排除（务必先读）────────────────────────────────────────────────
 * • 覆盖（R2 只读可验）：**D1、D2、D3、D4、D5、D6、D8、D9、D10、D11、D12、D13、D16**。
 *   - D1 按「纠偏①」改写：四项标识全空时 `:1419` 面板 `v-if` 为假 ⇒ **整块不渲染**（无按钮），
 *     规格「按钮 disabled」所指 `:1426` 空值分支是**不可达死代码**。
 *   - D7 跳过：生产未复现 `candidates>1`（本会话 4 次只读探针 0/1 候选）；构造会引入猜测数据。
 *     候选渲染/不自动套用机制已由 D8 用真实生产响应覆盖。
 * • **排除**：**D14、D15**——二者属**写库**动作，不得进 R2 只读剧本：
 *   - D15 点 `Import to Knowledge Base` → `POST /products/import-protocol/`（`ai_views.py:471`，写 protocol/method）。
 *   - D14 的 `Adopt` → `handleAdoptBiozRef`(:831) 打 `POST /products/{id}/adopt-bioz-refs/`；**新建态 productId=null**
 *     ⇒ `/products/null/…` 必 404，且 `ai_views.py:677` 会写 Reference/ProductReference。故 Adopt 一律不入本剧本。
 * • **只读铁律**：本剧本只发 `POST /products/enrich/`（已由代码 `ai_views.py:211-434` 无写 + 生产实测 11 表前后计数一致双重证明为**纯计算不落库**）
 *   与 GET/登录。**绝不**触碰 `import-protocol` / `adopt-bioz-refs` / 任何写端点。
 *
 * ── D-DB / N-负向（生产）──────────────────────────────────────────────────
 * 生产 D-DB 走 `e2e/helpers/prod-db.cjs`（ssh 容器内只读 `SELECT count(*)`；非 localhost 护栏）。
 * 因 ssh 每次约 2–5s，**只在代表性用例 D16 上跑前后各一次 Δ0**（覆盖 product/协议/方法血缘 + audit_log + 权威表）。
 * D2/D5/D6/D8/D9/D12/D13 的「enrich 只读」由代码证明 + D16 实测共同背书，不逐例 ssh。
 *
 * ── 期望值来源纪律（L0>L1>L2；现算优先，禁止硬编码）──────────────────────
 * D2 期望值取自本会话生产实测 `_probe_dgroup/enrich_D2.json`（cas=150718-26-6 ⇒ cid=121487800 等），
 * 且 UI 侧用 `waitForResponse` **现场取同一响应**断言，不硬编码。
 * D6/D4/D8 期望值取自本会话生产只读探针 `_probe_dgroup/probe_d6d4.out` / `probe_d7.out`。
 *
 * ── 认证（生产两层，见 e2e/README.md §3）────────────────────────────────
 * • nginx Basic：env `E2E_BASIC_USER/PASS` → `httpCredentials`（浏览器）+ `helpers/api.cjs` 显式头。
 * • 应用层：`/auth/login` 取 token；前端从 `localStorage.token` + `localStorage.is_staff` 判定
 *   （`stores/auth.js:11,23` + `router/index.js:272` 守卫同步读缓存）⇒ 用 `addInitScript` 注入，
 *   规避生产登录页竞态；**未改任何应用代码**。
 *
 * ── console 断言说明 ────────────────────────────────────────────────────
 * 生产页含第三方/CDN 噪音，本剧本**不做 console 零错误断言**（留待本地 dev 集），
 * 以免把无关噪音误判为 D 组失败。这是**记录项**，非疏漏。
 *
 * 运行（本机，见 e2e/README.md §1）：
 *   cd src_claude/frontend
 *   E2E_BASIC_USER=scire01 E2E_BASIC_PASS=… E2E_API_BASE=https://scireagent.com BASE_URL=https://scireagent.com \
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-ai-automatch.spec.cjs \
 *     --project=chromium --reporter=line --retries=1 > ../../_prod_dgroup.log 2>&1
 *
 * 验收线：**每条 test 函数体 ≤ 15 行**（断言复用 helpers）。
 */
const { test, expect } = require('@playwright/test')
const fs = require('node:fs')
const path = require('node:path')
const { BASE_URL, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, expectDelta, zeroSpec, getPath } = require('./helpers/assertions.cjs')
const { prodCounts } = require('./helpers/prod-db.cjs')

// ── 生产两层认证：nginx Basic 交 httpCredentials（仅当提供了生产凭据） ──
const BASIC_USER = process.env.E2E_BASIC_USER || ''
const BASIC_PASS = process.env.E2E_BASIC_PASS || ''
if (BASIC_USER) test.use({ httpCredentials: { username: BASIC_USER, password: BASIC_PASS } })

const PANEL = 'section.pubchem-enrich-section'
const ENRICH_RE = /\/products\/enrich\// // route + waitForResponse 统一用正则，避免 glob 漏配
const APPLY_ALL = `${PANEL} button.btn.btn-primary.btn-sm` // 需配合 hasText('Apply All to Form')，否则会撞候选行的 "Use this"
const F = {
  name: `input[placeholder="e.g. 2'-Amino-ATP"]`,
  cas: 'input[placeholder="e.g. 1927-31-7"]',
  formula: 'input[placeholder="e.g. C10H17N6O13P3"]',
  mw: 'input[type="number"]',
  smiles: 'textarea[placeholder="e.g. C1=CC=C(C=C1)N"]',
}
const NAME = '5-Propargylamino-CTP'
const CAS = '150718-26-6'
const NAME_ONLY = '5-Propargylamino CTP' // 实测 PubChem/ChEMBL/片段三查皆 0 命中
const D2_BODY = { product_name: NAME, cas: CAS }
const D4_BODY = { product_name: 'Biotin-16-ddUTP' } // 分词降级命中母核 ⇒ fallback_used
const D6_BODY = { product_name: NAME, cas: CAS, molecular_weight: 500 } // 与库值 536.22 相差>1Da
const D8_BODY = { product_name: 'adenosine' } // name-only 单候选 ⇒ unverified（稳定 ~6s）

// ── 应用层 token（进程内缓存，避免每例重复登录） ──
let TOKEN = null
async function appToken(request) {
  if (!TOKEN) TOKEN = await getToken(request, ADMIN_USER, ADMIN_PASS)
  return TOKEN
}
/** 生产应用层登录：注入 token + is_staff（对齐 stores/auth.js:11,23 与路由守卫），落到新建页 */
async function loginProd(page, request) {
  const token = await appToken(request)
  await page.addInitScript(([t]) => {
    localStorage.setItem('token', t)
    localStorage.setItem('is_staff', 'true')
  }, [token])
  await gotoNew(page)
}
async function gotoNew(page) {
  await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' })
  await expect(page.locator('h3', { hasText: '1. Basic Information' })).toBeVisible({ timeout: 20000 })
}
async function fillIds(page, { name, cas, formula, mw } = {}) {
  if (name !== undefined) await page.locator(F.name).fill(name)
  if (cas !== undefined) await page.locator(F.cas).fill(cas)
  if (formula !== undefined) await page.locator(F.formula).fill(formula)
  if (mw !== undefined) await page.locator(F.mw).fill(String(mw))
}
const triggerEnrich = (page) => page.locator(`${PANEL} button.file-upload-btn`).click()
/** 用真实生产响应回放 enrich（UI 渲染类断言确定性；数据本身来自生产只读实跑） */
const stubEnrich = (page, envelope) =>
  page.route(ENRICH_RE, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(envelope) }))

async function staffApi(request) {
  return apiContext(await appToken(request))
}
/** 生产实跑 enrich（带 504 容错重试）；返回 { body: envelope|null, status, ms } */
async function enrichLive(api, body, retries = 3) {
  for (let i = 0; i < retries; i++) {
    const t0 = Date.now()
    const r = await api.post('/products/enrich/', { data: body, timeout: 150000 })
    const ms = Date.now() - t0
    if (r.status() === 200) return { body: await r.json(), status: 200, ms }
    if (r.status() === 504) { await new Promise((res) => setTimeout(res, 3000)); continue }
    return { body: null, status: r.status(), ms }
  }
  return { body: null, status: 504, ms: 0 }
}
// 进程内缓存：每个 fixture key 只实跑一次（同一 worker 内 module state 共享）
const CAP = {}
const CAP_DUR = {}
async function cap(request, key, body) {
  if (CAP[key] !== undefined) return CAP[key]
  const api = await staffApi(request)
  const r = await enrichLive(api, body)
  await api.dispose()
  CAP[key] = r.body || null
  CAP_DUR[key] = r.ms
  return CAP[key]
}
/** 读前端 enrich 超时常量（L2 代码现值；规格 §8.3 写 90s，此处现读以暴露偏差） */
function enrichTimeoutMs() {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/api/aiTools.js'), 'utf8')
  const m = src.match(/enrichProduct[\s\S]*?timeout:\s*(\d+)/)
  return m ? Number(m[1]) : null
}

test.describe('Part1 · 新建页组 D「AI AUTO MATCH」生产只读', () => {
  test.describe.configure({ timeout: 180000 })

  test('D1 @readonly @prod-ok 四标识全空：AI AUTO MATCH 面板整块不渲染（v-if，纠偏①）', async ({ page, request }) => {
    await loginProd(page, request)
    await expect(page.locator('h3', { hasText: 'Word Import' })).toBeVisible()
    await expect(page.locator(PANEL), '全空时应无面板').toHaveCount(0)
    await fillIds(page, { name: NAME })
    await expect(page.locator(PANEL), '填了 name 后面板出现').toHaveCount(1)
  })

  test('D2 @readonly @prod-ok cas=150718-26-6：命中 CID 121487800 + 身份已验证（API+UI 同源）', async ({ page, request }) => {
    await loginProd(page, request)
    await fillIds(page, { name: NAME, cas: CAS })
    const [resp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/products/enrich/')),
      triggerEnrich(page),
    ])
    if (resp.status() === 504) test.skip(true, '上游冷启动 504（重试可过）')
    await expectApi(resp, {
      status: 200,
      json: {
        'data.chemical.cid': 121487800,
        'data.chemical.cas_resolved': CAS,
        'data.chemical.properties.molecular_formula': 'C12H19N4O14P3',
        'data.chemical.identity_verified': true,
        'data.jena.matched': true,
        'data.bioz.equivalence': 'exact',
        'data.chemical.mismatches': [],
      },
      label: 'D2',
    })
    await expect(page.locator(`${PANEL} .word-status.word-ok`).filter({ hasText: 'Found: PubChem CID 121487800' })).toBeVisible()
    await expect(page.locator(`${PANEL} .word-status`).filter({ hasText: '身份已验证' })).toBeVisible()
  })

  test('D3 @readonly @prod-ok 仅 name（无 CAS）：found=false + search_hint + 无"已验证"（容忍 504）', async ({ page, request }) => {
    await loginProd(page, request)
    await fillIds(page, { name: NAME_ONLY })
    await triggerEnrich(page)
    const nf = page.locator(`${PANEL} .pubchem-notfound`)
    try {
      await nf.waitFor({ timeout: 130000 })
    } catch {
      test.skip(true, '上游冷启动超时/504（该 name-only 查询实测约 50s）')
    }
    // ⚠️ 用**不区分大小写**的正则：UI 实际文案是 "Not found in PubChem. …"（大写 N），
    //    而 `toContainText` **区分大小写** ⇒ 原写法 `'not found in PubChem'`（小写 n）必挂。
    //    此前该分支一直被 504 跳过（`test.skip`）⇒ 这个大小写 bug 被掩蔽，直到线上真返回"未找到"才暴露。
    await expect(nf).toContainText(/not found in pubchem/i)
    await expect(page.locator(`${PANEL} .word-status`).filter({ hasText: '身份已验证' })).toHaveCount(0)
  })

  test('D4 @readonly @prod-ok Biotin-16-ddUTP 分词降级：fallback_used + 未验证候选（非"已验证"）', async ({ request }) => {
    const c4 = await cap(request, 'd4', D4_BODY)
    if (!c4) test.skip(true, 'CAP_D4 未取到（504/上游超时）')
    expect(getPath(c4, 'data.chemical.found')).toBe(true)
    expect(getPath(c4, 'data.chemical.fallback_used'), '应走分词降级').toBe(true)
    expect(getPath(c4, 'data.chemical.identity_verified'), '降级命中不得标已验证').toBe(false)
    expect(getPath(c4, 'data.chemical.candidates.length')).toBeGreaterThanOrEqual(1)
  })

  test('D5 @readonly @prod-ok CAS 三源冲突：Form≠PubChem/jena → ⚠ CAS sources inconsistent', async ({ page, request }) => {
    const c2 = await cap(request, 'd2', D2_BODY)
    if (!c2) test.skip(true, 'CAP_D2 未取到（504/上游超时）')
    await loginProd(page, request)
    await fillIds(page, { name: NAME, cas: '1927-31-7' }) // 与回放载荷的 cas_resolved/jena CAS 不同
    await stubEnrich(page, c2)
    await triggerEnrich(page)
    await expect(page.locator(`${PANEL} .cas-conflict-title`)).toContainText('CAS sources inconsistent')
  })

  test('D6 @readonly @prod-ok 文档 MW 与 PubChem 不符：降级为候选 + 隐藏 Apply All（护栏）', async ({ page, request }) => {
    const c6 = await cap(request, 'd6', D6_BODY)
    if (!c6) test.skip(true, 'CAP_D6 未取到（504/上游超时）')
    await loginProd(page, request)
    await fillIds(page, { name: NAME, cas: CAS, mw: 500 })
    await stubEnrich(page, c6)
    await triggerEnrich(page)
    await expect(page.locator(`${PANEL} .candidate-item .field-error`)).toContainText('与文档 Formula/MW 不一致')
    await expect(page.locator(APPLY_ALL).filter({ hasText: 'Apply All to Form' }), '候选态不应有 Apply All').toHaveCount(0)
  })

  test('D7 @readonly @prod-ok 多候选（candidates>1）渲染且不自动套用', async () => {
    test.skip(true, '生产未复现 >1 候选（本会话 4 次只读探针 0/1 候选）；构造需猜数据。候选渲染机制由 D8 真实响应覆盖。')
  })

  test('D8 @readonly @prod-ok 未验证（name-only 单候选）：⚠ 自动匹配未经验证 + 隐藏 Apply All', async ({ page, request }) => {
    const c8 = await cap(request, 'd8', D8_BODY)
    if (!c8) test.skip(true, 'CAP_D8 未取到（504/上游超时）')
    await loginProd(page, request)
    await fillIds(page, { name: 'adenosine' })
    await stubEnrich(page, c8)
    await triggerEnrich(page)
    await expect(page.locator(`${PANEL} .form-hint`).filter({ hasText: '自动匹配未经验证' })).toBeVisible()
    await expect(page.locator(APPLY_ALL).filter({ hasText: 'Apply All to Form' }), '未验证态不应有 Apply All').toHaveCount(0)
  })

  test('D9 @readonly @prod-ok Apply All 只填空字段：既有 Formula 不被覆盖', async ({ page, request }) => {
    const c2 = await cap(request, 'd2', D2_BODY)
    if (!c2) test.skip(true, 'CAP_D2 未取到（504/上游超时）')
    await loginProd(page, request)
    await fillIds(page, { name: NAME, cas: CAS, formula: 'ZZZ-SENTINEL' })
    await stubEnrich(page, c2)
    await triggerEnrich(page)
    await page.locator(APPLY_ALL).filter({ hasText: 'Apply All to Form' }).click()
    await expect(page.locator(F.formula), '既有值不得被覆盖').toHaveValue('ZZZ-SENTINEL')
    await expect(page.locator(F.smiles), '空字段应被填入').not.toHaveValue('')
  })

  test('D10 @readonly @prod-ok enrich 前端超时=120s（非规格§8.3 的 90s），实跑耗时 < 超时', async ({ request }) => {
    const t = enrichTimeoutMs()
    expect(t, 'aiTools.js#enrichProduct timeout').toBe(120000)
    const c2 = await cap(request, 'd2', D2_BODY)
    if (!c2) test.skip(true, 'CAP_D2 未取到（504/上游超时）')
    expect(CAP_DUR.d2).toBeGreaterThan(0)
    expect(CAP_DUR.d2).toBeLessThan(t)
  })

  test('D11 @readonly @prod-ok enrich 进行中：触发按钮 disabled + 文案 Searching', async ({ page, request }) => {
    await loginProd(page, request)
    await fillIds(page, { name: NAME })
    await page.route(ENRICH_RE, () => {}) // 挂起请求，稳定捕获"进行中"态
    const btn = page.locator(`${PANEL} button.file-upload-btn`)
    await btn.click()
    await expect(btn).toBeDisabled()
    await expect(btn).toContainText('Searching')
  })

  test('D12 @readonly @prod-ok jena 规格匹配：Apply from jena + Scope=fill empty fields only', async ({ page, request }) => {
    const c2 = await cap(request, 'd2', D2_BODY)
    if (!c2) test.skip(true, 'CAP_D2 未取到（504/上游超时）')
    await loginProd(page, request)
    await fillIds(page, { name: NAME, cas: CAS })
    await stubEnrich(page, c2)
    await triggerEnrich(page)
    await expect(page.locator(`${PANEL} .ms-section .ms-title`)).toContainText('Supplier Spec Match')
    await expect(page.locator(`${PANEL} .ms-apply-btn`)).toContainText('Apply from jena')
    await expect(page.locator(`${PANEL} .ms-section .form-hint`).filter({ hasText: 'fill empty fields only' })).toBeVisible()
  })

  test('D13 @readonly @prod-ok Knowledge Chain Matches：Methods 分组 + ✓/✕ 链接开关', async ({ page, request }) => {
    const c2 = await cap(request, 'd2', D2_BODY)
    if (!c2) test.skip(true, 'CAP_D2 未取到（504/上游超时）')
    await loginProd(page, request)
    await fillIds(page, { name: NAME, cas: CAS })
    await stubEnrich(page, c2)
    await triggerEnrich(page)
    await expect(page.locator(`${PANEL} .knowledge-match-group .km-section-title`).first()).toContainText('Methods')
    await expect(page.locator(`${PANEL} .km-link-btn`).first()).toBeVisible()
  })

  test('D16 @readonly @prod-ok 未 Import 协议就 enrich：product/协议/方法血缘 + audit_log 计数 Δ0', async ({ request }) => {
    const before = prodCounts()
    const api = await staffApi(request)
    const r = await enrichLive(api, D2_BODY)
    await api.dispose()
    if (r.status !== 200) test.skip(true, `enrich 未 200（status=${r.status}），Δ0 判据不足`)
    expectDelta(before, prodCounts(), zeroSpec(before), 'D16 enrich 未 Import')
  })

  // ── D14c：★ **B5 闸门** —— 新建态"采纳文献"不得打到 `/products/null/` ────────
  //   组件 `BiozEvidenceSection` 本就设计为 `canAdopt=false` 时**禁用 Adopt 并给 tooltip**
  //   （`:title="!canAdopt ? 'Save the product before adopting' : ''"`），
  //   但父组件曾**硬编码 `:can-adopt="true"`** ⇒ 新建态按钮可点
  //   ⇒ 必打 `/products/null/adopt-bioz-refs/` ⇒ **404**（B5）。已修为 `:can-adopt="!!productId"`。
  //   本闸门只做**只读**观测：全程不得出现 `/products/null/` 请求；Bioz 段若渲染，其 Adopt 必须 disabled。
  test('D14c @readonly @prod-ok 新建态：不得发出 /products/null/ 请求；Bioz 若渲染则 Adopt 必须 disabled（B5）', async ({ page, request }) => {
    const nullHits = []
    page.on('request', (r) => { if (r.url().includes('/products/null/')) nullHits.push(r.url()) })
    await loginProd(page, request)
    await fillIds(page, { name: NAME, cas: CAS })
    const btn = page.locator(`${PANEL} button.file-upload-btn`)
    if (await btn.count()) { await btn.click().catch(() => {}); await page.waitForTimeout(9000) }
    if (await page.locator('.bioz-section').count()) {
      const adoptBtns = page.locator('.bioz-adopt-one, .bioz-adopt-all')
      for (let i = 0; i < (await adoptBtns.count()); i++) {
        await expect(adoptBtns.nth(i), '新建态 Adopt 必须 disabled（canAdopt=false）').toBeDisabled()
      }
    }
    expect(nullHits, `新建态不得请求 /products/null/，实际：${JSON.stringify(nullHits)}`).toEqual([])
  })
})

/**
 * ── 发现（纠偏 / 纠错 / 记录）──────────────────────────────────────────────
 * 1) 纠偏①（D1）：规格称"全空时按钮 disabled"——实际 `:1419` 面板 `v-if="form.name||cas||smiles||inchi"`
 *    为假 ⇒ **整块不渲染**，`:1426` 的 disabled 空值分支不可达。断言已改为"面板不出现"。
 * 2) 纠偏②（D14/D15）：规格把 Bioz 与 Literature 混谈。Bioz 段用 `Adopt`（写库、新建态 404）；
 *    `📥 Import` 属**独立 Literature 块**(`:1608`)；两者皆写库 ⇒ 不入 R2 只读。已整条排除。
 * 3) 纠偏③（D6 触发条件）：规格举例"MW 536.22 vs docx 536.01 触发 doc_value_mismatch"**不成立**——
 *    `pubchem_enhancer.py:358` 容差 **1.0 Da**，0.21 差不会触发。实测须使 |ΔMW|>1（本剧本用 mw=500）才降级。
 *    另：规格把 `⚠ Cross-field Mismatches`(:1527, 来自 `mismatches[]`，由 `ProductValidator` 算 cas/smiles 一致性)
 *    与 `⚠ 与文档 Formula/MW 不一致`(:1663, 来自 `formula_mismatch/mw_mismatch`) **混为一谈**——二者机制不同。
 * 4) 纠错（D3/D10）：name-only 冷缓存查询实测 **50.7s**（曾 504），非"必 200 秒回"；断言已容忍 504/超时并 skip。
 * 5) 记录（D10）：前端 enrich 超时 `aiTools.js:59` = **120000ms**，规格 §8.3 写 **90s** ⇒ 文档旧值（L1≠L2，交用户定改哪侧）。
 * 6) 记录（D2 徽标）：`✓ Found: PubChem CID …` 与 `✓ 身份已验证 (verified)` 同屏出现，符合 `:1440/:1443` 条件；
 *    生产 `molecular_weight=536.22`（与 B1 docx 基准 536.01 不符但未超 1Da ⇒ 不触发 mismatch），已核实。
 * 7) 记录（D-DB）：新增 `helpers/prod-db.cjs`（ssh 容器内只读 SELECT；非 localhost 护栏）。实测可用，单次 ~4.9s。
 *    生产 enrich 前后计数（product=125 / audit_log=102 / protocol=14128 / method=47935 / product_protocol=23431 …）**Δ0**。
 */
