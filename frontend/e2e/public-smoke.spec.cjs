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
 *  - 详情页用真实 id（products/66、methods/35、protocols/128、applications/30、research-goals/27）；
 *    订单详情用占位 id=1（即使 404，只要 SPA 渲染出「未找到」也是成功加载，不报错）。
 *
 * 运行：
 *   cd src_claude/frontend
 *   npx playwright test e2e/public-smoke.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff, loginAsCustomer } = require('./helpers/auth');
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
  { path: '/applications/30', role: 'anonymous', name: 'AppDetail' },
  { path: '/methods', role: 'anonymous', name: 'MethodIndex' },
  { path: '/methods/35', role: 'anonymous', name: 'MethodDetail' },
  { path: '/protocols', role: 'anonymous', name: 'ProtocolIndex' },
  { path: '/protocols/128', role: 'anonymous', name: 'ProtocolDetail' },
  { path: '/products', role: 'anonymous', name: 'ProductIndex' },
  { path: '/products/66', role: 'anonymous', name: 'ProductDetail' },
  { path: '/research-goals', role: 'anonymous', name: 'RGIndex' },
  { path: '/research-goals/27', role: 'anonymous', name: 'RGDetail' },
  { path: '/quote-request', role: 'anonymous', name: 'QuoteRequestPage' },
  { path: '/cart', role: 'anonymous', name: 'CartPage' },
  { path: '/zzz-route-not-exist', role: 'anonymous', name: 'NotFound404' },

  // ── 认证页（customer）──
  { path: '/settings', role: 'customer', name: 'SettingsPage' },
  { path: '/checkout', role: 'customer', name: 'CheckoutPage' },
  { path: '/orders', role: 'customer', name: 'OrderListPage' },
  { path: '/orders/1', role: 'customer', name: 'OrderDetailPage' },
  { path: '/po/submit', role: 'customer', name: 'PoSubmit' },
  { path: '/po/orders', role: 'customer', name: 'PoOrderList' },
  { path: '/po/orders/1', role: 'customer', name: 'PoOrderDetail' },
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

test.describe('阶段0 全站路由冒烟雷达', () => {
  for (const r of ROUTES) {
    test(`${r.name} [${r.role}] ${r.path}`, async ({ page }) => {
      const errors = attachConsoleErrorCollector(page);

      // 认证页先登录对应角色
      if (r.role === 'customer') await loginAsCustomer(page);
      else if (r.role === 'admin') await loginAsStaff(page);

      // 导航（不用 networkidle，避免 AI 端点挂起）
      await page.goto(`${BASE_URL}${r.path}`, { waitUntil: 'domcontentloaded' });

      // 等待 Vue 挂载
      await page.waitForSelector('#app', { timeout: 20000 });

      // 防白屏：#app 渲染出非空内容
      const textLen = await page.evaluate(
        () => (document.querySelector('#app')?.innerText || '').trim().length
      );
      expect(textLen, `${r.path} 渲染内容为空（疑似白屏）`).toBeGreaterThan(0);

      // 无 console / pageerror（白屏与运行时异常雷达）
      expect(errors, `${r.path} 存在 console 错误:\n${errors.join('\n')}`).toEqual([]);
    });
  }
});
