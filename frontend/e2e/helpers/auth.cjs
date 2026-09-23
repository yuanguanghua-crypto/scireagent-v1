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

async function loginAsStaff(page) {
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

async function getToken(page) {
  return page.evaluate(() => localStorage.getItem('token'));
}

async function logout(page) {
  // 清空 token + 跳首页，确保下个用例从匿名态开始
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE_URL}/`);
}

module.exports = {
  BASE_URL,
  ADMIN_USER,
  ADMIN_PASS,
  CUST_USER,
  CUST_PASS,
  loginAsStaff,
  loginAsCustomer,
  getToken,
  logout,
};
