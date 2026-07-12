/**
 * 阶段 2 — 认证流程穷举（inventory-driven/auth.spec.cjs）
 *
 * 覆盖 §4 阶段2：登录/注册/设置/购物车/结算/下单/我的订单/Quote 全字段校验+跳转+toast。
 * 选择器以真实源码为准（已逐页读取 RegisterPage/SettingsPage/CartPage/CheckoutPage/
 * OrderListPage/OrderDetailPage/QuoteRequestPage）：
 *  - 表单字段：Checkout 用 AppInput(=el-input)，按 placeholder 定位；
 *    Register 用原生 .form-input(#reg-*)；Quote 用 .rfq-input(placeholder) + input[type=number]。
 *  - Toast：Settings 用自定义 .save-message--success；其余成功跳转无 toast（Checkout/Order 仅重定向）。
 *  - 写操作隔离：Checkout 下单后 cancelOrder(POST /orders/<id>/cancel/) 清理；
 *    Quote 真实提交(唯一邮箱)后 admin 删除(/quote-requests/<id>/) 尽力清理。
 *
 * 运行：
 *   cd src_claude/frontend
 *   npx playwright test e2e/inventory-driven/auth.spec.cjs --project=chromium
 */
const { test, expect, request } = require('@playwright/test');
const { BASE_URL, loginAsCustomer, loginAsStaff, getToken: pageGetToken, ADMIN_USER, ADMIN_PASS } = require('../helpers/auth');
const { attachConsoleErrorCollector } = require('../helpers/console');
const { apiContext } = require('../helpers/api');

// 已知环境噪声：无头沙箱内化学结构查看器 wasm 回退实例化（与阶段1 同家族）。
const CONSOLE_WHITELIST = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation'];

async function gotoPage(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
}

// 加购（认证态）：导航到产品详情 → Add to Cart → 任意 .el-message 可见即视为加购交互发生。
async function addToCart(page, productId = 66) {
  await gotoPage(page, `/products/${productId}`);
  await page.getByRole('button', { name: 'Add to Cart' }).first().click();
  await expect(page.locator('.el-message').first()).toBeVisible({ timeout: 8000 });
}

// 清理：取消自建订单（customer 可取消自己的订单）。
async function cleanupOrder(page, orderId) {
  if (!orderId) return;
  const token = await pageGetToken(page);
  const ctx = await apiContext(token);
  try {
    await ctx.post(`/orders/${orderId}/cancel/`);
  } catch (e) { /* 尽力清理，失败不阻断 */ }
  await ctx.dispose().catch(() => {});
}

// 清理：删除匿名提交的 QuoteRequest（需 admin 令牌）。
// 注意：apiGetToken(request,...) 需要 Playwright request 夹具实例，模块作用域无此夹具，
// 故此处自行用 apiContext 登录 admin 后删除。
async function cleanupQuote(quoteId) {
  if (!quoteId) return;
  let ctx;
  try {
    ctx = await apiContext(null);
    const loginResp = await ctx.post('/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { username: ADMIN_USER, password: ADMIN_PASS },
    });
    const loginBody = await loginResp.json().catch(() => ({}));
    const adminToken = loginBody?.data?.token;
    if (adminToken) {
      const authCtx = await apiContext(adminToken);
      await authCtx.delete(`/quote-requests/${quoteId}/`).catch(() => {});
      await authCtx.dispose().catch(() => {});
    }
  } catch (e) { /* 尽力清理，失败不阻断 */ }
  finally {
    if (ctx) await ctx.dispose().catch(() => {});
  }
}

