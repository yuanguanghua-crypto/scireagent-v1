/**
 * PO 订单 · 全流程真浏览器 E2E（逐步走完 UI）
 *
 * 定位：用**真实浏览器**把 PO 全流程逐步跑一遍 ——
 *   ① 客户 UI 提交（真填表：搜商品→选 SKU→数量→提交）
 *   ② staff 审核台 Approve
 *   ③ staff 发货台 Create Shipment → Mark Shipped → Mark Delivered
 *   ④ staff 发票台 Issue Invoice
 *   ⑤ staff 收款 Record Payment
 *   ⑥ 客户在订单列表确认单据存在
 *
 * 前置：dev 后端 :8000 + 前端 :5173；三个 seed 跑过（含夹具商品须 status=active）。
 * 运行：剥代理 + workers=1 --project=chromium --output=<独立目录> -g "@po-full"
 */
const { test, expect } = require('@playwright/test');
const { loginAsCustomer, loginAsStaff, logout, BASE_URL } = require('./helpers/auth.cjs');

test.describe('@po-full 全流程真浏览器', () => {
  test('客户提交 → staff 审核 → 发货 → 签收 → 开票 → 收款', async ({ page }) => {
    test.setTimeout(180000); // 全流程多次登录+导航，默认 45s 不够
    const poNumber = `E2E-FULL-${Date.now()}`;

    // ───── ① 客户：UI 提交 PO ─────
    await loginAsCustomer(page);
    await page.goto(`${BASE_URL}/po/submit`, { waitUntil: 'domcontentloaded' });

    await page.getByPlaceholder('无 PO 号可留空').fill(poNumber);
    await page.getByRole('button', { name: '+ Add Line Item' }).click();

    // 搜商品（PoSubmit 的 @input 触发 searchProducts）
    const prodInput = page.locator('.po-table tbody input.po-input').first();
    await prodInput.fill('E2E PO Test');
    await page.locator('.po-search-item').first().click({ timeout: 15000 });

    // 选 SKU（index 1 跳过占位 '— SKU —'）
    await page.locator('.po-table tbody select').first().selectOption({ index: 1 });
    // 数量
    await page.locator('.po-table tbody input[type="number"]').first().fill('2');

    // 提交
    await page.getByRole('button', { name: 'Submit PO' }).click();
    await expect(page.locator('.po-callout')).toContainText(/submitted successfully/i, { timeout: 20000 });
    const orderNo = (await page.locator('.po-callout .po-mono').innerText()).trim();
    expect(orderNo).toMatch(/^ORD-/);

    // ───── ② staff：审核台 Approve ─────
    await logout(page); // ★ 切角色前必须先登出（已登录访问 /login 会被守卫重定向）
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/admin/po/review`, { waitUntil: 'domcontentloaded' });
    const reviewCard = page.locator('.po-card', { hasText: poNumber });
    await expect(reviewCard).toBeVisible({ timeout: 20000 });
    await reviewCard.getByRole('button', { name: 'Approve' }).click();
    // 审核后应离开待审队列（confirmed）
    await expect(page.locator('.po-card', { hasText: poNumber })).toHaveCount(0, { timeout: 20000 });

    // ───── ③ staff：发货台 Create Shipment + Mark Shipped + Delivered ─────
    await page.goto(`${BASE_URL}/admin/po/shipments`, { waitUntil: 'domcontentloaded' });
    await page.locator('tr', { hasText: orderNo }).first().click();
    await page.locator('.po-field', { hasText: 'Carrier' }).locator('input').fill('FedEx');
    await page.locator('.po-field', { hasText: /Tracking #/ }).locator('input').fill(`TRK-${Date.now()}`);
    await page.getByRole('button', { name: 'Create Shipment' }).click();

    const markShipped = page.getByRole('button', { name: 'Mark Shipped' }).first();
    await expect(markShipped).toBeVisible({ timeout: 20000 });
    await markShipped.click();
    // 签收（需填 received by）
    const receivedBy = page.getByPlaceholder('Received by').first();
    await expect(receivedBy).toBeVisible({ timeout: 20000 });
    await receivedBy.fill('E2E Receiver');
    await page.getByRole('button', { name: 'Mark Delivered' }).first().click();

    // ───── ④ staff：发票台 Issue Invoice ─────
    await page.goto(`${BASE_URL}/admin/po/invoicing`, { waitUntil: 'domcontentloaded' });
    await page.locator('tr', { hasText: orderNo }).first().click();
    await page.getByRole('button', { name: 'Issue Invoice' }).click();

    // ───── ⑤ staff：收款 Record Payment ─────
    const amount = page.locator('.po-field', { hasText: 'Amount' }).locator('input').first();
    await expect(amount).toBeVisible({ timeout: 20000 });
    await amount.fill('20.00');
    await page.getByRole('button', { name: 'Record Payment' }).click();

    // ───── ⑥ 客户：订单列表可见该单 ─────
    await logout(page); // ★ 切回客户需先登出
    await loginAsCustomer(page);
    await page.goto(`${BASE_URL}/po/orders`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('body')).toContainText(orderNo, { timeout: 20000 });
  });
});
