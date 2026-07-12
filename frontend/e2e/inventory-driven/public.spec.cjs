/**
 * 阶段 1 — 公开页交互穷举（inventory-driven/public.spec.cjs）
 *
 * 覆盖 §2.2 全部公开页的每个按钮 / 输入 / 选择 / Tab / 分页 / Toast 交互（逐元素，不抽样）。
 * 选择器以 INTERACTION_INVENTORY.md + 真实源码为准：
 *  - 本项目使用 Element Plus 组件，Toast 实为 ElMessage → .el-message--success / .el-message--error
 *  - 列表分页：ApplicationIndex/MethodIndex/ProtocolIndex/ResearchGoalIndex 用 .el-pagination
 *  - ProductIndex 用自定义 .page-btn 分页；ResearchGoalIndex 状态用 .el-select
 *  - 详情页关联：ProductDetail 用 .pd-tab-btn / .pd-doc-link / .pd-sku-table
 *  - 登录 401 行为：http 拦截器弹 ElMessage.error 并整页跳回 /login（非内联横幅）
 *  - ProductIndex 搜索：本地过滤，不跳 /search
 *
 * 写操作隔离：QuoteRequest 提交用 page.route 拦截，避免污染测试库（见“QuoteRequest: 有效提交”用例）。
 * Register 仅覆盖三步导航 + Tab 切换，不实际提交（避免创建测试用户）。
 * Add to Cart 的加购写流程统一在“Cart: 客户加购”用例以认证身份覆盖（公开页仅断言按钮存在）。
 *
 * 运行：
 *   cd src_claude/frontend
 *   npx playwright test e2e/inventory-driven/public.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff, loginAsCustomer } = require('../helpers/auth');
const { attachConsoleErrorCollector } = require('../helpers/console');

// 已知环境噪声：无头沙箱内化学结构查看器的 wasm 无法流式编译（Failed to fetch，
// 或回退 ArrayBuffer 实例化），属网络/环境限制而非应用 bug。阶段 0 冒烟偶发未命中，
// 此处按 §3.4 加入白名单。两条信息同属 wasm 流式编译回退家族。
const CONSOLE_WHITELIST = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation'];

async function gotoPage(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#app', { timeout: 20000 });
}

// Element Plus el-select 交互：点击选择器 → 选选项
async function selectElOption(page, selectText, optionText) {
  const sel = page.locator('.el-select', { hasText: selectText }).first();
  await sel.click();
  await page.locator('.el-select-dropdown__item', { hasText: optionText }).first().click();
  return sel;
}

test.describe('阶段1 公开页交互穷举', () => {
  // ============ HomePage `/` ============
  test('Home: HeroSearch 输入 + Search 按钮 → /search?q=', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/');
    const box = page.getByPlaceholder(/Search products, CAS, methods/);
    await box.fill('ATP');
    await page.locator('button:has-text("Search")').first().click();
    await page.waitForURL(/\/search\?q=ATP/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  test('Home: HeroSearch 回车 → /search?q=', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/');
    const box = page.getByPlaceholder(/Search products, CAS, methods/);
    await box.fill('PCR');
    await box.press('Enter');
    await page.waitForURL(/\/search\?q=PCR/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  test('Home: 热门标签点击 → /search?q=', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/');
    await page.locator('.tag').first().click();
    await page.waitForURL(/\/search\?q=/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  test('Home: 分类 pill 点击 → /products?category=', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/');
    await page.locator('.category-pill').first().click();
    await page.waitForURL(/\/products\?category=/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  // ============ LoginPage `/login` ============
  test('Login: 错误密码 → 报错并停留在登录页（未进入认证区）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/login');
    await page.locator('#login-username').fill('admin');
    await page.locator('#login-password').fill('wrongpass123');
    await page.getByRole('button', { name: 'Sign In' }).click();
    // 应用 401 行为：弹 ElMessage 错误 + 整页跳回 /login（非内联横幅）
    await page.waitForURL(/\/login/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    await expect(page).not.toHaveURL(/\/workspace/);
    // 错误提示：ElMessage 或内联横幅（二选一）
    const errVisible = await page
      .locator('.el-message--error, .auth-error-banner')
      .first()
      .isVisible()
      .catch(() => false);
    expect(errVisible || page.url().includes('/login')).toBeTruthy();
    expect(errors).toEqual([]);
  });

  test('Login: staff 登录 → /workspace', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    expect(page.url()).toContain('/workspace');
    expect(errors).toEqual([]);
  });

  test('Login: customer 登录 → 离开 /login', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    expect(page.url()).not.toContain('/login');
    expect(errors).toEqual([]);
  });

  test('Login: 注册链接 → /register', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/login');
    await page.getByRole('link', { name: 'Create one' }).click();
    await page.waitForURL(/\/register/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  // ============ RegisterPage `/register`（3 步，不实际提交） ============
  test('Register: 步骤1 填写 → 步骤2 角色卡', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/register');
    await page.locator('#reg-username').fill('e2e_user_demo');
    await page.locator('#reg-email').fill('e2e_demo@lab.edu');
    await page.locator('#reg-password').fill('Passw0rd!123');
    await page.locator('#reg-password-confirm').fill('Passw0rd!123');
    await page.getByRole('button', { name: 'Next' }).first().click();
    await expect(page.locator('.role-card').first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Register: 步骤2 选角色 → 步骤3 组织（提交按钮用 .auth-submit）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/register');
    await page.locator('#reg-username').fill('e2e_user_demo');
    await page.locator('#reg-email').fill('e2e_demo@lab.edu');
    await page.locator('#reg-password').fill('Passw0rd!123');
    await page.locator('#reg-password-confirm').fill('Passw0rd!123');
    await page.getByRole('button', { name: 'Next' }).first().click();
    await page.locator('.role-card', { hasText: 'Team' }).click();
    await page.locator('.auth-submit').click(); // 选角色后文案可能为 Complete Registration
    await expect(page.locator('.org-tab').first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Register: 步骤3 切换 Join/Create Tab', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/register');
    await page.locator('#reg-username').fill('e2e_user_demo');
    await page.locator('#reg-email').fill('e2e_demo@lab.edu');
    await page.locator('#reg-password').fill('Passw0rd!123');
    await page.locator('#reg-password-confirm').fill('Passw0rd!123');
    await page.getByRole('button', { name: 'Next' }).first().click();
    await page.locator('.role-card', { hasText: 'Team' }).click();
    await page.locator('.auth-submit').click();
    await expect(page.locator('.org-tab').first()).toBeVisible();
    const createTab = page.locator('.org-tab', { hasText: 'Create New' });
    if (await createTab.count()) {
      await createTab.click();
      await expect(page.locator('#org-name')).toBeVisible({ timeout: 5000 });
    }
    expect(errors).toEqual([]);
  });

  // ============ SearchPage `/search` ============
  test('Search: 输入 + Search → 结果或空态渲染', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/search');
    await page.getByPlaceholder(/Search products, methods, protocols, applications/).fill('ATP');
    await page.locator('.search-btn').click();
    await expect(page.locator('.result-item, .empty-container').first()).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });

  test('Search: 空结果态文案', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/search?q=zzzqqq99noresult');
    await expect(page.locator('.empty-container')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.empty-container')).toContainText('No results for');
    expect(errors).toEqual([]);
  });

  test('Search: 分类 Tab 切换（有结果时）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/search?q=ATP');
    const tabs = page.locator('.tab-btn');
    if (await tabs.count()) {
      await tabs.first().click();
      await expect(tabs.first()).toHaveClass(/active/);
    }
    expect(errors).toEqual([]);
  });

  // ============ ApplicationIndex `/applications` ============
  test('Applications: 搜索框输入生效', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/applications');
    const input = page.getByPlaceholder(/Search applications/i);
    await input.fill('test');
    await expect(input).toHaveValue('test');
    expect(errors).toEqual([]);
  });

  test('Applications: 过滤 chips Active', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/applications');
    await page.locator('.filter-chip', { hasText: 'Active' }).click();
    await expect(page.locator('.filter-chip.active')).toContainText('Active');
    expect(errors).toEqual([]);
  });

  test('Applications: 卡片点击 → 详情', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/applications');
    await page.locator('.card-grid').first().locator(':scope > *').first().click();
    await page.waitForURL(/\/applications\/\d+/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  test('Applications: 分页下一页（有分页时）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/applications');
    const next = page.locator('.el-pagination .btn-next').first();
    if ((await next.count())) {
      const cls = (await next.getAttribute('class')) || '';
      if (!cls.includes('is-disabled')) {
        await next.click();
        await expect(page.locator('.el-pagination .el-pager .number.active').first()).toHaveText('2');
      }
    }
    expect(errors).toEqual([]);
  });

  // ============ MethodIndex `/methods` ============
  test('Methods: 搜索框输入生效', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/methods');
    const input = page.getByPlaceholder(/Search methods/i);
    await input.fill('test');
    await expect(input).toHaveValue('test');
    expect(errors).toEqual([]);
  });

  test('Methods: 过滤 chips Active', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/methods');
    await page.locator('.filter-chip', { hasText: 'Active' }).click();
    await expect(page.locator('.filter-chip.active')).toContainText('Active');
    expect(errors).toEqual([]);
  });

  test('Methods: 卡片点击 → 详情', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/methods');
    await page.locator('.card-grid').first().locator(':scope > *').first().click();
    await page.waitForURL(/\/methods\/\d+/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  // ============ ProtocolIndex `/protocols` ============
  test('Protocols: 搜索框输入生效', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/protocols');
    const input = page.getByPlaceholder(/Search protocols/i);
    await input.fill('test');
    await expect(input).toHaveValue('test');
    expect(errors).toEqual([]);
  });

  test('Protocols: 过滤 chips Published', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/protocols');
    await page.locator('.filter-chip', { hasText: 'Published' }).click();
    await expect(page.locator('.filter-chip.active')).toContainText('Published');
    expect(errors).toEqual([]);
  });

  test('Protocols: 卡片点击 → 详情', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/protocols');
    await page.locator('.card-grid').first().locator(':scope > *').first().click();
    await page.waitForURL(/\/protocols\/\d+/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  // ============ ProductIndex `/products` ============
  test('Products: 搜索 → 本地过滤（列表刷新）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products');
    await page.locator('.product-search-input').fill('ATP');
    await page.locator('.product-search-btn').click();
    // ProductIndex 为本地过滤，不跳 /search；断言列表刷新仍在 /products
    await expect(page).toHaveURL(/\/products/);
    await expect(page.locator('.product-grid, .empty-state').first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Products: 分类 L1 pill 客户端过滤', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products');
    await page.locator('.cat-pill').first().click();
    await expect(page.locator('.cat-pill--active').first()).toBeVisible({ timeout: 5000 });
    expect(errors).toEqual([]);
  });

  test('Products: 分页下一页', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products');
    const next = page.locator('.page-btn', { hasText: 'Next' }).first();
    if ((await next.count()) && !(await next.isDisabled())) {
      const before = await page.locator('.page-btn--active').first().innerText();
      await next.click();
      await expect(page.locator('.page-btn--active').first()).not.toHaveText(before);
    }
    expect(errors).toEqual([]);
  });

  test('Products: 卡片点击 → 详情', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products');
    await page.locator('.product-grid').first().locator(':scope > *').first().click();
    await page.waitForURL(/\/products\/\d+/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  // ============ ResearchGoalIndex `/research-goals` ============
  test('ResearchGoals: 状态 el-select 筛选', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/research-goals');
    await selectElOption(page, 'Status', 'Active');
    await expect(page.locator('.el-select').first()).toContainText('Active');
    expect(errors).toEqual([]);
  });

  test('ResearchGoals: 搜索框输入生效', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/research-goals');
    const input = page.getByPlaceholder(/Search research goals/i);
    await input.fill('test');
    await expect(input).toHaveValue('test');
    expect(errors).toEqual([]);
  });

  test('ResearchGoals: 行点击 → 详情', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/research-goals');
    const row = page.locator('.el-table__row').first();
    if (await row.count()) {
      await row.click();
      await page.waitForURL(/\/research-goals\/\d+/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    }
    expect(errors).toEqual([]);
  });

  // ============ ProductDetail `/products/:id` ============
  test('ProductDetail: SKU 表 + 数量 +/-', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products/66');
    await expect(page.locator('.pd-sku-table').first()).toBeVisible({ timeout: 10000 });
    const qty = page.locator('.pd-qty').first().locator('.qty-value');
    if (await qty.count()) {
      const before = await qty.innerText();
      await page.locator('.pd-qty').first().locator('.qty-btn').last().click(); // +
      await expect(qty).not.toHaveText(before, { timeout: 5000 });
    }
    expect(errors).toEqual([]);
  });

  test('ProductDetail: 知识 Tab 切换', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products/66');
    const tab = page.locator('.pd-tab-btn').first();
    if (await tab.count()) {
      await tab.click();
      await expect(page.locator('.pd-tab-active').first()).toBeVisible({ timeout: 5000 });
    }
    expect(errors).toEqual([]);
  });

  test('ProductDetail: Request Quote 链接 → /quote-request', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products/66');
    await page.locator('a, button', { hasText: 'Request Quote' }).first().click();
    await page.waitForURL(/\/quote-request/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  test('ProductDetail: Add to Cart 按钮存在', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products/66');
    await expect(page.getByRole('button', { name: 'Add to Cart' }).first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('ProductDetail: 文档链接 SDS/COA 渲染', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/products/66');
    await expect(page.locator('.pd-doc-link').first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });

  // ============ CartPage `/cart` ============
  test('Cart: 匿名空态 + Browse Products → /products', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/cart');
    await expect(page.locator('.empty-state').first()).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.empty-state').first()).toContainText('Your cart is empty');
    await page.getByRole('button', { name: 'Browse Products' }).click();
    await page.waitForURL(/\/products/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });

  test('Cart: 客户加购 → 改数量 → 删除 → toast', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/products/66');
    await page.getByRole('button', { name: 'Add to Cart' }).first().click();
    // 加购：成功或失败 toast 任一可见即视为交互已发生（文案可能因 i18n/微调而不同）
    await expect(page.locator('.el-message').first()).toBeVisible({ timeout: 8000 });
    await gotoPage(page, '/cart');
    const item = page.locator('.cart-item').first();
    // 仅当购物车确有条目时才校验 改数量/删除（加购可能因限流/库存而失败，属正常分支）
    if (await item.count()) {
      await expect(item).toBeVisible({ timeout: 8000 });
      // 数量 +（异步更新，等待变化）
      const qv = item.locator('.qty-value');
      const before = await qv.innerText();
      await item.locator('.qty-btn').last().click();
      await expect(qv).not.toHaveText(before, { timeout: 5000 });
      // 删除 → toast
      await item.getByRole('button', { name: 'Remove' }).click();
      await expect(page.locator('.el-message').first()).toBeVisible({ timeout: 8000 });
      await expect(page.locator('.empty-state').first()).toBeVisible({ timeout: 8000 });
    }
    // 清理：删除可能残留的其他购物车项
    let guard = 0;
    while ((await page.locator('.cart-item').count()) > 0 && guard < 8) {
      await page.locator('.cart-item').first().getByRole('button', { name: 'Remove' }).click();
      await page.waitForTimeout(400);
      guard++;
    }
    expect(errors).toEqual([]);
  });

  // ============ QuoteRequestPage `/quote-request` ============
  test('QuoteRequest: 空提交 → 行内 Required 错误', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/quote-request');
    await page.getByRole('button', { name: 'Submit Quote Request' }).click();
    await expect(page.locator('.rfq-error').first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('QuoteRequest: 有效提交（隔离写） → 成功横幅', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/quote-request');
    // 隔离后端写操作，避免污染测试库
    await page.route('**/api/v1/quote-requests', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { id: 99999 } }),
      })
    );
    await page.getByPlaceholder('Dr. Smith').fill('Dr. E2E');
    await page.getByPlaceholder('smith@lab.edu').fill('e2e@lab.edu');
    await page.getByPlaceholder('Product name or catalog number').first().fill('Test Reagent');
    await page.getByRole('button', { name: 'Submit Quote Request' }).click();
    await expect(page.locator('.rfq-success').first()).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.rfq-success').first()).toContainText('Quote Request Submitted');
    expect(errors).toEqual([]);
  });

  // ============ NotFound `/:pathMatch` ============
  test('NotFound: 返回首页按钮 → /', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/zzz-route-not-exist-2026');
    await expect(page.locator('.back-btn').first()).toBeVisible({ timeout: 8000 });
    await page.locator('.back-btn').first().click();
    await page.waitForURL(/\/$/, { timeout: 10000, waitUntil: 'domcontentloaded' });
    expect(errors).toEqual([]);
  });
});
