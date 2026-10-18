/**
 * 认证 helper —— 基于真实登录页 DOM（已核对 cascader-workflow / verify-dialog-style spec）。
 *
 * 登录页选择器（确认存在）：
 *   input[placeholder="Enter your username"]
 *   input[placeholder="Enter your password"]
 *   getByRole('button', { name: 'Sign In' })
 * staff 登录后由 router 重定向到 /workspace；customer 登录后落到非 /login 页。
 */
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

const ADMIN_USER = process.env.E2E_USER || 'admin';
const ADMIN_PASS = process.env.E2E_PASS || 'admin123';
const CUST_USER = process.env.E2E_CUSTOMER_USER || 'e2e_customer';
const CUST_PASS = process.env.E2E_CUSTOMER_PASS || 'E2ePass123!';
// ★ 内部采购/销售（procurement，**非 staff**）—— 用于验证跨机构可见 + 内部操作权限
const PROC_USER = process.env.E2E_PROC_USER || 'e2e_proc';
const PROC_PASS = process.env.E2E_PROC_PASS || 'E2ePass123!';

// ★ 2026-10-18 生产实测：**会话复用**开关（默认开）。
//
// 为什么需要：后端 `core/permissions.py` 的 `LoginRateThrottle` = **5 次/分钟/IP**。
//   生产 E2E 的全部流量来自**同一台机器的同一个出口 IP**，而每个用例要登录**2 次**
//   （UI 表单登录 1 次 + API 取 token 1 次）⇒ 连跑几个用例就必然 429 ⇒ 用例随机失败
//   （实测：3 连跑得到 2 passed / 1 failed，两种失败形态分别是
//     ① `loginAsStaff 未确认登录成功`（表单提交被 429 打断）
//     ② 断言成 "0 products"（API 侧登录静默失败 ⇒ 静默降级成空列表））。
//
// 做法：整轮**只登录 1 次**，把 DRF Token（**不过期**，生产实测 40 位 hex 长期有效）
//   直接写进 localStorage，跳过 UI 登录 ⇒ 登录请求数从 2N 降到 1，限流不再触发。
//   落盘键与前端 `src/stores/auth.js:67-69` 完全一致（token / is_staff / role），
//   前端判定登录态也只读这三个键（`router/index.js:295`）⇒ 语义等价。
//
// ⚠️ 不适用于**要验证登录页本身**的用例（那种用例请自己填表单，见 cascader-workflow /
//   verify-dialog-* 等，它们各自定义了本地 loginAsStaff，未走本 helper）。
// ⚠️ 本地 dev 无此需求，但复用同样成立（DRF token 同样不过期）⇒ 默认开启，行为一致。
const REUSE_SESSION = process.env.E2E_REUSE_SESSION !== '0';

/**
 * 每个 page 上"会话注入"的 init script（Playwright 1.60 的 `Disposable`，可 `dispose()` 摘除）。
 * ⚠️ 必须摘：否则 `addInitScript` 会在后续每次导航把 token 写回去，
 *   破坏"登出后换角色"的用例（`po-lifecycle.fullflow` 靠 `logout()` 切客户/staff）。
 */
const _sessionInitScriptDisposables = new Map();

// 登录等待超时。原为 15s，对"登录接口慢 / 跳转慢"偶发超时（重跑即过），放宽到 30s。
const LOGIN_TIMEOUT_MS = 30000;

// 登录成功信号（首次提交后）：token 已写入，或 URL 已落到 /workspace。
// 权威信号是 localStorage.token —— auth store 在登录接口成功后写入（见 frontend/src/stores/auth.js:45），
// 登录失败绝不写 token。取"或"以吸收"接口已成功但跳转慢"的抖动；首次从 /login 出发，
// URL 分支只会在真正跳转后为真 ⇒ 不会把失败误判为已登录。
function _loggedIn() {
  return !!(localStorage.getItem('token') || '').trim() ||
         /\/workspace/.test(window.location.pathname);
}

// 兜底判据：只认 token（权威信号）。直连 /workspace 时 URL 可能瞬时为 /workspace 而尚未被守卫
// 重定向回 /login，若此处也用 URL 判定会有"假通过"风险 ⇒ 兜底严格只认 token。
function _hasToken() {
  return !!(localStorage.getItem('token') || '').trim();
}

/**
 * 会话复用登录：**不发起 UI 登录**，直接注入 localStorage。
 *
 * 依据（生产实测）：
 *   - 前端 `src/stores/auth.js:8,12,15,67-69` 登录态只落在 localStorage 的
 *     `token` / `is_staff` / `role` 三个键；`router/index.js:295` 守卫也只读 `token`。
 *   - DRF `Token` 恒定不过期（`apps/accounts/api/v1/views.py:94` get_or_create）⇒ 可整轮复用。
 *   ⇒ 注入这三个键 ≡ 登录成功，且**零登录请求** ⇒ 绕开 5 次/分钟的 LoginRateThrottle。
 */
