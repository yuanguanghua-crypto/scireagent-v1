/**
 * P0 回归 · 「保存无关字段不得删除知识链接」
 * ---------------------------------------------------------------------------
 * 守护的不变量（见 backend/apps/commerce/api/v1/serializers.py:492-533
 * `_refresh_inherited_bridges(product, *, chain_specified=True)`）：
 *   仅当**本次请求显式给出了方法链**（method_ids / research_goal_ids / application_ids
 *   任一非 None）才允许按当前链收敛、删除 INHERITED 行；省略则**一律不删**。
 * 配套前端（frontend/src/views/workspace/ProductEditPage.vue:105-110 / 1298-1309）：
 *   只在用户**真正改动**方法链时才回传 method_ids（methodIdsBaseline + sameIdSet 门控）。
 * ⇒ 在工作台改一个无关字段后保存，**绝不应删除该产品的任何 INHERITED 行**。
 *
 * 原位缺陷：`_refresh_inherited_bridges` 原先**无条件**执行删除，且编辑页无条件回传
 * method_ids（空链时为 []）⇒「顺手保存」即静默、不可逆清空知识链接。本 spec 用例 1 在
 * 修复前会红（被删成 0），修复后应为绿。
 *
 * 判据层级（e2e/README.md §6）：L0 铁律 > L1 规格 > L2 代码现值；L3 不变量恒成立。
 * 期望值全部**现算**（禁止硬编码），D-DB 数字由 dbQuery 只读取回。
 *
 * 本机跑法（**必须**，见 e2e/README.md §1；输出重定向到文件，勿管道给 tail；共用 dev 库须加锁串行）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do echo "lock busy, wait..."; sleep 30; done
 *   echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test e2e/product-save-keeps-links.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p0 > ../../_p0.log 2>&1
 *   rm -f ../../_pw.lock
 *
 * 前置：本地 dev 已起（Django :8000 DB_ENGINE=sqlite / Vite :5173，且 Vite 从 **E: 物理路径** 启动）。
 * 纪律：只新增本文件；不改应用代码、不 git commit；写操作只碰 `E2E-` 前缀夹具（产品）；
 *      afterAll 按捕获的 id 硬删产品，并只读核验四表残留为 0。
 *
 * 已实测（2026-09-24，lead）：
 *   method 54 存在，派生 753 条 MethodProtocol ⇒ `POST /products/ {method_ids:[54]}` 建夹具后
 *   该产品 ProductMethod=1、ProductProtocol=753（link_source 全部 'inherited'，**值是小写**）。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')

const J = JSON.stringify
// 与现成 spec 一致的 console 白名单（wasm / 资源加载噪声，非本页逻辑错误）
const WL2 = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation', 'Failed to load resource']
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

// ── D-DB 只读现算（禁止硬编码期望值）─────────────────────────────────
/** 该产品四表关键计数：pp=ProductProtocol 总数、ppI=其中 INHERITED、pm=ProductMethod */
const ppOf = (pid) => dbQuery(
  `import json\nfrom apps.bridges.models import ProductProtocol, ProductMethod\n` +
  `pid=${pid}\n` +
  `print('__SNAP__' + json.dumps({` +
  `'pp': ProductProtocol.objects.filter(product_id=pid).count(),` +
  `'ppI': ProductProtocol.objects.filter(product_id=pid, link_source='inherited').count(),` +
  `'pm': ProductMethod.objects.filter(product_id=pid).count()}))`)

// 忠实 DOM（frontend/src/views/workspace/ProductEditPage.vue，非猜测）：
//   Overview 文本域 :1889-1890（el-input type=textarea ⇒ <textarea placeholder="Describe the product…">）
//   Save Draft 按钮 :2070-2072（.form-actions button）
//   成功提示 toast  :1419-1420（.toast.toast-success，文案 "Draft saved"，4s 自动消失）
//   Methods chips   :1831-1838（.chip-group > .chip-label("Methods:") + .chip + .chip-remove）
const overviewBox = (page) => page.getByPlaceholder(/Describe the product/)
const saveBtn = (page) => page.locator('.form-actions button', { hasText: /Save Draft|Saving/ })
const methodsChips = (page) => page.locator('.chip-group')
  .filter({ has: page.locator('.chip-label', { hasText: 'Methods:' }) })

