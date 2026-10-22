/**
 * 说明书事实核验 · 第二批 —— 2026-10-22
 *
 * 深挖三个仍属"读码推断"的断言：
 *   1. 登录页「重发验证邮件」点击后到底发生了什么（是否真发请求、是否抛错）
 *   2. procurement 打开订单详情页 /ops/orders/:id 是否同样不可用
 *   3. PO 审核台的「Assign Rep」对 procurement 是否真是一点就 403 的死按钮
 */
const { test, expect } = require('@playwright/test');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5174';
const PW = 'Probe#2026!';

function fact(name, payload) {
  console.log('[FACT] ' + JSON.stringify({ name, ...payload }));
}

async function login(page, username, password = PW) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(username);
  await page.locator('input[placeholder="Enter your password"]').fill(password);
  await page.getByRole('button', { name: /Sign In/i }).click();
  await page.waitForTimeout(2500);
}

test.describe.configure({ mode: 'serial' });

test.describe('@probe 说明书事实核验 2', () => {
  test('F-06b 重发验证邮件：是否真发请求 / 是否抛错', async ({ page }) => {
    const reqs = [];
    const errs = [];
    page.on('request', (r) => {
      if (/resend|verif/i.test(r.url())) reqs.push(`${r.method()} ${new URL(r.url()).pathname}`);
    });
    page.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 150)));
    // async 函数里抛错是 unhandledrejection，pageerror 抓不到 ⇒ 必须单独注入监听
    await page.addInitScript(() => {
      window.__unhandled = [];
      window.addEventListener('unhandledrejection', (e) => {
        window.__unhandled.push(String((e.reason && e.reason.message) || e.reason).slice(0, 150));
      });
    });

    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('input[placeholder="Enter your username"]').fill('probe_unverified');
    await page.locator('input[placeholder="Enter your password"]').fill(PW);
    await page.getByRole('button', { name: /Sign In/i }).click();
    await page.waitForTimeout(2500);

    const before = reqs.length;
    await page.getByRole('button', { name: /Resend verification email/i }).first().click();
    await page.waitForTimeout(2000);
    const after = reqs.length;

    fact('resend_verification_click', {
      requestCountBefore: before,
      requestCountAfter: after,
      newRequests: reqs.slice(before),
      unhandled: await page.evaluate(() => window.__unhandled || []),
      pageerrors: errs,
      pageText: await page.evaluate(() => (document.getElementById('app')?.innerText || '').replace(/\s+/g, ' ').slice(0, 300)),
    });
  });

  test('F-09 procurement 打开订单详情页 —— 是否可用', async ({ page }) => {
    const denied = [];
    page.on('response', (r) => {
      if (r.status() === 403 || r.status() === 401) denied.push(`${r.status()} ${new URL(r.url()).pathname}`);
    });
    await login(page, 'probe_procure');
    await page.goto(`${BASE}/ops/orders/1`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    fact('procurement_ops_order_detail', {
      url: page.url(),
      denied: denied.slice(0, 6),
      text: await page.evaluate(() => (document.getElementById('app')?.innerText || '').replace(/\s+/g, ' ').slice(0, 400)),
    });
  });

  test('F-10 PO 审核台 Assign Rep 真点 —— procurement 与 admin_role 对比', async ({ page }) => {
    const denied = [];
    page.on('response', (r) => {
      if (r.status() === 403) denied.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
    });

    for (const who of ['probe_procure', 'probe_adminrole']) {
      await page.context().clearCookies();
      await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
      await page.evaluate(() => localStorage.clear());
      await login(page, who);
      await page.goto(`${BASE}/ops/po/review`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2500);

      const cards = await page.evaluate(() => document.querySelectorAll('.po-card, [class*=card]').length);
      const repInput = page.locator('input[placeholder="Rep ID"]').first();
      const hasRep = await repInput.count();
      let clicked = false;
      if (hasRep) {
        await repInput.fill('probe_staff');
        const btn = page.getByRole('button', { name: /^Assign Rep$/i }).first();
        if (await btn.count()) { await btn.click(); clicked = true; }
        await page.waitForTimeout(2000);
      }

      // 抓 Element Plus 的 toast 文本（点后是否给了反馈、内容是什么）
      const toasts = await page.evaluate(() =>
        Array.from(document.querySelectorAll('.el-message, .el-message__content, .el-notification'))
          .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 4));

      fact('assign_rep_click', {
        identity: who, cards, hasRepIdInput: hasRep > 0, clicked,
        toasts,
        denied403: denied.slice(-4),
        pageText: (await page.evaluate(() => (document.getElementById('app')?.innerText || '').replace(/\s+/g, ' '))).slice(0, 260),
      });
    }
  });
});
