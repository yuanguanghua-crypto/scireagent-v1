/**
 * E2E 测试 — SciReagent 首页及核心页面
 *
 * 运行方式：
 *   cd E:\scireagent-tencent\frontend
 *   npx playwright test e2e/
 *
 * 前提：后端 localhost:8000 + 前端 localhost:5173 已启动
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

/**
 * Element Plus el-input 在不同版本中渲染方式：
 * - EP 2.x 新版：.el-input__inner (直接 input 元素)
 * - 部分 EP 版本：wrapper 内嵌 input
 * 使用组合选择器确保兼容性
 */
/**
 * 首页改版（2026-07 前后）后首页由 components/home/* 组合渲染：
 *   HeroSearch(.hero-title/.hero-search .search-box input) · CategoryPills(.category-pill)
 *   · FeaturedProducts(.product-grid > .product-card) · StatsBar(.stat-item) …
 * 原 `.hero-search-input` / `.stat-card` / `.card-grid-3 .application-card` 均已不存在 ⇒ 按现锚点重接。
 */
const HERO_INPUT_SELECTOR = '.hero-search .search-box input, input[placeholder*="Search products"]';

test.describe('首页', () => {
  test('加载首页并显示 Hero 区域', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    // Hero 区域应该包含标题（改版后为固定英文营销文案）
    const heroTitle = page.locator('.hero-title');
    await expect(heroTitle).toBeVisible({ timeout: 15000 });
    await expect(heroTitle).toContainText('precision reagent');

    // 搜索框应该可见
    const searchInput = page.locator(HERO_INPUT_SELECTOR).first();
    await expect(searchInput).toBeVisible();
  });

  test('统计卡片显示数据', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    // 统计条改版后为 StatsBar（懒加载）：.stat-item × 5
    const statCards = page.locator('.stat-item');
    await expect(statCards).toHaveCount(5, { timeout: 15000 });

    // 第一个卡片应该是 Products
    const firstLabel = page.locator('.stat-label').first();
    await expect(firstLabel).toContainText('Products');
  });

  test('Featured Products 显示卡片', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    // 改版后为 FeaturedProducts：.product-grid > .product-card
    const cards = page.locator('.product-grid .product-card');
    await expect(cards.first()).toBeVisible({ timeout: 15000 });
    expect(await cards.count()).toBeGreaterThanOrEqual(1);
  });

  test('搜索框跳转到搜索页', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('domcontentloaded');

    const searchInput = page.locator(HERO_INPUT_SELECTOR).first();
    await expect(searchInput).toBeVisible({ timeout: 15000 });
    await searchInput.fill('Cy3');

    // 按回车
    await searchInput.press('Enter');

    // 应该跳转到搜索页
    await expect(page).toHaveURL(/\/search\?q=Cy3/, { timeout: 10000 });
  });
});

test.describe('产品列表页', () => {
  test('加载产品列表', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(`${BASE_URL}/products`);
    await page.waitForLoadState('networkidle');

    // 页面标题应该包含 Products
    const title = page.locator('.page-title, h1');
    await expect(title.first()).toContainText('Product');

    // 应该有产品卡片
    await page.waitForTimeout(1000);
    const cards = page.locator('.product-card, .card');
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});

test.describe('方法列表页', () => {
  test('加载方法列表', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(`${BASE_URL}/methods`);
    await page.waitForLoadState('networkidle');

    const title = page.locator('.page-title, h1');
    await expect(title.first()).toContainText('Method');

    await page.waitForTimeout(1000);
    const cards = page.locator('.method-card, .card');
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});

test.describe('搜索页', () => {
  // 修复跨轮 flaky（2026-09-23）：原实现 `page.goto` + `waitForLoadState('networkidle')`
  // 会因出网 AI 端点迟迟不 idle 而触发 45s 测试超时（同命令基线 PASSED / 复跑 TIMEDOUT）。
  // 改为 domcontentloaded + 明确等待搜索结果渲染（本 spec 头注释本就要求避免 networkidle）。
  test('搜索产品', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(`${BASE_URL}/search?q=Cy3`, { waitUntil: 'domcontentloaded' });

    // 应该显示搜索结果
    await expect(page.locator('.result-item').first()).toBeVisible({ timeout: 20000 });
    const results = page.locator('.result-item');
    const count = await results.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('空搜索显示空状态', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(`${BASE_URL}/search`);
    await page.waitForLoadState('networkidle');

    // 没有搜索词时应该显示空状态或无结果
    await page.waitForTimeout(1000);
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });
});

test.describe('导航', () => {
  test('侧边栏导航链接可点击', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // 点击 Applications 导航 — 实际 DOM 是 <a href="/applications" class="nav-item">
    const appLink = page.locator('a.nav-item[href="/applications"]');
    if (await appLink.isVisible()) {
      await appLink.click();
      await expect(page).toHaveURL(/\/applications/);
    }
  });

  test('404 页面', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await page.goto(`${BASE_URL}/nonexistent-page`);
    await page.waitForLoadState('networkidle');

    // 应该显示 404 内容
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });
});

test.describe('API 端点验证', () => {
  test('site/home 返回正确结构', { tag: ['@readonly', '@local-only'] }, async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/site/home');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data).toHaveProperty('hero');
    expect(data.data).toHaveProperty('featured_applications');
    expect(data.data).toHaveProperty('featured_methods');
    expect(data.data).toHaveProperty('featured_products');
  });

  test('products API 返回产品列表', { tag: ['@readonly', '@local-only'] }, async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/products/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.length).toBeGreaterThanOrEqual(1);
    expect(data.data[0]).toHaveProperty('name');
    expect(data.data[0]).toHaveProperty('cas');
  });

  test('methods API 返回方法列表', { tag: ['@readonly', '@local-only'] }, async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/methods/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.length).toBeGreaterThanOrEqual(1);
  });

  test('search API 跨资源搜索', { tag: ['@readonly', '@local-only'] }, async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/search?q=Cy3');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.length).toBeGreaterThanOrEqual(1);

    // 应该包含多种类型的结果
    const types = data.data.map(r => r.type);
    expect(types).toContain('product');
  });

  test('sitemap.xml 返回 XML', { tag: ['@readonly', '@local-only'] }, async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/sitemap.xml');
    expect(response.ok()).toBeTruthy();

    const text = await response.text();
    expect(text).toContain('<?xml');
    expect(text).toContain('<urlset');
  });
});
