/**
 * PO 订单 · 分批发货 / 部分签收（L1 API 级）
 *
 * 为什么单独一条：`po-lifecycle.api` 只测「单批全发」，而“分批发货”是设计里明确支持的
 * 交互（`ShippingService` 支持多批，`_all_items_delivered` 按**已送达数量之和**判定）。
 * 这条路此前**没有任何自动化覆盖**，2026-10-28 真跑一遍立刻暴露两个问题：
 *
 *   ① 审计留痕不完整（已修，本文件第 4 步反向断言锁死）
 *      实际发生 4 个批次动作（2 发 2 签），`status_log` 只留 2 条 —— 因为原代码是
 *      `if 状态机允许推进: transition_to(...)`，而**中间批次**既不能把订单推进到
 *      shipped（已是 shipped）也不能推进到 delivered（还没全送达）⇒ 整段日志被跳过。
 *      结果订单详情页的 Status Timeline 缺条，运营查不到“某一批什么时候发的”。
 *      修法：状态不变的批次动作也写 StatusLog（from=to=当前状态）。
 *
 *   ② 「首批发货后能否再建第二批」= 400 INVALID_OPERATION（**未修，待业务决策**）
 *      `create_shipment` 只允许 confirmed/in_production，而首批 mark_shipped 后订单
 *      已是 shipped ⇒ “先发一批、下周再发” 做不到。本文件**不断言**这条的期望值
 *      （避免把待定行为固化成闸门），只在注释里标注；要测可用 `-g` 单独跑。
 *
 * 夹具同 `po-lifecycle.api.spec.cjs`（`e2e_po_fixture.json`）。
 * 运行：npx playwright test e2e/po-multi-batch.api.spec.cjs --project=chromium --workers=1
 */
const { test, expect } = require('@playwright/test');
const { loadFixture, GENERATE_HINT } = require('./helpers/po-fixture.cjs');

const API_BASE = process.env.API_BASE || 'http://localhost:8000/api/v1';
const FIXTURE = loadFixture();
test.beforeEach(() => { test.skip(!FIXTURE, GENERATE_HINT); });

const ADMIN = { u: process.env.E2E_USER || 'admin', p: process.env.E2E_PASS || 'admin123' };
const CUST = {
  u: process.env.E2E_CUSTOMER_USER || 'e2e_customer',
  p: process.env.E2E_CUSTOMER_PASS || 'E2ePass123!',
};

let _seq = 0;
const uniquePo = () => `E2E-MB-${Date.now()}-${++_seq}`;

async function apiLogin(ctx, { u, p }) {
  const res = await ctx.post(`${API_BASE}/auth/login`, { data: { username: u, password: p } });
  expect(res.status(), `login ${u} 应 200`).toBe(200);
  return (await res.json()).data.token;
}
const H = (token) => ({ headers: { Authorization: `Token ${token}` } });

async function post(ctx, token, path, data = {}) {
  return ctx.post(`${API_BASE}${path}`, { ...H(token), data });
}

async function getOrder(ctx, token, id) {
  const res = await ctx.get(`${API_BASE}/orders/${id}/`, H(token));
  expect(res.status()).toBe(200);
  return (await res.json()).data;
}

async function findOrderByPo(ctx, token, po) {
  const res = await ctx.get(`${API_BASE}/orders/?page_size=400`, H(token));
  const data = (await res.json()).data;
  const list = Array.isArray(data) ? data : (data.results || []);
  const hit = list.find((o) => o.po_number === po);
  expect(hit, `应能在订单列表找到 PO ${po}`).toBeTruthy();
  return hit;
}

