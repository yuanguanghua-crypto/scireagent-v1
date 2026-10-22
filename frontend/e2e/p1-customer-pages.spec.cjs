/**
 * Batch 2 / P1-3~P1-5 —— 客户侧三个零功能用例的页面
 *   F3-11 下载中心（发票 PDF / PO 附件）
 *   F3-12 再次订购（Re-order 跳转与预填）
 *   F3-13 收藏夹（收藏 / 取消 / 未登录提示）
 *
 * 夹具由 scripts/probe_seed_customer_flow.py 造：
 *   order_completed=1259（供再次订购）、order_invoiced=1260 + invoice=291 + attachment=1（供下载中心）
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p1 @local-only F3-11 下载中心', () => {
  /**
   * 2026-10-22 修：此前 `PoDownloadCenter.vue` 用 `o.invoice || o.attachments.length` 过滤订单，
   * 而 `/api/v1/orders/` 的列表序列化器**不返回这两个字段** ⇒ 页面永远空态。
   * 修复：`OrderListSerializer` 增加最小子集 invoice{id,invoice_no} / attachments[{id,original_filename}]，
   * 并在两个 ViewSet 的 queryset 加 select_related/prefetch 防 N+1。
   * 本用例从"锁缺陷"改为"验功能"。
   */
  test('列表接口返回 invoice / attachments（契约）', async ({ page }) => {
    const IDS = H.ids();
    await H.login(page, 'probe_ouser_a');
    const list = await H.api(page, 'GET', '/api/v1/orders/?page_size=100');
    const rows = (list.data?.data ?? list.data) || [];
    const inv = rows.find((o) => String(o.id) === String(IDS.order_invoiced));
    expect(inv, `夹具订单 ${IDS.order_invoiced} 不在列表里`).toBeTruthy();

    expect(inv.invoice, '列表仍未返回 invoice 字段（下载中心会继续空态）').toBeTruthy();
    expect(String(inv.invoice.invoice_no), '发票号缺失').toMatch(/PROBE-INV-1/);
    expect(Array.isArray(inv.attachments), 'attachments 应为数组').toBe(true);
    expect(inv.attachments.length, '夹具 PO 附件未出现在列表').toBeGreaterThan(0);
    expect(inv.attachments[0].id, '附件缺 id（前端按钮需要）').toBeTruthy();
  });

  test('页面列出可下载文档，点 Invoice PDF 真的发请求', async ({ page }) => {
    const hits = [];
    page.on('request', (r) => {
      if (/\/invoices\/\d+\/pdf\//.test(r.url())) hits.push(r.url());
    });

    await H.login(page, 'probe_ouser_a');
    await page.goto(`${H.BASE}/po/downloads`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const txt = await H.bodyText(page);
    expect(txt, '仍显示空态（修复未生效）').not.toMatch(/No downloadable documents yet/i);
    expect(txt, '页面没显示该订单').toMatch(/PROBE-CUST-INV-1/);
    expect(txt, '页面没显示发票号').toMatch(/PROBE-INV-1/);

    const pdf = page.getByRole('button', { name: /Invoice PDF/i }).first();
    expect(await pdf.count(), '没有 Invoice PDF 按钮').toBeGreaterThan(0);
    await pdf.click();
    await page.waitForTimeout(2000);
    expect(hits.length, '点 Invoice PDF 没发请求').toBeGreaterThan(0);
  });

  test('PO 附件按钮渲染并可点', async ({ page }) => {
    const hits = [];
    page.on('request', (r) => {
      if (/orders\/attachments\/\d+\/download/.test(r.url())) hits.push(r.url());
    });
    await H.login(page, 'probe_ouser_a');
    await page.goto(`${H.BASE}/po/downloads`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const att = page.getByRole('button', { name: /^PO \d+/ }).first();
    expect(await att.count(), '没有 PO 附件按钮').toBeGreaterThan(0);
    await att.click();
    await page.waitForTimeout(1500);
    expect(hits.length, 'PO 附件下载没发请求').toBeGreaterThan(0);
  });

  test('没有发票/附件的客户仍显示空态（不误报）', async ({ page }) => {
    await H.login(page, 'probe_ouser_b');
    await page.goto(`${H.BASE}/po/downloads`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const txt = await H.bodyText(page);
    expect(txt).toMatch(/No downloadable documents yet/i);
  });
});

test.describe('@p1 @local-only F3-12 再次订购', () => {
  test('只列已完成订单，Re-order 跳到提交页并带 reorder 参数', async ({ page }) => {
    await H.login(page, 'probe_ouser_a');
    await page.goto(`${H.BASE}/po/reorder`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);

    const txt = await H.bodyText(page);
    if (/No completed orders available to re-order/i.test(txt)) {
      throw new Error('再次订购页显示空态，但夹具有一张 completed 订单（order_completed）');
    }
    expect(txt, '列表里应出现夹具订单号').toMatch(/PROBE-CUST-DONE-1/);

    const btn = page.getByRole('button', { name: /Re-order/i }).first();
    await btn.click();
    await page.waitForTimeout(2000);
    expect(page.url(), 'Re-order 没跳到 PO 提交页').toContain('/po/submit');
    expect(page.url(), 'Re-order 没带 reorder 参数').toMatch(/reorder=\d+/);
  });
});

test.describe('@p1 @local-only F3-13 收藏夹', () => {
  test('未登录访问给出登录引导（不是空白）', async ({ page }) => {
    await page.goto(`${H.BASE}/wishlist`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    const txt = await H.bodyText(page);
    expect(txt, '未登录应提示登录').toMatch(/请先登录|Sign In|login/i);
  });

  test('收藏 → 出现 → 移除 → 消失（含侧证）', async ({ page }) => {
    const IDS = H.ids();
    const pid = IDS.customer_product_id;

    await H.login(page, 'probe_ouser_a');
    // 先清空，保证可重复
    const wl = await H.api(page, 'GET', '/api/v1/wishlist/');
    const list = wl.data?.data ?? wl.data;
    const cur = Array.isArray(list) ? list[0] : null;
    // ★ 读取返回的是 `products: [{id,...}]`；`product_ids` 只在**写入**时用（实测踩过）
    if (cur && (cur.products || []).length) {
      await H.api(page, 'PATCH', `/api/v1/wishlist/${cur.id}/`, { product_ids: [] });
    }

    // 在产品详情页收藏
    await page.goto(`${H.BASE}/products/${pid}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const fav = page.getByRole('button', { name: /收藏/ }).first();
    expect(await fav.count(), '产品详情页没有收藏按钮').toBeGreaterThan(0);
    await fav.click();
    await page.waitForTimeout(1800);

    // 侧证：API 里真的有
    const after = await H.api(page, 'GET', '/api/v1/wishlist/');
    const l2 = after.data?.data ?? after.data;
    const w = Array.isArray(l2) ? l2[0] : null;
    expect((w?.products || []).map((x) => String(x.id)), '收藏未落库').toContain(String(pid));

    // 收藏夹页能看到，并移除
    await page.goto(`${H.BASE}/wishlist`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const before = await H.bodyText(page);
    expect(before, '收藏夹里看不到刚收藏的产品').not.toMatch(/还没有收藏/);

    const rm = page.getByRole('button', { name: /移除|Remove/ }).first();
    if (await rm.count()) {
      await rm.click();
      await page.waitForTimeout(1800);
      const l3 = await H.api(page, 'GET', '/api/v1/wishlist/');
      const l3d = l3.data?.data ?? l3.data;
      const w3 = Array.isArray(l3d) ? l3d[0] : null;
      expect((w3?.products || []).map((x) => String(x.id)), '移除后仍在收藏里').not.toContain(String(pid));
    }
  });
});