test.describe('阶段2 认证流程穷举', () => {

  // ============ 认证守卫（匿名 → 登录页） ============
  test('Guard: 匿名 /settings → /login?redirect=/settings', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/settings');
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    expect(page.url()).toContain('redirect=');
    expect(errors).toEqual([]);
  });

  test('Guard: 匿名 /checkout → /login?redirect=/checkout', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/checkout');
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    expect(page.url()).toContain('redirect=');
    expect(errors).toEqual([]);
  });

  test('Guard: 匿名 /orders → /login?redirect=/orders', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/orders');
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    expect(page.url()).toContain('redirect=');
    expect(errors).toEqual([]);
  });

  // ============ 登录（guest 重定向 + 空提交） ============
  test('Login: 已登录(customer) 访问 /login → 重定向到首页（guest 守卫已实现）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/login');
    // guest 重定向：已登录用户不应停留在登录页，customer → 首页
    await expect(page).not.toHaveURL(/\/login/, { timeout: 8000 });
    await expect(page).toHaveURL(/\/$/, { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Login: 已登录(staff) 访问 /login → 重定向到 /workspace（guest 守卫已实现）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/login');
    // guest 重定向：已登录 staff 用户 → 工作台
    await expect(page).not.toHaveURL(/\/login/, { timeout: 8000 });
    await expect(page).toHaveURL(/\/workspace/, { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Login: 空用户名提交 → 停留 /login（未进入认证区）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/login');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  // ============ 注册校验（不实际提交，避免污染库） ============
  test('Register: 用户名过短 blur → .form-error "at least 3 characters"', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/register');
    await page.locator('#reg-username').fill('ab');
    await page.locator('#reg-email').click(); // blur username → 触发校验
    await expect(page.locator('.form-error').first()).toContainText('at least 3 characters', { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Register: 无效邮箱 blur → .form-error "valid email"；且 Next 不完整时 disabled', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/register');
    await page.locator('#reg-email').fill('not-an-email');
    await page.locator('#reg-username').click(); // blur email → 触发校验
    await expect(page.locator('.form-error').first()).toContainText('valid email', { timeout: 8000 });
    await expect(page.locator('button.auth-submit').first()).toBeDisabled();
    expect(errors).toEqual([]);
  });

  // ============ Settings（认证） ============
  test('Settings: Profile 改 nickname → Save Changes → .save-message--success（并还原）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/settings');
    const nick = page.locator('#nickname');
    await expect(nick.first()).toBeVisible({ timeout: 8000 });
    const orig = await nick.inputValue();
    await nick.fill('E2E_Nick_' + Date.now());
    await page.getByRole('button', { name: 'Save Changes' }).click();
    await expect(page.locator('.save-message--success').first()).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.save-message--success').first()).toContainText('Profile updated successfully');
    // 还原（尽力，避免污染账号资料）
    await nick.fill(orig);
    await page.getByRole('button', { name: 'Save Changes' }).click();
    expect(errors).toEqual([]);
  });

  test('Settings: Shipping tab → 填字段 → Save Shipping Info → .save-message--success', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/settings');
    await page.locator('.sidebar-tab', { hasText: 'Shipping' }).click();
    await page.locator('#ship-name').fill('E2E Org');
    await page.locator('#ship-phone').fill('+1-617-555-0000');
    await page.locator('#ship-email').fill('ship@e2e.edu');
    await page.locator('#ship-addr').fill('1 E2E Way, Test City');
    await page.locator('#ship-payment').selectOption('purchase_order');
    await page.getByRole('button', { name: 'Save Shipping Info' }).click();
    await expect(page.locator('.save-message--success').first()).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.save-message--success').first()).toContainText('Shipping info updated successfully');
    expect(errors).toEqual([]);
  });

  // ============ Cart（认证，交易入口） ============
  test('Cart: 客户加购后 "Place Order" → /checkout', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await addToCart(page);
    await gotoPage(page, '/cart');
    await page.getByRole('button', { name: 'Place Order' }).click();
    await expect(page).toHaveURL(/\/checkout/, { timeout: 10000 });
    expect(errors).toEqual([]);
  });

  test('Cart: "Submit for Approval" 仅 researcher+org 可见（customer 不显示则跳过）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await addToCart(page);
    await gotoPage(page, '/cart');
    const sb = page.getByRole('button', { name: 'Submit for Approval' });
    if (await sb.count()) {
      await sb.click();
      await expect(page).toHaveURL(/\/checkout/, { timeout: 10000 });
    }
    expect(errors).toEqual([]);
  });

  // ============ Checkout + 下单（核心写路径） ============
  test('Checkout: 必填缺失 → 不跳转（停留 /checkout）且 .form-error 可见', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await addToCart(page);
    await gotoPage(page, '/checkout');
    await expect(page.locator('.checkout-form').first()).toBeVisible({ timeout: 8000 });
    // 清空必填项（el-input 按 placeholder 定位）
    await page.getByPlaceholder('Dr. John Smith').fill('');
    await page.getByPlaceholder('123 Lab Street, Cambridge, MA 02139, USA').fill('');
    await page.getByRole('button', { name: 'Place Order' }).click();
    await expect(page).toHaveURL(/\/checkout/, { timeout: 8000 });
    await expect(page.locator('.form-error').first()).toBeVisible({ timeout: 5000 });
    expect(errors).toEqual([]);
  });

  test('Checkout: purchase_order 完整填写 → Place Order → /orders/:id（真实下单）+ 取消清理', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await addToCart(page);
    await gotoPage(page, '/checkout');
    await expect(page.locator('.checkout-form').first()).toBeVisible({ timeout: 8000 });
    await page.locator('input[type="radio"][value="purchase_order"]').check();
    await page.getByPlaceholder('Dr. John Smith').fill('Dr. E2E Test');
    await page.getByPlaceholder('+1-617-555-0123').fill('+1-617-555-0199');
    await page.getByPlaceholder('jsmith@university.edu').fill('e2e@university.edu');
    await page.getByPlaceholder('123 Lab Street, Cambridge, MA 02139, USA').fill('123 E2E Street, Test City, TS 00000');
    await page.getByPlaceholder('PO-2026-00123').fill('PO-E2E-' + Date.now());
    await page.getByRole('button', { name: 'Place Order' }).click();
    await expect(page).toHaveURL(/\/orders\/\d+/, { timeout: 15000 });
    const m = page.url().match(/\/orders\/(\d+)/);
    await cleanupOrder(page, m && m[1]);
    expect(errors).toEqual([]);
  });

  test('Checkout: payment=quote → 按钮变 "Request Quote" → 提交建 quoted 订单 → /orders/:id + 清理', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await addToCart(page);
    await gotoPage(page, '/checkout');
    await expect(page.locator('.checkout-form').first()).toBeVisible({ timeout: 8000 });
    await page.locator('input[type="radio"][value="quote"]').check();
    await page.getByPlaceholder('Dr. John Smith').fill('Dr. E2E Quote');
    await page.getByPlaceholder('123 Lab Street, Cambridge, MA 02139, USA').fill('123 E2E Street, Test City, TS 00000');
    await page.getByRole('button', { name: 'Request Quote' }).click();
    await expect(page).toHaveURL(/\/orders\/\d+/, { timeout: 15000 });
    const m = page.url().match(/\/orders\/(\d+)/);
    await cleanupOrder(page, m && m[1]);
    expect(errors).toEqual([]);
  });

  // ============ Orders 列表 + 详情（认证，读） ============
  test('Orders: 列表渲染（.order-table 或 .empty-state）；行点击 → /orders/:id', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/orders');
    await expect(page.locator('.order-table').or(page.locator('.empty-state')).first()).toBeVisible({ timeout: 8000 });
    const rows = page.locator('.order-row');
    if (await rows.count()) {
      await rows.first().click();
      await expect(page).toHaveURL(/\/orders\/\d+/, { timeout: 10000 });
    }
    expect(errors).toEqual([]);
  });

  test('OrderDetail: 自建订单 → .order-title / .status-badge / .items-table 渲染 + 清理', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await addToCart(page);
    await gotoPage(page, '/checkout');
    await expect(page.locator('.checkout-form').first()).toBeVisible({ timeout: 8000 });
    await page.locator('input[type="radio"][value="purchase_order"]').check();
    await page.getByPlaceholder('Dr. John Smith').fill('Dr. E2E Detail');
    await page.getByPlaceholder('123 Lab Street, Cambridge, MA 02139, USA').fill('123 Detail St, Test City');
    await page.getByPlaceholder('PO-2026-00123').fill('PO-DETAIL-' + Date.now());
    await page.getByRole('button', { name: 'Place Order' }).click();
    await expect(page).toHaveURL(/\/orders\/\d+/, { timeout: 15000 });
    await expect(page.locator('.order-title').first()).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.status-badge').first()).toBeVisible();
    await expect(page.locator('.items-table').first()).toBeVisible();
    const m = page.url().match(/\/orders\/(\d+)/);
    await cleanupOrder(page, m && m[1]);
    expect(errors).toEqual([]);
  });

  // ============ Quote 写路径 ============
  test('Quote: 空 Name/Email 提交 → .rfq-error "Required"', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/quote-request');
    await page.getByRole('button', { name: 'Submit Quote Request' }).click();
    await expect(page.locator('.rfq-error').first()).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.rfq-error').first()).toContainText('Required');
    expect(errors).toEqual([]);
  });

  test('Quote: 无效邮箱 → .rfq-error "Invalid email"', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/quote-request');
    await page.getByPlaceholder('Dr. Smith').fill('Dr. E2E');
    await page.getByPlaceholder('smith@lab.edu').fill('not-an-email');
    await page.getByRole('button', { name: 'Submit Quote Request' }).click();
    await expect(page.locator('.rfq-error').first()).toContainText('Invalid email', { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Quote: 无有效 item → "At least one item required"', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/quote-request');
    await page.getByPlaceholder('Dr. Smith').fill('Dr. E2E');
    await page.getByPlaceholder('smith@lab.edu').fill('e2e@lab.edu');
    await page.getByRole('button', { name: 'Submit Quote Request' }).click();
    await expect(page.locator('.rfq-error-block').first()).toContainText('At least one item required', { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('Quote: 有效提交（真实写，唯一邮箱）→ .rfq-success + RFQ # + 清理', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/quote-request');
    const ts = Date.now();
    await page.getByPlaceholder('Dr. Smith').fill('Dr. E2E ' + ts);
    await page.getByPlaceholder('smith@lab.edu').fill(`e2e-quote-${ts}@lab.edu`);
    await page.getByPlaceholder('Product name or catalog number').first().fill('Test Reagent');
    await page.locator('input[type="number"]').first().fill('2');
    await page.getByRole('button', { name: 'Submit Quote Request' }).click();
    await expect(page.locator('.rfq-success').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.rfq-success').first()).toContainText('Quote Request Submitted');
    await expect(page.locator('.rfq-ref').first()).toContainText('RFQ #');
    const refTxt = await page.locator('.rfq-ref').first().innerText();
    const rfqId = (refTxt.match(/RFQ #(\d+)/) || [])[1];
    await cleanupQuote(rfqId);
    expect(errors).toEqual([]);
  });
});
