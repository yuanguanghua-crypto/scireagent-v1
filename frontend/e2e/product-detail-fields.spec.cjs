/**
 * E2E 测试 — 产品详情页字段完整性校验
 *
 * 验证 Product Intake Tool 的所有字段在产品详情页上正确展示。
 * 使用产品 ID 66 (SC8047 - 2'-Azido-dATP) 作为测试数据。
 *
 * 运行方式：
 *   cd E:\scireagent-tencent\frontend
 *   npx playwright test e2e/product-detail-fields.spec.cjs
 *
 * 前提：后端 localhost:8000 + 前端 localhost:5173 已启动
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = 'http://localhost:5173';
const PRODUCT_URL = `${BASE_URL}/products/66`;

test.describe('Product Detail Page — Field Completeness', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(PRODUCT_URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
    // Wait for product data to load (API response)
    await page.waitForSelector('.pd-name', { timeout: 15000 });
  });

  // ═══════════════════════════════════════════
  // Hero Section — 基本信息
  // ═══════════════════════════════════════════

  test('TC-01: Product name is displayed', async ({ page }) => {
    const name = await page.locator('.pd-name').textContent();
    expect(name.trim()).toBeTruthy();
    expect(name).toContain("Azido");
  });

  test('TC-02: Catalog number is displayed as chip', async ({ page }) => {
    const chip = page.locator('.pd-chip-primary');
    await expect(chip).toBeVisible();
    const text = await chip.textContent();
    expect(text).toMatch(/SC\d+/);
  });

  test('TC-03: CAS number is displayed as chip', async ({ page }) => {
    const casChip = page.locator('.pd-chip-mono');
    await expect(casChip).toBeVisible();
    const text = await casChip.textContent();
    // CAS format: digits-digits-digit
    expect(text).toMatch(/\d+-\d+-\d/);
  });

  test('TC-04: Status badge is displayed', async ({ page }) => {
    const badge = page.locator('.pd-badge').first();
    await expect(badge).toBeVisible();
  });

  test('TC-05: Research Use Only badge is displayed', async ({ page }) => {
    const ruoBadge = page.locator('.pd-badge.badge-amber', { hasText: 'RUO' });
    await expect(ruoBadge).toBeVisible();
  });

  test('TC-06: Overview text is displayed', async ({ page }) => {
    const overview = page.locator('.pd-overview');
    await expect(overview).toBeVisible();
    const text = await overview.textContent();
    expect(text.length).toBeGreaterThan(10);
  });

  test('TC-07: Synonyms are displayed', async ({ page }) => {
    const synonyms = page.locator('.pd-synonyms');
    await expect(synonyms).toBeVisible();
    const text = await synonyms.textContent();
    expect(text).toContain('Also known as');
  });

  // ═══════════════════════════════════════════
  // Scientific Parameters — 科学参数
  // ═══════════════════════════════════════════

  test('TC-08: Formula is displayed', async ({ page }) => {
    const spec = page.locator('.pd-spec', { hasText: 'Formula' });
    await expect(spec).toBeVisible();
    const val = spec.locator('.pd-spec-val');
    const text = await val.textContent();
    // Formula should contain C, H, N, O, P etc.
    expect(text).toMatch(/[A-Z][a-z]?\d*/);
  });

  test('TC-09: Molecular weight is displayed with g/mol', async ({ page }) => {
    const spec = page.locator('.pd-spec', { hasText: 'MW' });
    await expect(spec).toBeVisible();
    const val = spec.locator('.pd-spec-val');
    const text = await val.textContent();
    expect(text).toContain('g/mol');
    // Should be a number
    expect(text).toMatch(/\d+/);
  });

  test('TC-10: Purity is displayed', async ({ page }) => {
    const spec = page.locator('.pd-spec', { hasText: 'Purity' });
    await expect(spec).toBeVisible();
    const val = spec.locator('.pd-spec-val');
    const text = await val.textContent();
    expect(text).toBeTruthy();
  });

  test('TC-11: Concentration is displayed', async ({ page }) => {
    const spec = page.locator('.pd-spec', { hasText: 'Conc' });
    await expect(spec).toBeVisible();
    const val = spec.locator('.pd-spec-val');
    const text = await val.textContent();
    expect(text).toMatch(/\d+\s*mM/);
  });

  test('TC-12: Storage condition is displayed', async ({ page }) => {
    const spec = page.locator('.pd-spec', { hasText: 'Storage' });
    await expect(spec).toBeVisible();
  });

  test('TC-13: Shipping condition is displayed', async ({ page }) => {
    const spec = page.locator('.pd-spec', { hasText: 'Shipping' });
    await expect(spec).toBeVisible();
  });

  // ═══════════════════════════════════════════
  // SKU Table — 规格列表
  // ═══════════════════════════════════════════

  test('TC-14: SKU table is displayed with rows', async ({ page }) => {
    const table = page.locator('.pd-sku-table');
    await expect(table).toBeVisible();
    const rows = table.locator('.pd-sku-row');
    const count = await rows.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('TC-15: SKU table has all required columns', async ({ page }) => {
    const header = page.locator('.pd-sku-head');
    await expect(header).toBeVisible();
    const text = await header.textContent();
    expect(text).toContain('SKU');
    expect(text).toContain('Pack Size');
    expect(text).toContain('Conc');
    expect(text).toContain('Price');
    expect(text).toContain('Status');
    expect(text).toContain('Lead Time');
  });

  test('TC-16: SKU code is displayed in each row', async ({ page }) => {
    const firstRow = page.locator('.pd-sku-row').first();
    const skuCode = firstRow.locator('.pd-mono-sm');
    await expect(skuCode).toBeVisible();
    const text = await skuCode.textContent();
    expect(text).toMatch(/SC\d+-\d+/);
  });

  test('TC-17: Pack size is displayed in each row', async ({ page }) => {
    const firstRow = page.locator('.pd-sku-row').first();
    const cells = firstRow.locator('span');
    // Pack size is the 2nd span
    const packSize = cells.nth(1);
    const text = await packSize.textContent();
    expect(text).toBeTruthy();
  });

  test('TC-18: Price is displayed with currency', async ({ page }) => {
    const priceCell = page.locator('.pd-sku-row .pd-price').first();
    await expect(priceCell).toBeVisible();
    const text = await priceCell.textContent();
    // Should contain a number
    expect(text).toMatch(/\d+/);
  });

  test('TC-19: Inventory status badge is displayed', async ({ page }) => {
    const statusBadge = page.locator('.pd-sku-row .pd-badge-sm').first();
    await expect(statusBadge).toBeVisible();
  });

  test('TC-20: Add to Cart button is present', async ({ page }) => {
    const btn = page.locator('.pd-cart-btn').first();
    await expect(btn).toBeVisible();
    await expect(btn).toHaveText('Add to Cart');
  });

  test('TC-21: Quantity control is present', async ({ page }) => {
    const qty = page.locator('.pd-qty').first();
    await expect(qty).toBeVisible();
    // Should show default quantity 1
    const val = qty.locator('span');
    await expect(val).toHaveText('1');
  });

  // ═══════════════════════════════════════════
  // Chemical Identifiers — 化学标识符
  // ═══════════════════════════════════════════

  test('TC-22: SMILES is displayed in Chemical Identifiers section', async ({ page }) => {
    const section = page.locator('.pd-section', { hasText: 'Chemical Identifiers' });
    await expect(section).toBeVisible();
    const smilesItem = section.locator('.pd-id-item', { hasText: 'SMILES' });
    await expect(smilesItem).toBeVisible();
    const val = smilesItem.locator('.pd-id-val');
    const text = await val.textContent();
    expect(text.length).toBeGreaterThan(5);
  });

  // ═══════════════════════════════════════════
  // Classification — 分类
  // ═══════════════════════════════════════════

  test('TC-23: Category L1 is displayed', async ({ page }) => {
    const section = page.locator('.pd-section', { hasText: 'Classification' });
    await expect(section).toBeVisible();
    const l1 = section.locator('.pd-class-item', { hasText: 'Category L1' });
    await expect(l1).toBeVisible();
    const val = l1.locator('.pd-class-val');
    const text = await val.textContent();
    expect(text).toBeTruthy();
  });

  // ═══════════════════════════════════════════
  // Structure SVG — 结构图
  // ═══════════════════════════════════════════

  test('TC-24: Structure image area is present', async ({ page }) => {
    const imgArea = page.locator('.pd-hero-img');
    await expect(imgArea).toBeVisible();
    // Should have either rendered SVG, loading spinner, or placeholder
    const hasSvg = await page.locator('.pd-svg-wrap svg').count();
    const hasLoading = await page.locator('.pd-svg-placeholder .spinner').count();
    const hasPlaceholder = await page.locator('.pd-svg-placeholder').count();
    expect(hasSvg + hasLoading + hasPlaceholder).toBeGreaterThanOrEqual(1);
  });

  // ═══════════════════════════════════════════
  // Breadcrumb — 面包屑导航
  // ═══════════════════════════════════════════

  test('TC-25: Breadcrumb is displayed with product name', async ({ page }) => {
    const breadcrumb = page.locator('.pd-breadcrumb');
    await expect(breadcrumb).toBeVisible();
    const link = breadcrumb.locator('a', { hasText: 'Products' });
    await expect(link).toBeVisible();
    const current = breadcrumb.locator('.pd-breadcrumb-cur');
    const text = await current.textContent();
    expect(text).toBeTruthy();
  });
});
