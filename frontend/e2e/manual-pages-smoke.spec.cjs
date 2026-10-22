/**
 * 补齐「未在浏览器里跑过」的页面 —— 加载级验证（第 2 版，修正两处自测缺陷）
 *
 * V1 的两个缺陷（已修）：
 *   ① 收敛类 id 取成 null：`/convergence-classes` 返回的是 `data.items[]` 而不是数组，
 *      导致 `/applications/classes/null` 也被算"渲染成功" —— 假通过
 *   ② 漏了 `/po/orders/:id`，且客户页（/orders/:id）用 staff 身份测，
 *      staff 的默认回复。② 起按"客户看自己订单"用客户上下文
 */
const { test, expect } = require('@playwright/test');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5174';
const PW = 'Probe#2026!';

function fact(name, payload) {
  console.log('[PAGE] ' + JSON.stringify({ name, ...payload }));
}

async function login(page, username, password = PW) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(username);
  await page.locator('input[placeholder="Enter your password"]').fill(password);
  await page.getByRole('button', { name: /Sign In/i }).click();
  await page.waitForTimeout(2500);
}

async function apiIds(page) {
  return page.evaluate(async () => {
    const tok = localStorage.getItem('token');
    const get = async (p) => {
      const r = await fetch(p, { headers: { 'X-Auth-Token': tok } });
      if (!r.ok) return null;
      return r.json();
    };
    const first = async (p, key) => {
      const d = await get(p);
      if (!d) return null;
      const data = d.data;
      const arr = Array.isArray(data) ? data : (data?.items || data?.results || []);
      return arr[0] ? arr[0][key] : null;
    };
    return {
      app: await first('/api/v1/applications/?page_size=1', 'id'),
      method: await first('/api/v1/methods/?page_size=1', 'id'),
      protocol: await first('/api/v1/protocols/?page_size=1', 'id'),
      goal: await first('/api/v1/research-goals/?page_size=1', 'id'),
      product: await first('/api/v1/products/?page_size=1', 'id'),
      cls_ap: await first('/api/v1/convergence-classes/?group=ap', 'class_id'),
      cls_rg: await first('/api/v1/convergence-classes/?group=rg', 'class_id'),
      order: await first('/api/v1/orders/?page_size=1', 'id'),
    };
  });
}

async function visit(page, path) {
  const errors = [];
  const onErr = (e) => errors.push(String(e.message || e).slice(0, 100));
  page.on('pageerror', onErr);
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2200);
  const txt = await page.evaluate(() =>
    (document.getElementById('app')?.innerText || '').replace(/\s+/g, ' '));
  page.off('pageerror', onErr);
  // 判据：渲染出正文 + URL 未被踢走 + 没有把 "null"/"undefined" 当 id
  const kicked = !page.url().includes(path.split('?')[0].split('/').slice(0, 2).join('/'));
  return {
    path, len: txt.length, url: page.url(), kicked,
    ok: txt.length > 200 && !kicked,
    errors: errors.slice(0, 3), excerpt: txt.slice(0, 100),
  };
}

test.describe.configure({ mode: 'serial' });

test('补测：staff 上下文的 12 页', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await login(page, 'probe_staff');
  const ids = await apiIds(page);
  fact('ids_staff', ids);
  expect(ids.cls_ap, '收敛类 id 必须拿到（V1 这里是 null）').toBeTruthy();

  const cases = [
    '/about', '/privacy', '/terms', '/verify-email', '/wishlist',
    `/applications/${ids.app}`,
    `/applications/classes/${ids.cls_ap}`,
    `/methods/${ids.method}`,
    `/protocols/${ids.protocol}`,
    `/research-goals/${ids.goal}`,
    `/research-goals/classes/${ids.cls_rg}`,
    '/ops/inventory',
    '/ops/rfq',
    `/workspace/products/${ids.product}/edit`,
  ];
  const results = [];
  for (const p of cases) {
    const r = await visit(page, p);
    results.push(r);
    fact('page', { path: r.path, len: r.len, ok: r.ok, url: r.url, errors: r.errors });
  }
  console.log('[PAGE-SUMMARY-STAFF] ' + JSON.stringify({
    total: results.length, ok: results.filter((r) => r.ok).length,
    failed: results.filter((r) => !r.ok).map((r) => r.path),
  }));
  expect(results.filter((r) => !r.ok).map((r) => r.path)).toEqual([]);
  await ctx.close();
});

test('补测：客户上下文的 3 页（自己的订单与 PO 单）', async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await login(page, 'probe_ouser_a', PW);
  const ids = await apiIds(page);
  fact('ids_customer', ids);
  expect(ids.order, '客户必须有一条自己的订单').toBeTruthy();

  const results = [];
  for (const p of [`/orders/${ids.order}`, `/po/orders/${ids.order}`, '/wishlist']) {
    const r = await visit(page, p);
    results.push(r);
    fact('page', { path: r.path, len: r.len, ok: r.ok, url: r.url, errors: r.errors });
  }
  console.log('[PAGE-SUMMARY-CUST] ' + JSON.stringify({
    total: results.length, ok: results.filter((r) => r.ok).length,
    failed: results.filter((r) => !r.ok).map((r) => r.path),
  }));
  expect(results.filter((r) => !r.ok).map((r) => r.path)).toEqual([]);
  await ctx.close();
});
