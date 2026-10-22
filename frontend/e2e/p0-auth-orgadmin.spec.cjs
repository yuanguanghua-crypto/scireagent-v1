/**
 * Batch 1 / P0-2 + P0-3 —— F2-1 未验证登录被拒 & F4-1 机构管理员零影响
 *
 * P0-2 为什么重要：`/login` 的「重发验证邮件」按钮**读的是不存在的 form.email**，
 *   点击后不发请求、也没提示——但此前没有任何用例锁住它。
 *   本用例**故意断言"点击后零请求"**：一旦有人修好按钮，这里会立刻变红，提醒更新文档。
 *
 * P0-3 为什么重要：`is_org_admin` 对权限零影响。不锁住的话，
 *   将来有人给它加权限（哪怕合理），也不会有任何告警。
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p0 @local-only F2-1 未验证用户登录被拒', () => {
  test('登录返回 403 提示，且重发按钮点了不发请求（缺陷锁定）', async ({ page }) => {
    const resends = [];
    page.on('request', (r) => {
      if (/resend-verification/.test(r.url())) resends.push(r.url());
    });

    await page.goto(`${H.BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('input[placeholder="Enter your username"]').fill('probe_unverified');
    await page.locator('input[placeholder="Enter your password"]').fill(H.PW);
    await page.getByRole('button', { name: /Sign In/i }).click();
    await page.waitForTimeout(2500);

    const txt = await H.bodyText(page);
    expect(txt, '未显示"邮箱未验证"提示').toMatch(/not been verified|not verified/i);
    // 仍停在登录页
    expect(page.url()).toContain('/login');

    const before = resends.length;
    const btn = page.getByRole('button', { name: /Resend verification email/i }).first();
    expect(await btn.count(), '重发按钮不存在（说明 UI 变了，需更新本文档）').toBeGreaterThan(0);
    await btn.click();
    await page.waitForTimeout(2000);

    // ★ 缺陷锁定：当前点击**不发任何请求**
    expect(resends.length, '重发按钮开始发请求了 —— 若这是修复，请更新说明书 §11.2 #2',
    ).toBe(before);

    const after = await H.bodyText(page);
    expect(after, '出现"已发送"字样但没发请求 = 假成功').not.toMatch(
      /A new verification link has been sent/i,
    );

    // 侧证：确实拿不到 token（认证层被拒）
    const tok = await page.evaluate(() => localStorage.getItem('token'));
    expect(tok, '未验证用户竟然拿到了 token').toBeFalsy();
  });

  test('未验证账号 API 侧登录同样 403，且错误文案说明原因', async ({ page }) => {
    await page.goto(`${H.BASE}/login`, { waitUntil: 'domcontentloaded' });
    const r = await page.evaluate(async ({ base, pw }) => {
      const res = await fetch(`${base}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'probe_unverified', password: pw }),
      });
      return { status: res.status, body: await res.json() };
    }, { base: H.BASE, pw: H.PW });

    expect(r.status).toBe(403);
    const msg = JSON.stringify(r.body);
    expect(msg, '403 但没说原因').toMatch(/not verified/i);
  });
});

test.describe('@p0 @local-only F4-1 is_org_admin 零影响（否定命题锁定）', () => {
  async function identityAndBadge(page, username) {
    // 用独立 context，避免 localStorage 串味
    const ctx = await page.context().browser().newContext();
    const p = await ctx.newPage();
    await H.login(p, username);
    const me = await H.api(p, 'GET', '/api/v1/auth/me');

    await p.goto(`${H.BASE}/settings`, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(1500);
    const acct = p.getByText(/^Account$/i).first();
    if (await acct.count()) await acct.click();
    await p.waitForTimeout(800);

    const badge = await p.locator('.badge.badge-success').filter({ hasText: /^Admin$/ }).count();
    const txt = await H.bodyText(p);

    // 越权探测：能否进内部台 / 能否写产品
    await p.goto(`${H.BASE}/workspace`, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(2000);
    const wsUrl = p.url();
    const writeProduct = await H.api(p, 'POST', '/api/v1/products/', { name: 'probe-x' });

    await ctx.close();
    return {
      me: me.data?.data || {},
      badge, wsUrl, hasAdminRow: /Organization Admin/.test(txt),
      writeStatus: writeProduct.status,
    };
  }

  test('org_admin 与普通客户：除徽章外逐项相同', async ({ page }) => {
    const a = await identityAndBadge(page, 'probe_orgadmin');
    const b = await identityAndBadge(page, 'probe_researcher');

    // 1) 差异只在 is_org_admin
    expect(a.me.is_org_admin, 'org_admin 账号的 is_org_admin 应为 true').toBe(true);
    expect(b.me.is_org_admin, '对照账号的 is_org_admin 应为 false').toBe(false);
    expect(a.me.role, 'role 不应因 is_org_admin 改变').toBe(b.me.role);
    expect(a.me.is_staff).toBe(b.me.is_staff);
    expect(a.me.is_superuser).toBe(b.me.is_superuser);

    // 2) UI：只有 org_admin 显示徽章
    expect(a.badge, 'org_admin 的 Account 面板缺 Admin 徽章').toBeGreaterThan(0);
    expect(b.badge, '普通客户不该有 Admin 徽章').toBe(0);

    // 3) 权限：内部台都进不去、写产品都 403 —— 完全一致
    expect(a.wsUrl, 'org_admin 不该能进 /workspace').not.toContain('/workspace');
    expect(b.wsUrl, 'researcher 不该能进 /workspace').not.toContain('/workspace');
    expect(a.writeStatus, 'org_admin 竟然能写产品（说明 is_org_admin 被赋予了权限）').toBe(403);
    expect(b.writeStatus).toBe(403);
  });
});
