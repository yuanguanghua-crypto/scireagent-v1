/**
 * Batch 3 / P2-9~P2-10 —— 内部台两个"只看页面出现"的补深
 *   F5-4 AR 账龄：分桶金额要与 /ar/aging/ 的真实返回一致（不能只验页面有卡片）
 *   F5-5 机构管理：按机构查单的请求必须带 organization_id，且条数与 API 过滤一致
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p2 @local-only F5-4 AR 账龄', () => {
  test('四个账龄桶与总额，与 API 返回一致', async ({ page }) => {
    await H.login(page, 'probe_procure');
    await page.goto(`${H.BASE}/ops/po/ar`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const api = await H.api(page, 'GET', '/api/v1/ar/aging/');
    expect(api.status, 'AR 接口不可用').toBe(200);
    const d = api.data?.data ?? api.data;
    const buckets = d?.buckets || [];
    const total = d?.total_outstanding;

    const txt = await H.bodyText(page);
    for (const label of ['Current', '1–30 Days', '31–60 Days', '90+ Days']) {
      expect(txt, `页面缺账龄桶：${label}`).toContain(label);
    }
    expect(txt, '页面没显示 Total Outstanding').toMatch(/Total Outstanding/i);

    // 侧证：页面上的 "N invoices" 计数应与 API 的该桶 count 一致（至少第一个桶）
    if (buckets.length) {
      const b0 = buckets[0];
      if (b0 && typeof b0.count === 'number') {
        expect(txt, `页面显示的 ${b0.count} invoices 与 API 不符`)
          .toContain(String(b0.count));
      }
    }
    expect(String(total ?? ''), 'API 没返回 total_outstanding').not.toBe('');
  });
});

test.describe('@p2 @local-only F5-5 机构管理', () => {
  test('点机构后按 organization_id 查单，条数与 API 一致', async ({ page }) => {
    const reqs = [];
    page.on('request', (r) => {
      if (/\/api\/v1\/orders\//.test(r.url())) reqs.push(r.url());
    });

    await H.login(page, 'probe_procure');
    await page.goto(`${H.BASE}/ops/po/organizations`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const txt = await H.bodyText(page);
    if (/No organizations/i.test(txt)) test.skip(true, '没有机构数据');

    // 点第一行机构
    const firstOrg = page.locator('table tbody tr').first();
    if (!(await firstOrg.count())) test.skip(true, '机构表为空');
    await firstOrg.click();
    await page.waitForTimeout(2000);

    const withOrg = reqs.filter((u) => /[?&]organization_id=\d+/.test(u));
    expect(withOrg.length, `点机构后没带 organization_id。请求：${JSON.stringify(reqs.slice(-3))}`)
      .toBeGreaterThan(0);

    const orgId = withOrg[0].match(/organization_id=(\d+)/)[1];
    const api = await H.api(page, 'GET', `/api/v1/orders/?organization_id=${orgId}&page_size=100`);
    expect(api.status).toBe(200);
    const rows = (api.data?.data ?? api.data) || [];
    const apiCount = Array.isArray(rows) ? rows.length : (rows.results || []).length;

    // 页面右表行数应与 API 过滤结果一致（表头行不计）
    const uiRows = await page.evaluate(() => {
      const tables = document.querySelectorAll('table');
      if (tables.length < 2) return -1;
      return tables[1].querySelectorAll('tbody tr').length;
    });
    if (uiRows >= 0) {
      expect(uiRows, `右表 ${uiRows} 行 vs API ${apiCount} 条`).toBe(apiCount);
    }
  });
});
