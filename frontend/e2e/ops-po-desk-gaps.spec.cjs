/**
 * PO 内部台 · I 维（交互）空白补齐 —— shipments / invoicing / organizations
 *
 * 覆盖 INTERACTION_VERDICT.md 里 3 个 `✗` 未命中项：
 *   1. `/ops/po/shipments` — **创建 ShippingRecord**（此前只测过 mark-shipped / delivered）
 *   2. `/ops/po/invoicing` — **开票字段**（此前只测「对 DELIVERED 开票」这个动作）
 *   3. `/ops/po/organizations` — **订单查看**（此前只测机构/地址）
 *
 * ## 拟人化纪律
 * 全部数据用**真 UI** 造：客户在 /po/submit 填表提交 → staff 在审核台 Approve →
 * 发货台建发货单 → 发票台开票。**没有任何一条 spec 用 POST 接口造前置状态**。
 * 唯一用到接口的地方是 `afterAll` 的**清理**（删除本用例创建的订单，非被测路径）。
 *
 * ## 数据标记 / 清理
 * 每条 PO 的 po_number 都带 `E2E-<ts>-<4位随机>`；`afterAll` 按该标记**精确**回查订单并
 * DELETE（不碰其他行、不按数量清理）。发货记录随订单级联删除。
 *
 * ## 运行
 *   npx playwright test e2e/ops-po-desk-gaps.spec.cjs --project=chromium \
 *     --reporter=line --output=/tmp/pw-po
 */
const { test, expect, request } = require('@playwright/test');
const {
  BASE_URL, loginAsCustomer, loginAsStaff, logout,
} = require('./helpers/auth.cjs');
const { getAdminToken } = require('./helpers/poHelpers.cjs');

const ROOT = 'http://localhost:8000';
const API = '/api/v1';

// 本轮创建的所有 PO 号（用于 afterAll 精确清理）
const createdPoNumbers = [];

function makeTag() {
  return `E2E-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

/* ─────────────── 清理（仅删除本用例创建的那一条订单） ─────────────── */

async function deleteOrderByPoNumber(poNumber) {
  const token = await getAdminToken();
  const ctx = await request.newContext({ baseURL: ROOT });
  try {
    const res = await ctx.get(`${API}/orders/`, {
      headers: { Authorization: `Token ${token}` },
      params: { page_size: 200 },
    });
    const body = await res.json();
    const rows = body?.data?.results || body?.data || [];
    const mine = rows.find((o) => o.po_number === poNumber);
    if (!mine) return; // 已不存在 ⇒ 无需清理
    const del = await ctx.delete(`${API}/orders/${mine.id}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    if (!del.ok()) {
      // 不静默：清理失败要能被看见（多为状态机不允许删除），但不影响用例判定
      console.warn(`[cleanup] 删除订单 ${poNumber}(id=${mine.id}) 失败：${del.status()}`);
    }
  } finally {
    await ctx.dispose();
  }
}

test.afterAll(async () => {
  for (const po of createdPoNumbers) {
    await deleteOrderByPoNumber(po).catch((e) => console.warn('[cleanup] error', po, e));
  }
});

/* ─────────────── 纯 UI 的公共步骤 ─────────────── */

/**
 * 客户侧真填表提交 PO（选择器证据见 src/views/po/PoSubmit.vue）：
 *   - PO 号输入框 placeholder「无 PO 号可留空」           :208
 *   - 「+ Add Line Item」按钮                              :327
 *   - 商品搜索 input（placeholder「Search product…」）      :294
 *   - 搜索结果项 `.po-search-item`                          :303-304
 *   - SKU 下拉 `select.po-select`                           :312-317
 *   - 数量 input[type=number] / 单价 input[placeholder=0.00] :319-320
 *   - 成功回执 `.po-callout` 内含 `.po-mono` 订单号          :196-201
 */
