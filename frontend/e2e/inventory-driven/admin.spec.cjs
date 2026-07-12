/**
 * 阶段 5 — Admin 穷举（inventory-driven/admin.spec.cjs）
 *
 * 覆盖：AdminOrdersPage（列表/状态过滤/搜索/行点击）+ AdminOrderDetail（渲染 + 全状态机 UI 流转）。
 *
 * 重要环境事实（经实证，2026-07-11）：
 *   - AdminOrderDetail.vue 已按用户决策「A」迁移到 PO 新状态机，按钮条件对齐
 *     po_received→confirmed→in_production→shipped→delivered→invoiced→paid→completed，
 *     动作统一走 PO 门户端点（approveOrder / createShipment+markShipped / markDelivered /
 *     issueInvoice / payInvoice / completeOrder / cancelOrder）。
 *   - 因此本 spec 对每一条状态流转做「真实 UI 点击 → 状态推进」断言（绿）。
 *   - 状态机合法终态（paid / completed / cancelled）不可再 cancel，故清理时跳过这些（cancel 静默失败不影响）。
 *   - 种子：各状态经 PO 门户端点推进（seedPoReceived/Approved/Shipped/Delivered/Invoiced/Paid）；
 *     quote_pending 经 legacy checkout(quote)。
 *
 * 运行：
 *   cd src_claude/frontend
 *   npx playwright test e2e/inventory-driven/admin.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff } = require('../helpers/auth');
const { attachConsoleErrorCollector } = require('../helpers/console');
const {
  getAdminToken, getCustomerToken, getProductWithSku,
  submitPoApi, approve, advanceToDelivered, createShipmentApi, markShippedApi,
  getOrder, seedQuotePending, cancelOrder,
  seedPoReceived, seedApproved, seedShipped, seedDelivered, seedInvoiced, seedPaid,
} = require('../helpers/poHelpers');

const CONSOLE_WHITELIST = [
  'wasm streaming compile failed',
  'falling back to ArrayBuffer instantiation',
  'Failed to load resource',
];

async function gotoPage(page, path) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
}

let adminToken = null;
let custToken = null;
let shared = null;
const allCreated = [];

test.beforeAll(async () => {
  adminToken = await getAdminToken();
  custToken = await getCustomerToken();
  const prod = await getProductWithSku(adminToken);
  const ts = Date.now();
  const base = { productId: prod.id, skuId: prod.sku.id };

  // confirmed（PO 流程：submit → approve）
  const poC = await submitPoApi(custToken, { ...base, poNumber: `PO-E2E-A5-C-${ts}` });
  await approve(adminToken, poC.id);

  // delivered（submit → approve → shipment → shipped → delivered）
  const poD = await submitPoApi(custToken, { ...base, poNumber: `PO-E2E-A5-D-${ts}` });
  await advanceToDelivered(adminToken, poD.id);

  // quote_pending（legacy checkout quote）
  const poQ = await seedQuotePending(custToken);

  shared = {
    confirmed: { id: poC.id, order_no: poC.order_no },
    delivered: { id: poD.id, order_no: poD.order_no },
    quotePending: { id: poQ.id, order_no: poQ.order_no },
  };
  allCreated.push(poC.id, poD.id, poQ.id);
});

test.afterAll(async () => {
  // 终态（paid/completed/cancelled）不可 cancel，静默失败即可
  for (const id of allCreated) {
    await cancelOrder(custToken, adminToken, id).catch(() => {});
  }
});

test.describe('阶段5 Admin 穷举', () => {

  // ============ AdminOrdersPage ============
  test('AdminOrdersPage: 渲染 + 状态过滤 + 搜索 + 行点击进详情', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/admin/orders');

    await expect(page.locator('.admin-orders-page .page-title')).toHaveText('Order Management');
    // 表格渲染（库里有订单，含种子 confirmed）
    await expect(page.locator('.order-table tbody tr').first()).toBeVisible({ timeout: 10000 });

    // 状态过滤：选 Confirmed → 含种子 confirmed 行
    await page.locator('.filter-select').selectOption('confirmed');
    await expect(page.locator('.order-table tbody tr', { hasText: shared.confirmed.order_no }))
      .toBeVisible({ timeout: 10000 });

    // 搜索：在 confirmed 过滤下叠加搜索该订单号（避免 reset 与 search 的 fetch 竞态）
    await page.locator('.admin-orders-page .search-input').fill(shared.confirmed.order_no);
    await page.locator('.admin-orders-page .search-btn').click();
    await expect(page.locator('.order-table tbody tr', { hasText: shared.confirmed.order_no }))
      .toBeVisible({ timeout: 10000 });
    // 行点击进详情
    await page.locator('.order-table tbody tr', { hasText: shared.confirmed.order_no }).click();
    await expect(page).toHaveURL(new RegExp(`/admin/orders/${shared.confirmed.id}`), { timeout: 10000 });
    expect(errors).toEqual([]);
  });

  // ============ AdminOrderDetail: 渲染 ============
  test('AdminOrderDetail: delivered 订单渲染 header/items/customer/payment/shipping', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${shared.delivered.id}`);

    await expect(page.locator('.order-title')).toHaveText(`Order ${shared.delivered.order_no}`);
    await expect(page.locator('.items-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.section-title', { hasText: 'Customer' })).toBeVisible();
    await expect(page.locator('.section-title', { hasText: 'Payment' })).toBeVisible();
    await expect(page.locator('.section-title', { hasText: 'Shipping Address' })).toBeVisible();
    // Internal notes textarea 渲染
    await expect(page.locator('textarea.form-textarea')).toBeVisible();
    expect(errors).toEqual([]);
  });

  // ============ AdminOrderDetail: quote 操作（legacy quote 流程，合法可用） ============
  test('AdminOrderDetail: quote_pending → Enter Quote → Submit Quote → quoted', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${shared.quotePending.id}`);

    await expect(page.locator('.quote-form h3')).toHaveText('Enter Quote');
    await page.locator('.quote-form input[type="number"]').fill('123.45');
    await page.locator('.quote-form input[type="date"]').fill('2026-12-31');
    await page.locator('.quote-form .btn-action', { hasText: 'Submit Quote' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Quoted' })).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });

  // ============ AdminOrderDetail: 新状态机 UI 流转（穷举每条转移） ============

  test('AdminOrderDetail: po_received → Approve → confirmed', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const po = await seedPoReceived(custToken);
    allCreated.push(po.id);
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${po.id}`);

    await expect(page.locator('.btn-action', { hasText: 'Approve' })).toBeVisible({ timeout: 10000 });
    await page.locator('.btn-action', { hasText: 'Approve' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Confirmed' })).toBeVisible({ timeout: 10000 });
    // confirmed 态显示 Create Shipment
    await expect(page.locator('.btn-action', { hasText: 'Create & Mark Shipped' })).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('AdminOrderDetail: confirmed → Create & Mark Shipped → shipped', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const po = await seedApproved(custToken, adminToken);
    allCreated.push(po.id);
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${po.id}`);

    await expect(page.locator('.btn-action', { hasText: 'Create & Mark Shipped' })).toBeVisible({ timeout: 10000 });
    await page.locator('.btn-action', { hasText: 'Create & Mark Shipped' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Shipped' })).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });

  test('AdminOrderDetail: shipped → Mark as Delivered → delivered', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const po = await seedShipped(custToken, adminToken);
    allCreated.push(po.id);
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${po.id}`);

    await expect(page.locator('.btn-action', { hasText: 'Mark as Delivered' })).toBeVisible({ timeout: 10000 });
    await page.locator('.btn-action', { hasText: 'Mark as Delivered' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Delivered' })).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });

  test('AdminOrderDetail: delivered → Generate Invoice → invoiced', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const po = await seedDelivered(custToken, adminToken);
    allCreated.push(po.id);
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${po.id}`);

    await expect(page.locator('.btn-action', { hasText: 'Generate Invoice' })).toBeVisible({ timeout: 10000 });
    await page.locator('.btn-action', { hasText: 'Generate Invoice' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Invoiced' })).toBeVisible({ timeout: 10000 });
    // 发票区块出现
    await expect(page.locator('.section-title', { hasText: 'Invoice' })).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });

  test('AdminOrderDetail: invoiced → Record Payment → paid', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const po = await seedInvoiced(custToken, adminToken);
    allCreated.push(po.id);
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${po.id}`);

    await expect(page.locator('.btn-action', { hasText: 'Record Payment' })).toBeVisible({ timeout: 10000 });
    await page.locator('.btn-action', { hasText: 'Record Payment' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Paid' })).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });

  test('AdminOrderDetail: paid → Mark as Completed → completed', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const po = await seedPaid(custToken, adminToken);
    allCreated.push(po.id);
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${po.id}`);

    await expect(page.locator('.btn-action', { hasText: 'Mark as Completed' })).toBeVisible({ timeout: 10000 });
    await page.locator('.btn-action', { hasText: 'Mark as Completed' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Completed' })).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });

  test('AdminOrderDetail: confirmed → Cancel Order → cancelled', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    const po = await seedApproved(custToken, adminToken);
    allCreated.push(po.id);
    await loginAsStaff(page);
    await gotoPage(page, `/admin/orders/${po.id}`);

    await expect(page.locator('.btn-action', { hasText: 'Cancel Order' })).toBeVisible({ timeout: 10000 });
    await page.locator('.btn-action', { hasText: 'Cancel Order' }).click();
    await expect(page.locator('.status-badge', { hasText: 'Cancelled' })).toBeVisible({ timeout: 10000 });
    expect(errors).toEqual([]);
  });
});
