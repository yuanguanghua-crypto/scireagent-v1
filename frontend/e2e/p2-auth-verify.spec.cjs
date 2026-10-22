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

  test('★ 畸形 token（非 UUID）⇒ 400 + 链接无效（2026-10-22 已修，原为 500）', async ({ page }) => {
    // 历史缺陷：`verify-email` 用 UUIDField 解析 token，非 UUID 字符串抛
    //   `django.core.exceptions.ValidationError`（**不是** ValueError），原 `except` 漏捕
    //   → 500 + HTML 错误页（不是 JSON 信封），用户看到白屏而不是"链接无效"。
    //   已改为 400 + 与"合法但不存在"同一条文案。本条锁**修复后**的行为。
    await page.goto(`${H.BASE}/login`, { waitUntil: 'domcontentloaded' });
    const r = await page.evaluate(async ({ base }) => {
      const res = await fetch(`${base}/api/v1/auth/verify-email?token=probe-invalid-token`);
      let body = null;
      try { body = await res.json(); } catch (_) { body = null; }
      return {
        status: res.status,
        ctype: res.headers.get('content-type') || '',
        body,
      };
    }, { base: H.BASE });

    expect(r.status, '畸形 token 必须 400（回退到 500 说明 ValidationError 又漏捕了）').toBe(400);
    expect(r.ctype, '错误响应必须是 JSON，不能再回 HTML 错误页').toMatch(/json/i);
    // 文案不能泄露内部异常类型；与"合法但不存在"保持一致
    expect(JSON.stringify(r.body || {})).toMatch(/Invalid or expired/i);
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