async function submitPoViaUI(page, poNumber) {
  await loginAsCustomer(page);
  await page.goto(`${BASE_URL}/po/submit`, { waitUntil: 'domcontentloaded' });

  await page.getByPlaceholder('无 PO 号可留空').fill(poNumber);
  await page.getByRole('button', { name: '+ Add Line Item' }).click();

  const row = page.locator('.po-table tbody tr').first();
  await row.getByPlaceholder('Search product…').fill('E2E PO Test');
  await page.locator('.po-search-item').first().click({ timeout: 20000 });
  await row.locator('select.po-select').selectOption({ index: 1 }); // 跳过占位「— SKU —」
  await row.locator('input[type="number"]').fill('2');
  await row.locator('input[placeholder="0.00"]').fill('10.00');

  await page.getByRole('button', { name: 'Submit PO' }).click();
  const callout = page.locator('.po-callout').filter({ hasText: /submitted successfully/i });
  await expect(callout).toBeVisible({ timeout: 20000 });
  const orderNo = (await callout.locator('.po-mono').innerText()).trim();
  expect(orderNo).toMatch(/^ORD-/);
  createdPoNumbers.push(poNumber);
  return orderNo;
}

/**
 * staff 在审核台 Approve（选择器证据：src/views/admin/OrderReviewDesk.vue 的
 * `.po-card` 卡片 + Approve 按钮；用法同已绿的 po-lifecycle.fullflow.spec.cjs:50-54）。
 */
async function approveViaUI(page, poNumber) {
  await page.goto(`${BASE_URL}/ops/po/review`, { waitUntil: 'domcontentloaded' });
  const card = page.locator('.po-card', { hasText: poNumber });
  await expect(card).toBeVisible({ timeout: 20000 });
  await card.getByRole('button', { name: 'Approve' }).click();
  await expect(page.locator('.po-card', { hasText: poNumber })).toHaveCount(0, { timeout: 20000 });
}

/**
 * 发货台：选中订单 → 填 Carrier / Tracking # → Create Shipment。
 * 选择器证据（src/views/admin/PoShipmentDesk.vue）：
 *   - 订单行可点（`@click="openOrder(o)"`）                       :82
 *   - Carrier / Tracking # 输入框（.po-field > .po-input）        :99-100
 *   - 明细数量 input[type=number]                                 :109
 *   - 「Create Shipment」按钮                                     :113
 *   - 已建发货单卡片 `.po-shipment`（含 StatusBadge/运单号/carrier）:117-123
 */
async function openShipmentDeskOrder(page, orderNo) {
  await page.goto(`${BASE_URL}/ops/po/shipments`, { waitUntil: 'domcontentloaded' });
  const row = page.locator('tr', { hasText: orderNo }).first();
  await expect(row).toBeVisible({ timeout: 20000 });
  await row.click();
  const detailCard = page.locator('.po-card').filter({ hasText: 'New Shipment' });
  await expect(detailCard).toBeVisible({ timeout: 20000 });
  return detailCard;
}

