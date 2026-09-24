/**
 * N1 + A3 · 产品编辑页「Methods 芯片用真名」与「Methods 下拉口径 = origin=imported」 —— **只读**
 * （@readonly @local-only）
 *
 * 两条已验证有效的只读校验，固化为回归 spec：
 *
 *   N1（方法名不变量）—— 编辑页第 5 节（5. Knowledge Links）的 Methods 芯片必须用
 *     `method_links[].name` 渲染，**不得**退化成裸 `#35`。
 *     背景（ProductEditPage.vue:112-119 注释 + :1871-1875）：
 *       `/methods/` 只取前 200 条，而全表约 6.7 万条；挂在前 200 之外的方法若靠
 *       `/methods/` 找名字就会显示成裸 `#id`。修复后名字改由**产品详情自带**的
 *       `method_links`（`[{id, name, is_hidden}]`）渲染；`is_hidden===true` 的芯片
 *       额外带一个文本为 `旧种子` 的 `.badge`（旧种子 = is_test_fixture，对知识面隐藏）。
 *
 *   A3（下拉数据源口径）—— 第 5 节「Link existing Method」下拉应请求
 *     `/methods/?origin=imported`（ProductEditPage.vue:425-430），以排除 6.7 万条
 *     T2 的 AI 空壳（`origin='ai_extracted'`，无协议链）。可选项从 201 降到约 88。
 *
 * 判据（恒等式，期望值全部**现算**，不硬编码）：
 *   用例 1（N1）：UI 的 Methods 芯片数 == 服务端 `method_links.length`；
 *                 逐片：`a.chip-link` 文本 == 对应 `method_links[i].name` 且不匹配 `/^#\d+$/`；
 *                 `is_hidden===true` 的芯片内 `.badge` 文本 == `旧种子`。
 *   用例 2（A3）：UI 下拉选项数 n == k + 1（k = `/methods/?origin=imported&page_size=200`
 *                 返回条数，+1 是占位项 `— Link existing Method —`）；另 n < 120（记录型护栏）。
 *
 * 只读：不点 Save、不新增/删除数据；afterAll 无需清理（未写入）。
 *
 * 运行（照 e2e/README.md §1，务必用 E: 物理路径 / node 直调 cli.js / 输出重定向到文件 /
 *       与同伴共用 dev 库须抢 _pw.lock 串行）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do sleep 15; done; echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test \
 *     e2e/product-edit-method-chip-names.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-n1a3 \
 *     > ../../_n1a3.log 2>&1
 *   rm -f ../../_pw.lock
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')

// 已验证有效的目标产品（dev sqlite）：method_links = 2 条，两条皆 is_hidden===true。
const PRODUCT_ID = 66

const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })

async function staffApi(request) {
  return apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))
}

test.describe('N1/A3 · 产品编辑页 Methods 芯片真名 + 下拉口径（只读）', () => {
  // 与同目录 product-edit-weak-count-consistency.spec.cjs 一致：放宽用例超时，但**不放宽任何断言**。
  test.describe.configure({ timeout: 120000 })

  test('N1 @readonly @local-only product #66：Methods 芯片显示真名 + 隐藏标记（不退化成裸 #id）', async ({ page, request }) => {
    await loginAsStaff(page)

    // ── 1) A-API 现算真值（判据来源：产品详情自带的 method_links）──
    const api = await staffApi(request)
    const r = await api.get(`/products/${PRODUCT_ID}/`)
    expect(r.status(), `GET /products/${PRODUCT_ID}/ 状态码`).toBe(200)
    const body = await r.json()
    await api.dispose()
    const methodLinks = (body && body.data && body.data.method_links) || []
    // 无链接则本用例无意义（显式失败，不静默通过）
    expect(methodLinks.length, `#${PRODUCT_ID} 应至少有一个 method_link`).toBeGreaterThan(0)

    // ── 2) 打开编辑页并等载入完成（.edit-form 可见）──
    // 不用 waitForResponse 等详情接口：靠下方 DOM 断言的 auto-retry 等数据落定。
    await goto(page, `/workspace/products/${PRODUCT_ID}/edit`)
    await expect(page.locator('.edit-form')).toBeVisible({ timeout: 30000 })

    // ── 3) Methods 芯片（真实 DOM：.chip-group > span.chip:not(.chip-protocol) > a.chip-link）──
    const chips = page.locator('.chip-group .chip:not(.chip-protocol)')
    // 等数据落定（auto-retry）：芯片数应等于服务端 method_links.length
    await expect(chips, `#${PRODUCT_ID} Methods 芯片数应 == 服务端 method_links.length`).toHaveCount(
      methodLinks.length,
      { timeout: 30000 },
    )

    // ── 4) 逐片断言 ──
    for (let i = 0; i < methodLinks.length; i++) {
      const chip = chips.nth(i)
      const link = chip.locator('a.chip-link')
      // ⚠️ 读 a.chip-link 自身 innerText 与期望名**全等**比较；
      //    绝不用 textContent.slice(...) 截断后做包含判断（本站名字很长，会误判）。
      const text = (await link.innerText()).trim()
      const exp = methodLinks[i]

      // ★N1 核心：芯片文本 == 对应 method_links[i].name
      expect(text, `#${PRODUCT_ID} 芯片[${i}] 文本应 == method_links[${i}].name="${exp.name}"`).toBe(exp.name)
      // 不得退化成裸 id
      expect(text, `#${PRODUCT_ID} 芯片[${i}] 不得退化成裸 #id`).not.toMatch(/^#\d+$/)

      // 隐藏方法：芯片内应有文本为「旧种子」的 .badge（用 .badge 元素文本判断，不做整块 innerText 截断）
      if (exp.is_hidden === true) {
        const badge = chip.locator('.badge')
        await expect(badge, `#${PRODUCT_ID} 芯片[${i}]（is_hidden）应有且仅有 1 个 .badge`).toHaveCount(1)
        expect((await badge.innerText()).trim(), `#${PRODUCT_ID} 芯片[${i}] 隐藏徽标文本应为「旧种子」`).toBe('旧种子')
      }

      console.log(
        `[N1] #${PRODUCT_ID} chip[${i}] name="${text}" 期望="${exp.name}" id=${exp.id} is_hidden=${exp.is_hidden === true}`,
      )
    }
    console.log(`[N1] #${PRODUCT_ID} method_links.length=${methodLinks.length} UI 芯片数=${await chips.count()}`)
  })

  test('A3 @readonly @local-only product #66：Methods 下拉口径 == /methods/?origin=imported（不硬编码）', async ({ page, request }) => {
    await loginAsStaff(page)

    // ── 1) A-API 现算真值：origin=imported 的返回条数 k（信封：数组在 data）──
    const api = await staffApi(request)
    const r = await api.get('/methods/?origin=imported&page_size=200')
    expect(r.status(), 'GET /methods/?origin=imported&page_size=200 状态码').toBe(200)
    const body = await r.json()
    await api.dispose()
    const imported = Array.isArray(body && body.data) ? body.data : ((body && body.data && body.data.results) || [])
    const k = imported.length

    // ── 2) 打开编辑页 → 第 5 节第 1 个 AppSelect（Methods 下拉）──
    await goto(page, `/workspace/products/${PRODUCT_ID}/edit`)
    await expect(page.locator('.edit-form')).toBeVisible({ timeout: 30000 })

    const section5 = page.locator('.form-section').filter({
      has: page.locator('h3', { hasText: '5. Knowledge Links' }),
    })
    const methodSelect = section5.locator('.el-select').first()
    await expect(methodSelect, '第 5 节应有 Methods 下拉').toBeVisible({ timeout: 30000 })
    await methodSelect.click()

    const items = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    // 等数据落定（**DOM 断言的 auto-retry**，不加多余 waitForResponse）：
    //   knowledgeList.methods 请求完成前，下拉里只有占位项 ⇒ 以「选项数达到期望」作为落定信号。
    //   期望 = k+1（现算，不硬编码）；若 UI 口径错（如未加 origin 过滤 ⇒ 201），此处会等到超时后失败。
    await expect(items, `下拉选项数应 == k+1=${k + 1}（k=${k}，+1 为占位项）`).toHaveCount(k + 1, { timeout: 30000 })
    const n = await items.count()

    // ── 3) 断言：UI 选项数 == k + 1（+1 = 占位项「— Link existing Method —」）──
    expect(n, `下拉选项数 n 应 == k+1=${k + 1}（k=${k}，+1 为占位项）`).toBe(k + 1)
    // 记录型护栏：已排除 6.7 万条 AI 空壳（A3 前为 201）
    expect(n, `下拉选项数应 < 120（已排除 AI 空壳）`).toBeLessThan(120)

    console.log(`[A3] #${PRODUCT_ID} 下拉选项数 n=${n} 期望=k+1=${k + 1} (k=${k})`)

    // 只读收尾：收起 popper
    await page.keyboard.press('Escape')
  })
})
