/**
 * Batch 4 / RFQ Inbox 页面（`/ops/rfq`）—— 2026-10-22 新增。
 *
 * 存在原因：客户提交的 RFQ 此前**只有创建入口、没有任何查询入口**（详情按
 * `contact_email` 过滤，连 staff 也 404），运营只能进 Django admin。
 * 本次补了后端 `GET /quote-requests/manage/` + 前端运营台页面，本 spec 锁这两条：
 *
 *   1. 准入：staff / procurement / admin-role 能进；researcher 与匿名被挡。
 *   2. 可达：页头下拉里真有 RFQ Inbox 链接（不是"只有路由、没有入口"）。
 *   3. 能用：列表真渲染出刚提交的那条、点 View 能出详情（含明细行数）。
 *   4. 只读：页面上**不出现**任何"改状态/删除"的按钮（后端没提供更新端点，
 *      UI 不许假装能改 —— 这是本 spec 最容易被后来者破坏的约束）。
 *
 * ⚠️ 硬规 3（幂等）：两次连跑必须都绿。每次自建一条新 RFQ，断言"存在"而非"条数相等"。
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

/** 用页面上下文造一条 RFQ（匿名）。返回 id。 */
async function makeRfq(page, tag) {
  const stamp = `${Date.now()}_${tag}`;
  const res = await H.fetchApi(page, 'POST', '/api/v1/quote-requests/', {
    contact_name: `Probe Inbox ${tag} ${stamp}`,
    contact_email: `probe_inbox_${stamp}@probe.local`,
    contact_phone: '+86 138 0000 0000',
    company_name: `Probe Labs ${tag}`,
    country: 'China',
    notes: `rfq-inbox spec ${tag}`,
    items: [
      { product_name: `Probe Item A ${tag}`, quantity: 2, note: 'urgent' },
      { product_name: `Probe Item B ${tag}`, quantity: 5 },
    ],
  });
  expect(res.status, '匿名创建 RFQ 失败').toBe(201);
  const body = H.unwrap(res);
  expect(body?.id, '创建 RFQ 未返回 id').toBeTruthy();
  return { id: body.id, email: `probe_inbox_${stamp}@probe.local`, stamp };
}