test.describe('@po-multibatch 分批发货与部分签收', () => {
  test('4 件拆两批：中间批次签收后订单不得提前 delivered；每个批次动作都必须留痕', async ({ request }) => {
    test.setTimeout(120000);
    const admin = await apiLogin(request, ADMIN);
    const cust = await apiLogin(request, CUST);
    const po = uniquePo();
    let orderId;
    const created = [];

    try {
      // ── 建单：1 行 × 4 件 ──
      const submit = await request.post(`${API_BASE}/orders/po/`, {
        ...H(cust),
        data: {
          po_number: po,
          shipping_name: 'Multi Batch Lab',
          shipping_address: '1 Batch Rd',
          shipping_email: 'e2e_customer@example.com',
          items: [{ sku_id: FIXTURE.sku_id, quantity: 4 }],
        },
      });
      expect(submit.status(), `提交 PO 应 201: ${await submit.text()}`).toBe(201);
      const found = await findOrderByPo(request, admin, po);
      orderId = found.id;
      created.push(orderId);

      const approve = await post(request, admin, `/orders/${orderId}/approve/`);
      expect(approve.status(), '审核应 200').toBe(200);

      const withItems = await getOrder(request, admin, orderId);
      const itemId = withItems.items[0].id;

      // ── ① 两批都必须**在发货前**建好（shipped 之后建不了，见文件头 ②）──
      const shipA = await post(request, admin, `/orders/${orderId}/shipments/`, {
        carrier: 'SF', tracking_number: 'MB-A',
        items: [{ order_item_id: itemId, quantity: 2 }],
      });
      const shipB = await post(request, admin, `/orders/${orderId}/shipments/`, {
        carrier: 'SF', tracking_number: 'MB-B',
        items: [{ order_item_id: itemId, quantity: 2 }],
      });
      expect(shipA.status(), `建批次 A 应 201: ${await shipA.text()}`).toBe(201);
      expect(shipB.status(), `建批次 B 应 201: ${await shipB.text()}`).toBe(201);

      const beforeShip = await getOrder(request, admin, orderId);
      expect(beforeShip.status, '建了发货单但还没发运，订单应仍为 confirmed').toBe('confirmed');
      const [a, b] = beforeShip.shipments.map((s) => s.id);

      // ── ② 批次 A 发货 → 订单推进 shipped ──
      expect((await post(request, admin, `/shipments/${a}/mark-shipped/`)).status()).toBe(200);
      expect((await getOrder(request, admin, orderId)).status).toBe('shipped');

      // ── ③ 批次 A 签收 → **只送达 2/4，订单必须仍为 shipped**（核心断言）──
      expect((await post(request, admin, `/shipments/${a}/mark-delivered/`,
        { received_by: 'Receiver A' })).status()).toBe(200);
      const afterA = await getOrder(request, admin, orderId);
      expect(afterA.status, '部分签收（2/4）不得把订单推进为 delivered').toBe('shipped');

      // ── ④ 批次 B 发货 + 签收 → 此时才 delivered ──
      expect((await post(request, admin, `/shipments/${b}/mark-shipped/`)).status()).toBe(200);
      expect((await getOrder(request, admin, orderId)).status, '第二批发货不改变 shipped').toBe('shipped');
      expect((await post(request, admin, `/shipments/${b}/mark-delivered/`,
        { received_by: 'Receiver B' })).status()).toBe(200);
      const done = await getOrder(request, admin, orderId);
      expect(done.status, '两批全部送达后订单应为 delivered').toBe('delivered');

      // ── ⑤ 审计完整性：6 个批次动作（2 建 + 2 发 + 2 签）都要在 status_log 里 ──
      const shipLogs = done.status_logs.filter((l) => l.action_type === 'shipment');
      const notes = shipLogs.map((l) => l.note);
      expect(shipLogs.length,
        `批次动作应有 6 条日志（2 建 + 2 发 + 2 签），实际 ${shipLogs.length}：${JSON.stringify(notes)}`)
        .toBe(6);
      expect(notes.filter((n) => /marked shipped/.test(n)).length,
        '两批各自都要有「marked shipped」记录（中间批次曾被跳过）').toBe(2);
      expect(notes.filter((n) => /delivered/.test(n)).length,
        '两批各自都要有签收记录（中间批次曾被跳过）').toBe(2);
      expect(notes.some((n) => /awaiting remaining items/.test(n)),
        '中间批次签收应留下「awaiting remaining items」记录').toBe(true);

      // ── ⑥ 两批的收货人都落库 ──
      const reci = done.shipments.map((s) => s.received_by).sort();
      expect(reci).toEqual(['Receiver A', 'Receiver B']);
    } finally {
      // 清理：delivered 仍可 cancel（VALID_TRANSITIONS['delivered'] 含 cancelled）
      if (orderId) await post(request, admin, `/orders/${orderId}/cancel/`, { reason: 'e2e-multibatch cleanup' });
    }
  });
});
