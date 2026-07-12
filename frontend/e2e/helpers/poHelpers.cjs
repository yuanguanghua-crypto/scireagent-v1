/**
 * PO 门户 E2E helper —— API 侧数据工厂 + 清理。
 * 用于阶段 4（PO 门户穷举）setup/teardown：构造不同状态订单、推进状态机、取消清理。
 * 所有写操作均配套 cleanup（cancel），保证库干净、可重复。
 *
 * 注意：request context 的 baseURL 取根域 'http://localhost:8000'，所有路径自行带 '/api/v1' 前缀，
 * 避免 baseURL 带路径时绝对路径引用把 '/api/v1' 前缀丢掉（new URL('/x', base+'/api/v1') 会丢掉 /api/v1）。
 */
const { ADMIN_USER, ADMIN_PASS, CUST_USER, CUST_PASS } = require('./auth.cjs');
const ROOT = 'http://localhost:8000';
const API = '/api/v1';

async function apiContext(token) {
  const { request } = require('@playwright/test');
  return request.newContext({
    baseURL: ROOT,
    extraHTTPHeaders: token ? { Authorization: `Token ${token}` } : {},
  });
}

async function getToken(username, password) {
  const { request } = require('@playwright/test');
  const ctx = await request.newContext({ baseURL: ROOT });
  try {
    const resp = await ctx.post(`${API}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { username, password },
    });
    const body = await resp.json();
    return body?.data?.token || null;
  } finally {
    await ctx.dispose().catch(() => {});
  }
}

async function getAdminToken() {
  return getToken(ADMIN_USER, ADMIN_PASS);
}
async function getCustomerToken() {
  return getToken(CUST_USER, CUST_PASS);
}

// 找一个带真实 SKU 的产品（UI/API 提交测试用）。
// 经实证：dev 库 SKU 挂在 products 24-53 上（/skus/ 列表可查），product 列表/详情端点
// 不暴露 skus 顶层键（detail 端点把数据嵌套在 data.product 下）。故直接从 /skus/ 取真实
// (product_id, sku_id) 再补产品名，避免依赖不可靠的 PATCH 种子路径。
async function getProductWithSku(token) {
  const ctx = await apiContext(token);
  try {
    const res = await ctx.get(`${API}/skus/`, { params: { page_size: 1 } });
    const body = await res.json();
    const arr = body?.data?.results || body?.data || body?.results || [];
    if (!arr.length) return null;
    const sku = arr[0];
    const pid = sku.product_id;
    if (!pid) return null;
    const pres = await ctx.get(`${API}/products/${pid}/`);
    const pbody = await pres.json();
    const prod = pbody?.data || pbody;
    return { id: pid, name: prod.name, sku: { id: sku.id, sku_code: sku.sku_code } };
  } finally {
    await ctx.dispose().catch(() => {});
  }
}

// 通过 API 提交一个 PO（JSON；multipart 方括号格式后端不展开，dev 下不可靠）。
// 后端 submit 响应只回 { order_no, status }，不含 id，故回查 id 一并返回。
async function submitPoApi(token, { poNumber, productId, skuId, qty = 1, price = '10.00' }) {
  const ctx = await apiContext(token);
  try {
    const res = await ctx.post(`${API}/orders/po/`, {
      headers: { 'Content-Type': 'application/json' },
      data: {
        po_number: poNumber,
        shipping_name: 'E2E Ship',
        shipping_address: '1 E2E Way, Test City',
        shipping_email: 'e2e@lab.edu',
        items: [{ product_id: productId, sku_id: skuId, quantity: qty, unit_price: String(price) }],
      },
    });
    const body = await res.json().catch(() => ({}));
    const data = body?.data || body || {};
    if (data.order_no) {
      data.id = await findOrderIdByPo(token, poNumber);
    }
    return data;
  } finally {
    await ctx.dispose().catch(() => {});
  }
}

async function findOrderIdByPo(adminToken, poNumber) {
  const ctx = await apiContext(adminToken);
  try {
    const res = await ctx.get(`${API}/orders/`, { params: { po_number: poNumber, page_size: 20 } });
    const body = await res.json();
    // 列表端点 data 为纯数组（非 {results} 包装）
    const results = body?.data?.results || body?.results || body?.data || [];
    return results.find((o) => o.po_number === poNumber)?.id || null;
  } finally {
    await ctx.dispose().catch(() => {});
  }
}

async function getOrder(adminToken, id) {
  const ctx = await apiContext(adminToken);
  try {
    const res = await ctx.get(`${API}/orders/${id}/`);
    const body = await res.json();
    return body?.data || body;
  } finally {
    await ctx.dispose().catch(() => {});
  }
}

// 通用：POST 一个 admin 动作端点
async function adminPost(adminToken, path, body) {
  const ctx = await apiContext(adminToken);
  try {
    await ctx.post(path, { headers: { 'Content-Type': 'application/json' }, data: body || {} });
  } finally {
    await ctx.dispose().catch(() => {});
  }
}

async function approve(adminToken, id) {
  return adminPost(adminToken, `${API}/orders/${id}/approve/`);
}
async function reject(adminToken, id, reason = 'e2e') {
  return adminPost(adminToken, `${API}/orders/${id}/reject/`, { reason });
}
async function createShipmentApi(adminToken, id, items) {
  return adminPost(adminToken, `${API}/orders/${id}/shipments/`, {
    carrier: 'DHL',
    tracking_number: 'TRK' + Date.now(),
    items: items.map((it) => ({ order_item_id: it.id, quantity: it.quantity })),
  });
}
async function markShippedApi(adminToken, sid) {
  return adminPost(adminToken, `${API}/shipments/${sid}/mark-shipped/`);
}
async function markDeliveredApi(adminToken, sid, receivedBy = 'E2E') {
  return adminPost(adminToken, `${API}/shipments/${sid}/mark-delivered/`, { received_by: receivedBy });
}
async function issueInvoiceApi(adminToken, id, terms = 'NET30') {
  return adminPost(adminToken, `${API}/orders/${id}/invoice/`, { payment_terms: terms });
}

// 把订单推进到 delivered（approve → shipment → shipped → delivered）
async function advanceToDelivered(adminToken, id) {
  await approve(adminToken, id);
  const order = await getOrder(adminToken, id);
  await createShipmentApi(adminToken, id, order.items || []);
  const refreshed = await getOrder(adminToken, id);
  const sid = refreshed.shipments?.[0]?.id;
  if (sid) {
    await markShippedApi(adminToken, sid);
    await markDeliveredApi(adminToken, sid);
  }
}

// 造一个 quote_pending 订单（legacy checkout 流程：加购物车 → checkout payment_method=quote）。
// 仅用于阶段 5 AdminOrderDetail 的 quote 操作路径（quote_pending → quoted 状态机合法）。
async function seedQuotePending(custToken) {
  const prod = await getProductWithSku(custToken);
  const ctx = await apiContext(custToken);
  try {
    await ctx.post(`${API}/basket/items`, {
      headers: { 'Content-Type': 'application/json' },
      data: { product_id: prod.id, sku_id: prod.sku.id, quantity: 1 },
    });
    const res = await ctx.post(`${API}/checkout/`, {
      headers: { 'Content-Type': 'application/json' },
      data: {
        payment_method: 'quote',
        shipping_name: 'E2E Quote',
        shipping_address: '1 E2E Way, Test City',
        shipping_email: 'e2e@lab.edu',
      },
    });
    const body = await res.json().catch(() => ({}));
    const data = body?.data || body || {};
    if (data.id) return data;
    // 回查（checkout 响应是 OrderDetailSerializer 包裹）
    return data;
  } finally {
    await ctx.dispose().catch(() => {});
  }
}

// ── 各状态订单种子（AdminOrderDetail 迁移后穷举测试用）──
async function payInvoiceApi(adminToken, invoiceId, amount, method = 'wire') {
  return adminPost(adminToken, `${API}/invoices/${invoiceId}/pay/`, { amount, method });
}
async function completeOrderApi(adminToken, id) {
  return adminPost(adminToken, `${API}/admin/orders/${id}/complete/`);
}
async function seedPoReceived(custToken) {
  const prod = await getProductWithSku(custToken);
  return submitPoApi(custToken, { poNumber: 'PO-E2E-PR-' + Date.now(), productId: prod.id, skuId: prod.sku.id });
}
async function seedApproved(custToken, adminToken) {
  const po = await seedPoReceived(custToken);
  await approve(adminToken, po.id);
  return po;
}
async function seedShipped(custToken, adminToken) {
  const po = await seedApproved(custToken, adminToken);
  const o = await getOrder(adminToken, po.id);
  await createShipmentApi(adminToken, po.id, o.items || []);
  const r = await getOrder(adminToken, po.id);
  const sid = r.shipments?.[0]?.id;
  if (sid) await markShippedApi(adminToken, sid);
  return po;
}
async function seedDelivered(custToken, adminToken) {
  const po = await seedShipped(custToken, adminToken);
  const r = await getOrder(adminToken, po.id);
  const sid = r.shipments?.[0]?.id;
  if (sid) await markDeliveredApi(adminToken, sid);
  return po;
}
async function seedInvoiced(custToken, adminToken) {
  const po = await seedDelivered(custToken, adminToken);
  await issueInvoiceApi(adminToken, po.id);
  return po;
}
async function seedPaid(custToken, adminToken) {
  const po = await seedInvoiced(custToken, adminToken);
  const o = await getOrder(adminToken, po.id);
  const invId = o.invoice?.id;
  if (invId) await payInvoiceApi(adminToken, invId, o.grand_total, 'wire');
  return po;
}
async function seedCompleted(custToken, adminToken) {
  const po = await seedPaid(custToken, adminToken);
  await completeOrderApi(adminToken, po.id);
  return po;
}
async function seedCancelled(custToken, adminToken) {
  const po = await seedPoReceived(custToken);
  await cancelOrder(custToken, adminToken, po.id);
  return po;
}

// 清理：优先 customer 取消，失败回退 admin 取消
async function cancelOrder(customerToken, adminToken, id) {
  for (const t of [customerToken, adminToken]) {
    if (!t || !id) continue;
    const ctx = await apiContext(t);
    try {
      const r = await ctx.post(`${API}/orders/${id}/cancel/`);
      if (r.ok()) return true;
    } catch {
      /* 尝试下一种 */
    } finally {
      await ctx.dispose().catch(() => {});
    }
  }
  return false;
}

// 经实证：dev 库 SKU 挂在 products 24-53 上，detail 端点把数据嵌套在 data.product 下，
// 且 Product 嵌套 PATCH 种子路径不可靠。故测试直接复用真实 SKU 数据（getProductWithSku），
// 不再做写操作种子，避免引入脏数据。

module.exports = {
  ROOT,
  getAdminToken,
  getCustomerToken,
  getProductWithSku,
  submitPoApi,
  findOrderIdByPo,
  getOrder,
  approve,
  reject,
  createShipmentApi,
  markShippedApi,
  markDeliveredApi,
  issueInvoiceApi,
  advanceToDelivered,
  seedQuotePending,
  cancelOrder,
  payInvoiceApi,
  completeOrderApi,
  seedPoReceived,
  seedApproved,
  seedShipped,
  seedDelivered,
  seedInvoiced,
  seedPaid,
  seedCompleted,
  seedCancelled,
};
