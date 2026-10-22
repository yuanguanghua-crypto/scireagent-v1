/**
 * 探测栈专用 helper —— Batch 1~3 的 P0/P1/P2 用例共用。
 *
 * 与 `helpers/auth.cjs` 的区别：
 *   auth.cjs   用开发库默认账号（admin / e2e_customer / e2e_proc），给老 spec 用
 *   本文件     用**独立探测栈**的 probe_* 账号（配额 7 个身份，见 scripts/probe_seed_accounts.py）
 *
 * 账号 id 从 `backend/_probe_ids.json` 读（种子脚本生成），**不硬编码**——副本重建后 id 会变。
 */
const fs = require('fs');
const path = require('path');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5174';
const PW = process.env.PROBE_PASS || 'Probe#2026!';

const IDS_FILE = path.resolve(__dirname, '..', '..', '..', 'backend', '_probe_ids.json');

function ids() {
  try {
    return JSON.parse(fs.readFileSync(IDS_FILE, 'utf8'));
  } catch (e) {
    throw new Error(
      `读不到 ${IDS_FILE}：先跑 seed（见 MANUAL_FACTS_MEASURED §0）。原始错误：${e.message}`,
    );
  }
}

async function login(page, username, password = PW) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(username);
  await page.locator('input[placeholder="Enter your password"]').fill(password);
  await page.getByRole('button', { name: /Sign In/i }).click();
  await page.waitForTimeout(2500);
}

/** 用页面里已登录的 token 调一次 API（X-Auth-Token，与前端一致） */
async function api(page, method, apiPath, body) {
  return page.evaluate(
    async ({ method, apiPath, body }) => {
      const tok = localStorage.getItem('token');
      const opt = { method, headers: { 'X-Auth-Token': tok || '' } };
      if (body !== undefined) {
        opt.headers['Content-Type'] = 'application/json';
        opt.body = JSON.stringify(body);
      }
      const r = await fetch(apiPath, opt);
      let data = null;
      try { data = await r.json(); } catch (_) { data = null; }
      return { status: r.status, data };
    },
    { method, apiPath, body },
  );
}

/** 未登录状态的 API 调用（匿名探测用） */
async function anonApi(page, method, apiPath) {
  return page.evaluate(
    async ({ method, apiPath }) => {
      const r = await fetch(apiPath, { method });
      let data = null;
      try { data = await r.json(); } catch (_) { data = null; }
      return { status: r.status, data };
    },
    { method, apiPath },
  );
}

async function bodyText(page) {
  return page.evaluate(() => (document.getElementById('app')?.innerText || '').replace(/\s+/g, ' '));
}

module.exports = { BASE, PW, ids, login, api, anonApi, bodyText };
