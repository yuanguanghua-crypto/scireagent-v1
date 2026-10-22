/**
 * Batch 1 / P0-4 —— F6-1 指派销售（admin(role) 的唯一独有能力）
 *
 * 背景（实测已确认）：
 *   · `POST /orders/{id}/assign-rep/` 的权限是 `IsAdmin`（`is_staff` **或** `role=='admin'`）
 *   · 前端输入框 placeholder 只写 `Rep ID`，**没说要填数字用户 ID**
 *   · 后端 `po_views.py:130` 只 catch `User.DoesNotExist`，
 *     传非数字 → `ValueError` → **500 + HTML 错误页**（应为 400）
 *
 * 本用例同时做两件事：
 *   1. 正例：填**数字** id ⇒ 200，且 `assigned_rep` 真的落库（侧证）
 *   2. 缺陷锁定：填**用户名** ⇒ 断言 500。一旦后端改成 400，这里会红，提醒更新
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p0 @local-only F6-1 指派销售', () => {
  test('填数字 Rep ID ⇒ 成功且落库', async ({ page }) => {
    const IDS = H.ids();
    const repId = IDS.probe_procure;
    expect(repId, '_probe_ids.json 缺 probe_procure，先跑 seed').toBeTruthy();

    const calls = [];
    page.on('response', (r) => {
      if (/assign-rep/.test(r.url())) calls.push({ status: r.status(), url: r.url() });
    });

    await H.login(page, 'probe_adminrole');
    await page.goto(`${H.BASE}/ops/po/review`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const repInput = page.locator('input[placeholder="Rep ID"]').first();
    expect(await repInput.count(), '队列里没有可指派的单（需 po_received 数据）').toBeGreaterThan(0);

    await repInput.fill(String(repId));
    const [resp] = await Promise.all([
      page.waitForResponse((r) => /assign-rep/.test(r.url()) && r.request().method() === 'POST'),
      page.getByRole('button', { name: /^Assign Rep$/i }).first().click(),
    ]);
    await page.waitForTimeout(1500);
    expect(resp.status(), '指派应返回 200').toBe(200);

    // 侧证必须走**详情**：`/orders/` 列表序列化器**不含** assigned_rep_id（实测）
    const body = await resp.json().catch(() => null);
    const orderId = body?.data?.id;
    expect(orderId, '指派响应里没有订单 id').toBeTruthy();

    const detail = await H.api(page, 'GET', `/api/v1/orders/${orderId}/`);
    expect(detail.status).toBe(200);
    const d = detail.data?.data ?? detail.data;
    expect(String(d.assigned_rep_id), '订单详情里的 assigned_rep_id 未更新，落库可能失败 / 或字段名变了')
      .toBe(String(repId));
  });

  test('★ 缺陷锁定：填用户名 ⇒ 500（应为 400）', async ({ page }) => {
    const calls = [];
    page.on('response', (r) => {
      if (/assign-rep/.test(r.url())) calls.push(r.status());
    });

    await H.login(page, 'probe_adminrole');
    await page.goto(`${H.BASE}/ops/po/review`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const repInput = page.locator('input[placeholder="Rep ID"]').first();
    if (!(await repInput.count())) test.skip(true, '队列为空，跳过');

    await repInput.fill('probe_procure');   // 用户名，不是数字
    await page.getByRole('button', { name: /^Assign Rep$/i }).first().click();
    await page.waitForTimeout(2500);

    // 当前行为 500；修好后应为 400 —— 出现 400 时这条会红，请同时更新说明书 §11.2 #19
    expect(calls, `期望捕获到一次 assign-rep 响应，实际 ${JSON.stringify(calls)}`).not.toEqual([]);
    expect(calls[0], '输入非数字 rep_id 的行为变了：若已修为 400，请更新本文档与 §11.2 #19')
      .toBe(500);
  });

  test('采购点 Assign Rep ⇒ 403（越权探测）', async ({ page }) => {
    const calls = [];
    page.on('response', (r) => {
      if (/assign-rep/.test(r.url())) calls.push(r.status());
    });

    await H.login(page, 'probe_procure');
    await page.goto(`${H.BASE}/ops/po/review`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const repInput = page.locator('input[placeholder="Rep ID"]').first();
    if (!(await repInput.count())) test.skip(true, '队列为空，跳过');
    await repInput.fill(String(H.ids().probe_staff));
    await page.getByRole('button', { name: /^Assign Rep$/i }).first().click();
    await page.waitForTimeout(2000);

    expect(calls[0], '采购不该能指派销售').toBe(403);
  });
});
