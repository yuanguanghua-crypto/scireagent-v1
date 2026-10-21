/**
 * 订单 / PO · 错误处理路径 E2E（补齐 INTERACTION_VERDICT 的 5 个「alert 错误 / alert 校验」空白）
 *
 * ## 覆盖范围
 * | 页面 | 组件 | 本 spec 的用例 |
 * |---|---|---|
 * | /orders           | OrderListPage   | 列表接口 500 ⇒ 全局 toast + 列表降级为空态 |
 * | /orders/:id       | OrderDetailPage | ① 详情接口 500 ⇒ toast + 无内容；② 报价动作 500 ⇒ 原生 alert('Action failed') |
 * | /ops/orders       | AdminOrdersPage | 列表接口 500 ⇒ toast + 空态（无数据行） |
 * | /ops/orders/:id   | AdminOrderDetail| ① 详情接口 500 ⇒ toast + 无内容；② Approve 动作 500 ⇒ **持久** .error-banner |
 * | /po/submit        | PoSubmit        | 3 条原生 alert 校验（空行项目 / 行项目缺 SKU / 交付日期早于今天） |
 *
 * ## 错误 UI 的真相（先读码，不猜选择器）
 * - **全局 toast**：`frontend/src/utils/http.js` 的响应拦截器。任何非 2xx 都会
 *   `ElMessage.error(extractErrorMessage(data))`（http.js 响应拦截器 error 分支）。
 *   `{ detail: 'Injected failure for E2E' }` 会经 `extractErrorMessage` 的第 3 条规则
 *   （`if (data?.detail) return data.detail`）原样透出 ⇒ toast 文案可精确断言。
 *   ⚠️ 这是 **toast（约 3s 自动消失），不是持久横幅** —— 所以断言要「导航后立刻抓」。
 * - **`/orders` 与 `/ops/orders` 没有错误横幅**：
 *   - `stores/orders.js:22-24` `catch` 只 `console.error`，页面因此落 `EmptyState`；
 *   - `AdminOrdersPage.vue:33-35` 同样只 `console.error`。
 *   ⇒ 这两页的「alert 错误」可观测面 = **全局 toast**，断言里额外验证「数据没渲染」。
 * - **`/orders/:id`**：`OrderDetailPage.vue:33` `alert(err?.data?.meta?.error?.message || 'Action failed')`
 *   —— 这是**浏览器原生弹框**（`page.on('dialog')`），不是 DOM。
 * - **`/ops/orders/:id`**：`AdminOrderDetail.vue:125` `<div v-if="actionError" class="error-banner">`
 *   （样式 :301）—— **持久横幅**，只在动作（approve/ship/…）失败时出现；加载失败只有 toast（:39-40 仅 console.error）。
 *   `approveOrder(id)` 打到 `POST /api/v1/orders/<id>/approve/`（`api/adminPo.js:16-18`）。
 * - **`/po/submit`**：`PoSubmit.vue:147-159` 三条 `alert(...)` 守卫，**全部 return 在发请求之前**
 *   ⇒ 走自然路径即可，且**零写入**。
 *
 * ## 拟人化 / 零写入
 * - 全部通过真实点击推进；故障注入用 `page.route(...).fulfill(500)`，**请求不出浏览器**
 *   ⇒ 既不会产生订单，也不会推进真实订单状态机。
 * - 唯一的「读取」是 `page.request.get` 只读列表（用于在共享库里找到一条 quoted / po_received 单），
 *   token 从 localStorage 只读，不写任何状态。
 *
 * ## 登录次数（限流 5 次/分钟/IP，见 core/permissions.py 的 LoginRateThrottle）
 * 本 spec **只登录 2 次**：1 次 customer（token 注入，等价登录）+ 1 次 staff（token 注入复用）。
 * 为此整个文件用 `mode: 'serial'` + `beforeAll` 共享**同一个 page**；
 * 代价：某条用例失败会让后续用例转为 skipped（不是假绿，日志里会明确显示）。
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/order-error-paths.spec.cjs --project=chromium \
 *     --reporter=line --output=/tmp/pw-ord
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, CUST_USER, CUST_PASS, loginAsStaff } = require('./helpers/auth.cjs');
const { getSession } = require('./helpers/api.cjs');

test.describe.configure({ mode: 'serial' });

/** 故障注入的响应体：detail 会被 http.js 的 extractErrorMessage 原样透出 */
const FAIL_BODY = { detail: 'Injected failure for E2E' };
const FAIL_TEXT = 'Injected failure for E2E';

