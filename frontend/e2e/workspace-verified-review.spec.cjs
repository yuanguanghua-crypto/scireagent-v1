/**
 * E2E — C3 workspace 审核流 + Phase 4 verified 卡片有数据路径（消除覆盖缺口）
 *
 * 流程（e2e 自建合成测试数据，避免触碰真实 8 条草稿）：
 *   1. API：产品 66 + 首个 Method → 若无该对 verified 则 POST 建 REVIEW 草稿（合成 PMID 99999999）
 *   2. UI（staff）：/workspace/verified → Review tab → 该行可见（产品名/方法/PMID chip/Approve 按钮）
 *   3. UI：Approve（处理 confirm 弹窗）→ 行移出 Review（状态 active）
 *   4. 公开页：/products/66 → Methods tab → Verified Applicability 卡片出现该方法 + PMID chip
 *   5. 清理：reject 该 e2e 行，恢复 dev 状态
 *
 * 前提：后端 localhost:8000 + 前端 localhost:5173 已启动；admin/admin123 存在
 */

const { test, expect } = require('@playwright/test');
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs');
const { API_BASE, apiContext, getToken } = require('./helpers/api.cjs');

const PRODUCT_ID = 66;
const SYNTH_PMID = '99999999';

let ctx, token, method, productName, pmrId = null;

test.beforeAll(async ({ request }) => {
  token = await getToken(request, 'admin', 'admin123');
  expect(token, 'admin token').toBeTruthy();
  ctx = await apiContext(token);

  // 取产品名 + 首个方法
  const prodResp = await ctx.get(`${API_BASE}/products/${PRODUCT_ID}/`);
  productName = (await prodResp.json()).data.name;
  const methodsResp = await ctx.get(`${API_BASE}/methods/`);
  const methods = (await methodsResp.json()).data;
  method = methods[0];

  // 幂等：该对已有 verified 则复用，否则建草稿（full evidence 才能 approve）
  const listResp = await ctx.get(`${API_BASE}/verified/?product_id=${PRODUCT_ID}`);
  const rows = (await listResp.json()).data || [];
  const existing = rows.find((r) => r.method_id === method.id);
  if (existing) {
    pmrId = existing.id;
  } else {
    const createResp = await ctx.post(`${API_BASE}/verified/`, {
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
  }
});

test.afterAll(async () => {
  // 清理：reject e2e 行，恢复 dev 状态（已 ACTIVE 亦可 reject 下架）
  if (ctx && pmrId) {
    await ctx.post(`${API_BASE}/verified/${pmrId}/reject/`, { data: { note: 'e2e cleanup' } });
  }
});

test.describe('C3 Workspace Verified Review', () => {

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
