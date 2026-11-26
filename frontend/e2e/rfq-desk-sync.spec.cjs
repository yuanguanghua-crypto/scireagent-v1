/**
 * A-090 / A-220 / A-222 —— RFQ 运营台的「列表与详情不同步」+「Refresh 不重置」（2026-11-18 / S4）
 *
 * ## 三个症状同源
 * `RfqDesk.vue` 的右侧详情是**按 id 单独取**的（`GET /quote-requests/:id/`），
 * 不跟着左列走；而 `load()` 只替换 `rows`、从不检查 `detail` 是否还在新结果里。
 * 于是：
 *   1. **A-090**：按状态筛选后，详情仍停在一条**已从列表消失**的单子上 ——
 *      运营会以为"它还在当前视图里"，在看不见的行上填报价。
 *   2. **A-220 / A-222**：`Refresh` 按钮直接绑 `load()`，语义退化成"按当前筛选再查一遍"
 *      ⇒ 点了刷新，状态筛选还停在 `pending`、搜索词还在，与"刷新 = 重新开始"不符。
 *
 * ## 修法与判据
 *   · `load()` 末尾：列表换批后若 `detail` 的 id 不在新 `rows` 里 ⇒ 清空详情（含报价表单）
 *   · 新增 `refresh()` = 清空搜索 + 清空状态筛选 + `load()`；Refresh 按钮改绑它
 *   · `Apply` 仍绑 `load()`（它的语义本来就是"按当前条件查"）
 *
 * ⚠️ 本 spec 跑在**主 dev 栈**（5173，`helpers/auth.cjs`），不是探测栈。
 *    RFQ 创建是匿名接口，所以自建单子不需要额外账号，幂等（每次自造、断言"存在"不断言条数）。
 */
const { test, expect } = require('@playwright/test');
const A = require('./helpers/auth.cjs');

const SEARCH_SEL = '[data-testid="rfq-search"]';
const STATUS_SEL = '[data-testid="rfq-status-filter"]';
const APPLY_SEL = '[data-testid="rfq-apply"]';
const REFRESH_SEL = '[data-testid="rfq-refresh"]';
const DETAIL_SEL = '[data-testid="rfq-detail"]';

/** 匿名创建一条 RFQ（返回 id / email） */
async function createRfq(page) {
  const stamp = `${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  const email = `e2e_rfqsync_${stamp}@e2e.local`;
  const res = await page.evaluate(
    async ({ email, stamp }) => {
      const r = await fetch('/api/v1/quote-requests/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contact_name: `E2E RFQ Sync ${stamp}`,
          contact_email: email,
          company_name: 'E2E Sync Labs',
          country: 'China',
          notes: 'rfq-desk-sync spec',
          items: [{ product_name: 'E2E Item A', quantity: 2 }],
        }),
      });
      let body = null;
      try { body = await r.json(); } catch { body = null; }
      return { status: r.status, body };
    },
    { email, stamp },
  );
  expect(res.status, `匿名创建 RFQ 失败：${JSON.stringify(res.body).slice(0, 300)}`).toBe(201);
  const data = res.body?.data ?? res.body;
  expect(data?.id, '创建 RFQ 未返回 id').toBeTruthy();
  return { id: data.id, email };
}

test.describe('@local-only A-090/220/222 RFQ 运营台：详情跟随列表 + Refresh 重置', () => {
  test('筛选掉当前行 ⇒ 详情清空；Refresh ⇒ 筛选与搜索都被重置', async ({ page }) => {
    test.setTimeout(120_000);

    // 1) 匿名态先造一条 RFQ（此时还没登录，fetch 就是匿名请求）
    await page.goto(`${A.BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const rfq = await createRfq(page);

    // 2) staff 进运营台
    await A.loginAsStaff(page);
    await page.goto(`${A.BASE_URL}/ops/rfq`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    expect(new URL(page.url()).pathname, 'staff 被踢出 /ops/rfq').toBe('/ops/rfq');

    // 3) 用搜索把列表收敛到这一条，再打开详情
    await page.locator(SEARCH_SEL).fill(rfq.email);
    await page.locator(APPLY_SEL).click();
    await page.waitForTimeout(1500);

    const row = page.locator('tr', { hasText: rfq.email }).first();
    await expect(row, '搜索没有收敛到刚造的 RFQ').toHaveCount(1);
    await row.getByRole('button', { name: /View/i }).click();
    await page.waitForTimeout(1200);

    await expect(page.locator(DETAIL_SEL), '点了 View 却没出详情面板').toHaveCount(1);
    await expect(page.locator(DETAIL_SEL)).toContainText(`RFQ #${rfq.id}`);

    // 4) ★ A-090：换成「必然查不到这一条」的筛选 ⇒ 列表空了，详情必须跟着清掉
    await page.locator(STATUS_SEL).selectOption('quoted');
    await page.locator(APPLY_SEL).click();
    await page.waitForTimeout(1500);

    await expect(row, 'status=quoted 却仍列出 pending 的新单（筛选失效）').toHaveCount(0);
    await expect(
      page.locator(DETAIL_SEL),
      '★ 列表已经筛掉了这条，右侧详情还停在旧行（A-090 未修）',
    ).toHaveCount(0);

    // 5) ★ A-220 / A-222：Refresh 必须把状态筛选与搜索词都复位
    await page.locator(REFRESH_SEL).click();
    await page.waitForTimeout(1800);

    await expect(page.locator(STATUS_SEL), '★ Refresh 后状态筛选没复位（A-220/222 未修）')
      .toHaveValue('');
    await expect(page.locator(SEARCH_SEL), '★ Refresh 后搜索词没清空').toHaveValue('');

    // 复位之后这一条应该重新出现在列表里
    await expect(
      page.locator('tr', { hasText: rfq.email }).first(),
      'Refresh 复位后仍看不到这条 RFQ（列表没重取）',
    ).toHaveCount(1);
  });

  test('Refresh 不清掉「仍然在结果里」的详情（避免过度重置）', async ({ page }) => {
    test.setTimeout(120_000);

    await page.goto(`${A.BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const rfq = await createRfq(page);

    await A.loginAsStaff(page);
    await page.goto(`${A.BASE_URL}/ops/rfq`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    await page.locator(SEARCH_SEL).fill(rfq.email);
    await page.locator(APPLY_SEL).click();
    await page.waitForTimeout(1500);
    await page.locator('tr', { hasText: rfq.email }).first()
      .getByRole('button', { name: /View/i }).click();
    await page.waitForTimeout(1200);
    await expect(page.locator(DETAIL_SEL)).toContainText(`RFQ #${rfq.id}`);

    // 详情这条在全量列表里依然存在 ⇒ 清筛选后详情应保留（不该被无差别清掉）
    await page.locator(REFRESH_SEL).click();
    await page.waitForTimeout(1800);
    await expect(
      page.locator(DETAIL_SEL),
      'Refresh 把仍在列表里的详情也清掉了 —— 重置做过头了',
    ).toContainText(`RFQ #${rfq.id}`);
  });
});
