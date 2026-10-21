/**
 * I 维补白（1/3）：`/search` 结果点击 + `/products/:id` 文档链接
 *
 * ## 为什么需要
 * `docs/e2e/INTERACTION_VERDICT.md` 里 `/search` 的「结果点击」、`/products/:id` 的
 * 「文档链接」都标记为 **✗ 无 spec**。本文件只补这两项，不动其它已绿用例。
 *
 * ## 读码结论（选择器证据）
 * 1) 搜索结果点击：`SearchPage.vue:160-165`（All tab）与 `:181-186`（单类型 tab）
 *    `.result-item` 上绑 `@click="goToResult(...)"`；`goToResult`（`:74-87`）按 `_type`
 *    拼 `/products/` `/applications/` `/methods/` `/protocols/` 后 `router.push`。
 *    `references` 无详情页（`:81` typeMap 里是 null）⇒ 点 reference 不跳转，属已知设计。
 * 2) 文档链接：**不在** `ProductIndex.vue`（产品列表 = ProductCard 网格，`ProductLayout.vue`
 *    与 `ProductCard.vue` 里 grep 无 doc/download/SDS 任何字样）⇒ `/products` 页的
 *    「文档链接」是判定表把详情页交互列表套到列表页的产物，**该页没有这个元素**（如实报告）。
 *    真正的文档链接在详情页：`ProductDetail.vue:709-725`
 *      - `.pd-sds-group`（`v-if="currentSds"`）
 *      - `.pd-doc-link`（文案 SDS）→ `previewSds()` → `openPreview('sds', …)`（`:400-402`）
 *      - `.pd-doc-link[title="Download SDS"]` → `downloadSds()` → `window.open('/api/v1/sds-revisions/<id>/download/')`（`:403-405`、`api/documents.js:66-68`）
 *    数据源 = `documentsApi.getSdsList(product_id)`（`ProductDetail.vue:383-389`），
 *    即 `documents.SdsRevision`，**不是** `ProductDocument` / `Coa`。
 *
 * ## 数据前置（本轮实测，2026-10-21）
 * - `GET /api/v1/sds-revisions/` → 仅 2 条：
 *      id=1  product=23 (SC8003) status=published is_current=true  pdf_path=documents/sds/SDS-SC8003-v1.pdf
 *      id=17 product=2432          status=draft     is_current=false pdf_path=""
 *   ⇒ 唯一能渲染文档链接的公开产品是产品 23（路由 `/products/23`）；`Coa = 0` 条
 *     ⇒ 无 SKU 级 COA 图标可测。
 * - ⚠️ `GET /api/v1/sds-revisions/1/download/` 实测 **404**（`{"error":"PDF 文件不存在"}`）：
 *   DB 有 `pdf_path`，但 `backend/media/documents/sds/` 下**没有** `SDS-SC8003-v1.pdf`
 *   （目录里只有 E2E-H3 系列的历史文件）⇒ 下载链接是**坏的**。
 *   成因：`approve_sds()`（`backend/apps/documents/services/workflow.py:309-323`）才是
 *   「生成 PDF + 发布」的那一步，而这条记录是直接塞库状态为 published，没走过生成。
 *
 * ## 下载用例怎么处理（不造假绿）
 * 走 **UI 修复**而不是绕过页面 POST：staff 进 `/workspace/products/23/edit` 第 9 节
 * （`ProductEditPage.vue:2305-2380`），对当前版本点 `Withdraw`（`:2357` 仅在 is_current 时出现）
 * 再点 `Approve & Publish SDS`（`:2356` 仅在 !is_current 时出现）——后者调用 approve 接口正是
 * 「生成 PDF + 置回 published + 重新指向 current」（`workflow.py:316-328`），**不新增记录**，
 * 属于修数据不是造数据。修完再回公开页点下载，断言真实 HTTP 200。
 * 若 GET 本来就是 200（别人已修好），则跳过修复直接测下载。
 *
 * ## 拟人化
 * - 搜索结果：真实 `page.goto('/search?q=…')` + 真实点击（不用 evaluate 改路由）
 * - 文档：真实点击按钮；下载断言用 `context` 的 `request` 事件抓**页面自己发出的**请求
 *   （不是自己拼 URL 去 GET 假装用户点了）
 *
 * ## 不做什么
 * - 不断言搜索结果「条数」（共享 dev 库，别的 worker 会改产品）；只断言「有结果」+ 自洽跳转
 * - 不 snapshotDb()
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/search-result-docs.spec.cjs --project=chromium --output=/tmp/pw-ui
 */

