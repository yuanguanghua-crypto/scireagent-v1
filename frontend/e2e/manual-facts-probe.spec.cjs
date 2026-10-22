/**
 * 说明书事实核验（实测层）—— 2026-10-22
 *
 * 目的：把 SITE_ROLE_OPERATION_MANUAL.md 里**靠读代码得出**的断言，改为**真实浏览器观察**。
 * 每个 case 都只做「观察 + 记录」，断言取宽（能记录到事实即可），因为目的是取证不是防回归。
 * 产出：控制台逐条打印 `[FACT] ...`，由 scripts/collect_manual_facts.py 汇总成 JSON。
 *
 * 运行栈（与开发栈隔离）：
 *   后端 127.0.0.1:8011  ← DB 副本 db_probe.sqlite3（probe_* 账号）
 *   前端 127.0.0.1:5174  ← VITE_API_PROXY 指向 8011
 *   命令：BASE_URL=http://127.0.0.1:5174 npx playwright test manual-facts-probe --project=chromium
 *
 * ⚠️ 必须剥代理：本机 http_proxy=127.0.0.1:56679 会把回环请求转发出去（实测得 502）
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

/** 统计页面主区域的表格行数（Element Plus 与原生 table 都覆盖） */
async function rowCount(page) {
  return page.evaluate(() => {
    const el = document.querySelectorAll('.el-table__body-wrapper tbody tr').length;
    const native = document.querySelectorAll('table tbody tr').length;
    return Math.max(el, native);
  });
}

/** 抓页面上的可见文本（用于判断空态/错误横幅/统计数字） */
async function mainText(page) {
  return page.evaluate(() => (document.getElementById('app')?.innerText || '').replace(/\s+/g, ' ').slice(0, 600));
}

test.describe.configure({ mode: 'serial' });

test.describe('@probe 说明书事实核验', () => {
  test('F-01 procurement 打开 /ops/orders —— 是否真的空白', async ({ page }) => {
    const res403 = [];
    page.on('response', (r) => {
      if (r.status() === 403 || r.status() === 401) res403.push(`${r.status()} ${new URL(r.url()).pathname}`);
    });
    await login(page, 'probe_procure');
    await page.goto(`${BASE}/ops/orders`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const out = {
      url: page.url(),
      rows: await rowCount(page),
      text: await mainText(page),
      denied: res403.slice(0, 6),
    };
    fact('procurement_ops_orders', out);
    // 取证不设强断言：只要抓到事实即可
    expect(typeof out.rows).toBe('number');
  });

  test('F-02 procurement 打开 /workspace/verified —— 是否真的空白', async ({ page }) => {
    const res403 = [];
    page.on('response', (r) => {
      if (r.status() === 403 || r.status() === 401) res403.push(`${r.status()} ${new URL(r.url()).pathname}`);
    });
    await login(page, 'probe_procure');
    await page.goto(`${BASE}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    fact('procurement_workspace_verified', {
      url: page.url(), rows: await rowCount(page), text: await mainText(page), denied: res403.slice(0, 6),
    });
  });

  test('F-03 procurement 打开 /workspace 首页 —— 统计卡是否有数据', async ({ page }) => {
    const res403 = [];
    page.on('response', (r) => {
      if (r.status() === 403) res403.push(`${r.status()} ${new URL(r.url()).pathname}`);
    });
    await login(page, 'probe_procure');
    await page.goto(`${BASE}/workspace`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    fact('procurement_workspace_home', {
      url: page.url(), text: await mainText(page), denied: res403.slice(0, 6),
    });
  });

  test('F-04 procurement 打开 /workspace/products —— 能看但写被拒', async ({ page }) => {
    const res403 = [];
    page.on('response', (r) => {
      if (r.status() === 403) res403.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
    });
    await login(page, 'probe_procure');
    await page.goto(`${BASE}/workspace/products`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    const before = await rowCount(page);

    // 点第一行的 Actions 菜单（若存在），记录菜单里有哪些项 —— 这些项对采购本应禁用
    let menuItems = [];
    try {
      const actionsBtn = page.locator('button', { hasText: /Actions/i }).first();
      if (await actionsBtn.count()) {
        await actionsBtn.click({ timeout: 5000 });
        await page.waitForTimeout(800);
        menuItems = await page.evaluate(() =>
          Array.from(document.querySelectorAll('[role="menu"] *, .el-dropdown-menu__item, .menu-item'))
            .map((e) => (e.innerText || '').trim()).filter((t) => t && t.length < 30).slice(0, 12));
        await page.keyboard.press('Escape');
      }
    } catch (e) {
      menuItems = ['(打开菜单失败: ' + e.message.slice(0, 60) + ')'];
    }

    fact('procurement_products_page', {
      url: page.url(), rows: before, menuItems, deniedWhileLoading: res403.slice(0, 8),
      text: (await mainText(page)).slice(0, 400),
    });
  });

  test('F-05 researcher /settings 改密码 —— 是否假成功', async ({ page }) => {
    await login(page, 'probe_researcher');
    await page.goto(`${BASE}/settings`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    // 切到 Security tab（文案可能为 Security）
    const secTab = page.getByText(/^Security$/i).first();
    if (await secTab.count()) await secTab.click();
    await page.waitForTimeout(800);

    const inputs = page.locator('input[type="password"]');
    const n = await inputs.count();
    if (n >= 3) {
      await inputs.nth(0).fill('Whatever#123');
      await inputs.nth(1).fill('NewPass#2026');
      await inputs.nth(2).fill('NewPass#2026');
    }
    const btn = page.getByRole('button', { name: /Update Password/i }).first();
    let clicked = false;
    if (await btn.count()) { await btn.click(); clicked = true; }
    await page.waitForTimeout(1500);

    fact('settings_password_change', {
      passwordInputs: n, clicked, text: await mainText(page),
    });
  });

  test('F-06 未验证用户登录 + 点重发验证 —— 是否崩', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (e) => errors.push('pageerror: ' + e.message.slice(0, 120)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 120)); });

    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('input[placeholder="Enter your username"]').fill('probe_unverified');
    await page.locator('input[placeholder="Enter your password"]').fill(PW);
    await page.getByRole('button', { name: /Sign In/i }).click();
    await page.waitForTimeout(2500);
    const afterLogin = await mainText(page);

    const resend = page.getByRole('button', { name: /Resend verification email/i }).first();
    const hasResend = await resend.count();
    let afterClick = '';
    if (hasResend) {
      await resend.click();
      await page.waitForTimeout(1500);
      afterClick = await mainText(page);
    }
    fact('unverified_login_resend', {
      hasResendButton: hasResend > 0, afterLogin, afterClick, errors: errors.slice(0, 8),
    });
  });

  test('F-07 researcher 访问 /workspace —— 是否被踢回首页', async ({ page }) => {
    await login(page, 'probe_researcher');
    await page.goto(`${BASE}/workspace`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    fact('researcher_workspace_redirect', { url: page.url() });
  });

  test('F-08 token 失效后请求 —— 是否整页跳登录', async ({ page }) => {
    await login(page, 'probe_researcher');
    // 把 token 改成非法值，再触发一次需要认证的请求
    await page.evaluate(() => localStorage.setItem('token', 'invalid-token-for-probe'));
    await page.goto(`${BASE}/orders`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    fact('expired_token_behaviour', {
      url: page.url(), token: await page.evaluate(() => localStorage.getItem('token')),
      text: (await mainText(page)).slice(0, 200),
    });
  });
});
