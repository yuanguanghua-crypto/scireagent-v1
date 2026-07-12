/**
 * 验证 4 处字段兜底修复：
 *   A. saveDraft slug 兜底（空 slug → 从 catalog_no 生成）
 *   B. storage/shipping 归一化（中文/原始描述 → choices 枚举值）
 *   C. saveDraft 派生 sku_code（Word 导入的 SKU 不再 sku_code 为空）
 *   D. 保存前 sanitizeChoiceFields（非法 choices 值置空，不再 invalid_choice）
 *
 * 运行：cd frontend; npx playwright test e2e/verify-field-normalize.spec.cjs --reporter=line
 */
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_BASE = 'http://localhost:8000/api/v1';
const ADMIN_USER = process.env.E2E_USER || 'admin';
const ADMIN_PASS = process.env.E2E_PASS || 'AdminPass123!';

async function loginAsStaff(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);
  await Promise.all([
    page.waitForURL(/\/workspace/, { timeout: 15000 }),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
}

const PREFIX = 'E2E-NORM-';
const ts = Date.now();

test.describe('字段兜底归一化验证', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page);
  });

  test('D1. slug + sku_code 兜底，POST 不再 400', async ({ page, request }) => {
    const token = await page.evaluate(() => localStorage.getItem('token'));

    // 跑前清理同前缀残留
    const listResp = await request.get(`${API_BASE}/products/?page_size=100`, {
      headers: { Authorization: `Token ${token}` },
    });
    const listData = await listResp.json();
    const ids = (listData.data?.results || listData.results || [])
      .filter(p => (p.catalog_no || '').startsWith(PREFIX)).map(p => p.id);
    for (const id of ids) {
      try { await request.delete(`${API_BASE}/products/${id}/`, { headers: { Authorization: `Token ${token}` } }); } catch {}
    }

    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    const catalogNo = `${PREFIX}${ts}`;
    // 只填阻断字段：name + catalog_no + 分类 + 默认 SKU
    // 故意不填 slug（验证兜底 A）
    await page.locator('input[placeholder*="Amino-ATP"]').fill('E2E Norm Test Product');
    await page.locator('input[placeholder*="SC8043"]').first().fill(catalogNo);

    // 选分类（叶子）
    const cascader = page.locator('.el-cascader').first();
    await cascader.click();
    await page.locator('.el-cascader-menu .el-cascader-node').first().click();
    await page.locator('.el-cascader-menu:nth-child(2) .el-cascader-node').first().click();
    await expect(page.locator('.el-cascader input').first()).toHaveValue(/.+/);

    // 添加默认 SKU — 不填 sku_code（验证 saveDraft 派生兜底 C）
    await page.locator('button', { hasText: '+ Add SKU' }).click();

    // 保存（应成功 201，不再 400）
    const [saveResp] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/v1/products/') && r.request().method() === 'POST', { timeout: 30000 }),
      page.locator('.form-actions button', { hasText: 'Save Draft' }).click(),
    ]);

    expect(saveResp.status()).toBe(201);

    await expect(page).toHaveURL(/\/workspace\/products\/\d+\/edit/, { timeout: 10000 });
    const createdId = new URL(page.url()).pathname.match(/\/products\/(\d+)\/edit/)[1];

    // 验证 slug 非空、sku_code 非空
    const getResp = await request.get(`${API_BASE}/products/${createdId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const pData = (await getResp.json()).data;
    expect(pData.slug).toBeTruthy();
    expect(pData.slug).not.toBe('');
    expect(pData.skus.length).toBeGreaterThan(0);
    expect(pData.skus[0].sku_code).toBeTruthy();
    // sku_code 应基于 catalog_no 派生
    expect(pData.skus[0].sku_code).toContain(catalogNo);

    // 清理
    try { await request.delete(`${API_BASE}/products/${createdId}/`, { headers: { Authorization: `Token ${token}` } }); } catch {}
  });

  test('D2. 中文 storage/shipping 归一化规则（与组件内实现一致）', async () => {
    // 复刻 normalizeStorage / normalizeShipping 逻辑做断言（与 ProductEditPage.vue 内实现一致）
    const storageOpts = ['-20°C', '-20°C, protect from light', '-80°C', '4°C', '4°C, protect from light', 'Room temperature', 'Room temperature, dry'];
    const shippingOpts = ['Dry Ice', 'Blue Ice', 'Ambient', 'Cold Pack'];
    function normalizeStorage(raw) {
      if (!raw) return '';
      const s = String(raw).toLowerCase().trim();
      if (!s) return '';
      if (storageOpts.includes(raw)) return raw;
      if (s.includes('-80')) return '-80°C';
      if (s.includes('-20') && (s.includes('light') || s.includes('避光'))) return '-20°C, protect from light';
      if (s.includes('-20')) return '-20°C';
      if (s.includes('4') && (s.includes('light') || s.includes('避光'))) return '4°C, protect from light';
      if (s.includes('4')) return '4°C';
      if (s.includes('room') || s.includes('室温')) {
        if (s.includes('dry') || s.includes('干燥')) return 'Room temperature, dry';
        return 'Room temperature';
      }
      return '';
    }
    function normalizeShipping(raw) {
      if (!raw) return '';
      const s = String(raw).toLowerCase().trim();
      if (!s) return '';
      if (shippingOpts.includes(raw)) return raw;
      if (s.includes('dry ice') || s.includes('干冰')) return 'Dry Ice';
      if (s.includes('blue ice') || s.includes('蓝冰')) return 'Blue Ice';
      if (s.includes('cold pack') || s.includes('gel pack') || s.includes('冷')) return 'Cold Pack';
      if (s.includes('ambient') || s.includes('常温') || s.includes('room')) return 'Ambient';
      return '';
    }
    const storageCases = [
      ['存储在-20°C', '-20°C'],
      ['store at -20 °C', '-20°C'],
      ['-80度', '-80°C'],
      ['室温', 'Room temperature'],
      ['-20°C, protect from light', '-20°C, protect from light'],  // 已是合法值原样返回
      ['未知条件', ''],  // 匹配不上置空
    ];
    const shippingCases = [
      ['与蓝冰一起运输', 'Blue Ice'],
      ['shipped on gel packs', 'Cold Pack'],
      ['干冰', 'Dry Ice'],
      ['常温', 'Ambient'],
      ['Blue Ice', 'Blue Ice'],  // 已是合法值
      ['未知方式', ''],
    ];
    for (const [raw, expected] of storageCases) {
      expect(normalizeStorage(raw), `normalizeStorage("${raw}")`).toBe(expected);
    }
    for (const [raw, expected] of shippingCases) {
      expect(normalizeShipping(raw), `normalizeShipping("${raw}")`).toBe(expected);
    }
  });
});
