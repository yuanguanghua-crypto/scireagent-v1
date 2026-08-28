/**
 * E2E — 产品详情页双 edge 展示（Phase 4：verified 置顶区块）
 *
 * 验证 T4.1 验收线：
 *   - Methods tab 顶部渲染「Verified Applicability」区块（verified 置顶，最强相关性）
 *   - 空态：verified=0 时显示 "No verified method applicability …"（暂无已验证适用）
 *   - 遗留 methods 列表（ProductMethod 桥表）保留不替换，与 verified 区块互不混入
 *   - 公开读（AllowAny）：匿名访问不触发 401 → /login 重定向
 *
 * 运行方式：
 *   cd frontend && npx playwright test e2e/product-detail-verified-methods.spec.cjs
 *
 * 前提：后端 localhost:8000 + 前端 localhost:5173 已启动
 * 数据：产品 ID 66（SC8047，dev 种子数据）
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const PRODUCT_URL = `${BASE_URL}/products/66`;

test.describe('Product Detail — Verified Applicability block', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(PRODUCT_URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForSelector('.pd-name', { timeout: 15000 });
  });

  test('P4-01: Methods tab shows Verified Applicability block with heading', async ({ page }) => {
    await page.click('.pd-tab-btn:has-text("Methods")');
    const block = page.locator('[data-testid="verified-applicability"]');
    await expect(block).toBeVisible();
    await expect(block.locator('.pd-verified-heading')).toHaveText('Verified Applicability');
  });

  test('P4-02: empty state shown when no verified edges (dev seed verified=0)', async ({ page }) => {
    await page.click('.pd-tab-btn:has-text("Methods")');
    const block = page.locator('[data-testid="verified-applicability"]');
    await expect(block).toBeVisible();
    // 空态文案（若 dev 库有 verified 边则应出现卡片，两者互斥）
    const empty = block.locator('.pd-verified-empty');
    const cards = block.locator('.pd-verified-card');
    await expect(empty.or(cards.first())).toBeVisible();
  });

  test('P4-03: legacy methods list still rendered below verified block (not replaced)', async ({ page }) => {
    await page.click('.pd-tab-btn:has-text("Methods")');
    const block = page.locator('[data-testid="verified-applicability"]');
    await expect(block).toBeVisible();
    // 遗留 methods 区块仍存在：要么方法卡片（.pd-icon-method）要么 fallback 文案
    const legacyCards = page.locator('.pd-icon-method');
    const fallback = page.getByText('Method associations are being mapped');
    const cardCount = await legacyCards.count();
    if (cardCount === 0) {
      await expect(fallback.first()).toBeVisible();
    } else {
      expect(cardCount).toBeGreaterThan(0);
    }
  });

  test('P4-04: anonymous (public) access — no 401 redirect to /login', async ({ page }) => {
    await page.click('.pd-tab-btn:has-text("Methods")');
    // verified 拉取发生在页面加载期；公开读 AllowAny 下不应触发全局 401 跳登录
    await page
      .locator('[data-testid="verified-applicability"]')
      .waitFor({ state: 'attached', timeout: 5000 });
    expect(page.url()).not.toContain('/login');
  });
});
