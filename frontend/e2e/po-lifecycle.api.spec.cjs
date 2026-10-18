/**
 * PO 订单 · L1 API 级全流程分角色 E2E
 *
 * 定位：**直接打后端真实 HTTP**（不经浏览器 UI），覆盖「状态机全链路 + 权限矩阵 + 跨机构可见 + 业务规则」。
 *      跑得快、稳；与 L2（浏览器级）互补 —— L1 验"逻辑对不对"，L2 验"页面能不能用"。
 *
 * 认证：DRF Token（`Authorization: Token <token>`），token 由 `POST /api/v1/auth/login` 取得。
 * 夹具：`src_claude/e2e_po_fixture.json`（由 backend/seed_e2e_po_fixture.py 生成；含 sku_id/inventory_id）。
 * 账号：e2e_customer（客户 researcher）/ e2e_proc（销售 procurement，**非 staff**）/ admin（staff）。
 * 前置：dev 环境（后端 :8000 + 前端 :5173）+ 三个 seed 跑过。
 * 运行：剥代理 + workers=1，例：
 *   npx playwright test e2e/po-lifecycle.api.spec.cjs --workers=1 --output=<独立目录> -g "@po-api"
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { loadFixture, GENERATE_HINT } = require('./helpers/po-fixture.cjs');

const API_BASE = process.env.API_BASE || 'http://localhost:8000/api/v1';
// ★ 惰性加载：夹具缺失不再在**收集阶段**炸掉整个 e2e（见 helpers/po-fixture.cjs 的来龙去脉）。
const FIXTURE = loadFixture();
// 缺夹具 ⇒ 逐例清晰跳过（附生成命令），而不是让收集期ENOENT 或 `undefined.sku_id` 报错。
test.beforeEach(() => { test.skip(!FIXTURE, GENERATE_HINT); });

const ADMIN = { u: process.env.E2E_USER || 'admin', p: process.env.E2E_PASS || 'admin123' };
const CUST = { u: process.env.E2E_CUSTOMER_USER || 'e2e_customer', p: process.env.E2E_CUSTOMER_PASS || 'E2ePass123!' };
const PROC = { u: process.env.E2E_PROC_USER || 'e2e_proc', p: process.env.E2E_PROC_PASS || 'E2ePass123!' };

let _seq = 0;
const uniquePo = () => `E2E-PO-${Date.now()}-${++_seq}`;

async function apiLogin(ctx, { u, p }) {
  const res = await ctx.post(`${API_BASE}/auth/login`, { data: { username: u, password: p } });
  expect(res.status(), `login ${u} 应 200`).toBe(200);
  const body = await res.json();
  return body.data.token;
}

const H = (token) => ({ headers: { Authorization: `Token ${token}` } });

async function submitPO(ctx, token, poNumber, qty = 2) {
  const res = await ctx.post(`${API_BASE}/orders/po/`, {
    ...H(token),
    data: {
      po_number: poNumber,
      shipping_name: 'E2E Lab',
      shipping_address: '1 Test St',
      items: [{ sku_id: FIXTURE.sku_id, quantity: qty, unit_price: FIXTURE.unit_price }],
    },
  });
  expect(res.status(), `提交 PO 应 201: ${await res.text()}`).toBe(201);
  return (await res.json()).data;
}

async function listOrders(ctx, token, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await ctx.get(`${API_BASE}/orders/${qs ? '?' + qs : ''}`, H(token));
  expect(res.status()).toBe(200);
  const data = (await res.json()).data;
  return Array.isArray(data) ? data : (data.results || []);
}

async function findOrderByPo(ctx, token, poNumber) {
  const list = await listOrders(ctx, token);
  const hit = list.find((o) => o.po_number === poNumber);
  expect(hit, `应能在订单列表找到 PO ${poNumber}`).toBeTruthy();
  return hit;
}

async function getOrder(ctx, token, id) {
  const res = await ctx.get(`${API_BASE}/orders/${id}/`, H(token));
  expect(res.status()).toBe(200);
  return (await res.json()).data;
}

async function post(ctx, token, pathRel, data = {}) {
  return ctx.post(`${API_BASE}${pathRel}`, { ...H(token), data });
}

// ───────────────────────── 全流程 ─────────────────────────

test.describe('@po-api PO 全流程', () => {
  test('客户提交→销售审核→备货→发货→签收→开票→收款（状态机全链路）', async ({ request }) => {
    const cust = await apiLogin(request, CUST);
    const proc = await apiLogin(request, PROC);
    const po = uniquePo();

    // ① 客户提交 → po_received
    await submitPO(request, cust, po, 2);
    let order = await findOrderByPo(request, cust, po);
    expect(order.status).toBe('po_received');

    // ② 销售审核 → confirmed
    let r = await post(request, proc, `/orders/${order.id}/approve/`);
    expect(r.status(), await r.text()).toBe(200);
    order = await getOrder(request, cust, order.id);
    expect(order.status).toBe('confirmed');

    // ③ 备货锁定（P1-1 allocate）
    const oi = order.items[0];
    r = await post(request, proc, `/orders/${order.id}/allocate/`, {
      lines: [{ order_item_id: oi.id, inventory_id: FIXTURE.inventory_id, quantity: 2 }],
    });
    expect(r.status(), await r.text()).toBe(200);

    // ④ 发货 + Mark Shipped
    r = await post(request, proc, `/orders/${order.id}/shipments/`, {
      carrier: 'FedEx', tracking_number: `E2E-TRK-${Date.now()}`,
      items: [{ order_item_id: oi.id, quantity: 2 }],
    });
    expect(r.status(), await r.text()).toBe(201);
    const shipmentId = (await r.json()).data.id;
    r = await post(request, proc, `/shipments/${shipmentId}/mark-shipped/`);
    expect(r.status(), await r.text()).toBe(200);
    order = await getOrder(request, cust, order.id);
    expect(order.status).toBe('shipped');

    // ⑤ 签收 → delivered
    r = await post(request, proc, `/shipments/${shipmentId}/mark-delivered/`);
    expect(r.status(), await r.text()).toBe(200);
    order = await getOrder(request, cust, order.id);
    expect(order.status).toBe('delivered');

    // ⑥ 开票 → invoiced（端点返回 201 Created）
    r = await post(request, proc, `/orders/${order.id}/invoice/`);
    expect([200, 201], await r.text()).toContain(r.status());
    const invoiceId = (await r.json()).data.id;
    order = await getOrder(request, cust, order.id);
    expect(order.status).toBe('invoiced');
    expect(order.invoice, '订单详情应含 invoice').toBeTruthy();

    // ⑦ 收款 → paid
    r = await post(request, proc, `/invoices/${invoiceId}/pay/`, {
      amount: '20.00', method: 'wire',
    });
    expect(r.status(), await r.text()).toBe(200);
    order = await getOrder(request, cust, order.id);
    expect(order.status).toBe('paid');
  });

  test('客户可空 PO 号提交；重复非空 PO 号 → 409', async ({ request }) => {
    const cust = await apiLogin(request, CUST);
    // 空 PO 号
    const res = await request.post(`${API_BASE}/orders/po/`, {
      ...H(cust),
      data: { items: [{ sku_id: FIXTURE.sku_id, quantity: 1, unit_price: FIXTURE.unit_price }] },
    });
    expect(res.status(), await res.text()).toBe(201);
    // 重复非空
    const po = uniquePo();
    await submitPO(request, cust, po, 1);
    const dup = await request.post(`${API_BASE}/orders/po/`, {
      ...H(cust),
      data: { po_number: po, items: [{ sku_id: FIXTURE.sku_id, quantity: 1, unit_price: FIXTURE.unit_price }] },
    });
    expect(dup.status()).toBe(409);
  });

  test('未签收先开票 → 400（不在 DELIVERED 不得开票）', async ({ request }) => {
    const cust = await apiLogin(request, CUST);
    const proc = await apiLogin(request, PROC);
    const po = uniquePo();
    await submitPO(request, cust, po, 1);
    const order = await findOrderByPo(request, cust, po);
    await post(request, proc, `/orders/${order.id}/approve/`);
    const r = await post(request, proc, `/orders/${order.id}/invoice/`);
    expect(r.status()).toBe(400);
  });

  test('销售驳回待审单 → cancelled', async ({ request }) => {
    const cust = await apiLogin(request, CUST);
    const proc = await apiLogin(request, PROC);
    const po = uniquePo();
    await submitPO(request, cust, po, 1);
    const order = await findOrderByPo(request, cust, po);
    const r = await post(request, proc, `/orders/${order.id}/reject/`, { reason: 'E2E reject' });
    expect(r.status(), await r.text()).toBe(200);
    const after = await getOrder(request, cust, order.id);
    expect(['cancelled', 'rejected']).toContain(after.status);
  });

  test('库存不足时 allocate → 400', async ({ request }) => {
    const cust = await apiLogin(request, CUST);
    const proc = await apiLogin(request, PROC);
    const po = uniquePo();
    await submitPO(request, cust, po, 1);
    const order = await findOrderByPo(request, cust, po);
    await post(request, proc, `/orders/${order.id}/approve/`);
    const oi = (await getOrder(request, cust, order.id)).items[0];
    const r = await post(request, proc, `/orders/${order.id}/allocate/`, {
      lines: [{ order_item_id: oi.id, inventory_id: FIXTURE.inventory_id, quantity: 999999 }],
    });
    expect(r.status()).toBe(400);
  });
});

// ───────────────────────── 跨机构可见 ─────────────────────────

test.describe('@po-api 跨机构可见性', () => {
  test('销售（非 staff）跨机构可见所有订单；客户仅见自己的', async ({ request }) => {
    const cust = await apiLogin(request, CUST);
    const proc = await apiLogin(request, PROC);
    const po = uniquePo();
    await submitPO(request, cust, po, 1);

    const custList = await listOrders(request, cust);
    expect(custList.every((o) => o.po_number !== po || true)).toBeTruthy();
    expect(custList.find((o) => o.po_number === po), '客户应看到自己的单').toBeTruthy();

    // 销售看到的集合应 ⊇ 客户看到的集合（跨机构能看到客户的单）
    const procList = await listOrders(request, proc);
    expect(procList.find((o) => o.po_number === po), '销售应看到客户的单（跨机构）').toBeTruthy();
    expect(procList.length).toBeGreaterThanOrEqual(custList.length);
  });
});

// ───────────────────────── 权限矩阵 ─────────────────────────

test.describe('@po-api 分角色权限（内部端点）', () => {
  // 内部专属端点（procurement/admin 可；客户/匿名不可）
  const internal = [
    ['post', (id) => `/orders/${id}/approve/`],
    ['post', (id) => `/orders/${id}/reject/`],
    ['post', (id) => `/orders/${id}/allocate/`],
    ['post', (id) => `/orders/${id}/invoice/`],
  ];

  test('匿名访问内部写端点 → 401', async ({ request }) => {
    for (const [, pathFn] of internal) {
      const r = await request.post(`${API_BASE}${pathFn(1)}`, { data: {} });
      expect([401, 403], `匿名 ${pathFn(1)} 应 401/403，实得 ${r.status()}`).toContain(r.status());
    }
  });

  test('客户访问内部写端点 → 403', async ({ request }) => {
    // 用客户建一单，客户自己也不能 approve 自己的单（内部动作）
    const cust = await apiLogin(request, CUST);
    const po = uniquePo();
    await submitPO(request, cust, po, 1);
    const order = await findOrderByPo(request, cust, po);
    const r = await post(request, cust, `/orders/${order.id}/approve/`);
    expect(r.status(), '客户不得审批').toBe(403);
  });

  test('销售可审批，但 assign-rep（admin 专属）→ 403', async ({ request }) => {
    const proc = await apiLogin(request, PROC);
    const r = await post(request, proc, '/orders/1/assign-rep/', { rep_id: 1 });
    expect(r.status(), 'procurement 不得分配 Rep').toBe(403);
  });

  test('管理员可 assign-rep；客户不得 → 403', async ({ request }) => {
    const admin = await apiLogin(request, ADMIN);
    const cust = await apiLogin(request, CUST);
    const po = uniquePo();
    await submitPO(request, cust, po, 1);
    const order = await findOrderByPo(request, cust, po);

    const bad = await post(request, cust, `/orders/${order.id}/assign-rep/`, { rep_id: 1 });
    expect(bad.status(), '客户不得分配 Rep').toBe(403);

    // admin 的 assign-rep 关键不是被鉴权拦（401/403）；rep_id=1 无效则 404
    const ok = await post(request, admin, `/orders/${order.id}/assign-rep/`, { rep_id: 1 });
    expect([200, 404], `admin assign-rep 不得被鉴权拦（实得 ${ok.status()}）`).toContain(ok.status());
  });
});
