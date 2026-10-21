/**
 * D2 回归 —— `/orders` 客户订单历史的**真实总数与分页**
 *
 * ## 缺陷现场（2026-10-21 全站测试发现，P0）
 * 客户订单历史页只显示 20 条、**没有分页**，页面总数显示 **20**，而真值是 976+。
 * ⇒ 客户**永远查不到自己第 21 单以前的订单**（售后/对账/复购全靠它）。
 *
 * 根因（三层叠加，均已读码确认）：
 *   ① `OrderListPage.vue` 全文无分页控件（只有 table + empty state）；
 *   ② `stores/orders.js` 的 `fetchOrders(params)` 从不传 `page` ⇒ 后端恒返回第 1 页；
 *   ③ 同一文件的 `total.value = data.count || data.meta?.pagination?.count || orders.value.length`
 *      —— 这里 `data` 取的是 `res.data`，而 `core/renderers.py:31-37` 已把分页信息放在
 *      **信封的 `meta.pagination`**、`data` 直接就是**数组** ⇒ 前两个分支永远 undefined
 *      ⇒ `total` 恒等于当前页条数（20）。
 *
 * ## 判定
 * 用 **staff** 登录访问 `/orders`：`OrderViewSet.get_queryset` 对 `is_staff` 返回全量
 * （`views.py:31-33`），库里订单远多于 20 ⇒ 一页装不下，分页必然出现。**不造任何数据、只读。**
 *
 * 运行：npx playwright test e2e/orders-pagination.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff } = require('./helpers/auth.cjs')

const PAGE_SIZE = 20 // 后端 `core/pagination.py` StandardPagination.page_size

test.describe('@orders 订单历史：真实总数 + 分页（D2 回归）', { tag: ['@readonly', '@local-only'] }, () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page)
  })

  test('总数显示后端真实 count，而不是当前页条数', async ({ page }) => {
    await page.goto(`${BASE_URL}/orders`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.order-row', { timeout: 15000 })

    // 第 1 页正好一页的量（数据量远大于此，见下方断言）
    await expect(page.locator('.order-row')).toHaveCount(PAGE_SIZE)

    // ① 分页组件必须存在
    const pag = page.locator('.data-pagination')
    await expect(pag, '`/orders` 必须渲染分页控件（缺陷时完全没有）').toBeVisible({ timeout: 10000 })

    // ② 总数文案里的数字必须 > 一页的量（缺陷时恒等于 20）
    const totalText = (await pag.locator('.el-pagination__total').textContent()) || ''
    const shownTotal = parseInt(totalText.replace(/[^\d]/g, ''), 10)
    expect(
      Number.isFinite(shownTotal),
      `总数文案应含数字，实际拿到「${totalText}」`,
    ).toBe(true)
    expect(
      shownTotal,
      `总数应显示后端真实 count（>${PAGE_SIZE}），实际显示 ${shownTotal} —— 说明读的是当前页条数`,
    ).toBeGreaterThan(PAGE_SIZE)
  })

  test('翻到第 2 页：内容不同、能回第 1 页，且第 2 页末有下一页', async ({ page }) => {
    await page.goto(`${BASE_URL}/orders`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.order-row', { timeout: 15000 })

    const page1First = ((await page.locator('.order-row .order-no').first().textContent()) || '').trim()
    expect(page1First).not.toBe('')

    // 点第 2 页（el-pagination 的数字页码）
    await page.locator('.data-pagination .el-pager li').nth(1).click()

    // 内容必须真的换了 —— 不能只验证"点击没报错"
    await expect
      .poll(async () => ((await page.locator('.order-row .order-no').first().textContent()) || '').trim(), {
        timeout: 15000,
      })
      .not.toBe(page1First)

    const page2First = ((await page.locator('.order-row .order-no').first().textContent()) || '').trim()
    expect(page2First, '第 2 页首行不应与第 1 页相同').not.toBe(page1First)

    // 回第 1 页，应还原原内容（证明是真分页不是随机刷新）
    await page.locator('.data-pagination .el-pager li').first().click()
    await expect
      .poll(async () => ((await page.locator('.order-row .order-no').first().textContent()) || '').trim(), {
        timeout: 15000,
      })
      .toBe(page1First)
  })
})
