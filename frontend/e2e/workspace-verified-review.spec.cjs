/**
 * E2E — C3 workspace 审核流 + Phase 4 verified 卡片有数据路径（消除覆盖缺口）
 *
 * 流程（e2e 自建合成测试数据，避免触碰真实 8 条草稿）：
 *   1. API：产品 66 + 首个可用 Method → 若无该对 verified 则 POST 建 REVIEW 草稿（合成 PMID 99999999）
 *   2. UI（staff）：/workspace/verified → Review tab → 该行可见（产品名/方法/PMID chip/Approve 按钮）
 *   3. UI：Approve（处理 confirm 弹窗）→ 行移出 Review（状态 active）
 *   4. 公开页：/products/66 → Methods tab → Verified Applicability 卡片出现该方法 + PMID chip
 *   5. 清理：reject 该 e2e 行 + 本地 DB 硬删，恢复 dev 状态
 *
 * C4 追加块（2026-09-23，与 C3 解耦；各自建自己的合成草稿，跑完清理）：
 *   C4-01 tab 切换（选中态 / 请求 status 参数 / DOM 行数与 API 现算一致）
 *   C4-02 approve 的 confirm 取消 = 零写入（负向闸门）
 *   C4-03 reject UI 路径（toast / 离开 Review / status=rejected / note 落库）
 *   C4-04 操作按钮条件渲染（仅 review 行有 Approve/Reject）
 *   C4-05 空态文案（route 拦截 /verified/ 返回空列表）
 *   C4-06 行内链接 href == 现算 /products/{id}、/methods/{id}
 *   C4-07 证据 chip（有 evidence 显示 chip，无 evidence 显示 —）
 *
 * 说明（2026-09-23 修复）：
 *   - 原文件把整个文件的 beforeAll/afterAll 放在**文件顶层**，一旦失败会**阻断文件内全部用例**。
 *     且其 API 调用传**绝对 URL**（`${API_BASE}/...`）给 `apiContext().get()`，而当前
 *     `helpers/api.cjs` 的 wrapper 会再补一次 `/api/v1` ⇒ `…/api/v1/http://…` ⇒ 404 HTML，
 *     于是 beforeAll 直接抛 SyntaxError。此处把两个钩子**下沉到 C3 describe 内**（作用域隔离），
 *     并改用**相对路径**调用；同时让夹具选择对历史遗留行健壮（空闲/review 才用）。
 *   - C3-01/02/03 三个 test 体**逐字未改**。
 *
 * 前提：后端 localhost:8000 + 前端 localhost:5173 已启动；admin/admin123 存在
 */

const { test, expect } = require('@playwright/test');
const path = require('node:path');
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs');
const { apiContext, getToken } = require('./helpers/api.cjs');
const { runSync } = require('./helpers/sync-spawn.cjs');

const PRODUCT_ID = 66;
const SYNTH_PMID = '99999999';

// ── 本地 dev DB 硬删：只用于删除本 spec 自建的合成草稿，确保跑后 /verified/ 计数恢复原状 ──
// 说明：/verified/ **没有 DELETE 端点**（只有 approve/reject/patch），而 reject 只是把行置为
// rejected（行仍在库中）⇒ 单靠 reject 无法恢复计数（现存的 id=609 就是上一轮 reject 留下的
// 孤儿行）。故清理 = API reject（按约定） + 本地 sqlite 硬删（真正恢复）。仅删本 spec 创建的 id。
const BACKEND = path.resolve(__dirname, '../../backend');
const PY = path.join(BACKEND, 'venv', 'Scripts', 'python.exe');
function hardDeleteVerified(ids) {
  const list = (ids || []).filter(Boolean);
  if (!list.length) return;
  const code = [
    'from apps.bridges.models import ProductMethodRelation as P',
    `q = P.objects.filter(id__in=${JSON.stringify(list)}, relation_type='verified_applicability')`,
    "print('__DEL__', q.count(), q.delete())",
  ].join('\n');
  runSync(PY, ['-B', 'manage.py', 'shell', '-c', code], {
    cwd: BACKEND,
    env: { ...process.env, DB_ENGINE: 'sqlite', PYTHONDONTWRITEBYTECODE: '1' },
    timeout: 60000,
    label: 'hardDeleteVerified',
  });
}

