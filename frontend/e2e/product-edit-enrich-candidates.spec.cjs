/**
 * ★ F2 + F1 e2e 闸门（2026-09-24）：「AI 候选列表」的**条数**与「关联」动作。
 *
 * 覆盖（对应审定清单里的硬伤与验收线）：
 *   A. 新建页：默认渲染 5 条 → 点「显示全部 (N)」→ 渲染 N 条（N=50，F2 后端上限）
 *   A2. 「＋ 关联」只对**库内已有实体**（整数 id）出现；语料候选（非整数 id）**没有**该按钮
 *   A3. **硬伤 1 闸门**：无方法链时「＋ 关联」**必须 disabled**（否则 `_sync_protocol_bridges`
 *       在 `if not method_ids: return` 处直接返回 ⇒ 关联是 no-op，用户"点了→保存→没生效"）
 *   B. 编辑页（夹具已挂 method 54）：「＋ 关联」→「✕ 取消关联」→ 保存 ⇒
 *       该协议**从不在桥 → 在桥**（硬伤 3 的正确验收线；不能断言"桥 Δ>0"）
 *
 * 确定性：`POST /products/enrich/` 用 `page.route` **回放自造响应**（照既有
 * `product-new-ai-automatch.spec.cjs:105-108` 的做法），**不依赖 PubChem 等外网**。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth.cjs')
const { getToken, apiContext } = require('./helpers/api.cjs')
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')

const J = JSON.stringify
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))
const ENRICH_RE = /\/products\/enrich\//

const SEL = {
  name: `input[placeholder="e.g. 2'-Amino-ATP"]`,
  catalog: `input[placeholder="e.g. SC8043"]`,
  save: '.form-actions button',
  enrichBtn: '.pubchem-enrich-section button.file-upload-btn',
}

const created = []

test.describe('F2+F1 · 候选列表条数与关联动作', () => {
  test.describe.configure({ timeout: 120000 })

  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    const byPrefix = await cleanupByPrefix(api, { label: 'f2f1' })
    const deleted = []
    for (const id of created) deleted.push([id, (await api.post(`/products/${id}/hard-delete/`)).status()])
    const residual = dbQuery(
      `import json\nfrom apps.commerce.models import Product\n` +
      `from apps.bridges.models import ProductProtocol, ProductMethod\n` +
      `ids=${J(created)}\n` +
      `print('__SNAP__' + json.dumps({` +
      `'product': list(Product.objects.filter(id__in=ids).values_list('id', flat=True)),` +
      `'pp': ProductProtocol.objects.filter(product_id__in=ids).count(),` +
      `'pm': ProductMethod.objects.filter(product_id__in=ids).count()}))`)
    console.log(`__E2E__ F2F1_CLEANUP byPrefix=${J(byPrefix)} deleted=${J(deleted)} residual=${J(residual)}`)
    expect(residual.product, 'product 残留应为空').toEqual([])
    expect(residual.pp, 'product_protocol 残留应为 0').toBe(0)
    expect(residual.pm, 'product_method 残留应为 0').toBe(0)
    await ctx.dispose(); await api.dispose()
  })

  /** 造 50 条候选：前 49 条为**真实整数 protocol id**（可关联），最后 1 条为非整数（语料候选，不可关联）。 */
  function buildCandidates(realIds) {
    const rows = realIds.map((id, i) => ({
      id, source: 'auto_links', title: `E2E candidate ${i}`, abstract: 'x', url: '',
      score: 0.9 - i * 0.01, score_a: 0.9, score_b: 0, score_c: 0, relevance_score: 0.9,
      tier: 'document', link_source: 'auto', relevance_basis: 'vendor_only',
      literature_count: 0, method_hint: '', matched_query: '', steps: [],
    }))
    rows.push({
      id: 'corpus-string-id', source: 'Bio-protocol', title: 'E2E corpus candidate',
      abstract: 'y', url: '', score: 0.5, method_hint: '', matched_query: '', steps: [],
    })
    return rows
  }

  function envelope(rows) {
    return {
      success: true,
      data: {
        chemical: { found: false, properties: {}, source: '', candidates: [] },
        literature: {
          applications: [], methods: [], references: [], protocols: [],
          matched_apps: [], matched_methods: [],
          unmatched_app_keywords: [], unmatched_method_keywords: [],
        },
        protocols: rows,
        jena: {}, bioz: {},
      },
    }
  }

  async function stubEnrich(page, rows) {
    await page.route(ENRICH_RE, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: J(envelope(rows)) }))
  }

  test('A @write @local-only 新建页：候选默认 5 条 + 显示全部 50 条 + 无方法时「关联」disabled', async ({ page, request: req }) => {
    const api = await staffApi(req)
    // 取 49 个真实 protocol id（不必特殊挑选：新建页无方法链，关联按钮一律 disabled）
    const realIds = dbQuery(
      `import json\nfrom apps.knowledge.models import Protocol\n` +
      `print('__SNAP__' + json.dumps(list(Protocol.objects.order_by('id').values_list('id', flat=True)[:49])))`)
    expect(realIds.length, '需至少 49 个协议做夹具').toBeGreaterThanOrEqual(49)
    await stubEnrich(page, buildCandidates(realIds))

    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')
    await page.locator(SEL.name).fill('fluorescent labeled nucleotide E2E candidate probe')
    await page.locator(SEL.catalog).first().fill(catalogNo('F2F1'))

    await page.locator(SEL.enrichBtn).click()
    const cards = page.locator('.protocol-card')
    await expect(cards.first(), '候选卡片应渲染').toBeVisible({ timeout: 30000 })
    const previewN = await cards.count()
    console.log(`__E2E__ A 默认渲染条数 = ${previewN}`)
    expect(previewN, '默认只渲染预览条数 5').toBe(5)

    // 硬伤 1 闸门：无方法链 ⇒ 关联按钮存在但 disabled
    const linkBtn = cards.first().locator('.km-link-btn')
    await expect(linkBtn, '整数 id 候选应有「关联」按钮').toHaveCount(1)
    await expect(linkBtn, '无方法链时「关联」必须 disabled（否则保存后不生效）').toBeDisabled()

    // 语料候选（非整数 id）不得出现关联按钮（它没有 DB id 可关联）
    //   ⚠️ 必须在「展开」之后再断言：默认只渲染前 5 条，第 50 条（语料候选）**根本不在 DOM 里**
    //      —— 我第一次写成"展开前断言 last()"，结果 last() 其实是第 5 个真实候选（有按钮），
    //      是**测试逻辑错、不是代码错**。

    // 「显示全部 (50)」⇒ 渲染 50 条
    const expand = page.getByRole('button', { name: /显示全部 \(50\)/ })
    await expect(expand, '候选 50 条时应出现「显示全部 (50)」').toBeVisible()
    await expand.click()
    await expect.poll(async () => cards.count(), { timeout: 15000 }).toBe(50)
    console.log(`__E2E__ A 展开后条数 = ${await cards.count()}`)

    await expect(cards.last().locator('.km-link-btn'), '语料候选（非整数 id）不应有关联按钮').toHaveCount(0)
    await api.dispose()
  })

  test('B @write @local-only 编辑页（有方法链）：关联→取消关联→保存 ⇒ 该协议从不在桥变在桥', async ({ page, request: req }) => {
    const api = await staffApi(req)
    const resp = await api.post('/products/', {
      data: { name: 'E2E f2f1 bridge probe', catalog_no: catalogNo('F2F1B'), slug: slug('F2F1B'), method_ids: [54] },
    })
    expect(resp.status(), '夹具创建应 2xx').toBeLessThan(300)
    const id = (await resp.json()).data.id
    created.push(id)

    // 挑一个**不在 method 54 桥**里的协议 ⇒ "从不在桥 → 在桥" 才有意义（硬伤 3 的正确写法）
    const pick = dbQuery(
      `import json\nfrom apps.bridges.models import MethodProtocol\n` +
      `from apps.knowledge.models import Protocol\n` +
      `bridge=set(MethodProtocol.objects.filter(method_id=54).values_list('protocol_id', flat=True))\n` +
      `pid=[p for p in Protocol.objects.order_by('id').values_list('id', flat=True) if p not in bridge][0]\n` +
      `print('__SNAP__' + json.dumps({'pid': pid, 'bridge_size': len(bridge)}))`)
    const P = pick.pid
    const before = dbQuery(
      `import json\nfrom apps.bridges.models import MethodProtocol\n` +
      `print('__SNAP__' + json.dumps({'in_bridge': MethodProtocol.objects.filter(method_id=54, protocol_id=${P}).exists()}))`)
    expect(before.in_bridge, `协议 ${P} 初始必须不在 method 54 桥上`).toBe(false)
    console.log(`__E2E__ B 选中协议 ${P}（method54 桥 ${pick.bridge_size} 条，该协议不在其中）`)

    await stubEnrich(page, [{
      id: P, source: 'auto_links', title: `E2E link candidate ${P}`, abstract: 'z', url: '',
      score: 0.9, score_a: 0.9, score_b: 0, score_c: 0, relevance_score: 0.9,
      tier: 'document', link_source: 'auto', relevance_basis: 'vendor_only',
      literature_count: 0, method_hint: '', matched_query: '', steps: [],
    }])

    await loginAsStaff(page)
    await goto(page, `/workspace/products/${id}/edit`)
    await expect(page.locator('.edit-form'), '编辑页应载入').toBeVisible({ timeout: 30000 })
    await page.locator(SEL.enrichBtn).click()
    const card = page.locator('.protocol-card').first()
    await expect(card, '候选卡片应渲染').toBeVisible({ timeout: 30000 })

    // 有方法链 ⇒ 关联按钮可用；点一下 ⇒ 变「取消关联」
    const linkBtn = card.locator('.km-link-btn')
    await expect(linkBtn, '有方法链时「关联」应可用').toBeEnabled()
    await expect(linkBtn).toHaveText(/＋\s*关联/)
    await linkBtn.click()
    await expect(linkBtn, '点后应变为「取消关联」').toHaveText(/取消关联/)
    console.log('__E2E__ B 关联按钮状态切换 ✓')

    // 再点一次 ⇒ 复原（证明是 toggle，不是单向）
    await linkBtn.click()
    await expect(linkBtn, '再点应复原为「关联」').toHaveText(/＋\s*关联/)
    await linkBtn.click()
    await expect(linkBtn).toHaveText(/取消关联/)

    // 保存（PUT）⇒ 桥应新增该协议
    const saveResp = await page.locator(SEL.save, { hasText: /Save Draft|Saving/ }).click()
      .then(() => page.waitForResponse((r) => r.url().includes(`/products/${id}/`) && r.request().method() === 'PUT', { timeout: 60000 }))
    expect(saveResp.status(), '保存应 200').toBe(200)

    const after = dbQuery(
      `import json\nfrom apps.bridges.models import MethodProtocol\n` +
      `print('__SNAP__' + json.dumps({'in_bridge': MethodProtocol.objects.filter(method_id=54, protocol_id=${P}).exists()}))`)
    console.log(`__E2E__ B 保存后 in_bridge = ${after.in_bridge}`)
    expect(after.in_bridge, `保存后协议 ${P} 应已在 method 54 桥上（从不在桥 → 在桥）`).toBe(true)

    await api.dispose()
  })
})