const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff } = require('./helpers/auth.cjs');

/** 实测 `/api/v1/search/grouped?q=SC8003` → products=1（id=23），确定性强 */
const SEARCH_Q = 'SC8003';

/** 唯一带 published 当前版 SDS 的公开产品（见文件头数据前置） */
const DOCS_PRODUCT_ID = 23;
const DOCS_PRODUCT_PATH = `/products/${DOCS_PRODUCT_ID}`;
const SDS_REVISION_ID = 1;
const SDS_DOWNLOAD_PATH = `/api/v1/sds-revisions/${SDS_REVISION_ID}/download/`;

test.describe('@search 搜索结果点击', { tag: ['@readonly', '@local-only'] }, () => {
  test('点一条搜索结果 → 跳对应详情页（URL + 目标页关键元素）', async ({ page }) => {
    await page.goto(`${BASE_URL}/search?q=${SEARCH_Q}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.search-page', { timeout: 15000 });

    // 结果由 searchGrouped 异步返回（SearchPage.vue:60-72）
    const items = page.locator('.result-item');
    await expect(items.first()).toBeVisible({ timeout: 15000 });

    // 只断言"有结果"，不断言条数（共享库）
    const n = await items.count();
    expect(n, `搜索「${SEARCH_Q}」应至少返回 1 条结果（否则本用例无测试对象，属数据问题）`)
      .toBeGreaterThan(0);

    // 记录点击前的可识别信息：标题 + 副标题（副标题对产品是 "catalog_no | cas"，见 SearchPage.vue:99-106）
    const first = items.first();
    const name = ((await first.locator('.result-name').textContent()) || '').trim();
    const subtitle = ((await first.locator('.result-subtitle').textContent()) || '').trim();
    const catalog = subtitle.split('|')[0].trim();
    expect(name, '结果项应有标题').toBeTruthy();

    await first.click();

    // 断言 1：真的导航到详情页（不是停在 /search）
    await expect(page).toHaveURL(new RegExp(`/products/\\d+$`), { timeout: 10000 });

    // 断言 2：目标页渲染了对应产品（标题 + catalog 芯片，ProductDetail.vue:512-514）
    await expect(page.locator('.pd-name')).toHaveText(name, { timeout: 15000 });
    if (catalog) {
      await expect(page.locator('.pd-name-tags')).toContainText(catalog);
    }
  });
});

test.describe('@products 产品详情页文档链接（SDS）', { tag: ['@local-only'] }, () => {
  test('文档链接可见 + 点击打开合规预览弹层', async ({ page }) => {
    await page.goto(BASE_URL + DOCS_PRODUCT_PATH, { waitUntil: 'domcontentloaded' });

    // 文档区在 SKU 区块底部：ProductDetail.vue:709-720（v-if="currentSds"）
    const sdsGroup = page.locator('.pd-sds-group');
    await expect(sdsGroup, '产品 23 应渲染 SDS 文档组（documents.SdsRevision id=1 published/current）')
      .toBeVisible({ timeout: 20000 });

    // [0] = 预览（.pd-doc-link，文案 SDS），[1] = 下载（.pd-doc-link-alt[title="Download SDS"]）
    const previewBtn = sdsGroup.locator('.pd-doc-link').first();
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();

    // openPreview 命令式挂载 CompliancePreviewModal（utils/previewInject.js:24-38）
    // 弹层根：components/CompliancePreviewModal.vue:44-51（.preview-dialog + iframe[title="document preview"]）
    const dialog = page.locator('.preview-dialog');
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await expect(dialog.locator('iframe[title="document preview"]')).toBeVisible();

    // 关闭按钮（CompliancePreviewModal.vue:48）后弹层应卸载
    await dialog.locator('.preview-close').click();
    await expect(page.locator('.preview-dialog')).toHaveCount(0, { timeout: 5000 });
  });

  test('下载链接 → 页面发起下载请求且服务端返回 200 PDF', async ({ page }) => {
    // ① 先探测下载端点。DB 里有 pdf_path 但文件缺失时会 404（见文件头「数据前置」）。
    const probe = await page.request.get(BASE_URL + SDS_DOWNLOAD_PATH);
    if (probe.status() !== 200) {
      console.log(`__E2E__ 下载端点当前 ${probe.status()}（PDF 文件缺失）⇒ 走 UI 修复：withdraw → approve 重新生成 PDF`);
      await repairSdsPdf(page);
      const again = await page.request.get(BASE_URL + SDS_DOWNLOAD_PATH);
      expect(again.status(), 'UI 修复（Approve & Publish SDS）后下载端点应恢复 200').toBe(200);
    }

    // ② 回公开详情页，真实点击下载按钮
    await page.goto(BASE_URL + DOCS_PRODUCT_PATH, { waitUntil: 'domcontentloaded' });
    const sdsGroup = page.locator('.pd-sds-group');
    await expect(sdsGroup).toBeVisible({ timeout: 20000 });

    const downloadBtn = sdsGroup.locator('.pd-doc-link[title="Download SDS"]');
    await expect(downloadBtn, '下载按钮（title="Download SDS"，ProductDetail.vue:717）应可见').toBeVisible();

    // ③ 抓「页面自己发出的」下载请求：downloadSds 走 window.open(…)，请求归 context
    //    ⇒ 用 context 的 request 事件，而不是自己拼 URL 去 GET（那等于绕开被测路径）
    const reqPromise = page.context().waitForEvent('request', {
      predicate: (r) => r.url().includes(`/sds-revisions/${SDS_REVISION_ID}/download/`),
      timeout: 15000,
    });
    await downloadBtn.click();
    const req = await reqPromise;

    const resp = await req.response();
    expect(resp, '下载请求应拿到响应').toBeTruthy();
    expect(resp.status(), '下载应 200（PDF 存在）').toBe(200);
    expect(resp.headers()['content-type'] || '', '下载内容应为 PDF').toContain('application/pdf');
    console.log(`__E2E__ SDS 下载 ${req.url()} → ${resp.status()} ${resp.headers()['content-type']}`);
  });
});

/**
 * UI 修复 SDS PDF：staff 编辑页第 9 节对当前版本 Withdraw → Approve & Publish。
 * 依据：approve_sds 会 `generate_sds_pdf()` 并把状态置回 published、重新指向 current
 * （backend/apps/documents/services/workflow.py:309-328），记录数不变、rev 号不变。
 */
async function repairSdsPdf(page) {
  await loginAsStaff(page);
  await page.goto(`${BASE_URL}/workspace/products/${DOCS_PRODUCT_ID}/edit`, { waitUntil: 'domcontentloaded' });

  // 第 9 节 SDS 版本列表（ProductEditPage.vue:2340-2365）
  const revList = page.locator('.sds-rev-list');
  await expect(revList, '编辑页第 9 节应加载出 SDS 版本列表').toBeVisible({ timeout: 30000 });

  // ⚠️ 卡片必须按结构定位（`.sds-rev-card` 首张），**不能**用 text 过滤：
  //    Withdraw 之后卡片文案从 "Currently published" 变成 "Draft"，
  //    text 过滤的 locator 会立即失效（实测踩坑：`filter({hasText:'Currently published'})`
  //    在 withdraw 后解析为空 ⇒ 找不到 Approve 按钮，且把记录留在了 draft）。
  const card = revList.locator('.sds-rev-card').first();
  await expect(card, '应存在 SDS 版本卡片').toBeVisible({ timeout: 15000 });

  // 已发布态（is_current）只有 Withdraw（：2357）；draft 态只有 Approve（：2356）
  const withdrawBtn = card.getByRole('button', { name: 'Withdraw' });
  if (await withdrawBtn.count()) {
    await withdrawBtn.click();
  }

  const approveBtn = card.getByRole('button', { name: /Approve & Publish SDS/i });
  await expect(approveBtn, 'Withdraw 后应出现 Approve & Publish SDS 按钮').toBeVisible({ timeout: 20000 });

  // ：2356 —— approve 即「生成 PDF + 发布」（workflow.py:316-328）
  await approveBtn.click();
  await expect(revList.locator('.tag-sds'), '重新发布后应回到 Currently published').toBeVisible({ timeout: 25000 });
  await expect(card).toContainText('Currently published');
  console.log('__E2E__ SDS PDF 已通过编辑页 Withdraw → Approve 重新生成');
}
