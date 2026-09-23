/**
 * 阶段 0 — 全站路由冒烟雷达
 *
 * 目标：对全站每个可访问路由做「加载成功 + 0 console error + 页面渲染非空」的快速雷达，
 * 作为防白屏 / 运行时异常回归网。不做元素级交互（那是阶段 1~5）。
 *
 * 覆盖角色：
 *  - anonymous：公开页直接访问
 *  - customer ：登录 e2e_customer（is_staff=False）后访问认证页
 *  - admin    ：登录 admin（is_staff）后访问管理页
 *
 * 关键约定：
 *  - 不用 networkidle（避免出网 AI 端点挂起）。用 domcontentloaded + 等待 #app 渲染。
 *  - 每个用例挂 console / pageerror 收集器，末尾断言为空（白屏/异常雷达）。
 *  - 详情页 id **现算**（beforeAll 从 API 取真实首条）：applications / research-goals /
 *    orders / po 详情不再硬编码 id（原 products/66、methods/35 等静态 id 中，
 *    applications/30、research-goals/27、orders/1、po/orders/1 在 dev 库不存在 ⇒ 已改为现算）。
 *
 * 运行：
 *   cd src_claude/frontend
 *   npx playwright test e2e/public-smoke.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff, loginAsCustomer, CUST_USER, CUST_PASS } = require('./helpers/auth');
const { attachConsoleErrorCollector } = require('./helpers/console');

// 全站路由清单（对照 router/index.js + INTERACTION_INVENTORY.md）
// role: anonymous | customer | admin
const ROUTES = [
  // ── 公开页（匿名）──
  { path: '/', role: 'anonymous', name: 'HomePage' },
  { path: '/login', role: 'anonymous', name: 'Login' },
  { path: '/register', role: 'anonymous', name: 'Register' },
  { path: '/search', role: 'anonymous', name: 'SearchPage' },
  { path: '/applications', role: 'anonymous', name: 'AppIndex' },
  { path: '/applications/30', role: 'anonymous', name: 'AppDetail', dyn: 'app' },
  { path: '/methods', role: 'anonymous', name: 'MethodIndex' },
  { path: '/methods/35', role: 'anonymous', name: 'MethodDetail' },
  { path: '/protocols', role: 'anonymous', name: 'ProtocolIndex' },
  { path: '/protocols/128', role: 'anonymous', name: 'ProtocolDetail' },
  { path: '/products', role: 'anonymous', name: 'ProductIndex' },
  { path: '/products/66', role: 'anonymous', name: 'ProductDetail' },
  { path: '/research-goals', role: 'anonymous', name: 'RGIndex' },
  { path: '/research-goals/27', role: 'anonymous', name: 'RGDetail', dyn: 'rg' },
  { path: '/quote-request', role: 'anonymous', name: 'QuoteRequestPage' },
  { path: '/cart', role: 'anonymous', name: 'CartPage' },
  { path: '/zzz-route-not-exist', role: 'anonymous', name: 'NotFound404' },

  // ── 认证页（customer）──
  { path: '/settings', role: 'customer', name: 'SettingsPage' },
  { path: '/checkout', role: 'customer', name: 'CheckoutPage' },
  { path: '/orders', role: 'customer', name: 'OrderListPage' },
  { path: '/orders/1', role: 'customer', name: 'OrderDetailPage', dyn: 'order' },
  { path: '/po/submit', role: 'customer', name: 'PoSubmit' },
  { path: '/po/orders', role: 'customer', name: 'PoOrderList' },
  { path: '/po/orders/1', role: 'customer', name: 'PoOrderDetail', dyn: 'po' },
  { path: '/po/addresses', role: 'customer', name: 'PoAddressList' },
  { path: '/po/reorder', role: 'customer', name: 'PoReorder' },
  { path: '/po/downloads', role: 'customer', name: 'PoDownloadCenter' },

  // ── 管理员页（admin）──
  { path: '/workspace', role: 'admin', name: 'DashboardPage' },
  { path: '/workspace/products', role: 'admin', name: 'ProductsPage' },
  { path: '/workspace/products/new', role: 'admin', name: 'ProductEditNew' },
  { path: '/workspace/products/66/edit', role: 'admin', name: 'ProductEditDetail' },
  { path: '/workspace/goals', role: 'admin', name: 'GoalsPage' },
  { path: '/workspace/applications', role: 'admin', name: 'AppsPage' },
  { path: '/workspace/methods', role: 'admin', name: 'MethodsPage' },
  { path: '/workspace/protocols', role: 'admin', name: 'ProtocolsPage' },
  { path: '/workspace/references', role: 'admin', name: 'ReferencesPage' },
  { path: '/workspace/knowledge-intake', role: 'admin', name: 'KnowledgeIntake' },
  { path: '/admin/orders', role: 'admin', name: 'AdminOrdersPage' },
  { path: '/admin/orders/1', role: 'admin', name: 'AdminOrderDetail' },
  { path: '/admin/po/review', role: 'admin', name: 'PoReviewDesk' },
  { path: '/admin/po/shipments', role: 'admin', name: 'PoShipmentDesk' },
  { path: '/admin/po/invoicing', role: 'admin', name: 'PoInvoicingDesk' },
  { path: '/admin/po/ar', role: 'admin', name: 'PoArReport' },
  { path: '/admin/po/organizations', role: 'admin', name: 'PoOrgManagement' },
];

// ── 用例级 tier（2026-09-23 复核）─────────────────────────────────────────
// 原 4 条硬编码 dev 数据 id 的路由（/applications/30、/research-goals/27、/orders/1、
// /po/orders/1）会因"记录不存在 ⇒ 后端 404 ⇒ console 零错误断言失败"，属**依赖硬编码
// dev 数据 id**（其中 /po/orders/1 还跨轮 flaky）。
// ⇒ 修复方式：**现算 id**（从 API 取当前库真实首条记录），不再硬编码。
//    解析失败 ⇒ 用例显式失败（不静默跳过）。
// 全部 44 条均为只读（仅导航 + console 雷达，无写操作）⇒ @readonly + @local-only。
const API_ROOT = 'http://localhost:8000/api/v1';

async function firstId(request, path, { token = null, params = { page_size: 1 } } = {}) {
  const headers = token ? { Authorization: `Token ${token}` } : {};
  const resp = await request.get(`${API_ROOT}${path}`, { headers, params });
  const body = await resp.json().catch(() => ({}));
  const d = body?.data;
  const arr = Array.isArray(d) ? d : (d?.results || []);
  return arr[0]?.id ?? null;
}

async function customerToken(request) {
  const resp = await request.post(`${API_ROOT}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username: CUST_USER, password: CUST_PASS },
  });
  const body = await resp.json().catch(() => ({}));
  return body?.data?.token || null;
}

// 动态 id 现算（beforeAll 一次）。title 仍用静态 r.path 以保持与 GATE 表的可追溯映射。
let DYN = {};
test.beforeAll(async ({ request }) => {
  DYN = {
    app: await firstId(request, '/applications/'),
    rg: await firstId(request, '/research-goals/'),
  };
  const ct = await customerToken(request);
  DYN.custToken = ct;
  DYN.order = await firstId(request, '/orders/', { token: ct });
  DYN.po = await firstId(request, '/orders/', { token: ct, params: { page_size: 1, order_type: 'po' } });
});

function pathFor(r) {
  switch (r.dyn) {
    case 'app': return `/applications/${DYN.app}`;
    case 'rg': return `/research-goals/${DYN.rg}`;
    case 'order': return `/orders/${DYN.order}`;
    case 'po': return `/po/orders/${DYN.po}`;
    default: return r.path;
  }
}

test.describe('阶段0 全站路由冒烟雷达', () => {
  for (const r of ROUTES) {
    test(`${r.name} [${r.role}] ${r.path}`, { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
      const errors = attachConsoleErrorCollector(page);

      // 动态路由：现算真实 id（解析失败即显式失败，不静默跳过）
      let targetPath = r.path;
      if (r.dyn) {
        expect(DYN[r.dyn], `${r.name} 动态 id 未解析（dev 库无对应记录）`).toBeTruthy();
        targetPath = pathFor(r);
      }

      // 认证页先登录对应角色
      if (r.role === 'customer') await loginAsCustomer(page);
      else if (r.role === 'admin') await loginAsStaff(page);

      // 导航（不用 networkidle，避免 AI 端点挂起）
      await page.goto(`${BASE_URL}${targetPath}`, { waitUntil: 'domcontentloaded' });

      // 等待 Vue 挂载
      await page.waitForSelector('#app', { timeout: 20000 });

      // 防白屏：#app 渲染出非空内容
      const textLen = await page.evaluate(
        () => (document.querySelector('#app')?.innerText || '').trim().length
      );
      expect(textLen, `${targetPath} 渲染内容为空（疑似白屏）`).toBeGreaterThan(0);

      // 无 console / pageerror（白屏与运行时异常雷达）
      expect(errors, `${targetPath} 存在 console 错误:\n${errors.join('\n')}`).toEqual([]);
    });
  }
});
