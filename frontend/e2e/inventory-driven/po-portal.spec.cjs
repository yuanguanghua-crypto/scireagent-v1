/**
 * 阶段 4 — PO 门户 11 页交互穷举（inventory-driven/po-portal.spec.cjs）
 *
 * 覆盖：客户侧 6 页（PoSubmit / PoOrderList / PoOrderDetail / PoAddressList / PoReorder / PoDownloadCenter）
 *      + 内部台 5 页（PoReviewDesk / PoShipmentDesk / PoInvoicingDesk / PoArReport / PoOrgManagement）
 * 选择器以真实源码为准（已逐页读取 src/views/po/*.vue + src/views/admin/Po*.vue）。
 * 交互以原生 .po-btn / .po-input / .po-select / .po-table / .po-callout 为主，Toast 经 ElMessage（.el-message）。
 *
 * 关键环境事实（经实证，2026-07-11）：
 *   - dev 库 SKU 挂在 products 24-53 上（/skus/ 列表可查真实 product_id+sku_id）。
 *     submitPo 必填有效 sku_id。beforeAll 经 getProductWithSku 取一个真实 (product, sku) 复用，
 *     不写脏数据。
 *   - detail 端点把产品数据嵌套在 data.product 下；PoSubmit.selectProduct 已修复为读
 *     detail.product?.skus（原为 detail.skus，导致 SKU 下拉永远 disabled → 无法提交 PO）。
 *   - 列表端点 data 为纯数组（非 {results} 包装），findOrderIdByPo 已处理。
 *   - /addresses/ CRUD 是 P1 未实现（源码明文 warn），Save 走错误提示；测试只断言页面渲染 + P1 提示 + 表单可开 + 不崩溃。
 *   - 写操作隔离：建单经 API cancel 清理；SKU 复用真实数据不新增。
 *
 * 运行：
 *   cd src_claude/frontend
 *   npx playwright test e2e/inventory-driven/po-portal.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsCustomer, loginAsStaff } = require('../helpers/auth');
const { attachConsoleErrorCollector } = require('../helpers/console');
const {
  getAdminToken, getCustomerToken, getProductWithSku,
  submitPoApi, findOrderIdByPo, approve, advanceToDelivered, cancelOrder,
} = require('../helpers/poHelpers');

// 已知环境噪声：无头沙箱内化学结构查看器 wasm 回退；/addresses/ P1 未实现 404。
const CONSOLE_WHITELIST = [
  'wasm streaming compile failed',
  'falling back to ArrayBuffer instantiation',
  'Failed to load resource',
];

async function gotoPage(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
}

// 共享：一个带真实 SKU 的产品（beforeAll 取，afterAll 不清理——复用真实数据）
let shared = null;
let adminTokenGlobal = null;

test.beforeAll(async () => {
  adminTokenGlobal = await getAdminToken();
  shared = await getProductWithSku(adminTokenGlobal);
});
test.afterAll(async () => {
  // 仅复用真实数据，无写操作需清理
});

test.describe('阶段4 PO 门户穷举', () => {

  // ============ 客户侧：PoSubmit ============
  test('PoSubmit: 渲染 + 添加行项目 + 产品搜索 + SKU 选择 可用', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/po/submit');
    await expect(page.locator('.po-page-title')).toHaveText('Submit Purchase Order');
    await expect(page.locator('input.po-input').first()).toBeVisible(); // PO Number
    // 添加行项目
    await page.locator('button', { hasText: '+ Add Line Item' }).click();
    await expect(page.locator('.po-table tbody tr')).toHaveCount(1);
    // 产品搜索 → 选结果（按共享产品名精确点中带 SKU 的产品）→ SKU 下拉启用
    const search = page.locator('.po-input[placeholder="Search product…"]').first();
    await search.fill(shared.name);
    await expect(page.locator('.po-search-item', { hasText: shared.name }).first()).toBeVisible({ timeout: 8000 });
    await page.locator('.po-search-item', { hasText: shared.name }).first().click();
    const skuSelect = page.locator('.po-table select.po-select').first();
    await expect(skuSelect).toBeEnabled({ timeout: 10000 });
    await skuSelect.selectOption({ index: 1 });
    await page.locator('.po-table input[type="number"]').first().fill('2');
    await page.locator('.po-input[placeholder="0.00"]').first().fill('9.99');
    expect(errors).toEqual([]);
  });

  test('PoSubmit: 空 PO 号提交 → 原生 alert 校验', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    page.on('dialog', async (d) => { await d.accept(); });
    await loginAsCustomer(page);
    await gotoPage(page, '/po/submit');
    await page.locator('button', { hasText: 'Submit PO' }).click();
    // 校验触发后仍在提交页（未跳转），且 alert 已处理
    await expect(page).toHaveURL(/\/po\/submit/, { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('PoSubmit: 完整填写提交 → 成功 callout（真实写 + 清理）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const custToken = await getCustomerToken();
    const adminToken = await getAdminToken();
    const poNumber = 'PO-E2E-' + Date.now();
    await loginAsCustomer(page);
    await gotoPage(page, '/po/submit');
    await page.locator('.po-card input.po-input').first().fill(poNumber);
    await page.locator('button', { hasText: '+ Add Line Item' }).click();
    const search = page.locator('.po-input[placeholder="Search product…"]').first();
    await search.fill(shared.name);
    await expect(page.locator('.po-search-item', { hasText: shared.name }).first()).toBeVisible({ timeout: 8000 });
    await page.locator('.po-search-item', { hasText: shared.name }).first().click();
    const skuSelect = page.locator('.po-table select.po-select').first();
    await expect(skuSelect).toBeEnabled({ timeout: 10000 });
    await skuSelect.selectOption({ index: 1 });
    await page.locator('.po-table input[type="number"]').first().fill('2');
    await page.locator('.po-input[placeholder="0.00"]').first().fill('9.99');
    await page.locator('button', { hasText: 'Submit PO' }).click();
    await expect(page.locator('.po-callout')).toContainText('PO submitted successfully', { timeout: 10000 });
    // 清理
    const id = await findOrderIdByPo(adminToken, poNumber);
    await cancelOrder(custToken, adminToken, id);
    expect(errors).toEqual([]);
  });

  // ============ 客户侧：PoOrderList ============
  test('PoOrderList: 渲染 + 状态过滤 + + New PO 跳转', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/po/orders');
    await expect(page.locator('.po-page-title')).toHaveText('My Purchase Orders');
    await expect(page.locator('select.po-select').first()).toBeVisible(); // 状态过滤
    await page.locator('a', { hasText: '+ New PO' }).click();
    await expect(page).toHaveURL(/\/po\/submit/, { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  // ============ 客户侧：PoOrderDetail ============
  test('PoOrderDetail: 经 API 建单 → 详情渲染 order_no', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const custToken = await getCustomerToken();
    const adminToken = await getAdminToken();
    const poNumber = 'PO-E2E-D-' + Date.now();
    const created = await submitPoApi(custToken, { poNumber, productId: shared.productId, skuId: shared.sku.id });
    const id = await findOrderIdByPo(adminToken, poNumber);
    await loginAsCustomer(page);
    await gotoPage(page, `/po/orders/${id}`);
    await expect(page.locator('.po-page-title')).toContainText(created.order_no || poNumber, { timeout: 10000 });
    await expect(page.locator('.po-section-title', { hasText: 'Line Items' })).toBeVisible();
    await cancelOrder(custToken, adminToken, id);
    expect(errors).toEqual([]);
  });

  // ============ 客户侧：PoAddressList ============
  // /addresses/ 是 P1 未实现（源码明文 warn），Save 走错误提示且不持久化。
  // 测试只断言：页面渲染 + P1 提示可见 + 表单可开 + 填后 Save 不崩溃（页面仍在）。
  test('PoAddressList: 渲染 + P1 提示 + 表单可开 + Save 不崩溃', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    page.on('dialog', async (d) => { await d.accept(); });
    await loginAsCustomer(page);
    await gotoPage(page, '/po/addresses');
    await expect(page.locator('.po-page-title')).toHaveText('Address Book');
    await expect(page.locator('.po-callout.warn').first()).toBeVisible({ timeout: 8000 });
    await page.locator('button', { hasText: '+ New Address' }).click();
    await expect(page.locator('.po-card', { hasText: 'New Address' })).toBeVisible({ timeout: 8000 });
    const ts = Date.now();
    await page.locator('.po-field', { hasText: 'Address Line 1' }).locator('input').fill('1 E2E Addr ' + ts);
    await page.locator('.po-field', { hasText: 'City' }).locator('input').fill('E2ECity');
    await page.locator('.po-field', { hasText: 'Postal Code' }).locator('input').fill('00000');
    await page.locator('button', { hasText: 'Save' }).click();
    // 不崩溃：页面标题仍在，且未跳转离开
    await expect(page.locator('.po-page-title')).toHaveText('Address Book', { timeout: 8000 });
    expect(errors).toEqual([]);
  });

  // ============ 客户侧：PoReorder ============
  test('PoReorder: 渲染（列表或空态）+ Re-order 跳转', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/po/reorder');
    await expect(page.locator('.po-page-title')).toHaveText('Re-order');
    // 先等加载结束（订单行出现，或空态不再 Loading），避免 race
    const loading = page.locator('.po-empty', { hasText: 'Loading' });
    if (await loading.count()) {
      await expect(loading).toHaveCount(0, { timeout: 15000 });
    }
    const rows = page.locator('.po-table tbody tr');
    if (await rows.count()) {
      await rows.first().locator('button', { hasText: 'Re-order' }).click();
      await expect(page).toHaveURL(/\/po\/submit\?reorder=/, { timeout: 8000 });
    } else {
      await expect(page.locator('.po-empty')).toContainText('No completed orders', { timeout: 15000 });
    }
    expect(errors).toEqual([]);
  });

  // ============ 客户侧：PoDownloadCenter ============
  test('PoDownloadCenter: 渲染（列表或空态）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsCustomer(page);
    await gotoPage(page, '/po/downloads');
    await expect(page.locator('.po-page-title')).toHaveText('Download Center');
    await expect(page.locator('.po-card').first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  // ============ 内部台：PoReviewDesk ============
  test('PoReviewDesk: 种子 PO_RECEIVED → Approve 后离开待审列表（真实写 + 清理）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const custToken = await getCustomerToken();
    const adminToken = await getAdminToken();
    const poNumber = 'PO-E2E-RV-' + Date.now();
    const created = await submitPoApi(custToken, { poNumber, productId: shared.productId, skuId: shared.sku.id });
    await loginAsStaff(page);
    await gotoPage(page, '/admin/po/review');
    await expect(page.locator('.po-page-title')).toHaveText('Order Review Desk');
    const card = page.locator('.po-card', { hasText: created.order_no || poNumber });
    await expect(card).toBeVisible({ timeout: 10000 });
    await card.locator('button', { hasText: 'Approve' }).click();
    await expect(page.locator('.po-card', { hasText: created.order_no || poNumber })).toHaveCount(0, { timeout: 10000 });
    // 清理（已 approve → confirmed，仍可 cancel）
    const id = await findOrderIdByPo(adminToken, poNumber);
    await cancelOrder(custToken, adminToken, id);
    expect(errors).toEqual([]);
  });

  // ============ 内部台：PoShipmentDesk ============
  test('PoShipmentDesk: 种子 confirmed → 打开订单 + Create Shipment（真实写 + 清理）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const custToken = await getCustomerToken();
    const adminToken = await getAdminToken();
    const poNumber = 'PO-E2E-SH-' + Date.now();
    const created = await submitPoApi(custToken, { poNumber, productId: shared.productId, skuId: shared.sku.id });
    const id = await findOrderIdByPo(adminToken, poNumber);
    await approve(adminToken, id); // → confirmed
    await loginAsStaff(page);
    await gotoPage(page, '/admin/po/shipments');
    await expect(page.locator('.po-page-title')).toHaveText('Shipment Desk');
    const row = page.locator('.po-table tbody tr', { hasText: created.order_no });
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.click();
    await expect(page.locator('.po-card', { hasText: 'Order ' + created.order_no })).toBeVisible({ timeout: 10000 });
    await page.locator('.po-field', { hasText: 'Carrier' }).locator('input').fill('DHL');
    await page.locator('.po-field', { hasText: 'Tracking #' }).locator('input').fill('TRK' + Date.now());
    await page.locator('button', { hasText: 'Create Shipment' }).click();
    await expect(page.locator('.po-shipment').first()).toBeVisible({ timeout: 10000 });
    await cancelOrder(custToken, adminToken, id);
    expect(errors).toEqual([]);
  });

  // ============ 内部台：PoInvoicingDesk ============
  test('PoInvoicingDesk: 种子 delivered → Issue Invoice 出现发票（真实写 + 清理）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const custToken = await getCustomerToken();
    const adminToken = await getAdminToken();
    const poNumber = 'PO-E2E-INV-' + Date.now();
    const created = await submitPoApi(custToken, { poNumber, productId: shared.productId, skuId: shared.sku.id });
    const id = await findOrderIdByPo(adminToken, poNumber);
    await advanceToDelivered(adminToken, id); // → delivered
    await loginAsStaff(page);
    await gotoPage(page, '/admin/po/invoicing');
    await expect(page.locator('.po-page-title')).toHaveText('Invoicing Desk');
    const row = page.locator('.po-table tbody tr', { hasText: created.order_no });
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.click();
    await expect(page.locator('.po-card', { hasText: 'Order ' + created.order_no })).toBeVisible({ timeout: 10000 });
    await page.locator('button', { hasText: 'Issue Invoice' }).click();
    await expect(page.locator('button', { hasText: 'Record Payment' })).toBeVisible({ timeout: 10000 });
    await cancelOrder(custToken, adminToken, id);
    expect(errors).toEqual([]);
  });

  // ============ 内部台：PoArReport ============
  test('PoArReport: 渲染 4 账龄桶 + 总额', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/admin/po/ar');
    await expect(page.locator('.po-page-title')).toHaveText('Accounts Receivable Aging');
    await expect(page.locator('.po-ar-cell')).toHaveCount(4, { timeout: 8000 });
    await expect(page.locator('.po-total-value').first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  // ============ 内部台：PoOrgManagement ============
  test('PoOrgManagement: 渲染机构列表 + 选中机构显示订单', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/admin/po/organizations');
    await expect(page.locator('.po-page-title')).toHaveText('Organization Management');
    await expect(page.locator('.po-table tbody tr').first()).toBeVisible({ timeout: 8000 });
    await page.locator('.po-table tbody tr').first().click();
    await expect(page.locator('.po-card', { hasText: 'Orders' }).first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });
});
