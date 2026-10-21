/**
 * I 维补白（3/3）：`/checkout` 的「多步」
 *
 * ## ⚠️ 先纠正判定表里的描述（重要，别照抄）
 * `docs/e2e/INTERACTION_VERDICT.md` 把 `/checkout` 的空白项写成「多步 / steps」，
 * `docs/e2e/INTERACTION_INVENTORY.md:62` 的备注也写作「多步结算表单」。**但代码里没有 stepper**：
 *   - `CheckoutPage.vue` 全文 279 行，**没有任何 `steps` / stepper / Next / Back**
 *     （`grep -rn "steps" views/CheckoutPage.vue` 零命中；全站 `steps` 只在
 *      ResearchCartPanel / ProtocolDetail / ProductEditPage / RegisterPage 里）
 *   - 实际是一个**单页四段式表单**（`CheckoutPage.vue:136-231`）：
 *       ① Shipping Information（`:141`）
 *       ② Payment Method（`:160`，四种支付方式 radio）
 *       ③ Order Notes（`:205`）
 *       ④ Order Summary（`:211`）
 *   - 唯一的「推进 / 回退」式分段交互是**支付方式的按需展开**：
 *       `v-if="paymentMethod === 'purchase_order'"` ⇒ `.po-fields`（PO Number / PO Contact）
 *       （`CheckoutPage.vue:194-201`），以及主按钮文案随支付方式切换
 *       （`:227-230`：quote ⇒ `Request Quote`，其余 ⇒ `Place Order`）
 * ⇒ 本 spec 就按**真实实现**测：四段齐全 + 支付分段推进/回退（含显隐、选中样式、按钮文案）。
 *   判定表里的「多步」属**描述过时**，已在交付报告里如实标注。
 *
 * ## 绝不下单（硬纪律）
 * `handleCheckout()`（`CheckoutPage.vue:64-117`）会真的 `checkout(data)` 建单 +
 * `updateProfile()` 改档案 + `router.push('/orders/:id')`。
 * ⇒ 本 spec **从不点最终提交按钮**，只操作支付方式与字段显隐。
 *   （校验失败分支已由既有 `checkout-validation.spec.cjs` 覆盖，不重复。）
 *
 * ## 前置
 * - 必须登录（`router/index.js:156-160` requiresAuth）
 * - 购物车必须有商品，否则页面渲染 EmptyState（`CheckoutPage.vue:125-134`）而不是表单
 * - 加购走产品页真实点击；用例前后都清空购物车，避免污染其它 spec
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/checkout-progressive-sections.spec.cjs --project=chromium --output=/tmp/pw-ui
 */

const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsCustomer } = require('./helpers/auth.cjs');

/** 已知有 SKU 的产品（与 cart-page-interactions / checkout-validation 一致） */
const PRODUCT_PATH = '/products/66';

/** 四段标题（CheckoutPage.vue:142 / 161 / 206 / 212） */
const SECTION_TITLES = [
  'Shipping Information',
  'Payment Method',
  'Order Notes',
  'Order Summary',
];

async function addOneToCart(page) {
  await page.goto(BASE_URL + PRODUCT_PATH, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.pd-sku-row', { timeout: 15000 });
  const btn = page.locator('.pd-sku-row').first().getByRole('button', { name: 'Add to Cart' });
  await expect(btn).toBeVisible();
  await btn.click();
  // 徽章出现 = 真的加进去了（不信 toast）
  await expect(page.locator('.cart-badge')).toBeVisible({ timeout: 10000 });
}

async function clearCart(page) {
  await page.goto(BASE_URL + '/cart', { waitUntil: 'domcontentloaded' });
  for (let i = 0; i < 15; i++) {
    if ((await page.locator('.cart-item').count()) === 0) break;
    await page.locator('.cart-item').first()
      .getByRole('button', { name: /remove|delete|×/i }).click();
    await page.waitForTimeout(150);
  }
}

/** 选支付方式（radio 绑 v-model，见 CheckoutPage.vue:164-190） */
async function choosePayment(page, value) {
  await page.locator(`input[type="radio"][value="${value}"]`).check({ force: true });
}

test.describe('@checkout 结算页分段结构', { tag: ['@local-only'] }, () => {
  test.beforeEach(async ({ page }) => {
    // ★ 顺序：先登录再清购物车（未登录访问 /cart 会被打到 /login，见 checkout-validation 里的踩坑记录）
    await loginAsCustomer(page);
    await clearCart(page);
    await addOneToCart(page);
    await page.goto(BASE_URL + '/checkout', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.checkout-form', { timeout: 15000 });
  });

  test.afterEach(async ({ page }) => { await clearCart(page); });

  test('四段齐全且顺序正确（Shipping → Payment → Notes → Summary）', async ({ page }) => {
    const titles = await page.locator('.checkout-section .section-title').allTextContents();
    const normalized = titles.map((t) => t.trim());
    // 不断言"只有四段"，只断言这四段按顺序出现（容忍将来新增分段）
    let cursor = -1;
    for (const t of SECTION_TITLES) {
      const idx = normalized.indexOf(t);
      expect(idx, `结算页应包含分段「${t}」，实际：${JSON.stringify(normalized)}`).toBeGreaterThan(-1);
      expect(idx, `分段顺序应为 ${SECTION_TITLES.join(' → ')}`).toBeGreaterThan(cursor);
      cursor = idx;
    }
    // 订单摘要里应有总价行（CheckoutPage.vue:220-223）
    await expect(page.locator('.summary-total-value')).toBeVisible();
  });

  test('支付分段推进 / 回退：PO 展开字段 → 信用卡收起 → 报价换按钮文案 → 回退到 PO', async ({ page }) => {
    // ── 段 1：PO 支付 ⇒ `.po-fields` 展开（CheckoutPage.vue:194）
    await choosePayment(page, 'purchase_order');
    await expect(page.locator('.payment-option--active')).toContainText(/Purchase Order/i);
    await expect(page.locator('.po-fields')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.po-fields')).toContainText(/PO Number/);
    await expect(page.getByRole('button', { name: /^Place Order$/ })).toBeVisible();

    // ── 段 2：切信用卡 ⇒ PO 字段整体收起（这是"回退"的真实可见效果）
    await choosePayment(page, 'credit_card');
    await expect(page.locator('.payment-option--active')).toContainText(/Credit Card/i);
    await expect(page.locator('.po-fields')).toHaveCount(0, { timeout: 5000 });

    // ── 段 3：切"Request Quote" ⇒ 主按钮文案变化（CheckoutPage.vue:228-229）
    await choosePayment(page, 'quote');
    await expect(page.locator('.payment-option--active')).toContainText(/Request Quote/i);
    await expect(page.getByRole('button', { name: /Request Quote/ })).toBeVisible({ timeout: 5000 });

    // ── 段 4：回退到 PO ⇒ 字段重新出现、按钮文案回 `Place Order`
    await choosePayment(page, 'purchase_order');
    await expect(page.locator('.po-fields')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: /^Place Order$/ })).toBeVisible();

    // ★ 全程未点提交：URL 仍在 /checkout（没有任何订单被创建）
    await expect(page).toHaveURL(/\/checkout/);
  });
});
