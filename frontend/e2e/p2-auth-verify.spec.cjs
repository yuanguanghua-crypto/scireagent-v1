/**
 * Batch 3 / P2-4~P2-5 —— 邮箱验证的两个边角
 *   F1-9 邮箱验证：无 token、坏 token 的失败态
 *   F2-2 重走验证链接：过期 token
 *
 * 已知缺陷（说明书 §11.2 #3）：失败态下 "Resend verification email" 按钮**永不显示**
 *   （外层 `v-if="email"`，而 email 只在成功路径赋值）⇒ 链接过期后用户没有任何自助入口。
 *   本文件把这条锁死。
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p2 @local-only F1-9 邮箱验证失败态', () => {
  test('无 token 打开 ⇒ 明确提示缺 token，不是白屏', async ({ page }) => {
    await page.goto(`${H.BASE}/verify-email`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    const txt = await H.bodyText(page);
    expect(txt.length, '页面白屏').toBeGreaterThan(60);
    expect(txt, '没有提示缺少 token').toMatch(/Missing verification token|missing.*token/i);
  });

  test('坏 token ⇒ 失败提示', async ({ page }) => {
    await page.goto(`${H.BASE}/verify-email?token=probe-invalid-token`, {
      waitUntil: 'domcontentloaded',
    });
    await page.waitForTimeout(2500);
    const txt = await H.bodyText(page);
    expect(txt, '坏 token 没有失败提示').toMatch(/failed|invalid|expired/i);
  });

  test('★ 缺陷锁定：失败态下没有"重发验证邮件"入口', async ({ page }) => {
    await page.goto(`${H.BASE}/verify-email?token=probe-invalid-token`, {
      waitUntil: 'domcontentloaded',
    });
    await page.waitForTimeout(2500);
    const btn = page.getByRole('button', { name: /Resend verification email/i });
    expect(
      await btn.count(),
      '失败态出现了重发按钮 —— 若这是修复，请更新说明书 §11.2 #3 与本用例',
    ).toBe(0);
  });

  test('合法 UUID 格式但不存在 ⇒ 400 + 明确文案', async ({ page }) => {
    await page.goto(`${H.BASE}/login`, { waitUntil: 'domcontentloaded' });
    const uuid = '11111111-1111-1111-1111-111111111111';
    const r = await H.anonApi(page, 'GET', `/api/v1/auth/verify-email?token=${uuid}`);
    expect(r.status, `有效格式但不存在应 400，实得 ${r.status}`).toBe(400);
    expect(JSON.stringify(r.data || {})).toMatch(/Invalid or expired/i);
  });

  test('★ 缺陷锁定：畸形 token（非 UUID）⇒ 500（应为 400）', async ({ page }) => {
    // 实测：`verify-email` 用 UUIDField 解析 token，非 UUID 字符串直接抛 ValidationError
    //   → 未捕获 → **500 + HTML 错误页**（不是 JSON 信封）。
    //   前端若拼错 URL 或用户手改，就会看到白屏错误页而非"链接无效"。
    await page.goto(`${H.BASE}/login`, { waitUntil: 'domcontentloaded' });
    const r = await page.evaluate(async ({ base }) => {
      const res = await fetch(`${base}/api/v1/auth/verify-email?token=probe-invalid-token`);
      return { status: res.status, ctype: res.headers.get('content-type') || '' };
    }, { base: H.BASE });
    expect(r.status, '行为变了：若已修为 400，请更新说明书 §11.2 与本用例').toBe(500);
    expect(r.ctype, '500 但返回了 JSON —— 与预期不符').toMatch(/html/i);
  });
});

test.describe('@p2 @local-only F2-2 重走验证链接', () => {
  test('API 侧：重发验证对未验证账号应被接受（无论是否真的发出）', async ({ page }) => {
    await page.goto(`${H.BASE}/login`, { waitUntil: 'domcontentloaded' });
    const r = await page.evaluate(async ({ base }) => {
      const res = await fetch(`${base}/api/v1/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'probe_unverified@probe.local' }),
      });
      return { status: res.status, body: await res.json().catch(() => null) };
    }, { base: H.BASE });

    // 设计上应该 200/201/202（无论邮箱是否存在，避免枚举）；
    // 若返回 5xx 或 4xx 说明接口本身有问题
    expect(r.status, `重发接口返回 ${r.status}：${JSON.stringify(r.body).slice(0, 200)}`)
      .toBeLessThan(500);
    expect([200, 201, 202, 204], `重发接口异常状态 ${r.status}`).toContain(r.status);
  });

  test('★ 缺陷锁定：登录页的重发按钮走 UI 时不发请求（见 F2-1）', async ({ page }) => {
    // 与 p0-auth-orgadmin 呼应：这里只断言"接口本身是好的"，坏的是登录页的调用点
    const reqs = [];
    page.on('request', (r) => {
      if (/resend-verification/.test(r.url())) reqs.push(r.url());
    });
    await page.goto(`${H.BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('input[placeholder="Enter your username"]').fill('probe_unverified');
    await page.locator('input[placeholder="Enter your password"]').fill(H.PW);
    await page.getByRole('button', { name: /Sign In/i }).click();
    await page.waitForTimeout(2200);
    const btn = page.getByRole('button', { name: /Resend verification email/i }).first();
    if (await btn.count()) await btn.click();
    await page.waitForTimeout(1500);
    expect(reqs.length, '登录页重发开始发请求了 —— 若已修复，请更新 §11.2 #2 与本用例').toBe(0);
  });
});
