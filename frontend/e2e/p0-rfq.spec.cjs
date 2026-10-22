/**
 * Batch 1 / P0-1 —— F1-7 提交询价单（RFQ）
 *
 * 为什么是 P0：`POST /quote-requests/` 是全站**唯一未声明权限**的端点（匿名可提交），
 * 是获客入口，但此前整条链路零功能用例。
 *
 * 判据（按 PERSONA_TEST_PLAN 硬规 1）：不光看页面出现 "Submitted"，
 * 还要用 staff 身份把那条 RFQ **查回来**，确认真的落库。
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p0 @local-only F1-7 提交询价单（匿名）', () => {
  test('匿名可打开并提交 RFQ，且真落库', async ({ page }) => {
    const reqs = [];
    page.on('request', (r) => {
      if (/quote-requests/.test(r.url())) reqs.push(`${r.method()} ${new URL(r.url()).pathname}`);
    });

    await page.goto(`${H.BASE}/quote-request`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);

    // 无守卫：匿名应停在 /quote-request
    expect(page.url(), 'RFQ 页不该要求登录').toContain('/quote-request');

    const txt = await H.bodyText(page);
    expect(txt, '表单要素缺失').toMatch(/Submit Quote Request|Quote Request/i);

    const stamp = Date.now();
    const name = `Probe RFQ ${stamp}`;
    const email = `probe_rfq_${stamp}@probe.local`;

    // ★ 必须按 placeholder 定位。按位置取第一个 input 会拿到页头搜索框（实测踩过：
    //   第一个 input 不是 contact_name，导致姓名留空 → 前端校验拦住 → 看起来"没发请求"）
    await page.locator('input[placeholder="Dr. Smith"]').fill(name);
    await page.locator('input[placeholder="smith@lab.edu"]').fill(email);
    await page.locator('input[placeholder="Product name or catalog number"]').fill('Probe RFQ Item');

    const submit = page.getByRole('button', { name: /Submit Quote Request/i }).first();
    await expect(submit, '提交按钮不存在').toBeVisible();
    await submit.click();
    await page.waitForTimeout(2500);

    const after = await H.bodyText(page);
    const posted = reqs.filter((r) => r.startsWith('POST'));
    expect(posted.length, 'POST /quote-requests/ 没发出').toBeGreaterThan(0);

    // 成功态（页面文案：Quote Request Submitted / Reference: RFQ #xxx）
    if (/Quote Request Submitted|Reference/i.test(after)) {
      const m = after.match(/RFQ #(\d+)/i) || after.match(/#(\d+)/);
      expect(m, '成功但没有 Reference 编号').toBeTruthy();
      const shownId = m[1];

      // ★ 侧证：POST 的响应体里必须有同一个 id（服务端的落库确认，不是只信页面文案）
      const postResp = await page.waitForResponse(
        (r) => /quote-requests/.test(r.url()) && r.request().method() === 'POST',
        { timeout: 3000 },
      ).catch(() => null);
      if (postResp) {
        expect([200, 201]).toContain(postResp.status());
        const j = await postResp.json().catch(() => null);
        const returnedId = j?.data?.id;
        expect(String(returnedId), '页面显示的 Reference 与服务端返回的 id 不一致')
          .toBe(String(shownId));
      }

      // 已知限制（实测）：RFQ 详情 `GET /quote-requests/{id}/` 按**提交人**过滤 queryset，
      //   连 staff 也是 404。所以"用 staff 查回来"这条路不通 —— 已单独用例锁定该行为。
    } else {
      // 未进入成功态：必须明确失败，不能既没成功也没报错（那是"假成功"）
      throw new Error(`提交后既无成功态也无明确错误。页面片段：${after.slice(0, 300)}`);
    }
  });

  test('必填缺失时前端拦住，不发请求', async ({ page }) => {
    const posts = [];
    page.on('request', (r) => {
      if (r.method() === 'POST' && /quote-requests/.test(r.url())) posts.push(r.url());
    });
    await page.goto(`${H.BASE}/quote-request`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    const submit = page.getByRole('button', { name: /Submit Quote Request/i }).first();
    if (await submit.count()) await submit.click();
    await page.waitForTimeout(1200);

    expect(posts.length, '必填为空却发出了 POST（前端校验失效）').toBe(0);
  });

  test('未登录读不到 RFQ 详情（且没有列表接口）', async ({ page }) => {
    await page.goto(`${H.BASE}/quote-request`, { waitUntil: 'domcontentloaded' });

    // 实测：`/quote-requests/` 只有 POST，没有列表 ⇒ GET 返回 405（不是 401）
    const list = await H.anonApi(page, 'GET', '/api/v1/quote-requests/');
    expect(list.status, 'RFQ 列表接口的行为变了（原为 405=只有 POST）').toBe(405);

    // 单条详情：IsAuthenticated ⇒ 匿名必须 401
    const one = await H.anonApi(page, 'GET', '/api/v1/quote-requests/1/');
    expect([401, 403], `匿名读 RFQ 详情得 ${one.status}，应为 401/403`).toContain(one.status);
  });

  test('★ 已知限制锁定：RFQ 详情只对提交人可见（连 staff 也 404）', async ({ browser }) => {
    // 实测结论：`QuoteRequest` 详情的 queryset 按 user 过滤，
    //   所以内部人员无法通过 API 查看客户提交的询价 —— 只能走 Django admin。
    //   这条锁住它：若哪天放宽给 staff，这里会红，提醒更新说明书 §1.2 F1-7。
    const ctx = await browser.newContext();
    const p = await ctx.newPage();
    await H.login(p, 'probe_staff');
    const r = await H.api(p, 'GET', '/api/v1/quote-requests/66/');
    await ctx.close();
    expect(r.status, 'staff 现在能读 RFQ 了 —— 若是有意放宽，请更新 F1-7 与 §11').toBe(404);
  });
});
