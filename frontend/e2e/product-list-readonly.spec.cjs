/**
 * P1 基建 · **示范用例**（产品列表页只读集 = Part 2 组 A + H1 + 夹具闸门）
 *
 * 这份 spec 的**首要目的是验证 P1 基建本身可用**，其次才是覆盖剧本：
 *   A-API   → expectApi()                   （A1/A2 里与 UI 行数**交叉核对**）
 *   D-DB    → snapshotDb()/expectDelta()    （F0 闸门 + A3 的 before/after）
 *   U-UI    → Playwright 原生 + consoleErrors()
 *   N-负向  → expectNoWrites()              （A3 全程零写入）
 *   fixtures→ catalogNo()/PREFIX            （F0 命名规范 + 残留闸门）
 *
 * 运行（**本机必须用这条**，见 e2e/README.md §1）：
 *   cd src_claude/frontend
 *   node node_modules/@playwright/test/cli.js test e2e/product-list-readonly.spec.cjs \
 *     --project=chromium --reporter=line > "$HOME/_pw.log" 2>&1
 *
 * 前置：本地 dev 已起 → Django(:8000, DB_ENGINE=sqlite) + Vite(:5173)。
 *       启动方式见工作区根 `start_dev.sh`（注意本机 `bash` 被 WSL 别名劫持，
 *       须用 `/usr/bin/bash`，或直接按脚本内的两条命令分别起）。
 *
 * 验收线：**每个 test 的函数体 ≤ 15 行**（断言全部来自 helpers，不在用例里重写）。
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, expectNoWrites, consoleErrors } = require('./helpers/assertions.cjs')
const { catalogNo, slug, skuCode, PREFIX } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
// ★ 2026-09-23：原实现只等 `domcontentloaded` ⇒ **页面数据尚未加载完就断言** ⇒ 结构性 flaky：
//   A1/A2 紧接着就断 `.view-toggle__btn` 的 class，机器慢时直接 `element(s) not found`
//   （实测截图停在 "Loading..."）；A3 亦曾在**登录未成功**（登录页 + `Action failed`）时继续往下跑。
//   ⇒ 统一在 goto 后等**页面骨架就绪**：工作台列表页优先 `.filters-bar`，退化到回收站横幅/侧栏；
//     若 30s 内都等不到（例如未登录被踢回登录页、或后端 5xx 错误态），**就地报错**而不是让后续断言给出误导性的失败。
const goto = async (page, p) => {
  await page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
  await expect(
    page.locator('.filters-bar, .recycle-banner, .error, .sidebar, .app-shell').first(),
    `goto(${p}) 后页面骨架未就绪（可能未登录或后端异常）`
  ).toBeVisible({ timeout: 30000 })
}

/** 带 staff token 的 API 上下文（A-API 的统一入口） */
async function staffApi(request) {
  return apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))
}

/** 取「全量（含回收站）」，前端三层集合模型的唯一数据源 */
async function fetchAll(api) {
  const resp = await api.get('/products/', { params: { archived: 1, page_size: 500 } })
  return (await resp.json()).data || []
}

