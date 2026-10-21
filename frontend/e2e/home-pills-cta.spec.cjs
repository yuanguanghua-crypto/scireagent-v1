/**
 * 首页分类 Pills + 热门标签 CTA —— 补 I 维确认的两处空白
 *
 * ## 为什么需要
 * I 维判定（`docs/e2e/INTERACTION_VERDICT.md`）显示 `/` 有两项未命中：
 *   - 分类 pills
 *   - CTA
 *
 * 深挖后发现它们**不在 HomePage.vue 里**，而在子组件：
 *   - `components/home/CategoryPills.vue` → `.category-pill`（点击跳 `/products?category=<slug>`）
 *   - `components/home/HeroSearch.vue`   → `.tag`（热门标签，点击触发搜索）
 *   ⇒ 所以先前 grep `HomePage.vue` 找不到，不代表功能不存在。
 *
 * `homepage.spec.cjs` 已覆盖"搜索框跳转到搜索页"，但**没覆盖 pills 和 tag**。
 *
 * ## 拟人化
 * - 点 pills / tag 都是**用户真实操作**，不用 goto 直达带参数 URL
 * - 断言看**URL 变化**（pills 跳分类页、tag 触发搜索），不信 toast
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/home-pills-cta.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL } = require('./helpers/auth.cjs');

test.describe('@home 首页分类 Pills 与热门标签 CTA', { tag: ['@readonly', '@local-only'] }, () => {
  test('分类 pill 点击 → 跳 /products?category=<slug>', async ({ page }) => {
    await page.goto(BASE_URL + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.home', { timeout: 15000 });

    const pills = page.locator('.category-pill');
    // pills 来自后端 categories，正常至少有 1 个；为 0 时应视为数据问题而非跳过
    await expect(pills.first()).toBeVisible({ timeout: 10000 });
    const n = await pills.count();
    expect(n, '首页应有分类 pill（来自 /site/home 的 categories）').toBeGreaterThan(0);

    const first = pills.first();
    const label = (await first.textContent()) || '';
    await first.click();

    // 断言：跳到产品列表，且带上 category 查询参数（这是 pill 的语义）
    await expect(page).toHaveURL(/\/products\?.*category=/, { timeout: 10000 });
    // 额外证据：URL 里的 slug 非空
    const url = page.url();
    const slug = new URL(url).searchParams.get('category');
    expect(slug, `pill「${label.trim()}」的 category 参数不应为空`).toBeTruthy();
  });

  test('热门标签 tag 点击 → 触发搜索（URL 带 query 或跳 /search）', async ({ page }) => {
    await page.goto(BASE_URL + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.home', { timeout: 15000 });

    const tags = page.locator('.tag');
    const n = await tags.count();
    // 热门标签来自后端 tags，若无数据则该交互无对象 —— 明确跳过并说明，不假绿
    test.skip(n === 0, '首页未返回热门标签（tags 为空），本用例无测试对象');

    const first = tags.first();
    const label = ((await first.textContent()) || '').trim();
    await first.click();

    // 断言：搜索被触发 —— 要么跳 /search，要么 URL 上带 query/q 参数
    await expect
      .poll(async () => {
        const u = new URL(page.url());
        return u.pathname.startsWith('/search') || u.searchParams.has('q') || u.searchParams.has('query');
      }, { timeout: 10000, message: `点击标签「${label}」后应触发搜索` })
      .toBe(true);
  });
});
