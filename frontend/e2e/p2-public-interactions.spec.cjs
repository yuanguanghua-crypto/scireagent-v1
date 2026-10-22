/**
 * Batch 3 / P2-1~P2-3 —— 公开页交互补深
 *   F1-1 首页：分类胶囊点击、知识区展开
 *   F1-2 产品列表：排序 / 搜索联动（+ L3 子分类不生效锁定）
 *   F1-4 搜索：/search/suggest、按类型 Tab（客户端过滤不发请求）
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p2 @local-only F1-1 首页交互', () => {
  test('点分类胶囊跳到带 category 参数的列表页', async ({ page }) => {
    await page.goto(`${H.BASE}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    // 分类胶囊：带数量的按钮（如 "Nucleotides & Nucleosides 105"）
    const pill = page.getByRole('button', { name: /\d{2,}$/ }).first();
    if (!(await pill.count())) test.skip(true, '首页没有分类胶囊（数据为空）');
    await pill.click();
    await page.waitForTimeout(1500);
    expect(page.url(), '分类胶囊没跳 /products').toContain('/products');
    expect(page.url(), 'URL 没带 category 参数').toMatch(/category=/);
  });

  test('知识区可展开并显示 4 个领域', async ({ page }) => {
    await page.goto(`${H.BASE}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const toggle = page.getByRole('button', { name: /Explore Knowledge Graph/i }).first();
    if (!(await toggle.count())) test.skip(true, '知识区折叠开关不存在');
    await toggle.click();
    await page.waitForTimeout(800);
    const txt = await H.bodyText(page);
    for (const d of ['Research Goals', 'Applications', 'Methods', 'Protocols']) {
      expect(txt, `展开后缺少领域：${d}`).toContain(d);
    }
  });
});

test.describe('@p2 @local-only F1-2 产品列表筛选与排序', () => {
  test('切换排序会把 ordering 带给后端', async ({ page }) => {
    const reqs = [];
    page.on('request', (r) => {
      if (/\/api\/v1\/products/.test(r.url())) reqs.push(r.url());
    });
    await page.goto(`${H.BASE}/products`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    // 实测：排序是**原生 <select class="sort-select">**（不是 Element Plus 下拉）
    const sort = page.locator('select.sort-select').first();
    if (!(await sort.count())) test.skip(true, '没有排序控件');
    const opts = await sort.locator('option').evaluateAll((els) =>
      els.map((e) => ({ v: e.value, t: e.textContent })));
    const target = opts.find((o) => o.v && o.v !== 'default');
    expect(target, '排序下拉里没有非默认选项').toBeTruthy();
    await sort.selectOption(target.v);
    await page.waitForTimeout(2000);

    const withOrdering = reqs.filter((u) => /[?&]ordering=/.test(u));
    expect(withOrdering.length, `切排序后请求没带 ordering。请求：${JSON.stringify(reqs.slice(-3))}`)
      .toBeGreaterThan(0);
  });

  test('搜索框会把 search 带给后端', async ({ page }) => {
    const reqs = [];
    page.on('request', (r) => {
      if (/\/api\/v1\/products/.test(r.url())) reqs.push(r.url());
    });
    await page.goto(`${H.BASE}/products`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    const box = page.locator('input[placeholder*="Search products" i]').first();
    if (!(await box.count())) test.skip(true, '列表页没有搜索框');
    await box.fill('probe');
    await box.press('Enter');
    await page.waitForTimeout(2000);
    expect(reqs.some((u) => /[?&]search=probe/.test(u)), '搜索没带 search 参数').toBe(true);
  });
});

test.describe('@p2 @local-only F1-4 搜索页', () => {
  test('/search/suggest 可用且返回建议', async ({ page }) => {
    await page.goto(`${H.BASE}/search`, { waitUntil: 'domcontentloaded' });
    const r = await H.anonApi(page, 'GET', '/api/v1/search/suggest?q=a');
    expect(r.status, 'suggest 接口不可用').toBe(200);
    const body = JSON.stringify(r.data || {});
    expect(body.length, 'suggest 返回空').toBeGreaterThan(10);
  });

  test('输入关键词后结果来自 /search/grouped，切 Tab 不发新请求', async ({ page }) => {
    const reqs = [];
    page.on('request', (r) => {
      if (/search\/grouped/.test(r.url())) reqs.push(r.url());
    });
    await page.goto(`${H.BASE}/search?q=probe`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    expect(reqs.length, '搜索页没调用 /search/grouped').toBeGreaterThan(0);
    expect(reqs[0], 'grouped 请求没带 q').toMatch(/[?&]q=/);

    const n = reqs.length;
    const tab = page.getByRole('button', { name: /^Methods?$/i }).first();
    if (await tab.count()) {
      await tab.click();
      await page.waitForTimeout(1200);
      expect(reqs.length, '切类型 Tab 竟重新请求了（应为客户端过滤）').toBe(n);
    }
  });
});
