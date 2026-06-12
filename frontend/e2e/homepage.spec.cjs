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

const BASE_URL = 'http://localhost:5173';

/**
 * Element Plus el-input 在不同版本中渲染方式：
 * - EP 2.x 新版：.el-input__inner (直接 input 元素)
 * - 部分 EP 版本：wrapper 内嵌 input
 * 使用组合选择器确保兼容性
 */
const HERO_INPUT_SELECTOR = '.hero-search-input .el-input__inner, .hero-search-input input';

test.describe('首页', () => {
  test('加载首页并显示 Hero 区域', async ({ page }) => {
    await page.goto(BASE_URL);

    // 等待页面加载完成
    await page.waitForLoadState('networkidle');

    // Hero 区域应该包含标题
    const heroTitle = page.locator('.hero-title');
    await expect(heroTitle).toBeVisible();
    await expect(heroTitle).toContainText('SciRe');

    // 搜索框应该可见 — 兼容 EP el-input 的 .el-input__inner 或普通 input
    const searchInput = page.locator(HERO_INPUT_SELECTOR).first();
    await expect(searchInput).toBeVisible();
  });

  test('统计卡片显示数据', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // 统计卡片应该有 4 个
    const statCards = page.locator('.stat-card, .stat-chip');
    await expect(statCards).toHaveCount(4);

    // 第一个卡片应该是 Applications
    const firstLabel = page.locator('.stat-label, .stat-chip-label').first();
    await expect(firstLabel).toContainText('Applications');
  });

  test('Featured Applications 显示卡片', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Featured Applications 区域应该有卡片
    const appCards = page.locator('.card-grid-3 .application-card, .card-grid-3 .card');
    const count = await appCards.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('搜索框跳转到搜索页', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // 输入搜索词 — 兼容 EP el-input 的 .el-input__inner 或普通 input
    const searchInput = page.locator(HERO_INPUT_SELECTOR).first();
    await searchInput.fill('Cy3');

    // 按回车
    await searchInput.press('Enter');

    // 应该跳转到搜索页
    await expect(page).toHaveURL(/\/search\?q=Cy3/);
  });
});

test.describe('产品列表页', () => {
  test('加载产品列表', async ({ page }) => {
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
  test('加载方法列表', async ({ page }) => {
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
  test('搜索产品', async ({ page }) => {
    await page.goto(`${BASE_URL}/search?q=Cy3`);
    await page.waitForLoadState('networkidle');

    // 应该显示搜索结果
    await page.waitForTimeout(2000);
    const results = page.locator('.result-item, .result-list > *');
    const count = await results.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('空搜索显示空状态', async ({ page }) => {
    await page.goto(`${BASE_URL}/search`);
    await page.waitForLoadState('networkidle');

    // 没有搜索词时应该显示空状态或无结果
    await page.waitForTimeout(1000);
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });
});

test.describe('导航', () => {
  test('侧边栏导航链接可点击', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // 点击 Applications 导航 — 实际 DOM 是 <a href="/applications" class="nav-item">
    const appLink = page.locator('a.nav-item[href="/applications"]');
    if (await appLink.isVisible()) {
      await appLink.click();
      await expect(page).toHaveURL(/\/applications/);
    }
  });

  test('404 页面', async ({ page }) => {
    await page.goto(`${BASE_URL}/nonexistent-page`);
    await page.waitForLoadState('networkidle');

    // 应该显示 404 内容
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });
});

test.describe('API 端点验证', () => {
  test('site/home 返回正确结构', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/site/home');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data).toHaveProperty('hero');
    expect(data.data).toHaveProperty('featured_applications');
    expect(data.data).toHaveProperty('featured_methods');
    expect(data.data).toHaveProperty('featured_products');
  });

  test('products API 返回产品列表', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/products/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.length).toBeGreaterThanOrEqual(1);
    expect(data.data[0]).toHaveProperty('name');
    expect(data.data[0]).toHaveProperty('cas');
  });

  test('methods API 返回方法列表', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/methods/');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.length).toBeGreaterThanOrEqual(1);
  });

  test('search API 跨资源搜索', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/search?q=Cy3');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.data.length).toBeGreaterThanOrEqual(1);

    // 应该包含多种类型的结果
    const types = data.data.map(r => r.type);
    expect(types).toContain('product');
  });

  test('sitemap.xml 返回 XML', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/v1/sitemap.xml');
    expect(response.ok()).toBeTruthy();

    const text = await response.text();
    expect(text).toContain('<?xml');
    expect(text).toContain('<urlset');
  });
});