/** 与 axios 实际请求一一对应的精确正则（避免误伤同页其他请求） */
const RX = {
  myOrdersList: /\/api\/v1\/orders\/?(\?.*)?$/,              // GET /orders/
  myOrderDetail: /\/api\/v1\/orders\/\d+\/$/,                 // GET /orders/<id>/
  confirmQuote: /\/api\/v1\/orders\/\d+\/confirm-quote\/?(\?.*)?$/, // POST /orders/<id>/confirm-quote/
  adminOrdersList: /\/api\/v1\/admin\/orders\/?(\?.*)?$/,     // GET /admin/orders/
  adminOrderDetail: /\/api\/v1\/admin\/orders\/\d+\/$/,       // GET /admin/orders/<id>/
  approveOrder: /\/api\/v1\/orders\/\d+\/approve\/?(\?.*)?$/, // POST /orders/<id>/approve/
  poSubmit: /\/api\/v1\/orders\/po\/?(\?.*)?$/,               // POST /orders/po/（poPortal.js:43）
};

let sharedPage;
let context;
const activeRoutes = [];

/** 注入 500（请求不出浏览器 ⇒ 零写入） */
async function inject500(matcher) {
  const handler = (route) =>
    route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify(FAIL_BODY) });
  await sharedPage.route(matcher, handler);
  activeRoutes.push({ matcher, handler });
}

/**
 * 客户登录 —— 用 token 注入（与 `helpers/auth.cjs:73-108` 的会话复用同一套依据），
 * **不用** `loginAsCustomer` 的 UI 表单路径。
 *
 * 原因（实测，非偏好）：`auth.cjs:154` 的
 *   `page.waitForURL(url => !/\/login/.test(url), { timeout: 15000 })`
 * 在「登录成功后 SPA `router.push('/')`」这条路径上偶发 15s 超时
 * （本次首跑就卡在这里：日志出现 `navigated to /login` → `navigated to /` 但 waitForURL 仍未返回），
 * 而本文件把登录放在 `beforeAll` ⇒ 一次抖动会连坐整个文件。
 * token 注入等价于登录成功（`stores/auth.js:67-69` 落盘键 + `router/index.js:295` 守卫只读 token），
 * 且登录请求数不变（仍是 1 次）。
 */
let customerSessionDisposable = null;

async function loginAsCustomerViaSession(page) {
  const session = await getSession(page.request, CUST_USER, CUST_PASS);
  customerSessionDisposable = await page.addInitScript((s) => {
    try {
      localStorage.setItem('token', s.token);
      localStorage.setItem('is_staff', String(s.isStaff));
      localStorage.setItem('role', s.role || '');
    } catch {
      /* about:blank 等无 localStorage 的场景忽略 */
    }
  }, session);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => !!(localStorage.getItem('token') || '').trim(),
    null,
    { timeout: 30000 },
  );
}

test.beforeAll(async ({ browser }) => {
  // 共享一个 context/page：把「整轮登录次数」压到 2 次，避开 5 次/分钟限流。
  context = await browser.newContext({ baseURL: BASE_URL, viewport: { width: 1280, height: 720 } });
  sharedPage = await context.newPage();
  await loginAsCustomerViaSession(sharedPage); // 登录 #1
});

test.afterAll(async () => {
  await context?.close();
});

test.afterEach(async () => {
  for (const { matcher, handler } of activeRoutes.splice(0)) {
    await sharedPage.unroute(matcher, handler);
  }
});

/** 只读：拿当前会话的 token + 拉一次自己的订单列表，用于定位可点按钮的订单 */
async function fetchMyOrders() {
  const token = await sharedPage.evaluate(() => localStorage.getItem('token'));
  const res = await sharedPage.request.get(`${BASE_URL}/api/v1/orders/?page_size=100`, {
    headers: { 'X-Auth-Token': token },
  });
  expect(res.status(), '读取自己的订单列表失败（只读，不改状态）').toBe(200);
  const body = await res.json();
  const rows = body?.data?.results || body?.data || body?.results || [];
  return Array.isArray(rows) ? rows : [];
}

/* ══════════════════════════════════════════════════════════════════════════
 * 客户侧
 * ══════════════════════════════════════════════════════════════════════════ */
