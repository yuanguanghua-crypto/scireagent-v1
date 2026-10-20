/**
 * 购物车页面内部交互 —— 覆盖 `/cart` 的操作（I 维空白区）
 *
 * ## 为什么需要这个 spec
 * 全站审计发现：`/cart` 只被 a11y / visual-tokens 扫过（页面能打开 + 无障碍 + 令牌），
 * **页面上的操作一个都没测**。而 `cart-button-regression.spec` 测的是"**进入**购物车的入口"
 * （点导航栏按钮跳 /cart），不是购物车页面内部。
 *
 * ## 本 spec 覆盖的 6 个交互（对应 FULL_SITE §2.2 的 `/cart` 行）
 * - I 维：数量 +、数量 −、删除
 * - I 维：下单 / 请求报价 / 提交审批 —— **这三个在代码里只是 `router.push`，不写后端**
 *   （`CartPage.vue` 的 handlePlaceOrder / handleRequestQuote / handleSubmitApproval）
 *   ⇒ **真正的下单逻辑在 /checkout 页**，本 spec 只验导航正确
 *
 * ## 拟人化原则（遵守 e2e/README 与 CLAUDE.md）
 * - 加购走**产品页真实点击**（不直接 POST /basket/items），因为"被测路径必须走 UI"
 * - 断言看**页面状态变化**（数量文本、条目数、URL），不看 toast
 * - 删除当前**无确认弹窗**（读码确认），故直接断言条目消失
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/cart-page-interactions.spec.cjs --project=chromium
 * 前置：后端 8000 + 前端 5173 均就绪
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsCustomer } = require('./helpers/auth.cjs');

/** 已知有 SKU 的产品详情页（与 product-detail-fields.spec 一致） */
const PRODUCT_PATH = '/products/66';

/** 加购：从产品页点第一个 SKU 行的 Add to Cart（真实 UI 路径） */
async function addOneToCart(page) {
  await page.goto(BASE_URL + PRODUCT_PATH, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.pd-sku-row', { timeout: 15000 });
  const btn = page.locator('.pd-sku-row').first().getByRole('button', { name: 'Add to Cart' });
  await expect(btn).toBeVisible();
  await btn.click();
  // 加购后购物车徽章应出现/递增 —— 用它作为"真的加进去了"的证据（不信 toast）
  await expect(page.locator('.cart-badge')).toBeVisible({ timeout: 10000 });
}

/** 进入购物车并等条目渲染 */
async function openCartWithItems(page) {
  await addOneToCart(page);
  await page.goto(BASE_URL + '/cart', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.cart-item', { timeout: 15000 });
}

/** 清空购物车（避免污染后续用例 / 下一轮） */
async function clearCart(page) {
  await page.goto(BASE_URL + '/cart', { waitUntil: 'domcontentloaded' });
  // 反复点删除直到空态出现（每次删一条）
  for (let i = 0; i < 15; i++) {
    const n = await page.locator('.cart-item').count();
    if (n === 0) break;
    await page.locator('.cart-item').first().getByRole('button', { name: /remove|delete|×/i }).click();
    await page.waitForTimeout(150);
  }
}

test.describe('@cart 购物车页内部交互', { tag: ['@local-only'] }, () => {
  test.beforeEach(async ({ page }) => { await clearCart(page); });
  test.afterEach(async ({ page }) => { await clearCart(page); });

  test('数量 + / − 改变小计', async ({ page }) => {
    await openCartWithItems(page);
    const item = page.locator('.cart-item').first();
    const qty = item.locator('.qty-value');

    const before = parseInt((await qty.textContent()) || '0', 10);
    expect(before).toBeGreaterThan(0);

    // ⚠️ 用 class 定位而非 getByRole('button', {name:'+'})：
    //    实测该按钮的 accessible name 不等于 '+'（符号渲染/aria 覆盖），role 查不到。
    //    .qty-control 内：[0]=−、[1]=+（见 CartPage.vue 的 qty-control 结构）
    const btns = item.locator('.qty-control .qty-btn');
    await expect(btns).toHaveCount(2);

    await btns.nth(1).click();   // +
    await expect(qty).toHaveText(String(before + 1), { timeout: 10000 });

    await btns.nth(0).click();   // −
    await expect(qty).toHaveText(String(before), { timeout: 10000 });
  });

  test('删除条目后回到空态', async ({ page }) => {
    await openCartWithItems(page);
    await expect(page.locator('.cart-item')).toHaveCount(1);

    // 读码确认：handleRemove 无确认弹窗
    await page.locator('.cart-item').first()
      .getByRole('button', { name: /remove|delete|×/i }).click();

    await expect(page.locator('.cart-item')).toHaveCount(0, { timeout: 10000 });
    // 空态应有明确文案（不是白屏）
    await expect(page.locator('.cart-page')).toContainText(/empty|Browse Products/i);
  });

  test('「下单」跳 /checkout', async ({ page }) => {
    await openCartWithItems(page);
    await page.getByRole('button', { name: /place order|下单|checkout/i }).click();
    await expect(page).toHaveURL(/\/checkout/, { timeout: 10000 });
  });

  test('「请求报价」跳 /quote-request', async ({ page }) => {
    await openCartWithItems(page);
    await page.getByRole('button', { name: /request quote|报价/i }).click();
    await expect(page).toHaveURL(/\/quote-request/, { timeout: 10000 });
  });

  test('「提交审批」跳 /checkout（与下单同落点，这是当前实现）', async ({ page }) => {
    // ★ 该按钮由 showSubmitApproval 控制，条件（CartPage.vue:14-17）：
    //   ① 已登录 ② 有 organization
    //   e2e_customer 账号满足（org=E2E Customer Org）⇒ 必须登录才测得到。
    //   匿名访问时按钮不存在 —— 这也是为什么最初的匿名测试会 45s 超时。
    await loginAsCustomer(page);
    await openCartWithItems(page);

    const btn = page.getByRole('button', { name: 'Submit for Approval' });
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    // ⚠️ 当前实现两者都 push('/checkout')；
    //    若将来改成独立审批流，本断言应随之更新（而不是放宽成"任意 URL"）
    await expect(page).toHaveURL(/\/checkout/, { timeout: 10000 });
  });
});
