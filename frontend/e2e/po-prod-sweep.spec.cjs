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
 *
 * ★ 2026-10-18 安全修正：**生产口令不再硬编码在仓库里**（原为真实可用的生产口令）。
 *   改为**环境变量注入**，沿用项目既有命名（见 e2e/README.md §3）：
 *     第 1 层 nginx Basic ：E2E_BASIC_USER / E2E_BASIC_PASS
 *     第 2 层 应用层登录   ：E2E_USER / E2E_PASS（staff）
 *                            E2E_CUSTOMER_USER / E2E_CUSTOMER_PASS（客户）
 *                            E2E_PROC_USER / E2E_PROC_PASS（内部采购，非 staff）
 *   口令来源：服务器 deploy/CREDENTIALS.txt（权限 600，**不在仓库内**）。
 *   ⚠️ 缺任一必需项 ⇒ **整份 spec 清晰跳过**（不硬跑、不用假账号）。
 */
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.PROD_BASE || process.env.BASE_URL || 'https://scireagent.com';

// ── 第 1 层：nginx Basic Auth（浏览器原生弹框那一层）──
const BASIC = {
  username: process.env.E2E_BASIC_USER || '',
  password: process.env.E2E_BASIC_PASS || process.env.PROD_BASIC_PASS || '',
};
// ── 第 2 层：应用层登录（三个角色）──
const CUST = {
  u: process.env.E2E_CUSTOMER_USER || '',
  p: process.env.E2E_CUSTOMER_PASS || '',
};
const STAFF = {
  u: process.env.E2E_USER || '',
  p: process.env.E2E_PASS || '',
};
const PROC = {
  u: process.env.E2E_PROC_USER || '',
  p: process.env.E2E_PROC_PASS || '',
};

/**
 * 必需凭据清单（缺一即跳过整份 spec）。
 * 绝不回落到任何默认口令 —— 宁可"不跑"，也不拿猜的口令硬跑出一堆看不懂的错。
 */
const REQUIRED = [
  ['E2E_BASIC_USER', BASIC.username], ['E2E_BASIC_PASS', BASIC.password],
  ['E2E_CUSTOMER_USER', CUST.u], ['E2E_CUSTOMER_PASS', CUST.p],
  ['E2E_USER', STAFF.u], ['E2E_PASS', STAFF.p],
  ['E2E_PROC_USER', PROC.u], ['E2E_PROC_PASS', PROC.p],
];
const MISSING = REQUIRED.filter(([, v]) => !v).map(([k]) => k);
const SKIP_REASON =
  `缺少生产凭据环境变量：${MISSING.join(', ')}。\n` +
  '  ⇒ 请从服务器 deploy/CREDENTIALS.txt 取对应口令后注入（口令**不入库**）。\n' +
  '  ⇒ 两层认证互不相通：nginx Basic 与 Django 登录各需一套账号。';

test.use({ httpCredentials: BASIC, baseURL: BASE_URL });

const CUST_PAGES = ['/po/submit', '/po/orders', '/po/addresses', '/po/reorder', '/po/downloads'];
const INT_PAGES = ['/ops/po/review', '/ops/po/shipments', '/ops/po/invoicing', '/ops/po/ar', '/ops/po/organizations', '/ops/inventory'];

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
  // ★ 缺生产凭据 ⇒ 整份 spec 清晰跳过（不硬跑、不用假口令）。
  test.skip(MISSING.length > 0, SKIP_REASON);

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
