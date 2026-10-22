/**
 * 说明书事实核验 · 第三批 —— admin_role 的 Assign Rep（唯一独有能力）
 * 单独成文件：换身份必须换浏览器上下文，同 context 里 localStorage 清理会与导航竞态（上一轮实测 ERR_ABORTED）
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

test('F-10b admin_role 点 Assign Rep —— 是否真的成功', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const denied = [];
  const okResponses = [];
  page.on('response', async (r) => {
    const u = new URL(r.url()).pathname;
    if (u.includes('assign-rep')) {
      okResponses.push(`${r.status()} ${r.request().method()} ${u}`);
      if (r.status() === 403) denied.push(u);
    }
  });

  await login(page, 'probe_adminrole');
  // 自证身份
  const who = await page.evaluate(() => ({
    role: localStorage.getItem('role'),
    isStaff: localStorage.getItem('is_staff'),
  }));

  await page.goto(`${BASE}/ops/po/review`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);

  const repInput = page.locator('input[placeholder="Rep ID"]').first();
  const hasRep = await repInput.count();
  let clicked = false;
  if (hasRep) {
    await repInput.fill('probe_staff');
    const btn = page.getByRole('button', { name: /^Assign Rep$/i }).first();
    if (await btn.count()) { await btn.click(); clicked = true; }
    await page.waitForTimeout(2500);
  }

  const toasts = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.el-message, .el-message__content, .el-notification'))
      .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 4));

  fact('assign_rep_admin_role', {
    identity: who, hasRepIdInput: hasRep > 0, clicked,
    assignRepResponses: okResponses, toasts,
    pageExcerpt: (await page.evaluate(() =>
      (document.getElementById('app')?.innerText || '').replace(/\s+/g, ' '))).slice(0, 240),
  });
  await ctx.close();
});