/** 建 E2E- 夹具产品（默认带 method_ids:[54]，派生大量 INHERITED 行） */
async function fixtureProduct(api, pfx, extra = {}) {
  const cat = catalogNo(pfx)
  const resp = await api.post('/products/', {
    data: { name: `E2E ${pfx}`, catalog_no: cat, slug: slug(pfx), method_ids: [54], ...extra },
  })
  await expectApi(resp, { status: 201, label: `夹具 ${pfx}` })
  return { id: (await resp.json()).data.id, catalog_no: cat }
}

/** 点 Save Draft，等待编辑态 PUT 响应 + 成功 toast；返回 { resp, toastText }
 *  ⚠ 必须在调用**同步**的 dbQuery 之前先 await 到 toast —— dbQuery 走 runSync（阻塞 Node
 *   事件循环），若此时还有挂起的 waitForSelector，则它无法轮询，测试结束时报 "Test ended"。 */
async function saveDraft(page, pid) {
  const btn = saveBtn(page)
  await btn.scrollIntoViewIfNeeded()
  const respP = page.waitForResponse(
    (r) => r.request().method() === 'PUT' && r.url().includes(`/api/v1/products/${pid}/`),
    { timeout: 60_000 })
  // toast 由 service 端 setFeedback 在响应后触发、4s 自动消失 ⇒ 点击前先挂 waitForSelector 兜住
  const toastP = page.waitForSelector('.toast-success', { timeout: 30_000 })
  await btn.click()
  const resp = await respP
  await toastP
  const toastText = (await page.locator('.toast-success').textContent()) || ''
  return { resp, toastText }
}

