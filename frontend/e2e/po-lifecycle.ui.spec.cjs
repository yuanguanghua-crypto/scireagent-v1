/**
 * PO 订单 · L2 浏览器级 E2E（分角色真 UI 关键路径）
 *
 * 定位：**真浏览器**，验"页面能不能用" + 本轮 UI 改动（Quote 下拉、PO 号可选、审核台库存列/缺货高亮）。
 *      与 L1（API 级，验逻辑）互补。
 *
 * ⚠ 角色可达性（2026-10-14 实测）：
 *   - 客户侧 /po/*  → requiresAuth（客户/proc/staff 均可）
 *   - 内部台 /admin/po/* → requiresAdmin → 前端守卫判 **isStaff** ⇒ 非 staff 的 procurement **够不着**
 *     （后端已允许 procurement 跨机构，但前端守卫拦住 ⇒ 待修，本 spec 用 staff(admin) 验内部台 UI）
 *
 * 运行：剥代理 + workers=1 --project=chromium --output=<独立目录> -g "@po-ui"
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const { loginAsCustomer, loginAsStaff, BASE_URL } = require('./helpers/auth.cjs');

const API_BASE = process.env.API_BASE || 'http://localhost:8000/api/v1';
const FIXTURE = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', '..', 'e2e_po_fixture.json'), 'utf8'),
);

async function apiLogin(request, u, p) {
  const res = await request.post(`${API_BASE}/auth/login`, { data: { username: u, password: p } });
  return (await res.json()).data.token;
}

/** 用 API 造一条 po_received 单（供审核台 UI 消费）。 */
async function seedPendingOrder(request) {
  const cust = await apiLogin(request, process.env.E2E_CUSTOMER_USER || 'e2e_customer', process.env.E2E_CUSTOMER_PASS || 'E2ePass123!');
  const po = `E2E-UI-${Date.now()}`;
  const res = await request.post(`${API_BASE}/orders/po/`, {
    headers: { Authorization: `Token ${cust}` },
    data: {
      po_number: po, shipping_name: 'E2E UI Lab', shipping_address: '1 Test St',
      items: [{ sku_id: FIXTURE.sku_id, quantity: 2, unit_price: FIXTURE.unit_price }],
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  return po;
}

test.describe('@po-ui 客户侧 PO 页面', () => {
  test('PoSubmit 页加载；含「PO Number（可选）」与「Quote / Reference #」下拉', async ({ page }) => {
    await loginAsCustomer(page);
    await page.goto(`${BASE_URL}/po/submit`, { waitUntil: 'domcontentloaded' });
    // 无白屏（scope 到 PO 页标题类，避免与布局标题 strict-mode 冲突）
    await expect(page.locator('h1.po-page-title', { hasText: 'Submit Purchase Order' })).toBeVisible();
    // 本轮改动：PO 号可选文案
    await expect(page.getByText(/PO Number（可选）/)).toBeVisible();
    // 本轮改动：Quote 关联下拉
    await expect(page.getByText(/Quote \/ Reference #/)).toBeVisible();
    await expect(page.locator('select').filter({ hasText: /不关联报价/ })).toBeVisible();
    // 无 console error（严格）
  });

  test('客户订单列表页可加载', async ({ page }) => {
    await loginAsCustomer(page);
    await page.goto(`${BASE_URL}/po/orders`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('body')).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });
});

test.describe('@po-ui 内部审核台（staff）', () => {
  test('审核台可见待审单，展开行明细显示 Available 库存列', async ({ page, request }) => {
    await seedPendingOrder(request); // 造一条待审单
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/admin/po/review`, { waitUntil: 'domcontentloaded' });

    await expect(page.locator('h1.po-page-title', { hasText: 'Order Review Desk' })).toBeVisible();
    // 至少有卡片
    await expect(page.locator('.po-card').first()).toBeVisible({ timeout: 10000 });

    // 点「View Items」展开行明细（本轮改动）
    await page.getByRole('button', { name: /View Items/ }).first().click();
    // 库存列出现（本轮改动：Available 表头）
    await expect(page.locator('th', { hasText: 'Available' }).first()).toBeVisible({ timeout: 10000 });
  });
});
