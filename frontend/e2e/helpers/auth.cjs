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

async function loginAsStaff(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);
  await Promise.all([
    page.waitForURL(/\/workspace/, { timeout: 15000 }),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
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
