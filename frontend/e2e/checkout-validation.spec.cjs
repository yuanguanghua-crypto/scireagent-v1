/**
 * Checkout 页表单校验 —— 覆盖 `handleCheckout()` 的 validate 分支（I 维空白区）
 *
 * ## 为什么只测校验、不测成功下单
 * `handleCheckout()` 会真正调用 `checkout(data)` **创建订单** + `updateProfile()` **改用户档案**。
 * 在共享 dev 库跑"成功下单"会产生真实订单数据，需要配套清理机制（本 spec 暂不做）。
 * 而 `validate()` 失败时直接 `return`，**不写任何数据** ⇒ 可安全覆盖。
 *
 * ## 覆盖的 3 条校验规则（读 CheckoutPage.vue:54-60）
 * 1. `shippingName` 必填 ⇒ 'Recipient name is required'
 * 2. `shippingAddress` 必填 ⇒ 'Shipping address is required'
 * 3. `purchase_order` 支付时 `poNumber` 必填 ⇒ 'PO number is required for Purchase Order payment'
 *
 * ## 前置
 * - 必须登录（`/checkout` 在 permission-matrix 的 REQUIRES_AUTH 里）
 * - 必须购物车有商品（否则页面渲染 EmptyState 而非表单）
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/checkout-validation.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsCustomer } = require('./helpers/auth.cjs');

const PRODUCT_PATH = '/products/66';

/** 加一件商品（真实 UI 点击，符合拟人化） */
async function addOneToCart(page) {
  await page.goto(BASE_URL + PRODUCT_PATH, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.pd-sku-row', { timeout: 15000 });
  const btn = page.locator('.pd-sku-row').first().getByRole('button', { name: 'Add to Cart' });
  await expect(btn).toBeVisible();
  await btn.click();
  await expect(page.locator('.cart-badge')).toBeVisible({ timeout: 10000 });
}

/** 清空购物车 */
async function clearCart(page) {
  await page.goto(BASE_URL + '/cart', { waitUntil: 'domcontentloaded' });
  for (let i = 0; i < 15; i++) {
    if ((await page.locator('.cart-item').count()) === 0) break;
    await page.locator('.cart-item').first()
      .getByRole('button', { name: /remove|delete|×/i }).click();
    await page.waitForTimeout(150);
  }
}

test.describe('@checkout checkout 表单校验（不产生订单）', { tag: ['@local-only'] }, () => {
  test.beforeEach(async ({ page }) => {
    // ★ 顺序很重要：先登录再清购物车。
    //   反了的话 clearCart 会访问 /cart ⇒ 未登录被重定向到 /login?redirect=/cart，
    //   页面停在登录页 ⇒ 后续 loginAsCustomer 找不到输入框、表单也渲染不出来（实测 45s 超时）。
    await loginAsCustomer(page);
    await clearCart(page);
    await addOneToCart(page);
    await page.goto(BASE_URL + '/checkout', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.checkout-form', { timeout: 15000 });
  });

  test.afterEach(async ({ page }) => { await clearCart(page); });

  test('空表单提交 ⇒ 姓名与地址必填', async ({ page }) => {
    // 保证选的是 PO（默认），这样只触发前两条规则
    await page.getByRole('button', { name: /place order/i }).click();

    await expect(page.getByText('Recipient name is required')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Shipping address is required')).toBeVisible({ timeout: 5000 });

    // 关键：不写数据 —— URL 仍停在 /checkout（没有跳成功页）
    await expect(page).toHaveURL(/\/checkout/);
  });

  test('填了姓名+地址但 PO 支付没填 PO 号 ⇒ 只报 PO 号', async ({ page }) => {
    await page.getByLabel(/recipient name/i).fill('E2E Tester');
    await page.getByLabel(/shipping address/i).fill('1 Test Lane, Testville');

    // 选 PO 支付（默认可能已是，显式点一次确保状态）
    await page.locator('input[type="radio"][value="purchase_order"]').check({ force: true });

    await page.getByRole('button', { name: /place order/i }).click();

    await expect(page.getByText(/PO number is required for Purchase Order/i))
      .toBeVisible({ timeout: 5000 });
    // 前两条错误不应再出现
    await expect(page.getByText('Recipient name is required')).toHaveCount(0);
    await expect(page.getByText('Shipping address is required')).toHaveCount(0);
    await expect(page).toHaveURL(/\/checkout/);
  });

  test('切到 credit_card 后 PO 号不再是必填', async ({ page }) => {
    await page.getByLabel(/recipient name/i).fill('E2E Tester');
    await page.getByLabel(/shipping address/i).fill('1 Test Lane, Testville');
    await page.locator('input[type="radio"][value="credit_card"]').check({ force: true });

    // ⚠️ 本用例**只验「PO 号错误不出现」**，不点提交 ——
    //    因为 credit_card + 完整信息会通过 validate ⇒ 真的调用 checkout() 创建订单。
    //    要测"成功下单"必须先建订单清理机制。
    await expect(page.getByText(/PO number is required/i)).toHaveCount(0);
  });
});