test.describe('P1 师范用例 · 列表页只读集', () => {
  // ── A1 ─────────────────────────────────────────────
  test('A1 @readonly @prod-ok 进入 Products 视图：无横幅 / toggle active / 行数 == A-API 在售数', async ({ page, request }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page)
    const api = await staffApi(request)
    const live = (await fetchAll(api)).filter((p) => p.archived !== true).length
    await goto(page, '/workspace/products')
    await expect(page.locator('.recycle-banner')).toHaveCount(0)
    await expect(page.locator('.view-toggle__btn', { hasText: 'Products' })).toHaveClass(/is-active/)
    await expect(page.locator('.products-table tbody tr')).toHaveCount(live)
    await api.dispose()
    expect(errors).toEqual([])
  })

  // ── A2 ─────────────────────────────────────────────
  test('A2 @readonly @prod-ok 深链 ?view=recycle：toggle active / 横幅含 N products / 行数 == 归档数', async ({ page, request }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page)
    const api = await staffApi(request)
    const archived = (await fetchAll(api)).filter((p) => p.archived === true).length
    await goto(page, '/workspace/products?view=recycle')
    await expect(page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' })).toHaveClass(/is-active/)
    await expect(page.locator('.recycle-banner')).toContainText(`${archived} products`)
    if (archived > 0) await expect(page.locator('.products-table tbody tr')).toHaveCount(archived)
    await api.dispose()
    expect(errors).toEqual([])
  })

  // ── A3 + H1（N-负向 + D-DB）：一行化零写入断言 ────────
  test('A3 @readonly 视图切换双向同步 URL + 切换清空选中/重置筛选（A3↑），全程零写入', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page)
    await goto(page, '/workspace/products')
    // ★ A3↑ 前置：先勾选 1 行 + 把状态筛选改成 active，否则"被清空/被重置"不可观测。
    const boxes = page.locator('.products-table tbody td.col-check input[type=checkbox]')
    await expect(boxes.first(), '列表应先加载出可见行').toBeVisible({ timeout: 15000 })
    await boxes.first().check()
    await expect(page.getByRole('button', { name: 'Batch archive', exact: true }),
      'A3↑ 前置：勾选 1 行后应出现批量按钮').toBeVisible({ timeout: 10000 })
    await page.locator('.filters-bar select').first().selectOption('active')

    await expectNoWrites(async () => {
      await page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' }).click()
      await expect(page).toHaveURL(/view=recycle/)
      await expect(page.locator('.recycle-banner')).toBeVisible()

      // ★ A3↑：切视图必须**同时**清空选中 + 关闭菜单 + 重置筛选（代码在 `setView()`）：
      //   ① 选中被清空 → active 视图的批量按钮消失；② 且**不得**残留选中使 recycle 视图冒出
      //   `Restore selected`（那会让用户在新视图里对旧选中误操作）；③ 状态筛选回 `all`。
      await expect(page.getByRole('button', { name: 'Batch archive', exact: true }),
        'A3↑ 切视图应清空选中（active 批量按钮消失）').toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Restore selected', exact: true }),
        'A3↑ 不得残留选中（否则 recycle 视图会冒出 Restore selected）').toHaveCount(0)
      await expect(page.locator('.filters-bar select').first(),
        'A3↑ statusFilter 应重置为 all').toHaveValue('all')

      await page.locator('.view-toggle__btn', { hasText: 'Products' }).click()
      await expect(page).not.toHaveURL(/view=recycle/)
    }, 'A3 视图切换')
    expect(errors).toEqual([])
  })

  // ── F0（P1 基建自检）：夹具命名规范，恒应通过 ──────────
  test('F0 @readonly 夹具命名规范：catalogNo() 形如 E2E-<P>-<13位ts>', async () => {
    expect(catalogNo('F0'), '命名规范').toMatch(/^E2E-F0-\d{13}$/)
    expect(slug('F0')).toMatch(/^e2e-f0-\d{13}$/)
    expect(skuCode('F0')).toMatch(/^E2E-F0-\d{13}-SKU$/)
  })

  // ── F1（数据卫生闸门）：库内不得有 E2E- 残留 ───────────
  // 失败 ≠ 基建坏了，而是**真发现**：dev 库里有历史跑批遗留的夹具，需人工决定是否清理。
  test('F1 @readonly 清理闸门：dev 库内应无 E2E- 残留（红 = 需人工清理，非基建故障）', async ({ request }) => {
    const api = await staffApi(request)
    const leftovers = (await fetchAll(api))
      .filter((p) => String(p.catalog_no || '').startsWith(PREFIX))
      .map((p) => `${p.catalog_no}(id=${p.id})`)
    await api.dispose()
    const shown = leftovers.slice(0, 10)
    expect(
      leftovers.length,
      `残留 ${leftovers.length} 条（前 10 条：${JSON.stringify(shown)}）。\n` +
        '清理：await cleanupByPrefix(api, { label: "dev-hygiene" })（按 E2E- 前缀硬删，超管）；\n' +
        '若确认是历史脏数据且已无价值，再执行；有疑问先问人。'
    ).toBe(0)
  })
})