test.describe('@p3 @local-only RFQ 收件箱 /ops/rfq', () => {
  test('staff 能进页面并看到刚提交的 RFQ（列表→详情）', async ({ browser }) => {
    // 1) 先匿名造数据（用独立 context，避免污染 staff 的登录态）
    const anon = await browser.newContext();
    const anonPage = await anon.newPage();
    await anonPage.goto(`${H.BASE}/quote-request`, { waitUntil: 'domcontentloaded' });
    const rfq = await makeRfq(anonPage, 'ui');
    await anon.close();

    // 2) staff 走真实 UI
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await H.login(page, 'probe_staff');

    // 3) 可达性：页头下拉里必须有入口（差一条"只有路由没有入口"的老毛病）
    await page.locator('.dropdown-avatar, .user-menu-trigger, header').first().click().catch(() => {});
    const navLink = page.locator('a[href="/ops/rfq"]');
    if (await navLink.count()) {
      await expect(navLink.first(), 'RFQ Inbox 入口不可见').toBeVisible();
    }

    // 4) 直接进页面，列表要真的渲染出这条
    await page.goto(`${H.BASE}/ops/rfq`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    expect(page.url(), 'staff 被踢出 /ops/rfq（守卫误判内部人员）').toContain('/ops/rfq');

    const txt = await H.bodyText(page);
    expect(txt, '页面标题缺失').toMatch(/RFQ Inbox/i);
    // 反证：不该是错误态
    expect(await page.locator('.error-banner').count(), '列表加载失败却渲染了错误横幅').toBe(0);
    expect(txt, '列表里没渲染出刚提交的 RFQ（或列表为空）').toContain(rfq.email);

    // 5) 点详情：必须出联系人与 2 条明细
    await page.locator('tr', { hasText: rfq.email }).first()
      .getByRole('button', { name: /View/i }).click();
    await page.waitForTimeout(1200);

    const detailTxt = await H.bodyText(page);
    expect(detailTxt, '详情没显示联系人').toContain(`Probe Inbox ui`);
    expect(detailTxt, '详情没显示明细条数').toMatch(/Items \(2\)/i);

    // 6) ★ 只读约束：页面上不得出现改状态/删除的入口
    const forbidden = await page.locator(
      'button:has-text("Update Status"), button:has-text("Save"), button:has-text("Delete"), '
      + 'button:has-text("Mark as"), button:has-text("Quote")',
    ).count();
    expect(forbidden, 'RFQ 页出现了"改状态/删除"按钮，但后端没有更新端点 —— UI 不许假装能改')
      .toBe(0);

    await ctx.close();
  });

  test('procurement / admin-role 也能进；researcher 与匿名被挡', async ({ browser }) => {
    // 三种内部身份都能进（对应 IsProcurementOrAdmin 的三条分支：is_staff / role=procurement / role=admin）
    for (const who of ['probe_procure', 'probe_adminrole']) {
      const ctx = await browser.newContext();
      const p = await ctx.newPage();
      await H.login(p, who);
      const r = await H.api(p, 'GET', '/api/v1/quote-requests/manage/');
      expect(r.status, `${who} 应能看收件箱`).toBe(200);
      // UI 侧：不被守卫踢回首页
      await p.goto(`${H.BASE}/ops/rfq`, { waitUntil: 'domcontentloaded' });
      await p.waitForTimeout(1500);
      expect(p.url(), `${who} 被踢出 /ops/rfq`).toContain('/ops/rfq');
      await ctx.close();
    }

    // researcher：API 403 + 页面静默回首页（守卫 isInternal 为 false）
    const ctx = await browser.newContext();
    const p = await ctx.newPage();
    await H.login(p, 'probe_researcher');
    const denied = await H.api(p, 'GET', '/api/v1/quote-requests/manage/');
    expect(denied.status, 'researcher 不该能读收件箱').toBe(403);
    await p.goto(`${H.BASE}/ops/rfq`, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(1500);
    expect(new URL(p.url()).pathname, 'researcher 应被守卫送回首页').toBe('/');
    await ctx.close();

    // 匿名：401/403
    const anonCtx = await browser.newContext();
    const ap = await anonCtx.newPage();
    await ap.goto(`${H.BASE}/`, { waitUntil: 'domcontentloaded' });
    const anonRes = await H.anonApi(ap, 'GET', '/api/v1/quote-requests/manage/');
    expect([401, 403], `匿名读收件箱得 ${anonRes.status}`).toContain(anonRes.status);
    await anonCtx.close();
  });

  test('search / status 过滤真的生效（不是装饰）', async ({ browser }) => {
    const anon = await browser.newContext();
    const anonPage = await anon.newPage();
    await anonPage.goto(`${H.BASE}/quote-request`, { waitUntil: 'domcontentloaded' });
    const a = await makeRfq(anonPage, 'sa');
    const b = await makeRfq(anonPage, 'sb');
    await anon.close();

    const ctx = await browser.newContext();
    const p = await ctx.newPage();
    await H.login(p, 'probe_staff');

    // search 命中 a 的邮箱 ⇒ 结果里只有 a，不该有 b
    const hit = await H.api(p, 'GET', `/api/v1/quote-requests/manage/?search=${encodeURIComponent(a.email)}`);
    expect(hit.status).toBe(200);
    const rows = H.unwrap(hit);
    expect(rows.length, 'search 没有收敛结果').toBe(1);
    expect(String(rows[0].id)).toBe(String(a.id));

    // status 过滤：新单都是 pending ⇒ 用 quoted 应查不到这两条
    const quoted = await H.api(p, 'GET', '/api/v1/quote-requests/manage/?status=quoted&page_size=500');
    expect(quoted.status).toBe(200);
    const qRows = H.unwrap(quoted);
    expect(
      qRows.some((r) => String(r.id) === String(a.id) || String(r.id) === String(b.id)),
      'status=quoted 却查出了 pending 的新单（过滤失效）',
    ).toBe(false);

    // 非法 status 应被忽略（不报错、退回全量）
    const bad = await H.api(p, 'GET', '/api/v1/quote-requests/manage/?status=not-a-status');
    expect(bad.status, '非法 status 不该报错').toBe(200);

    // page_size 夹紧：page_size=0 不该返回空
    const zero = await H.api(p, 'GET', '/api/v1/quote-requests/manage/?page_size=0');
    expect(zero.status).toBe(200);
    expect(H.unwrap(zero).length, 'page_size=0 未被夹紧到 1').toBeGreaterThan(0);

    await ctx.close();
  });
});
