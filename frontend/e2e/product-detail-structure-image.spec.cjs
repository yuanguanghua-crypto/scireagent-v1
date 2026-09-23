/**
 * TDD E2E — 产品详情页应优先显示 Word 提取的结构图（structure_image），
 * 而非用 SMILES 渲染的图。
 *
 * ── 2026-09-23 复活（用户指示"捞回绿例"）───────────────────────────────
 *   原用例的两个前置**在 dev 库均不满足**，故此前标 @obsolete：
 *     ① 硬编码 `PRODUCT_SLUG='5-propargylamino-ctp'` 在产品表中不存在
 *        （且详情页路由是 `/products/:id`，非 slug）；
 *     ② 实测 dev 库 68 个产品中 **structure_image 非空者 = 0**。
 *   ⇒ 现改为 **自造夹具 + 用完还原**（不再依赖手工造数）：
 *     运行时现算一个可访问产品 → PATCH 一个 1×1 PNG 的 data URI 到 `structure_image`
 *     → 断详情页渲染 → **finally 里还原为原值**。
 *   ⚠️ 本用例**有写** ⇒ tier = `@write @local-only`。
 *
 * 断言（与原版**逐字一致，未降级**）：
 *   - `.pd-structure-box` 可见；其中出现 `img.pd-structure-img` 且 `src` 以 `data:image/` 开头；
 *   - 不出现 "No structure" 占位；
 *   - 页面无 JS 错误。
 *   ⚠️ 控制台错误收集**必须用 `attachConsoleErrorCollector`**（它内置外部字体 CDN 中和器）；
 *      自建 `page.on('console')` 会把本机无外网导致的 Google Fonts 噪声算成 JS 错误（已踩过）。
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { attachConsoleErrorCollector } = require('./helpers/console')

/** 1×1 透明 PNG —— 已解码校验：PNG 魔数 + IHDR = 1x1 */
const PNG_1x1 =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

test.describe('Product detail shows Word structure_image (priority over SMILES)', { tag: ['@write', '@local-only'] }, () => {
  test('structure box renders img.pd-structure-img with data URI', async ({ page, request }) => {
    const errors = attachConsoleErrorCollector(page)
    const api = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))

    // ① 现算目标产品（非归档；详情页为公开路由 /products/:id）
    const listBody = await (await api.get('/products/', { params: { page_size: 5 } })).json()
    const list = Array.isArray(listBody?.data) ? listBody.data : listBody?.data?.results || []
    expect(list.length, 'dev 库应至少有一个可访问产品').toBeGreaterThan(0)
    const target = list[0]

    // ② 记录原值以便还原
    const detailBody = await (await api.get(`/products/${target.id}/`)).json()
    const original = detailBody?.data?.structure_image ?? ''

    try {
      // ③ 造夹具
      const patch = await api.patch(`/products/${target.id}/`, { data: { structure_image: PNG_1x1 } })
      expect(patch.status(), `PATCH structure_image 应 2xx（实际 ${patch.status()}）`).toBeLessThan(300)

      // ④ 断言渲染（不用 networkidle —— 本仓已记录其不可靠）
      await loginAsStaff(page)
      await page.goto(`${BASE_URL}/products/${target.id}`, { waitUntil: 'domcontentloaded' })

      const box = page.locator('.pd-structure-box')
      await expect(box).toBeVisible({ timeout: 15000 })

      // 关键断言：不应只显示 SMILES 文本占位，而应出现 Word 结构图 <img>
      const img = box.locator('img.pd-structure-img')
      await expect(img).toBeVisible({ timeout: 15000 })

      const src = await img.getAttribute('src')
      expect(src, 'structure_image 必须是 data:image/... PNG').toMatch(/^data:image\//)

      // 不应出现 "No structure" 占位（结构图已显示）
      await expect(box.locator('.pd-svg-placeholder:has-text("No structure")')).toHaveCount(0)

      expect(errors, `页面存在 JS 错误: ${errors.join(' | ')}`).toHaveLength(0)
    } finally {
      // ⑤ 还原（无论成败）
      await api.patch(`/products/${target.id}/`, { data: { structure_image: original } }).catch(() => {})
      await api.dispose()
    }
  })
})