test.describe('C3 Workspace Verified Review', () => {
  let ctx, token, method, productName, pmrId = null, created = false;

  test.beforeAll(async ({ request }) => {
    token = await getToken(request, 'admin', 'admin123');
    expect(token, 'admin token').toBeTruthy();
    ctx = await apiContext(token);

    // 取产品名 + method 列表（相对路径：helpers/api.cjs 会自动补 /api/v1）
    const prodResp = await ctx.get(`/products/${PRODUCT_ID}/`);
    productName = (await prodResp.json()).data.name;
    const methodsResp = await ctx.get(`/methods/`);
    const methods = (await methodsResp.json()).data;

    // 现算已占用的 (product 66, method) 组合；只挑「空闲」或「已处于 review」的，避免撞唯一约束
    const listResp = await ctx.get(`/verified/?product_id=${PRODUCT_ID}`);
    const rows = (await listResp.json()).data || [];
    const byMethod = new Map(rows.map((r) => [r.method_id, r]));
    method = methods.find((m) => {
      const r = byMethod.get(m.id);
      return !r || r.status === 'review';
    });
    expect(method, 'product 66 存在空闲或 review 状态的 method').toBeTruthy();

    const existing = byMethod.get(method.id);
    if (existing && existing.status === 'review') {
      pmrId = existing.id; // 复用既有 review 草稿
      created = false;
    } else {
      const createResp = await ctx.post(`/verified/`, {
        data: {
          product_id: PRODUCT_ID,
          method_id: method.id,
          evidence_type: 'pubmed',
          evidence_reference: [{ type: 'PMID', value: SYNTH_PMID }],
          evidence_strength: 'high',
          evidence_note: 'e2e synthetic draft for C3 review flow',
        },
      });
      expect(createResp.status()).toBe(201);
      pmrId = (await createResp.json()).data.id;
      created = true;
    }
  });

  test.afterAll(async () => {
    // 清理：reject e2e 行 + 本地硬删（若为本轮新建），恢复 dev 状态
    if (ctx && pmrId) {
      await ctx.post(`/verified/${pmrId}/reject/`, { data: { note: 'e2e cleanup' } });
      if (created) hardDeleteVerified([pmrId]);
    }
  });

  test('C3-01: review queue lists the draft with evidence', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.locator('.wv-table').waitFor({ timeout: 15000 });
    // 找到 e2e 行（按方法名或 PMID chip）
    const row = page.locator('.wv-table tbody tr', {
      hasText: method.name,
    }).first();
    await expect(row).toBeVisible();
    await expect(row.locator('.wv-chip', { hasText: `PMID: ${SYNTH_PMID}` })).toBeVisible();
    await expect(row.locator('.wv-btn-approve')).toBeVisible();
    await expect(row.locator('.wv-badge-review')).toBeVisible();
  });

  test('C3-02: approve moves draft out of review queue', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.locator('.wv-table').waitFor({ timeout: 15000 });
    const row = page.locator('.wv-table tbody tr', { hasText: method.name }).first();
    page.on('dialog', (d) => d.accept());
    await row.locator('.wv-btn-approve').click();
    // 行不再处于 review（切到 Review tab 后该行消失 / 或状态徽标变化）
    await expect(page.locator('.wv-badge-review', { hasText: method.name }))
      .toHaveCount(0, { timeout: 15000 });
  });

  test('C3-03: public product page shows verified card (Phase 4 data path)', async ({ page }) => {
    // 公开读：无需登录
    await page.goto(`${BASE_URL}/products/${PRODUCT_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.pd-name', { timeout: 15000 });
    await page.click('.pd-tab-btn:has-text("Methods")');
    const block = page.locator('[data-testid="verified-applicability"]');
    await expect(block).toBeVisible();
    const card = block.locator('.pd-verified-card', { hasText: method.name });
    await expect(card).toBeVisible();
    await expect(card.locator('.pd-evidence-chip', { hasText: SYNTH_PMID })).toBeVisible();
  });
});

// ───────────────────────────────────────────────────────────────────────────
// C4 — Verified Applicability 覆盖缺口（与 C3 解耦：独立夹具 / 独立清理）
// ───────────────────────────────────────────────────────────────────────────
test.describe('C4 Verified Applicability — coverage gaps (decoupled)', () => {
  const createdIds = [];
  let ctx, token;
  let draftEv;   // 有证据的 review 草稿
  let draftNoEv; // 无证据的 review 草稿
  let draftRej;  // 用于 reject UI 路径的 review 草稿

  // 宽松的列表请求判定：GET /api/v1/verified/（approve/reject 均为 POST，天然排除）
  const isListGet = (resp) =>
    resp.request().method() === 'GET' && resp.url().includes('/api/v1/verified/');

  test.beforeAll(async ({ request }) => {
    token = await getToken(request, 'admin', 'admin123');
    expect(token, 'admin token').toBeTruthy();
    ctx = await apiContext(token);

    const all = (await (await ctx.get('/verified/')).json()).data || [];
    const used = new Set(all.map((r) => `${r.product_id}:${r.method_id}`));
    const products = (await (await ctx.get('/products/?page_size=200')).json()).data;
    const prodList = Array.isArray(products) ? products : (products.results || []);
    const methods = (await (await ctx.get('/methods/')).json()).data;

    // 取下一个空闲 (product, method) 组合（避开 C3 使用的 66+method[0]，且不与现有行冲突）
    const nextPair = () => {
      for (const p of prodList) {
        for (const m of methods) {
          if (p.id === PRODUCT_ID && m.id === 54) continue;
          const key = `${p.id}:${m.id}`;
          if (used.has(key)) continue;
          used.add(key);
          return { product_id: p.id, method_id: m.id };
        }
      }
      throw new Error('找不到空闲的 (product, method) 组合');
    };

    const makeDraft = async ({ ref, note }) => {
      const pair = nextPair();
      const payload = {
        product_id: pair.product_id,
        method_id: pair.method_id,
        evidence_type: ref ? 'pubmed' : '',
        evidence_strength: ref ? 'high' : '',
        evidence_note: note,
      };
      if (ref) payload.evidence_reference = ref; // 无证据时不传该字段（后端默认 None）
      const resp = await ctx.post('/verified/', { data: payload });
      expect(resp.status(), `创建合成草稿 ${JSON.stringify(pair)}`).toBe(201);
      const row = (await resp.json()).data;
      createdIds.push(row.id);
      return row;
    };

    draftEv = await makeDraft({ ref: [{ type: 'PMID', value: '77770001' }], note: 'e2e-gap evidence draft' });
    draftNoEv = await makeDraft({ ref: null, note: 'e2e-gap noevidence draft' });
    draftRej = await makeDraft({ ref: [{ type: 'PMID', value: '77770003' }], note: 'e2e-gap reject draft' });
  });

  test.afterAll(async () => {
    if (!ctx) return;
    // 按约定先走 API reject 清理，再本地硬删，确保 /verified/ 各状态计数恢复跑前
    for (const id of createdIds) {
      try {
        await ctx.post(`/verified/${id}/reject/`, { data: { note: 'e2e cleanup' } });
      } catch (e) {
        // 已被用例 reject 或已删除：忽略
      }
    }
    hardDeleteVerified(createdIds);
  });

  test('C4-01: tab 切换——选中态 / 请求 status 参数 / 行数与 API 现算一致', async ({ page }) => {
    await loginAsStaff(page);
    await Promise.all([
      page.waitForResponse(isListGet),
      page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' }),
    ]);

    const seq = [
      { label: 'Active', status: 'active' },
      { label: 'Rejected', status: 'rejected' },
      { label: 'All', status: '' },
      { label: 'Review', status: 'review' },
    ];

    for (const { label, status } of seq) {
      const tab = page.locator('.wv-tab', { hasText: label });
      const [resp] = await Promise.all([
        page.waitForResponse(isListGet),
        tab.click(),
      ]);

      // 1) 请求的 status 查询参数与 tab 一致（All ⇒ 不带 status）
      const url = new URL(resp.url());
      if (status) {
        expect(url.searchParams.get('status'), `${label} tab 的 status 参数`).toBe(status);
      } else {
        expect(url.searchParams.has('status'), 'All tab 不应带 status 参数').toBe(false);
      }

      // 2) 选中态类跟随
      await expect(tab).toHaveClass(/wv-tab-active/);

      // 3) DOM 行数 == API 按该 status 现算的行数
      const apiRows = (await (await ctx.get(status ? `/verified/?status=${status}` : '/verified/')).json()).data;
      const expected = apiRows.length;
      await expect(page.locator('.wv-table tbody tr')).toHaveCount(expected);
      if (expected === 0) {
        await expect(page.locator('.wv-empty')).toHaveText('No verified relations in this state.');
      }
    }
  });

  test('C4-02: Approve 的 confirm 取消 = 零写入', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.locator('.wv-table').waitFor({ timeout: 15000 });

    const approveCalls = [];
    page.on('request', (r) => {
      if (r.method() === 'POST' && r.url().includes(`/verified/${draftEv.id}/approve/`)) {
        approveCalls.push(r.url());
      }
    });
    page.on('dialog', (d) => d.dismiss()); // 取消 confirm

    const row = page.locator('.wv-table tbody tr').filter({
      has: page.locator('.wv-chip', { hasText: 'PMID: 77770001' }),
    });
    await expect(row).toBeVisible();
    await row.locator('.wv-btn-approve').click();

    await page.waitForTimeout(1500); // 给潜在写请求一个暴露窗口

    expect(approveCalls, 'confirm 取消 ⇒ 不得发出 approve 请求').toEqual([]);
    await expect(row, '该行仍留在 Review 列表').toBeVisible();
    await expect(page.locator('.el-message--success'), '不应出现成功 toast').toHaveCount(0);

    const rows = (await (await ctx.get(`/verified/?product_id=${draftEv.product_id}`)).json()).data;
    const cur = rows.find((r) => r.id === draftEv.id);
    expect(cur, 'API 现算存在该行').toBeTruthy();
    expect(cur.status, 'API 现算 status 未变').toBe('review');
  });

  test('C4-03: Reject UI 路径——toast / 离开 Review / status=rejected / note 落库', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.locator('.wv-table').waitFor({ timeout: 15000 });

    const NOTE = `e2e-gap-reject-note-${Date.now()}`;
    page.on('dialog', (d) => {
      if (d.type() === 'prompt') d.accept(NOTE);
      else d.accept();
    });

    const row = page.locator('.wv-table tbody tr').filter({
      has: page.locator('.wv-chip', { hasText: 'PMID: 77770003' }),
    });
    await expect(row).toBeVisible();

    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().includes(`/verified/${draftRej.id}/reject/`),
      ),
      row.locator('.wv-btn-reject').click(),
    ]);
    expect(resp.status()).toBe(200);

    // toast.success('Rejected')（element-plus：.el-message--success / .el-message__content）
    await expect(page.locator('.el-message--success').first()).toContainText('Rejected');
    // 该行离开 Review 列表
    await expect(row, '该行离开 Review 列表').toHaveCount(0, { timeout: 15000 });

    const rows = (await (await ctx.get(`/verified/?product_id=${draftRej.product_id}`)).json()).data;
    const cur = rows.find((r) => r.id === draftRej.id);
    expect(cur, 'API 现算存在该行').toBeTruthy();
    expect(cur.status, 'API 现算 status === rejected').toBe('rejected');
    // note 落库：实测后端 reject_verified 在 note 非空时写成 "[reject] <note>" 前缀
    expect(cur.evidence_note, 'evidence_note 应包含唯一备注').toContain(NOTE);
  });

  test('C4-04: 操作按钮条件渲染——仅 review 行有 Approve/Reject', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.locator('.wv-table').waitFor({ timeout: 15000 });

    // 正例：Review tab 必须同时出现 Approve 与 Reject
    await expect(page.locator('.wv-btn-approve').first()).toBeVisible();
    expect(await page.locator('.wv-btn-approve').count(), 'Review tab 应有 Approve').toBeGreaterThan(0);
    expect(await page.locator('.wv-btn-reject').count(), 'Review tab 应有 Reject').toBeGreaterThan(0);

    // 反例：Rejected tab 不得出现
    await Promise.all([
      page.waitForResponse(isListGet),
      page.locator('.wv-tab', { hasText: 'Rejected' }).click(),
    ]);
    await expect(page.locator('.wv-table')).toBeVisible();
    expect(await page.locator('.wv-btn-approve').count(), 'Rejected tab 不应有 Approve').toBe(0);
    expect(await page.locator('.wv-btn-reject').count(), 'Rejected tab 不应有 Reject').toBe(0);

    // 反例：Active tab 不得出现
    await Promise.all([
      page.waitForResponse(isListGet),
      page.locator('.wv-tab', { hasText: 'Active' }).click(),
    ]);
    await expect(page.locator('.wv-table')).toBeVisible();
    expect(await page.locator('.wv-btn-approve').count(), 'Active tab 不应有 Approve').toBe(0);
    expect(await page.locator('.wv-btn-reject').count(), 'Active tab 不应有 Reject').toBe(0);
  });

  test('C4-05: 空态——/verified/ 返回空列表时显示空态文案', async ({ page }) => {
    await loginAsStaff(page);
    await page.route('**/api/v1/verified/**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: [], meta: {} }),
      }),
    );
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.wv-empty')).toHaveText('No verified relations in this state.');
    await page.unroute('**/api/v1/verified/**');
  });

  test('C4-06: 行内链接 href == 现算 /products/{id} 与 /methods/{id}', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.locator('.wv-table').waitFor({ timeout: 15000 });

    const row = page.locator('.wv-table tbody tr').filter({
      has: page.locator('.wv-chip', { hasText: 'PMID: 77770001' }),
    });
    await expect(row).toBeVisible();
    const links = row.locator('a.wv-link');
    await expect(links).toHaveCount(2);
    await expect(links.nth(0)).toHaveAttribute('href', `/products/${draftEv.product_id}`);
    await expect(links.nth(1)).toHaveAttribute('href', `/methods/${draftEv.method_id}`);
  });

  test('C4-07: 证据 chip——有 evidence 显示 chip，无 evidence 显示 —', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/verified`, { waitUntil: 'domcontentloaded' });
    await page.locator('.wv-table').waitFor({ timeout: 15000 });

    // 正例：有 evidence_reference 的行显示 .wv-chip
    const rowEv = page.locator('.wv-table tbody tr').filter({
      has: page.locator('.wv-chip', { hasText: 'PMID: 77770001' }),
    });
    await expect(rowEv).toBeVisible();
    expect(await rowEv.locator('.wv-chip').count(), '有证据行应有 chip').toBeGreaterThan(0);

    // 反例：无 evidence_reference 的草稿（靠唯一 evidence_note 定位），Evidence 格显示 —
    const rowNo = page.locator('.wv-table tbody tr', { hasText: 'e2e-gap noevidence draft' });
    await expect(rowNo).toBeVisible();
    expect(await rowNo.locator('.wv-chip').count(), '无证据行不应有 chip').toBe(0);
    await expect(rowNo.locator('.wv-meta', { hasText: /^—$/ }), '无证据格应显示 —').toBeVisible();
  });
});
