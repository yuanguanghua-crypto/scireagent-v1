/**
 * ★ P2 第 3/4 步闸门（2026-09-24）：编辑页的 「Usage (vendor-claimed)」录入。
 *
 * 锁死三件事：
 *   A. **录入 + 持久化 + 预填**：编辑页填 usage → Save → 经 API 读回仍存在（预填链路依赖读序列化器）
 *   B. **★ 收益端到端**：有 usage + 方法链 → 保存后 `ProductProtocol` **行数 > 0**（原先恒为 0）
 *   C. **对照**：同样挂方法链但**不给 usage** → **0 行**（证明收益确实来自 usage）
 *
 * 注意：保存带 usage 会同步跑 `recompute_product`（dev 本机含轴C ⇒ 约 13s），故用例超时放宽到 120s。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth.cjs')
const { getToken, apiContext } = require('./helpers/api.cjs')
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')

const J = JSON.stringify
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

// Usage 文本域：用 placeholder 前缀定位（Overview 的 placeholder 不同，不会误选）
const USAGE_BOX = 'textarea[placeholder^="e.g. fluorescently labeled nucleotide analog"]'
const USAGE_TEXT = 'fluorescently labeled nucleotide analog used for direct enzymatic labeling and imaging'

const created = []

test.describe('P2 · 编辑页 Usage 录入与收益', () => {
  test.describe.configure({ timeout: 120000 })

  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    const byPrefix = await cleanupByPrefix(api, { label: 'p2-usage' })
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
    console.log(`__E2E__ P2_CLEANUP byPrefix=${J(byPrefix)} deleted=${J(deleted)} residual=${J(residual)}`)
    expect(residual.product, 'product 残留应为空').toEqual([])
    expect(residual.pp, 'product_protocol 残留应为 0').toBe(0)
    expect(residual.pm, 'product_method 残留应为 0').toBe(0)
    await ctx.dispose(); await api.dispose()
  })

  async function makeFixture(api, pfx) {
    const resp = await api.post('/products/', {
      data: { name: `E2E P2 ${pfx}`, catalog_no: catalogNo(pfx), slug: slug(pfx), method_ids: [54] },
    })
    expect(resp.status(), `夹具 ${pfx} 应创建成功`).toBeLessThan(300)
    const id = (await resp.json()).data.id
    created.push(id)
    return id
  }

  test('A+B @write @local-only 填 usage 保存 ⇒ 持久化 + 落 ProductProtocol 行', async ({ page, request: req }) => {
    const api = await staffApi(req)
    const id = await makeFixture(api, 'P2U')

    const before = dbQuery(
      `import json\nfrom apps.bridges.models import ProductProtocol\n` +
      `print('__SNAP__' + json.dumps({'pp': ProductProtocol.objects.filter(product_id=${id}).count()}))`)
    console.log(`__E2E__ P2 保存前 PP 行 = ${before.pp}`)

    await loginAsStaff(page)
    await goto(page, `/workspace/products/${id}/edit`)
    const box = page.locator(USAGE_BOX)
    await expect(box, 'Usage 文本域应存在（第 6 节）').toBeVisible({ timeout: 30000 })
    await box.fill(USAGE_TEXT)

    const saveBtn = page.locator('.form-actions button', { hasText: /Save Draft|Saving/ })
    const resp = await saveBtn.click()
      .then(() => page.waitForResponse(
        (r) => r.url().includes(`/products/${id}/`) && r.request().method() === 'PUT', { timeout: 90000 }))
    expect(resp.status(), '保存应 200').toBe(200)

    // ① 持久化（经 API 读回 —— 同时验证读序列化器带 usage）
    const detail = await (await api.get(`/products/${id}/`)).json()
    const saved = (detail?.data || detail)?.usage
    console.log(`__E2E__ P2 读回 usage 前 50 字 = ${J(String(saved || '').slice(0, 50))}`)
    expect(saved, '保存后 usage 应可经 API 读回').toContain('fluorescently labeled nucleotide')

    // ② 收益：ProductProtocol 落行
    const after = dbQuery(
      `import json\nfrom apps.bridges.models import ProductProtocol\n` +
      `print('__SNAP__' + json.dumps({'pp': ProductProtocol.objects.filter(product_id=${id}).count(),` +
      `'document': ProductProtocol.objects.filter(product_id=${id}, tier='document').count()}))`)
    console.log(`__E2E__ P2 保存后 PP 行 = ${after.pp}（document=${after.document}）`)
    expect(after.pp, '有 usage ⇒ 应落 ProductProtocol 行（P2 的核心收益）').toBeGreaterThan(0)
    expect(after.document, '落库行应含 document 档（非 weak）').toBeGreaterThan(0)

    // ③ 重载后预填仍在
    await goto(page, `/workspace/products/${id}/edit`)
    await expect(page.locator(USAGE_BOX), '重载后应回填').toHaveValue(USAGE_TEXT, { timeout: 30000 })
    console.log('__E2E__ P2 重载后 usage 已回填 ✓')

    await api.dispose()
  })

  test('C @write @local-only 对照：挂方法链但不填 usage ⇒ 0 行', async ({ request: req }) => {
    const api = await staffApi(req)
    const id = await makeFixture(api, 'P2N')   // 只挂 method_ids，不给 usage
    const st = dbQuery(
      `import json\nfrom apps.bridges.models import ProductProtocol, ProductMethod\n` +
      `print('__SNAP__' + json.dumps({'pp': ProductProtocol.objects.filter(product_id=${id}).count(),` +
      `'pm': ProductMethod.objects.filter(product_id=${id}).count()}))`)
    console.log(`__E2E__ P2 对照：pm=${st.pm} pp=${st.pp}`)
    expect(st.pm, '对照夹具应已挂上方法链（否则对照无意义）').toBe(1)
    expect(st.pp, '无 usage ⇒ 轴A=None ⇒ 不应落任何 PP 行（对照基线）').toBe(0)
    await api.dispose()
  })
})
