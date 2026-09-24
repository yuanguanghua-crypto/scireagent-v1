/**
 * ★ P1-a′（乙）UI 闸门（2026-09-24）：桥回退候选的**打分 · 排序 · "候选·未落库"标注**。
 *
 * 锁定的行为（均为刻意设计，见 backend `apps/bridges/tests/test_bridge_pending_candidates.py`）：
 *   产品 `ProductProtocol` 表 = 0 行 ⇒ 第 5 节走 **MethodProtocol 桥回退**；
 *   编辑页（`ProductDetailSerializer`，`compute_pending=True`）会对**桥可达的那批**逐条算轴A：
 *     · `S_A > 0`（品名/usage 命中 185-term 词表）⇒ 升为 `tier='document'`、带真实分 ⇒ 进入**强相关区**并可按分排序
 *     · 该行**未落库** ⇒ 必须显示"候选 · 未落库"徽标（否则与已物化的 document 行无法区分）
 *   `S_A == 0` 的行保持 `weak`（沉底到「弱相关」折叠区）。
 *
 * ⚠️ 与 P0 的分工：P0 修的是"strong=0 时只写 None"的**文案**；本用例锁的是"有分之后**真的进强相关区**"。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth.cjs')
const { getToken, apiContext } = require('./helpers/api.cjs')
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')

const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const chipGroup = (page, label) =>
  page.locator('.chip-group').filter({ has: page.locator('.chip-label', { hasText: label }) })

const created = []

test.describe('P1-a′ · 桥回退候选的打分与未落库标注', () => {
  test.describe.configure({ timeout: 120000 })

  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    const byPrefix = await cleanupByPrefix(api, { label: 'p1a-pending' })
    const deleted = []
    for (const id of created) deleted.push([id, (await api.post(`/products/${id}/hard-delete/`)).status()])
    const residual = dbQuery(
      `import json\nfrom apps.commerce.models import Product\n` +
      `from apps.bridges.models import ProductProtocol, ProductMethod\n` +
      `ids=${JSON.stringify(created)}\n` +
      `print('__SNAP__' + json.dumps({` +
      `'product': list(Product.objects.filter(id__in=ids).values_list('id', flat=True)),` +
      `'pp': ProductProtocol.objects.filter(product_id__in=ids).count(),` +
      `'pm': ProductMethod.objects.filter(product_id__in=ids).count()}))`)
    console.log(`__E2E__ P1A_CLEANUP byPrefix=${JSON.stringify(byPrefix)} deleted=${JSON.stringify(deleted)} residual=${JSON.stringify(residual)}`)
    expect(residual.product, 'product 残留应为空').toEqual([])
    expect(residual.pp, 'product_protocol 残留应为 0（P1-a′ 只读，不应新增行）').toBe(0)
    expect(residual.pm, 'product_method 残留应为 0').toBe(0)
    await ctx.dispose(); await api.dispose()
  })

  test('P1A @write @local-only 桥回退候选：品名命中词表 ⇒ 有分进强相关区 + 标"候选·未落库"',
    async ({ page, request }) => {
      const api = await staffApi(request)
      // 品名含词表 term（fluorescent / labeled / nucleotide）⇒ P 非空 ⇒ 部分桥协议 S_A>0
      const resp = await api.post('/products/', {
        data: {
          name: `fluorescent labeled nucleotide E2E ${Date.now()}`,
          catalog_no: catalogNo('P1A'), slug: slug('P1A'), method_ids: [54],
        },
      })
      expect(resp.status(), '夹具创建应 2xx').toBeLessThan(300)
      const id = (await resp.json()).data.id
      created.push(id)

      // ── A-API：编辑页口径（GET /products/{id}/）应有 document + pending ──
      const detail = await (await api.get(`/products/${id}/`)).json()
      const links = (detail?.data || detail)?.protocol_links || []
      const pending = links.filter((x) => x && x.pending === true)
      const docs = links.filter((x) => x && x.tier === 'document')
      console.log(`__E2E__ P1A API: protocol_links=${links.length} document=${docs.length} pending=${pending.length}`)
      expect(links.length, '桥回退应返回候选（753 量级）').toBeGreaterThan(0)
      expect(docs.length, '品名命中词表 ⇒ 应有行升为 document').toBeGreaterThan(0)
      expect(pending.length, '升级行必须带 pending=true').toBe(docs.length)
      // 分数必须真实非 0（可排序）
      expect(Math.max(...docs.map((x) => Number(x.relevance_score) || 0)), 'document 行应有非 0 分').toBeGreaterThan(0)

      // ── 只读性：P1-a′ 不得写 ProductProtocol ──
      const ppAfter = dbQuery(
        `import json\nfrom apps.bridges.models import ProductProtocol\n` +
        `print('__SNAP__' + json.dumps({'pp': ProductProtocol.objects.filter(product_id=${id}).count()}))`)
      expect(ppAfter.pp, 'P1-a′ 只展示、不落库').toBe(0)

      // ── U-UI：强相关区渲染 + 徽标可见 + 不再显示 None ──
      await loginAsStaff(page)
      await goto(page, `/workspace/products/${id}/edit`)
      const protocols = chipGroup(page, 'Protocols:')
      await expect(protocols.locator('.chip-protocol').first(), '强相关芯片应渲染').toBeVisible({ timeout: 30000 })

      const strongChips = protocols.locator('.chip-protocol:not(.chip-weak)')
      const strongCount = await strongChips.count()
      const pendingBadges = protocols.locator('.badge-pending')
      const badgeCount = await pendingBadges.count()
      const noneCount = await protocols.locator('.chip-none').count()
      console.log(`__E2E__ P1A DOM: strongChips=${strongCount} badge-pending=${badgeCount} chip-none=${noneCount}`)

      expect(strongCount, 'strong>0 ⇒ 强相关区应有芯片（最多 TopN=10）').toBeGreaterThan(0)
      expect(noneCount, 'strong>0 ⇒ 不应再渲染 None').toBe(0)
      expect(badgeCount, '"候选 · 未落库" 徽标应可见').toBeGreaterThan(0)
      expect(await pendingBadges.first().textContent(), '徽标文案').toContain('未落库')

      await api.dispose()
    })
})
