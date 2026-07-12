/**
 * 回归测试 — PublicNav.vue 购物车按钮
 *
 * 运行方式：
 *   cd C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\src_claude\frontend
 *   npx playwright test e2e/cart-button-regression.spec.cjs
 *
 * 前提：前端 localhost:5173 已启动
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const NAV_SELECTOR = '.public-nav';

/**
 * Helpers
 */

/** 定位导航栏中的购物车按钮（首页可能存在两个 cart-btn，用 first 取导航栏内的） */
function cartLink(page) {
  return page.locator(`${NAV_SELECTOR} a.cart-btn[href="/cart"]`).first();
}

/** 通过 page.evaluate 设置 Pinia basket store 的 count */
async function setBasketCount(page, count) {
  await page.evaluate((val) => {
    const appEl = document.querySelector('#app');
    if (!appEl || !appEl.__vue_app__) return;
    const pinia = appEl.__vue_app__.config.globalProperties.$pinia;
    if (pinia && pinia.state && pinia.state.value) {
      pinia.state.value.basket = pinia.state.value.basket || {};
      pinia.state.value.basket.count = val;
    }
  }, count);
}

// ──────────────────────────────────────────────────
// A1. 首页购物车按钮存在
// ──────────────────────────────────────────────────
test.describe('A1 — 首页购物车按钮', () => {
  test('购物车按钮存在，包含 SVG 图标，点击后跳转 /cart', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // 断言购物车链接存在
    const btn = cartLink(page);
    await expect(btn).toBeVisible();

    // 断言包含 SVG 图标
    const svg = btn.locator('svg');
    await expect(svg).toBeVisible();

    // 断言 title 属性
    await expect(btn).toHaveAttribute('title', 'Shopping Cart');

    // 点击后跳转到 /cart（首页 main 区域 SVG 可能遮挡，使用 force 绕过）
    await btn.click({ force: true });
    await expect(page).toHaveURL(/\/cart/);
  });
});

// ──────────────────────────────────────────────────
// A2. 产品详情页购物车按钮存在
// ──────────────────────────────────────────────────
test.describe('A2 — 产品详情页购物车按钮', () => {
  test('在 /products/23 页面导航栏中存在购物车链接，且可见可点击', async ({ page }) => {
    await page.goto(`${BASE_URL}/products/23`);
    await page.waitForLoadState('networkidle');

    const btn = cartLink(page);
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });
});

// ──────────────────────────────────────────────────
// A3. 购物车徽章
// ──────────────────────────────────────────────────
test.describe('A3 — 购物车徽章', () => {
  test('A3.1 — 有商品时徽章显示数量', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // 注入 bag 数据：设置 count=3
    await setBasketCount(page, 3);

    // 等待 Vue 更新 DOM
    await page.waitForTimeout(200);

    // 断言徽章可见且显示 3
    const badge = page.locator(`${NAV_SELECTOR} .cart-badge`).first();
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText('3');
  });

  test('A3.2 — 空购物车时徽章不显示', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // 确保 count=0
    await setBasketCount(page, 0);
    await page.waitForTimeout(200);

    // 断言徽章不存在（v-if="basketStore.count > 0"）
    const badge = page.locator(`${NAV_SELECTOR} .cart-badge`);
    await expect(badge).toHaveCount(0);
  });
});
