/**
 * D6 回归 —— `/po/orders/:id` 的 "For Research Use Only" 声明**必须与产品实际标记一致**
 *
 * ## 缺陷现场（2026-10-21 全站测试发现，P1 · 合规声明误标）
 * `PoOrderDetail.vue:105`：
 *   `v-if="order.items?.some(it => it.is_ruo !== false)"`
 * 但明细序列化器 `OrderItemSerializer` 的 `fields` 里**没有 `is_ruo`**
 * （`apps/transactions/api/v1/serializers.py`）⇒ `undefined !== false` **恒为真**
 * ⇒ **每张订单都显示** "For Research Use Only. Not for use in diagnostic or therapeutic procedures."，
 * 哪怕产品明确不是 RUO。
 *
 * ## 修复后的三态语义（本 spec 逐条钉住）
 * | `is_ruo` | 声明 | 理由 |
 * |---|---|---|
 * | `true`  | **显示** | 产品确认仅限科研 |
 * | `false` | **不显示** | 产品明确非 RUO，不能误标 |
 * | `null`/缺失 | **显示** | 产品已删（`SET_NULL`）无法判定 ⇒ 合规优先，宁可多声明不漏声明 |
 *
 * ## 为什么用网络注入而不是造非 RUO 产品
 * dev 库 **127 个产品全是 `research_use_only=True`**（实测），造一个非 RUO 产品还得建 SKU + 订单，
 * 且会在共享库里留数据。而本缺陷**真正出错的地方是前端的判定逻辑**，
 * 用 `page.route` 改写 `items[].is_ruo` 就能精确覆盖三个分支，零写入、零残留。
 * 后端"字段是否真的返回"由 `apps/transactions/tests/test_serializers.py::OrderItemIsRuoTest` 覆盖。
 *
 * 运行：npx playwright test e2e/po-ruo-declaration.spec.cjs --project=chromium
 * 前置：后端 8000 + 前端 5173。**本 spec 零写入。**
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff } = require('./helpers/auth.cjs')
const H = require('./helpers/poHelpers.cjs')

const DECL = /For Research Use Only/i

let admin
let orderId

/** 只读：找一个**有明细**的订单（优先 confirmed，其次任意） */
async function findOrderWithItems() {
  const ctx = await request.newContext({
    baseURL: H.ROOT,
    extraHTTPHeaders: { Authorization: `Token ${admin}`, Accept: 'application/json' },
  })
  try {
    for (const status of ['confirmed', 'paid', 'completed', '']) {
      const q = status ? `&status=${status}` : ''
      const r = await ctx.get(`/api/v1/orders/?page_size=30${q}`)
      const body = await r.json()
      for (const o of body.data || []) {
        const d = await ctx.get(`/api/v1/orders/${o.id}/`)
        const db = await d.json()
        const det = db.data || db
        if ((det.items || []).length > 0) return o.id
      }
    }
    return null
  } finally {
    await ctx.dispose().catch(() => {})
  }
}

/** 拦截订单详情请求，改写每个明细的 `is_ruo`（`undefined` = 删掉该键） */
async function stubIsRuo(page, value) {
  await page.route(`**/api/v1/orders/${orderId}/`, async (route) => {
    const resp = await route.fetch()
    const json = await resp.json()
    const det = json.data || json
    for (const it of det.items || []) {
      if (value === undefined) delete it.is_ruo
      else it.is_ruo = value
    }
    await route.fulfill({ response: resp, json })
  })
}

test.describe('@local-only D6 · /po/orders/:id 的 RUO 声明', () => {
  test.beforeAll(async () => {
    admin = await H.getAdminToken()
    expect(admin, '需要 admin token').toBeTruthy()
    orderId = await findOrderWithItems()
    expect(orderId, 'dev 库里应至少有一张含明细的订单（否则无法验证明细渲染）').toBeTruthy()
  })

  test('接口必须真的返回 is_ruo（布尔），不再让前端拿到 undefined', async ({ request: req }) => {
    const r = await req.get(`${H.ROOT}/api/v1/orders/${orderId}/`, {
      headers: { Authorization: `Token ${admin}` },
    })
    expect(r.ok()).toBeTruthy()
    const body = await r.json()
    const det = body.data || body
    expect((det.items || []).length, '该订单应有明细').toBeGreaterThan(0)
    for (const it of det.items) {
      expect(Object.prototype.hasOwnProperty.call(it, 'is_ruo'), `明细 ${it.id} 必须返回 is_ruo`).toBe(true)
      expect(['boolean', 'object'], `明细 ${it.id} 的 is_ruo 应为布尔或 null，实际 ${typeof it.is_ruo}`).toContain(
        typeof it.is_ruo,
      )
    }
  })

  test('is_ruo=true ⇒ 显示声明', async ({ page }) => {
    await loginAsStaff(page)
    await stubIsRuo(page, true)
    await page.goto(`${BASE_URL}/po/orders/${orderId}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.po-page')).toBeVisible({ timeout: 20000 })
    await expect(page.getByText(DECL).first(), 'RUO 产品必须显示合规声明').toBeVisible({ timeout: 20000 })
  })

  test('is_ruo=false ⇒ **不显示**声明（反向，缺陷时就错在这里）', async ({ page }) => {
    await loginAsStaff(page)
    await stubIsRuo(page, false)
    await page.goto(`${BASE_URL}/po/orders/${orderId}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.po-page')).toBeVisible({ timeout: 20000 })

    // 反向对照：先证明明细表真的渲染了（否则"不显示"可能只是白屏）
    await expect(page.locator('table tbody tr').first(), '明细表应已渲染').toBeVisible({ timeout: 20000 })
    await expect(page.getByText(DECL), '产品非 RUO 时不得误标该声明').toHaveCount(0)
  })

  test('is_ruo 缺失（产品已删）⇒ 保守显示声明', async ({ page }) => {
    await loginAsStaff(page)
    await stubIsRuo(page, undefined)
    await page.goto(`${BASE_URL}/po/orders/${orderId}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.po-page')).toBeVisible({ timeout: 20000 })
    await expect(
      page.getByText(DECL).first(),
      '无法判定时必须保守显示（合规优先：宁可多声明，不可漏声明）',
    ).toBeVisible({ timeout: 20000 })
  })
})