async function createShipmentViaUI(page, orderNo, carrier, tracking) {
  const detailCard = await openShipmentDeskOrder(page, orderNo);

  await detailCard.locator('.po-field').filter({ hasText: 'Carrier' }).locator('input').fill(carrier);
  await detailCard.locator('.po-field').filter({ hasText: /Tracking #/ }).locator('input').fill(tracking);

  // 明细行数量可编辑（真交互，不是只读展示）
  const qty = detailCard.locator('table.po-table tbody input[type="number"]').first();
  await expect(qty).toBeVisible();
  await qty.fill('2');

  await page.getByRole('button', { name: 'Create Shipment' }).click();
  return detailCard;
}

/* ══════════════════════════════════════════════════════════════
 * 1) /ops/po/shipments — 创建 ShippingRecord
 * ══════════════════════════════════════════════════════════════ */
test.describe('@local-only /ops/po/shipments · 创建 ShippingRecord', { tag: ['@local-only'] }, () => {
  test('真填 Carrier/运单号/数量 → Create Shipment → 发货单出现在下方列表且刷新后仍在', async ({ page }) => {
    test.setTimeout(180000); // 客户提交 + 审核 + 发货，多次登录与导航

    const tag = makeTag();
    const carrier = `E2E-CARRIER-${tag}`;
    const tracking = `E2E-TRK-${tag}`;

    // ① 客户 UI 提交 PO
    const orderNo = await submitPoViaUI(page, tag);
    await expect(page.locator('.po-callout .po-mono')).toContainText(orderNo);

    // ② staff 审核台 Approve（订单进入 confirmed ⇒ 出现在发货台）
    await logout(page);
    await loginAsStaff(page);
    await approveViaUI(page, tag);

    // ③ 发货台新建发货单（被测交互）
    await createShipmentViaUI(page, orderNo, carrier, tracking);

    // 断言效果 1：下方 Shipments 区域出现本条发货单（运单号 + 物流公司可见）
    const shipmentCard = page.locator('.po-shipment').filter({ hasText: tracking });
    await expect(shipmentCard).toBeVisible({ timeout: 20000 });
    await expect(shipmentCard).toContainText(carrier);
    // 断言效果 2：状态徽章为初始态 preparing（模型默认值，models.py:346-349）
    await expect(shipmentCard.locator('.po-badge, [class*="badge"]').first()).toContainText(/preparing/i);
    // 断言效果 3：「No shipments yet.」占位消失（PUShipmentDesk.vue:133）
    await expect(page.locator('.po-muted', { hasText: 'No shipments yet.' })).toHaveCount(0);

    // 断言效果 4：刷新页面 → 重新选中该单，发货单仍在（证明落库，不是前端乐观渲染）
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('tr', { hasText: orderNo }).first().click();
    await expect(page.locator('.po-shipment').filter({ hasText: tracking })).toBeVisible({ timeout: 20000 });
  });
});

/* ══════════════════════════════════════════════════════════════
 * 2) /ops/po/invoicing — 开票字段
 * ══════════════════════════════════════════════════════════════ */
test.describe('@local-only /ops/po/invoicing · 开票字段', { tag: ['@local-only'] }, () => {
  test('对 DELIVERED 单选 Net 45 开票 → 发票号/到期日/金额/状态字段正确，且重新拉详情仍在', async ({ page }) => {
    test.setTimeout(240000); // 全链路：提交 → 审核 → 发货 → 签收 → 开票

    const tag = makeTag();
    const carrier = `E2E-CARRIER-${tag}`;
    const tracking = `E2E-TRK-${tag}`;

    // ① 客户 UI 提交（2 × 10.00 = $20.00）
    const orderNo = await submitPoViaUI(page, tag);

    // ② staff 审核
    await logout(page);
    await loginAsStaff(page);
    await approveViaUI(page, tag);

    // ③ 发货台：建发货单 → Mark Shipped → 填签收人 → Mark Delivered
    //   （选择器证据：PUShipmentDesk.vue:125-129 的 Mark Shipped / Received by / Mark Delivered）
    await createShipmentViaUI(page, orderNo, carrier, tracking);
    const shipmentCard = page.locator('.po-shipment').filter({ hasText: tracking });
    await expect(shipmentCard).toBeVisible({ timeout: 20000 });

    await shipmentCard.getByRole('button', { name: 'Mark Shipped' }).click();
    const receivedBy = page.getByPlaceholder('Received by').first();
    await expect(receivedBy).toBeVisible({ timeout: 20000 });
    await receivedBy.fill(`E2E-RCV-${tag}`);
    await page.getByRole('button', { name: 'Mark Delivered' }).first().click();
    // 签收后该发货单徽章变 delivered（状态真实推进，才能开票）
    await expect(page.locator('.po-shipment').filter({ hasText: tracking })).toContainText(/delivered/i, { timeout: 20000 });

    // ④ 发票台：选单 → 断言「未开票」态 → 选 Net 45 → Issue Invoice
    //   选择器证据（src/views/admin/PoInvoicingDesk.vue）：
    //     - 订单行可点                                           :70
    //     - 未开票提示 .po-callout + 账期 select + Issue 按钮     :84-92
    //     - 开票后展示 发票号 .po-tag / 状态徽章 / Due date / 金额 :96-99
    await page.goto(`${BASE_URL}/ops/po/invoicing`, { waitUntil: 'domcontentloaded' });
    const orderRow = page.locator('tr', { hasText: orderNo }).first();
    await expect(orderRow).toBeVisible({ timeout: 20000 });
    await orderRow.click();

    const notInvoiced = page.locator('.po-callout').filter({ hasText: 'Not yet invoiced.' });
    await expect(notInvoiced).toBeVisible({ timeout: 20000 });
    await notInvoiced.locator('select.po-select').selectOption('NET45');
    await page.getByRole('button', { name: 'Issue Invoice' }).click();

    // 断言 1：发票号字段（格式 INV-YYYY-NNNN，生成逻辑见 backend/.../services.py:231-237）
    const invoiceTag = page.locator('.po-tag').filter({ hasText: /^INV-/ }).first();
    await expect(invoiceTag).toBeVisible({ timeout: 20000 });
    const invoiceNo = (await invoiceTag.innerText()).trim();
    expect(invoiceNo).toMatch(/^INV-\d{4}-\d{4}$/);

    // 断言 2：到期日字段 = 开票日 + Net45（服务端 NET_DAYS[NET45]=45，services.py:223-227/254）
    const dueText = await page.locator('.po-muted', { hasText: /^Due \d{4}-\d{2}-\d{2}$/ }).first().innerText();
    const dueDate = new Date(dueText.replace('Due ', ''));
    const diffDays = Math.round((dueDate - new Date(new Date().toISOString().slice(0, 10))) / 86400000);
    expect(diffDays).toBeGreaterThanOrEqual(44); // 允许 1 天时区/边界误差
    expect(diffDays).toBeLessThanOrEqual(46);

    // 断言 3：金额字段 = 订单总额 $20.00（2 × 10.00）
    await expect(page.locator('.po-num').filter({ hasText: '$20.00' }).first()).toBeVisible();

    // 断言 4：发票状态徽章 = issued（Invoice.Status.ISSUED，models.py:229）
    await expect(page.locator('.po-badge, [class*="badge"]').filter({ hasText: /issued/i }).first()).toBeVisible();

    // 断言 5：切到另一单再切回该单 ⇒ 详情重新走 GET /orders/<id>/ ⇒ 发票号仍在（服务端真值，非前端缓存）
    //   ⚠️ 这里**不能**用 page.reload() 验证：开票后订单状态由 delivered → invoiced，而本页列表
    //   过滤条件 `o.status === 'delivered' || o.invoice`（PoInvoicingDesk.vue:21）依赖列表返回
    //   `invoice` 字段，可 OrderListSerializer 的 fields 里**没有 invoice**
    //   （backend/apps/transactions/api/v1/serializers.py:58-61）⇒ 刷新后该单会从列表消失。
    //   这是本页另一个真实缺陷，见文件末尾 test.fixme 用例。
    const otherRow = page.locator('tbody tr').filter({ hasNotText: orderNo }).first();
    if (await otherRow.count()) await otherRow.click();
    await page.locator('tr', { hasText: orderNo }).first().click();
    await expect(page.locator('.po-tag').filter({ hasText: invoiceNo })).toBeVisible({ timeout: 20000 });
  });
});

/* ══════════════════════════════════════════════════════════════
 * 3) /ops/po/organizations — 订单查看
 * ══════════════════════════════════════════════════════════════ */
test.describe('@local-only /ops/po/organizations · 订单查看', { tag: ['@local-only'] }, () => {
  /**
   * 交互形态（先读码确认）：本页没有独立「查看订单」按钮 —— 点机构行即选中，
   * 右侧卡片按机构拉订单并渲染表格。证据：
   *   - 机构行 `@click="selectOrg(o)"`                       PoOrgManagement.vue:55
   *   - 右侧卡片标题 `{{ selectedOrg.name }} — Orders`       :67
   *   - 订单表：Order / Status / Total / Created 四列         :68-76
   *   - 取数 getOrgOrders(org.id) ⇒ GET /orders/?organization_id=  （adminPo.js:93-95）
   */
  /**
   * ⚠️ 前置数据（dev 库固定事实，2026-10-21 实测）：
   *   只有「E2E Customer Org」(id=4) 名下有订单（983 单）；其余机构 0 单。
   *   ⇒ 「有订单的机构」用 id=4 那个，「0 单机构」用「E2E Supplier Ops」(id=6)。
   *   两者成对使用，正好构成 D1 的正/反两个方向。
   */
  const ORG_WITH_ORDERS = 'E2E Customer Org'
  const ORG_WITHOUT_ORDERS = 'E2E Supplier Ops'

  test('点机构行 → 右侧出现「<机构名> — Orders」表格，订单号/状态/金额/日期均渲染', async ({ page }) => {
    test.setTimeout(90000);
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/ops/po/organizations`, { waitUntil: 'domcontentloaded' });

    await expect(page.locator('h1.po-page-title', { hasText: 'Organization Management' })).toBeVisible();

    // ★ 必须点**有订单**的机构：修复 D1 之前随便点哪个都能看到行（因为漏了过滤、显示全库），
    //   修复后 0 单机构会是空态 ⇒ 旧写法（点 E2E Supplier Ops 却断言有行）等于在钉住缺陷。
    const orgRow = page.locator('tr', { hasText: ORG_WITH_ORDERS }).first();
    await expect(orgRow, `dev 库应有机构「${ORG_WITH_ORDERS}」且名下有订单`).toBeVisible({ timeout: 20000 });
    await orgRow.click();

    // 断言 1：右侧卡片标题随选中机构变化
    const ordersCard = page.locator('.po-card').filter({ hasText: `${ORG_WITH_ORDERS} — Orders` });
    await expect(ordersCard).toBeVisible({ timeout: 20000 });

    // 断言 2：表头四列齐全
    await expect(ordersCard.locator('th', { hasText: 'Order' })).toBeVisible();
    await expect(ordersCard.locator('th', { hasText: 'Created' })).toBeVisible();

    // 断言 3：表格里确实渲染了订单号（ORD-xxx）+ 状态徽章 + 金额
    const firstOrderNo = ordersCard.locator('tbody tr').first().locator('td.po-mono').first();
    await expect(firstOrderNo).toBeVisible({ timeout: 20000 });
    await expect(firstOrderNo).toHaveText(/^ORD-/);
    await expect(ordersCard.locator('tbody tr').first().locator('td.po-num')).toContainText(/\$/);
  });

  /**
   * D1 回归（2026-10-21 **已修**，此例从 `test.fixme` 转正）：
   *
   * 缺陷现场：后端 `OrderViewSet.filterset_fields` 原先只有 `['status']`，
   * **不认 `organization_id`** ⇒ `GET /orders/?organization_id=6` 返回全量订单。
   * 实测（admin token）：organization_id=6 与 4 返回同一批（org4 的 937 单），
   * 而 org6「E2E Supplier Ops」一单都没有 ⇒ 本页「订单查看」展示的是**全库订单**。
   *
   * 修法：`transactions/api/v1/views.py` 的 filterset 补 `organization` + `organization_id`
   * （后端单测 `test_cross_org_visibility.py::OrderOrganizationFilterTest` 5 例钉住，
   *  含「客户传别的机构 id 不得提权」的反向断言）。
   *
   * 本用例断言：选中 0 单机构时右表**必须为空**，而不是显示其他机构的订单。
   */
  test('选择「E2E Supplier Ops」（0 单机构）时右表应为空，而不是显示其他机构的订单', async ({ page }) => {
    test.setTimeout(90000);
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/ops/po/organizations`, { waitUntil: 'domcontentloaded' });
    await page.locator('tr', { hasText: ORG_WITHOUT_ORDERS }).first().click();

    const ordersCard = page.locator('.po-card').filter({ hasText: `${ORG_WITHOUT_ORDERS} — Orders` });
    await expect(ordersCard).toBeVisible({ timeout: 20000 });

    // 该机构名下有 0 单 ⇒ 组件走 `v-else-if="orgLoading"` 之后的空态分支
    // （`PoOrgManagement.vue:80`：`<div v-else class="po-empty">No orders for this organization.</div>`）
    // 所以表格**根本不渲染**，不能断言 `th` 存在。
    await expect(
      ordersCard.locator('.po-empty'),
      '0 单机构必须显示空态文案，而不是别的机构的订单',
    ).toHaveText(/No orders for this organization/i, { timeout: 20000 });
    await expect(ordersCard.locator('table')).toHaveCount(0);
    await expect(ordersCard.locator('tbody tr'), '必须一行订单都没有').toHaveCount(0);
  });
});
