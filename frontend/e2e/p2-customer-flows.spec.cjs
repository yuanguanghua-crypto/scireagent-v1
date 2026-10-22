/**
 * Batch 3 / P2-6~P2-8 —— 客户侧三个 PART 补深
 *   F3-2 个人资料：Shipping/Contact 保存、改密码假成功锁定
 *   F3-6 订单详情：quoted 状态下 Accept Quote 成功路径
 *   F3-9 PO 单详情：发票区渲染 + 下载按钮发请求
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p2 @local-only F3-2 个人资料', () => {
  test('保存昵称确实落库（不是只弹 toast）', async ({ page }) => {
    await H.login(page, 'probe_ouser_a');
    await page.goto(`${H.BASE}/settings`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    const nick = `probe-${Date.now()}`;
    // ★ 用 placeholder 精确定位（按位置取会拿到页头搜索框 / Avatar URL —— 实测踩过）
    const nickBox = page.locator('input[placeholder="Your display name"]').first();
    expect(await nickBox.count(), '找不到昵称输入框').toBeGreaterThan(0);
    await nickBox.fill(nick);

    const save = page.getByRole('button', { name: /Save Changes/i }).first();
    expect(await save.count(), '找不到 Save Changes').toBeGreaterThan(0);
    await save.click();
    await page.waitForTimeout(2000);

    const me = await H.api(page, 'GET', '/api/v1/auth/me');
    const u = me.data?.data?.user || me.data?.data || {};
    expect(String(u.nickname || ''), `昵称未落库（页面填了 ${nick}，API 返回 ${u.nickname}）`)
      .toContain('probe-');
  });

  test('★ 缺陷锁定：Update Password 是假成功（零请求）', async ({ page }) => {
    const reqs = [];
    page.on('request', (r) => {
      const u = r.url();
      if (/password|auth\/profile/i.test(u) && r.method() !== 'GET') reqs.push(`${r.method()} ${u}`);
    });

    await H.login(page, 'probe_ouser_a');
    await page.goto(`${H.BASE}/settings`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    const sec = page.getByText(/^Security$/i).first();
    if (await sec.count()) await sec.click();
    await page.waitForTimeout(800);

    const pw = page.locator('input[type="password"]');
    if ((await pw.count()) < 3) test.skip(true, 'Security 面板结构变了');
    await pw.nth(0).fill('Whatever#123');
    await pw.nth(1).fill('NewPass#2026');
    await pw.nth(2).fill('NewPass#2026');

    const btn = page.getByRole('button', { name: /Update Password/i }).first();
    await btn.click();
    await page.waitForTimeout(1800);

    const txt = await H.bodyText(page);
    expect(txt, '没出现"即将上线"提示 —— 若已实现，请更新说明书 §11.2 #1').toMatch(
      /Password update feature will be available soon/i,
    );
    // 关键：没有任何写请求
    const writes = reqs.filter((r) => !/PUT \/api\/v1\/auth\/profile/.test(r));
    expect(writes.length, '改密码开始发请求了 —— 若已实现，请更新 §11.2 #1 与本用例').toBe(0);
  });
});

test.describe('@p2 @local-only F3-6 报价应答', () => {
  test('quoted 状态出现 Accept/Reject，点 Accept 后状态推进', async ({ page }) => {
    const IDS = H.ids();
    await H.login(page, 'probe_ouser_a');
    await page.goto(`${H.BASE}/orders/${IDS.order_quoted}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const txt = await H.bodyText(page);
    const pre = await H.api(page, 'GET', `/api/v1/orders/${IDS.order_quoted}/`);
    const preStatus = (pre.data?.data ?? pre.data)?.status;
    if (preStatus !== 'quoted') {
      // 硬规 3「可重复」：本用例会推进状态，重跑前必须重置夹具
      test.skip(true, `订单当前状态=${preStatus}，不是 quoted；先跑 scripts/probe_seed_all.py 重置夹具`);
    }
    expect(txt, 'quoted 订单没显示报价提示').toMatch(/quote has been provided|Accept Quote/i);

    const accept = page.getByRole('button', { name: /Accept Quote/i }).first();
    expect(await accept.count(), '没有 Accept Quote 按钮').toBeGreaterThan(0);

    const [resp] = await Promise.all([
      page.waitForResponse((r) => /confirm-quote/.test(r.url())),
      accept.click(),
    ]);
    expect([200, 201]).toContain(resp.status());

    await page.waitForTimeout(1500);
    const detail = await H.api(page, 'GET', `/api/v1/orders/${IDS.order_quoted}/`);
    const st = (detail.data?.data ?? detail.data)?.status;
    expect(['quote_accepted', 'confirmed'], `接受报价后状态是 ${st}`).toContain(st);
  });

  test('别人的 quoted 订单不能接受（越权）', async ({ page }) => {
    const IDS = H.ids();
    await H.login(page, 'probe_ouser_b');       // B 机构的客户
    const r = await H.api(page, 'POST', `/api/v1/orders/${IDS.order_quoted}/confirm-quote/`,
      { action: 'accept' });
    expect([403, 404], `跨用户接受报价得 ${r.status}`).toContain(r.status);
  });
});

test.describe('@p2 @local-only F3-9 PO 单详情与下载', () => {
  test('已开票订单详情渲染发票区，点下载发请求', async ({ page }) => {
    const IDS = H.ids();
    const hits = [];
    page.on('request', (r) => {
      if (/\/invoices\/\d+\/pdf\//.test(r.url())) hits.push(r.url());
    });

    await H.login(page, 'probe_ouser_a');
    await page.goto(`${H.BASE}/po/orders/${IDS.order_invoiced}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const txt = await H.bodyText(page);
    expect(txt, '详情页没渲染出发票区').toMatch(/Invoice/i);
    expect(txt, '缺 RUO 声明（合规要求）').toMatch(/Research Use Only/i);

    const dl = page.getByRole('button', { name: /Download PDF/i }).first();
    if (!(await dl.count())) test.skip(true, '该订单没有可下载的发票 PDF（pdf_path 为空）');
    await dl.click();
    await page.waitForTimeout(1500);
    expect(hits.length, '点下载没发请求').toBeGreaterThan(0);
  });

  test('别人的 PO 单读不到（越权）', async ({ page }) => {
    const IDS = H.ids();
    await H.login(page, 'probe_ouser_b');
    const r = await H.api(page, 'GET', `/api/v1/orders/${IDS.order_invoiced}/`);
    expect([403, 404], `跨机构读订单得 ${r.status}`).toContain(r.status);
  });
});
