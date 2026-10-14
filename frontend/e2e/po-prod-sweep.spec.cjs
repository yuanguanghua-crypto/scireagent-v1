/**
 * 生产环境 · PO 功能【全面浏览器巡检】（只读，不写入数据）
 *
 * 覆盖：所有 PO 页面（客户侧 5 + 内部台 5）× 所有角色（匿名 / 客户 / staff / procurement）
 *       × 跳转 + 按钮 + 关键控件 + 白屏检测 + 权限门禁。
 *
 * ⚠️ 只读：不提交/不审批/不发货/不开票/不收款 ⇒ 不产生生产数据。
 * ⚠️ 登录限流：生产 LoginRateThrottle = 5/min/IP ⇒ 本 spec **每角色只登录一次**（共 3 次），
 *    并内置 429 重试（等 65s 窗口重置）。
 * 运行：剥代理 + workers=1 --project=chromium --output=<目录> -g "@po-prod"
 */
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.PROD_BASE || 'https://scireagent.com';
const BASIC = { username: 'scire01', password: process.env.PROD_BASIC_PASS || 'RalyeNdTsXWfN3Pc' };
const CUST = { u: 'e2e_customer', p: 'E2ePass123!' };
const STAFF = { u: 'admin', p: 'admin123' };
const PROC = { u: 'proc_mgr', p: 'E2ePass123!' };

test.use({ httpCredentials: BASIC, baseURL: BASE_URL });

const CUST_PAGES = ['/po/submit', '/po/orders', '/po/addresses', '/po/reorder', '/po/downloads'];
const INT_PAGES = ['/ops/po/review', '/ops/po/shipments', '/ops/po/invoicing', '/ops/po/ar', '/ops/po/organizations'];

/** 登录（含 429 限流重试）。 */
async function login(page, { u, p }) {
  for (let attempt = 0; attempt < 4; attempt++) {
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('input[placeholder="Enter your username"]').fill(u);
    await page.locator('input[placeholder="Enter your password"]').fill(p);
    await page.getByRole('button', { name: 'Sign In' }).click();
    try {
      await page.waitForURL((url) => !/\/login/.test(url.toString()), { timeout: 10000 });
      return;
    } catch {
      const txt = await page.locator('body').innerText().catch(() => '');
      if (/429|Too Many/i.test(txt)) {
        await page.waitForTimeout(65000); // 等限流窗口重置
        continue;
      }
      await page.waitForTimeout(2000);
    }
  }
  throw new Error(`登录失败（含限流重试后）: ${u}`);
}

/** 断言"页面真渲染，非白屏"，并收集 console/page error。 */
async function assertRendered(page, path) {
  const errs = [];
  const onConsole = (m) => { if (m.type() === 'error') errs.push(m.text()); };
  const onErr = (e) => errs.push(String(e));
  page.on('console', onConsole);
  page.on('pageerror', onErr);
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  const appLen = await page.evaluate(() => (document.querySelector('#app')?.innerHTML || '').length);
  page.off('console', onConsole);
  page.off('pageerror', onErr);
  expect(appLen, `${path} 白屏检测（#app 长度）`).toBeGreaterThan(200);
  const fatal = errs.filter((e) => !/favicon|\.ico/.test(e));
  expect(fatal, `${path} console/page error: ${fatal.join(' | ')}`).toEqual([]);
}

test.describe('@po-prod 生产 PO 全面巡检', () => {
  test('匿名：所有 PO 页（客户侧 + 内部台）→ 落 /login', async ({ page }) => {
    test.setTimeout(120000);
    for (const p of [...CUST_PAGES, ...INT_PAGES]) {
      await page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' });
      await page.waitForURL(/\/login/, { timeout: 15000 });
    }
  });

  test('客户：5 页可渲染 + 内部台被拦 + 提交页控件齐全', async ({ page }) => {
    test.setTimeout(240000);
    await login(page, CUST);
    for (const p of CUST_PAGES) await assertRendered(page, p);
    for (const p of INT_PAGES) {
      await page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1500);
      const u = page.url();
      // 客户应被拦：SPA 守卫跳 /（或 /login）；不应停留在内部台
      expect(/\/(ops|admin)\/po\//.test(u), `客户访问 ${p} 不应停留，实得 ${u}`).toBe(false);
    }
    // 提交页关键控件
    await page.goto(`${BASE_URL}/po/submit`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1.po-page-title', { hasText: 'Submit Purchase Order' })).toBeVisible();
    await expect(page.getByText(/PO Number（可选）/)).toBeVisible();
    await expect(page.getByText(/Quote \/ Reference #/)).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add Line Item' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Submit PO' })).toBeVisible();
    await page.getByRole('button', { name: '+ Add Line Item' }).click();
    await expect(page.locator('.po-table')).toBeVisible();
  });

  test('staff：内部台 5 页可渲染 + 审核台库存列', async ({ page }) => {
    test.setTimeout(240000);
    await login(page, STAFF);
    for (const p of INT_PAGES) await assertRendered(page, p);
    await page.goto(`${BASE_URL}/ops/po/review`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1.po-page-title', { hasText: 'Order Review Desk' })).toBeVisible();
    if (await page.locator('.po-card').count() > 0) {
      await page.getByRole('button', { name: /View Items/ }).first().click();
      await expect(page.locator('th', { hasText: 'Available' }).first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('procurement（非 staff）：内部台 5 页可渲染（守卫修复验证）', async ({ page }) => {
    test.setTimeout(240000);
    await login(page, PROC);
    for (const p of INT_PAGES) await assertRendered(page, p);
  });
});