async function loginViaSession(page) {
  const { getSession } = require('./api.cjs');
  // 用 `page.request`（与该页面同一 browser context 共享 cookie 与 httpCredentials）
  // ⇒ 生产 nginx Basic 层自动带上。
  const request = page.request || (await require('@playwright/test').request.newContext());
  const session = await getSession(request, ADMIN_USER, ADMIN_PASS);

  // ★ 用 `addInitScript` 而非"先 goto('/') 写 localStorage 再 goto('/workspace')"：
  //   后者两次导航**存在竞态** —— 第二次 goto 会**中断**第一次尚未完成的导航
  //   ⇒ 报 `net::ERR_ABORTED; maybe frame was detached`（2026-10-18 生产实测，
  //     表现为「会话复用登录未成功，回落到 UI 表单登录」+ 随后 90s networkidle 超时）。
  //   `addInitScript` 在**每次导航的页面脚本之前**执行 ⇒ 只需**一次**导航即可，
  //   天然没有竞态；且 localStorage 按 origin 隔离，注入目标就是 BASE_URL 同源。
  //
  // ⚠️ 但 `addInitScript` 会**对该 page 的后续每次导航**都重新注入 ⇒ 会破坏
  //   "登出后换角色"的用例（`po-lifecycle.fullflow` 用 `logout()` 切客户/staff）。
  //   ⇒ Playwright 1.60 的 `addInitScript` 返回 **`Disposable`**（`dispose()` 可摘除），
  //   把它记下来，`logout()` 里 `dispose()` 掉 ⇒ 登出后不再被自动写回。
  const disposable = await page.addInitScript((s) => {
    try {
      localStorage.setItem('token', s.token);
      localStorage.setItem('is_staff', String(s.isStaff));
      localStorage.setItem('role', s.role || '');
    } catch {
      /* 某些页面（如 about:blank）无 localStorage ⇒ 忽略，交给后续严格校验 */
    }
  }, session);
  _sessionInitScriptDisposables.set(page, disposable);

  // 落到目标页并确认前端确实认了登录态（token 在 + 路由守卫放行到 /workspace）。
  // ⚠️ `waitUntil: 'domcontentloaded'`：默认的 'networkidle' 在生产 SPA 上
  //   会被长连接/轮询拖到 90s 超时（实测）⇒ 显式改掉。
  await page.goto(`${BASE_URL}/workspace`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(_hasToken, null, { timeout: LOGIN_TIMEOUT_MS });
  return session;
}

async function loginAsStaff(page) {
  // 优先走会话复用（少一次登录请求 ⇒ 不撞限流）；失败则回落到 UI 表单登录。
  if (REUSE_SESSION) {
    try {
      return await loginViaSession(page);
    } catch (err) {
      // 回落前先给一次清晰提示：为何没用复用路径。
      console.warn(
        `[auth] 会话复用登录未成功，回落到 UI 表单登录：${String(err.message).split('\n')[0]}`,
      );
    }
  }
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);

  const submit = page.getByRole('button', { name: 'Sign In' }).click();
  try {
    await Promise.all([
      page.waitForFunction(_loggedIn, null, { timeout: LOGIN_TIMEOUT_MS }),
      submit,
    ]);
    return;
  } catch (firstErr) {
    // 一次有界兜底：直接进 /workspace，再等"严格"条件（token 已写入）。
    // ⚠ 这不是"忽略失败/继续"：兜底仍严格判定登录是否成功，两次都失败即显式抛错（绝不静默放行）。
    try {
      await page.goto(`${BASE_URL}/workspace`, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(_hasToken, null, { timeout: LOGIN_TIMEOUT_MS });
      return;
    } catch (secondErr) {
      throw new Error(
        'loginAsStaff 未确认登录成功：提交后既未跳转 /workspace，localStorage.token 也未写入。' +
        `首次错误：${firstErr.message}；兜底错误：${secondErr.message}`,
      );
    }
  }
}

async function loginAsCustomer(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(CUST_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(CUST_PASS);
  await Promise.all([
    page.waitForURL((url) => !/\/login/.test(url.toString()), { timeout: 15000 }),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
}

async function loginAsProcurement(page) {
  // procurement 是**非 staff** ⇒ 登录后落到 /（非 /workspace），等待方式同 customer。
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(PROC_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(PROC_PASS);
  await Promise.all([
    page.waitForURL((url) => !/\/login/.test(url.toString()), { timeout: 15000 }),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
}

async function getToken(page) {  return page.evaluate(() => localStorage.getItem('token'));
}

async function logout(page) {
  // ★ 先摘掉会话注入的 init script（若本 page 用过 `loginAsStaff` 的会话复用路径）：
  //   否则它会在**下一次导航**又把 token 写回 localStorage ⇒ 登出失效、换角色失败。
  const disposable = _sessionInitScriptDisposables.get(page);
  if (disposable) {
    try {
      await disposable.dispose();
    } catch {
      /* page 已关闭等情况 ⇒ 忽略 */
    }
    _sessionInitScriptDisposables.delete(page);
  }
  // 清空 token + 跳首页，确保下个用例从匿名态开始
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
}

module.exports = {
  BASE_URL,
  ADMIN_USER,
  ADMIN_PASS,
  CUST_USER,
  CUST_PASS,
  PROC_USER,
  PROC_PASS,
  loginAsStaff,
  loginAsCustomer,
  loginAsProcurement,
  getToken,
  logout,
};
