/**
 * 内部台访问控制 · procurement（非 staff）可达性回归（2026-10-17）
 *
 * 缺陷本体：2026-10-14 路由层（router/index.js requiresAdmin）已放行 procurement，
 *   但 9 个 workspace 页面组件各留了一份只认 `auth.isStaff` 的旧守卫
 *   ⇒ 非 staff 的 procurement 过路由层后被页面层 `router.replace('/')` 踢回首页
 *   ⇒「口径对齐」修复实际无效。
 * 修法：语义收敛到 `src/utils/internalAccess.js`（口径 = is_staff || role∈(procurement,admin)，
 *   与后端 core/permissions.py:44 IsProcurementOrAdmin 一致），路由/页面/Header 统一调用。
 *
 * 本 spec 覆盖三层（都是本次改动触及的判定点）：
 *   1. workspace 内部台页面（页面层守卫本体 —— 缺陷就在这里）
 *   2. 登录后落地页（LoginPage：此前只认 isStaff，procurement 登录被送回首页）
 *   3. Header 下拉里的 Workspace / Order Management 入口可见性
 *
 * ★ 安全边界同样要验：普通注册用户（e2e_customer, role=researcher）必须仍被踢回首页。
 * ⚠ 只读：不提交/不审批/不发货/不开票/不收款 ⇒ 不产生数据。
 * ⚠ 串行：playwright.config.cjs 已锁 workers=1（共用 dev 库）。
 *
 * 运行：DB_ENGINE=sqlite 起 backend:8000 + frontend:5173，
 *      node node_modules/@playwright/test/cli.js test e2e/internal-access-procurement.spec.cjs \
 *        --project=chromium --reporter=line --output=./e2e-artifacts-ia --retries=0
 */
const { test, expect } = require('@playwright/test');
const { loginAsProcurement, loginAsCustomer, loginAsStaff, BASE_URL } = require('./helpers/auth.cjs');

/** workspace 下的实体页（本次修的 9 个守卫所在页面，抽 4 个代表性页面做浏览器级验证）。 */
const WS_PAGES = ['/workspace', '/workspace/products', '/workspace/goals', '/workspace/references'];

/** 断言"没被踢回首页"：URL 仍停留在 workspace 内部台，且 #app 有实质内容（非白屏）。 */
async function assertStaysOnWorkspace(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  const url = page.url();
  expect(url, `${path} 被踢离了 workspace（实得 ${url}）——页面层守卫未修复`).toMatch(/\/workspace/);
  const len = await page.evaluate(() => (document.querySelector('#app')?.innerHTML || '').length);
  expect(len, `${path} 白屏（#app 长度）`).toBeGreaterThan(200);
}

test.describe('@local-only @readonly 内部台可达性 · procurement（非 staff）', () => {
  test('procurement：workspace 4 页均不被页面层守卫踢回', async ({ page }) => {
    test.setTimeout(120000);
    await loginAsProcurement(page);
    // 守卫自证：登录后 store 确实是 { isStaff:false, role:'procurement' }
    const st = await page.evaluate(() => ({
      isStaff: localStorage.getItem('is_staff'),
      role: localStorage.getItem('role'),
    }));
    expect(st.isStaff, 'fixture 前提：procurement 必须是 is_staff=false').toBe('false');
    expect(st.role).toBe('procurement');

    for (const p of WS_PAGES) await assertStaysOnWorkspace(page, p);
  });

  test('procurement：登录后直接落到 /workspace（不被送去首页）', async ({ page }) => {
    test.setTimeout(60000);
    await loginAsProcurement(page);
    await page.waitForTimeout(1200);
    expect(page.url(), 'procurement 登录后应落到 workspace').toMatch(/\/workspace/);
  });

  test('procurement：Header 下拉可见 Workspace 与 Order Management 入口', async ({ page }) => {
    test.setTimeout(60000);
    await loginAsProcurement(page);
    // ⚠ 布局分三套（AppLayout.vue）：
    //   public 页(/ 等，meta.nav==='public') → PublicNav（条目 class 是 .nav-user-item）
    //   /workspace → AdminLayout 自带侧栏，无顶栏
    //   其余（/ops/orders、/settings…）→ AppHeader（条目 class 是 .dropdown-item）
    // 本用例验AppHeader ⇒ 选 /ops/orders，且下拉默认收起，须先点 .user-avatar 展开。
    await page.goto(`${BASE_URL}/ops/orders`, { waitUntil: 'domcontentloaded' });
    await page.locator('.user-avatar').first().click();
    await expect(page.locator('.dropdown-item', { hasText: 'Workspace' })).toBeVisible();
    await expect(page.locator('.dropdown-item', { hasText: 'Order Management' })).toBeVisible();
  });

  test('★ 安全边界：普通注册用户（researcher）仍被踢回首页', async ({ page }) => {
    test.setTimeout(60000);
    await loginAsCustomer(page);
    for (const p of WS_PAGES) {
      await page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1200);
      expect(page.url(), `researcher 不应停留在 ${p}`).not.toMatch(/\/workspace/);
    }
  });

  test('staff 回归：仍可进 workspace（本次改动未误伤既有路径）', async ({ page }) => {
    test.setTimeout(60000);
    await loginAsStaff(page);
    await assertStaysOnWorkspace(page, '/workspace/products');
  });
});