test.describe('P0 · 产品编辑保存不丢失知识链接（_refresh_inherited_bridges 契约）', () => {
  test.describe.configure({ timeout: 120_000 })

  const createdIds = []

  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    // 兜底：按 E2E- 前缀清理（幂等；只碰本项目夹具）
    const byPrefix = await cleanupByPrefix(api, { label: 'P0-keep-links' })
    // 主清理：按捕获 id 硬删
    const deleted = []
    for (const id of createdIds) {
      try {
        const r = await api.post(`/products/${id}/hard-delete/`)
        deleted.push([id, r.status()])
      } catch (e) {
        deleted.push([id, `sent/err ${String(e.message).split('\n')[0].slice(0, 80)}`])
      }
    }
    // 只读核验残留（四表按 id 查；期望全 0）
    const residual = dbQuery(
      `import json\nfrom apps.commerce.models import Product, SKU\n` +
      `from apps.bridges.models import ProductProtocol, ProductMethod\n` +
      `ids=${J(createdIds)}\n` +
      `print('__SNAP__' + json.dumps({` +
      `'product': list(Product.objects.filter(id__in=ids).values_list('id', flat=True)),` +
      `'sku': SKU.objects.filter(product_id__in=ids).count(),` +
      `'pp': ProductProtocol.objects.filter(product_id__in=ids).count(),` +
      `'pm': ProductMethod.objects.filter(product_id__in=ids).count()}))`)
    console.log(`__E2E__ CLEANUP byPrefix=${J(byPrefix)} deleted=${J(deleted)} residual=${J(residual)}`)
    await ctx.dispose(); await api.dispose()

    // 硬断言：清理后四表不得有残留（供货号前缀无关；只看本 spec 自建 id）
    expect(residual.product, 'afterAll 后 product 残留应为空').toEqual([])
    expect(residual.sku, 'afterAll 后 sku 残留应为 0').toBe(0)
    expect(residual.pp, 'afterAll 后 product_protocol 残留应为 0').toBe(0)
    expect(residual.pm, 'afterAll 后 product_method 残留应为 0').toBe(0)
  })

  // ── 用例 1（核心）：改无关字段保存 ⇒ 知识链接一行不少 ──────────────────────
  test('KEEP-1 @write @local-only 改无关字段保存 ⇒ INHERITED 知识链接一行不少', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'KEEP1')
    createdIds.push(f.id)

    // D-DB 基线（现算 N / M）
    const before = ppOf(f.id)
    console.log(`__E2E__ KEEP1 fixture id=${f.id} before=${J(before)}`)
    expect(before.pp, 'KEEP1 夹具应派生 >0 条 ProductProtocol').toBeGreaterThan(0)
    expect(before.pm, 'KEEP1 夹具应有 1 条 ProductMethod').toBe(1)
    const N = before.pp
    const M = before.pm

    // 真实浏览器打开编辑页；Methods chip 出现 = 产品已载入（链已带上）
    await loginAsStaff(page)
    await goto(page, `/workspace/products/${f.id}/edit`)
    await expect(methodsChips(page).locator('.chip'), 'KEEP1 编辑页应载入 1 个 method chip').toHaveCount(1)

    // 只改一个与知识链无关的字段（Overview 文本域），不触碰 Methods/Protocols chip
    await overviewBox(page).fill(`P0 回归：仅改无关字段 ${Date.now()}`)

    // 保存（省略 method_ids 由前端门控保证；此处只断言保存成功）
    const { resp, toastText } = await saveDraft(page, f.id)
    expect(resp.status(), 'KEEP1 Save Draft PUT 应 200').toBe(200)
    expect(toastText, 'KEEP1 应出现保存成功提示').toContain('Draft saved')

    // D-DB 复核：ProductProtocol 一行不少（== N），ProductMethod 未变（== M）
    const after = ppOf(f.id)
    console.log(`__E2E__ KEEP1 after=${J(after)} expect_pp=${N} expect_pm=${M}`)
    expect(after.pp, `KEEP1 保存后 ProductProtocol 应仍为 ${N}（不多不少），实际 ${after.pp}`).toBe(N)
    expect(after.pm, `KEEP1 保存后 ProductMethod 应仍为 ${M}，实际 ${after.pm}`).toBe(M)

    await api.dispose(); expect(errors).toEqual([])
  })

  // ── 用例 2（契约保留，防倒退）：显式改方法链保存 ⇒ 契约仍生效 ────────────────
  test('KEEP-2 @write @local-only 显式改方法链（删空 Methods chip）保存 ⇒ INHERITED 行被清空', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const f = await fixtureProduct(api, 'KEEP2')
    createdIds.push(f.id)

    const before = ppOf(f.id)
    console.log(`__E2E__ KEEP2 fixture id=${f.id} before=${J(before)}`)
    expect(before.ppI, 'KEEP2 夹具应有 >0 条 INHERITED ProductProtocol').toBeGreaterThan(0)

    await loginAsStaff(page)
    await goto(page, `/workspace/products/${f.id}/edit`)
    const g = methodsChips(page)
    await expect(g.locator('.chip'), 'KEEP2 编辑页应载入 1 个 method chip').toHaveCount(1)

    // 显式把方法链改成空：点 ✕（.chip-remove）移除唯一 chip ⇒ 前端回传 method_ids:[]
    await g.locator('.chip-remove').click()
    await expect(g.locator('.chip'), 'KEEP2 点 ✕ 后 chip 应消失').toHaveCount(0)

    const { resp, toastText } = await saveDraft(page, f.id)
    expect(resp.status(), 'KEEP2 Save Draft PUT 应 200').toBe(200)
    expect(toastText, 'KEEP2 应出现保存成功提示').toContain('Draft saved')

    // 既有契约（apps/commerce/tests/test_protocol_links_consistency.py 单测守护）：
    // 显式给出（空）方法链 ⇒ INHERITED 行应被删除至 0
    const after = ppOf(f.id)
    console.log(`__E2E__ KEEP2 after=${J(after)} expect_ppI=0 expect_pm=0`)
    expect(after.ppI, `KEEP2 显式空链保存后 INHERITED 行应为 0，实际 ${after.ppI}`).toBe(0)
    expect(after.pm, `KEEP2 显式空链保存后 ProductMethod 应为 0，实际 ${after.pm}`).toBe(0)

    await api.dispose(); expect(errors).toEqual([])
  })
})