test.describe('客户侧订单错误路径', () => {
  test('/orders 列表接口 500 ⇒ 全局 toast 出现，列表不渲染（降级为空态）', async () => {
    await inject500(RX.myOrdersList);

    await sharedPage.goto(`${BASE_URL}/orders`, { waitUntil: 'domcontentloaded' });

    // ① 错误 UI 可见且文案精确匹配（toast —— 非持久横幅，约 3s 消失）
    await expect(sharedPage.locator('.el-message--error')).toContainText(FAIL_TEXT, { timeout: 10000 });

    // ② 原本该渲染的数据没了：表体不存在、没有任何订单行
    await expect(sharedPage.locator('.order-table')).toHaveCount(0);
    await expect(sharedPage.locator('.order-row')).toHaveCount(0);

    // ③ 走进了错误分支的特征：loading 结束 + 落在了空态而不是无限 spinner
    await expect(sharedPage.locator('.loading-spinner')).toHaveCount(0);
    await expect(sharedPage.locator('.empty-title')).toHaveText('No orders yet');
  });

  test('/orders/:id 详情接口 500 ⇒ 全局 toast 出现，订单详情不渲染', async () => {
    await inject500(RX.myOrderDetail);

    await sharedPage.goto(`${BASE_URL}/orders/903`, { waitUntil: 'domcontentloaded' });

    await expect(sharedPage.locator('.el-message--error')).toContainText(FAIL_TEXT, { timeout: 10000 });

    // OrderDetailPage.vue:39 `v-if="order"` ⇒ 失败时 order 为 null，整块详情不渲染
    await expect(sharedPage.locator('.order-detail-page')).toHaveCount(0);
    await expect(sharedPage.locator('.order-title')).toHaveCount(0);
    // 且不是卡在 loading（store 的 finally 会把 loading 置回 false）
    await expect(sharedPage.locator('.loading-spinner')).toHaveCount(0);
  });

  test('/po/submit 原生 alert 校验 + 提交失败 toast（全程不发真实 PO，零写入）', async () => {
    await sharedPage.goto(`${BASE_URL}/po/submit`, { waitUntil: 'domcontentloaded' });
    await expect(sharedPage.locator('h1.po-page-title')).toContainText('Submit Purchase Order');

    // 原生 alert 不是 DOM ⇒ 用 page.on('dialog') 捕获（Playwright 默认会自动 dismiss，
    // 这里显式 dismiss 并记录，避免弹框阻塞后续操作）
    // ⚠️ 用 on/off + try/finally，而不是 once：once 在「没弹框」时不会被消费，会残留到后续用例。
    async function clickAndReadAlert(clickFn) {
      let captured = null;
      const h = async (d) => {
        captured = { type: d.type(), message: d.message() };
        await d.dismiss();
      };
      sharedPage.on('dialog', h);
      try {
        await clickFn();
        await expect.poll(() => captured && captured.message, { timeout: 5000 }).toBeTruthy();
      } finally {
        sharedPage.off('dialog', h);
      }
      return captured;
    }

    // ① PoSubmit.vue:147-150 —— 一条行项目都没有
    const d1 = await clickAndReadAlert(() =>
      sharedPage.getByRole('button', { name: 'Submit PO' }).click(),
    );
    expect(d1.type).toBe('alert');
    expect(d1.message).toBe('Add at least one line item.');

    // ② PoSubmit.vue:151-155 —— 有行项目但没选 SKU
    await sharedPage.getByRole('button', { name: '+ Add Line Item' }).click();
    await expect(sharedPage.locator('.po-table')).toBeVisible();
    const d2 = await clickAndReadAlert(() =>
      sharedPage.getByRole('button', { name: 'Submit PO' }).click(),
    );
    expect(d2.message).toBe('Each line item requires a SKU, quantity and unit price.');

    // 把行项目填「完整」，否则后面会被 ② 先拦下（校验顺序见源码 :147-159）
    const row = sharedPage.locator('.po-table tbody tr').first();
    // 产品搜索是真实 UI（输入 → 结果浮层 → 点击选中），不是塞状态
    await row.locator('input.po-input').first().fill('azido');
    await expect(sharedPage.locator('.po-search-pop .po-search-item').first()).toBeVisible({ timeout: 10000 });
    await sharedPage.locator('.po-search-pop .po-search-item').first().click();
    // 选中产品后会 getProductDetail 拉 SKU，等 SKU 下拉可用
    const skuSelect = row.locator('select.po-select');
    await expect(skuSelect).toBeEnabled({ timeout: 10000 });
    await skuSelect.selectOption({ index: 1 });
    // 行内输入框顺序（PoSubmit.vue:292/319/320）：[产品搜索, Qty(number), Unit Price(placeholder 0.00)]
    await row.locator('input[type="number"]').fill('2');
    await row.locator('input[placeholder="0.00"]').fill('10');

    // ③ 交付日期在过去 —— ⚠️ 实测发现：`#po-f5` 带 `:min="minDeliveryDate"`（PoSubmit.vue:232），
    //    填过去日期后浏览器先做 **HTML5 约束校验**并直接拦住 submit，
    //    `handleSubmit` 根本不会执行 ⇒ `PoSubmit.vue:156-159` 的 alert 在 UI 路径上**不可达**（死代码）。
    //    这里把「真实行为」断言下来，而不是假装能测到第三条 alert。
    await sharedPage.locator('#po-f5').fill('2000-01-01');
    expect(
      await sharedPage.locator('#po-f5').evaluate((el) => el.validity.rangeUnderflow),
      '过去日期应被 input[type=date][min] 判为 rangeUnderflow',
    ).toBe(true);

    // 统计「真的发出 PO 提交请求」的次数（/api/v1/orders/po/，poPortal.js:43/65）
    let poSubmitRequests = 0;
    const onRequest = (req) => {
      if (/\/api\/v1\/orders\/po\/?(\?.*)?$/.test(req.url())) poSubmitRequests += 1;
    };
    sharedPage.on('request', onRequest);

    // 注意：这里必须用 on/off（不能用 once）—— 因为本用例期望**没有**弹框，
    // once 监听器会一直挂着，污染下一条用例的 dialog 处理（实测：下一条用例
    // 两个监听器同时 dismiss ⇒ "Cannot dismiss dialog which is already handled"）。
    let blockedDialog = null;
    const blockHandler = async (d) => {
      blockedDialog = d.message();
      await d.dismiss();
    };
    sharedPage.on('dialog', blockHandler);
    await sharedPage.getByRole('button', { name: 'Submit PO' }).click();
    // 有界等待：这是**否定断言**（确认「没有提交、没有弹框」）所需的观察窗口
    await sharedPage.waitForTimeout(800);
    sharedPage.off('dialog', blockHandler);
    expect(blockedDialog, '过去日期应被浏览器原生校验拦住，不应弹出 JS alert').toBeNull();
    expect(poSubmitRequests, '过去日期被拦截时不应发出 PO 提交请求').toBe(0);
    await expect(sharedPage.locator('.po-callout')).toHaveCount(0);

    // ④ 清空日期让表单合法，注入 500 ⇒ 走 PoSubmit.vue:174-176 的失败分支（拦截器 toast）
    await sharedPage.locator('#po-f5').fill('');
    await inject500(RX.poSubmit);
    await sharedPage.getByRole('button', { name: 'Submit PO' }).click();

    // 请求确实发出去了（证明走到了提交分支），但没有到达后端（被 fulfill 掉）⇒ 零写入
    await expect.poll(() => poSubmitRequests, { timeout: 10000 }).toBe(1);
    await expect(sharedPage.locator('.el-message--error')).toContainText(FAIL_TEXT, { timeout: 10000 });
    // 失败后不出现成功横幅，按钮复位（submitting=false），URL 不变
    await expect(sharedPage.locator('.po-callout')).toHaveCount(0);
    await expect(sharedPage.getByRole('button', { name: 'Submit PO' })).toBeEnabled();
    await expect(sharedPage).toHaveURL(/\/po\/submit/);

    sharedPage.off('request', onRequest);
  });

  test('/orders/:id 报价动作 500 ⇒ 原生 alert("Action failed")（quoted 单，零写入）', async () => {
    const rows = await fetchMyOrders();
    const quoted = rows.find((r) => r.status === 'quoted');
    expect(quoted, '共享库里找不到 e2e_customer 名下 status=quoted 的订单，无法触发报价动作错误分支').toBeTruthy();

    await inject500(RX.confirmQuote);

    await sharedPage.goto(`${BASE_URL}/orders/${quoted.id}`, { waitUntil: 'domcontentloaded' });
    // OrderDetailPage.vue:52 `v-if="order.status === 'quoted'"` 才渲染动作条
    await expect(sharedPage.locator('.action-bar')).toBeVisible({ timeout: 10000 });

    let captured = null;
    const dialogHandler = async (d) => {
      captured = { type: d.type(), message: d.message() };
      await d.dismiss();
    };
    sharedPage.on('dialog', dialogHandler);
    await sharedPage.getByRole('button', { name: 'Reject Quote' }).click();
    await expect.poll(() => captured && captured.message, { timeout: 5000 }).toBeTruthy();
    sharedPage.off('dialog', dialogHandler);

    expect(captured.type).toBe('alert');
    // OrderDetailPage.vue:33 —— err.data 在 5xx 时为空 ⇒ 落到兜底文案 'Action failed'
    expect(captured.message).toBe('Action failed');

    // 请求被 fulfill 掉、没到后端 ⇒ 订单仍是 quoted（零写入证据）
    await expect(sharedPage.locator('.action-bar')).toBeVisible();
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * 内部台（角色切换发生在进入本 describe 时，只多 1 次登录）
 * ══════════════════════════════════════════════════════════════════════════ */
test.describe('内部台订单错误路径', () => {
  test.beforeAll(async () => {
    // 先摘掉客户会话的 init script，否则它会随每次导航把客户 token 写回去，覆盖 staff 会话
    if (customerSessionDisposable) {
      await customerSessionDisposable.dispose();
      customerSessionDisposable = null;
    }
    // staff 登录（loginAsStaff 走 token 注入复用 ⇒ 只 1 次 /auth/login）
    await loginAsStaff(sharedPage); // 登录 #2
  });

  test('/ops/orders 列表接口 500 ⇒ 全局 toast 出现，无任何数据行（落空态）', async () => {
    await inject500(RX.adminOrdersList);

    await sharedPage.goto(`${BASE_URL}/ops/orders`, { waitUntil: 'domcontentloaded' });
    // ⚠️ 必须限定在 main 里：AdminLayout 的顶部 header 也渲染了一个 `h1.page-title`（同名标题）
    await expect(sharedPage.locator('main h1.page-title')).toHaveText('Order Management');

    await expect(sharedPage.locator('.el-message--error')).toContainText(FAIL_TEXT, { timeout: 10000 });

    // AdminOrdersPage.vue:33-35 catch 只 console.error ⇒ 表格仍在，但 rows=[] ⇒ 落 EmptyState
    await expect(sharedPage.locator('.order-row')).toHaveCount(0);
    await expect(sharedPage.locator('.empty-title')).toHaveText('No orders found');
    await expect(sharedPage.locator('.loading-spinner')).toHaveCount(0);
  });

  test('/ops/orders/:id 详情接口 500 ⇒ 全局 toast 出现，订单详情不渲染', async () => {
    await inject500(RX.adminOrderDetail);

    await sharedPage.goto(`${BASE_URL}/ops/orders/1019`, { waitUntil: 'domcontentloaded' });

    await expect(sharedPage.locator('.el-message--error')).toContainText(FAIL_TEXT, { timeout: 10000 });

    // AdminOrderDetail.vue:39-40 加载失败只 console.error ⇒ order 为 null ⇒ 整块不渲染
    await expect(sharedPage.locator('main .admin-order-detail')).toHaveCount(0);
    await expect(sharedPage.locator('main .order-title')).toHaveCount(0);
    await expect(sharedPage.locator('.error-banner')).toHaveCount(0); // 加载失败不走动作错误横幅
  });

  test('/ops/orders/:id Approve 动作 500 ⇒ 持久 .error-banner 出现（不是 toast）', async () => {
    // 只读：找一条 po_received 单（该状态才渲染 Approve 按钮，AdminOrderDetail.vue:129）
    const token = await sharedPage.evaluate(() => localStorage.getItem('token'));
    const res = await sharedPage.request.get(`${BASE_URL}/api/v1/admin/orders/?status=po_received&page_size=10`, {
      headers: { 'X-Auth-Token': token },
    });
    expect(res.status(), '读取待审订单列表失败（只读）').toBe(200);
    const body = await res.json();
    const rows = body?.data?.results || body?.data || body?.results || [];
    const pending = (Array.isArray(rows) ? rows : []).find((r) => r.status === 'po_received');
    expect(pending, '共享库里没有 status=po_received 的订单，无法渲染 Approve 按钮').toBeTruthy();

    await inject500(RX.approveOrder);

    await sharedPage.goto(`${BASE_URL}/ops/orders/${pending.id}`, { waitUntil: 'domcontentloaded' });
    await expect(sharedPage.locator('main h1.order-title')).toContainText(pending.order_no, { timeout: 10000 });

    await sharedPage.getByRole('button', { name: 'Approve' }).click();

    // 持久横幅（AdminOrderDetail.vue:125），文案来自 doAction 的 catch（:104）：
    // err.data 为空 ⇒ err.message = 'Request failed with status code 500'。
    // ⇒ 这里只断言「横幅可见」，并对「确实进了错误分支」做结构断言（横幅挂在 header 下方）。
    await expect(sharedPage.locator('.error-banner')).toBeVisible({ timeout: 10000 });
    await expect(sharedPage.locator('.error-banner')).toContainText('500');
    // 动作没成功：订单仍是 po_received（请求被拦截，零写入），按钮还在
    await expect(sharedPage.getByRole('button', { name: 'Approve' })).toBeVisible();
    await expect(sharedPage.locator('.status-badge')).toHaveText(/Po Received/i);
  });
});
