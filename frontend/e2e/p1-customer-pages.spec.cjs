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
   * ★ 2026-10-22 实测发现的功能缺陷（不是权限问题）：
   *   `PoDownloadCenter.vue:18-21` 用 `o.invoice || o.attachments.length` 过滤订单，
   *   但 `/api/v1/orders/` 的**列表序列化器不返回这两个字段**
   *   ⇒ 即使客户有已开票订单 + PO 附件，页面**永远显示空态**。
   *
   * 本用例锁定的是"当前是坏的"：一旦列表补上字段/页面改走详情接口，这里会红，
   * 请同时更新说明书 §11.3 与 flow_coverage_matrix 的 F3-11。
   */
  test('★ 缺陷锁定：有已开票订单，页面仍空态（根因：列表缺 invoice/attachments）', async ({ page }) => {
    const IDS = H.ids();

    await H.login(page, 'probe_ouser_a');

    // 侧证 1：API 里确实有一张 invoiced 订单
    const list = await H.api(page, 'GET', '/api/v1/orders/?page_size=100');
    const rows = (list.data?.data ?? list.data) || [];
    const inv = rows.find((o) => String(o.id) === String(IDS.order_invoiced));
    expect(inv, `夹具订单 ${IDS.order_invoiced} 不在客户订单列表里`).toBeTruthy();
    expect(inv.status, '夹具订单状态应为 invoiced').toBe('invoiced');

    // 侧证 2：根因 —— 列表行里没有 invoice / attachments
    expect(inv.invoice, '列表开始返回 invoice 了 —— 若下载中心已修，请更新本文档与 F3-11')
      .toBeUndefined();
    expect(inv.attachments, '列表开始返回 attachments 了 —— 同上').toBeUndefined();

    // 现象：页面空态
    await page.goto(`${H.BASE}/po/downloads`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const txt = await H.bodyText(page);
    expect(txt, '页面不再空态了 —— 若已修复，请更新本文档').toMatch(
      /No downloadable documents yet/i,
    );
  });

  test('（应为绿）发票 PDF 端点本身对本人可用 —— 说明缺的只是页面数据通路', async ({ page }) => {
    const IDS = H.ids();
    await H.login(page, 'probe_ouser_a');
    const r = await H.api(page, 'GET', `/api/v1/invoices/${IDS.invoice_id}/pdf/`);
    // 200=有 PDF；404=发票存在但无 pdf_path；都不是权限问题（403/401）
    expect([200, 404], `本人读自己发票 PDF 得 ${r.status}，若是 403/401 说明权限有问题`)
      .toContain(r.status);
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
