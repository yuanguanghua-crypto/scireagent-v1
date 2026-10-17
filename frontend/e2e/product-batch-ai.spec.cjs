/**
 * 产品「批量 AI 校验 / 批量文献推荐」入口（2026-10-17）
 *
 * 背景：`AdminProductsPage.vue` 因"零引用"被当作死代码删除（5868600），连带丢掉了这两个
 *   批量 AI 操作的前端入口。后端端点（batch-validate / batch-recommend-literature）与
 *   前端 API 函数（api/aiTools.js:15-21）均健在，只是没人调用 ⇒ 能力失去唯一前端入口。
 *   本 spec 锁住补回后的入口，在 `views/workspace/ProductsPage.vue`（现役页）上验证。
 *
 * 覆盖点（对应能力本体，不是"按钮在那儿"的壳）：
 *   1. 未勾选产品 ⇒ 两个批量按钮**不出现**（header 内条件渲染）
 *   2. 勾选 ≥1 ⇒ 按钮出现，点击后**真的发出请求**（断言 URL + 请求体 product_ids）
 *   3. 结果对话框**逐产品**渲染：名称 / status / overall_match / mismatches / pubchem_cid
 *   4. mismatches 非空 ⇒ 有专门 class 视觉区分（运营最需要看的信号）
 *   5. 批量文献推荐 ⇒ 同样能触发请求并渲染 references
 *   6. ★ 权限口径差异：后端 `IsAdminUser`(= is_staff)，而页面守卫是 isInternal()
 *      (is_staff || role∈(procurement,admin)) ⇒ 非 staff 的 procurement 能进页面但调了会 403。
 *      本 spec 锁住"前端不给他看无法工作的按钮"。
 *
 * ⚠ 全部用 page.route 拦截两个批量端点返回固定信封：
 *   真跑会打 PubChem / PubMed 外网（慢且不稳），断言的是**前端交互**不是后端算法。
 *   后端算法的正确性由 backend/apps/commerce/tests/test_ai_views.py 覆盖。
 * ⚠ 只读：只勾选/只读列表，不提交任何写操作。
 * ⚠ 串行：playwright.config.cjs 已锁 workers=1。
 *
 * 运行：node node_modules/@playwright/test/cli.js test e2e/product-batch-ai.spec.cjs \
 *        --project=chromium --reporter=line --output=./e2e-artifacts-batchai --retries=0
 */
const { test, expect } = require('@playwright/test');
const { loginAsStaff, loginAsProcurement, BASE_URL } = require('./helpers/auth.cjs');

const BTN_VALIDATE = '[data-testid="batch-ai-validate"]';
const BTN_LITERATURE = '[data-testid="batch-ai-literature"]';
const DIALOG = '[data-testid="batch-ai-dialog"]';

/** 后端信封（与 core.mixins.EnvelopeMixin.success_response + utils/http.js:73 拦截器一致）：
 *  拦截器 `if (data && data.success) return data` ⇒ 组件拿到 body，用 `resp.data` 取结果数组。 */
function envelope(data) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, data, meta: {} }),
  };
}

const VALIDATE_RESULTS = [
  {
    product_id: 1,
    product_name: 'Specimen Alpha',
    validation: {
      status: 'completed',
      mismatches: ['cas', 'molecular_weight'],
      similar_compounds: [],
      pubchem_cid: 2244,
      overall_match: false,
    },
  },
  {
    product_id: 2,
    product_name: 'Specimen Beta',
    validation: {
      status: 'completed',
      mismatches: [],
      similar_compounds: [],
      pubchem_cid: 5793,
      overall_match: true,
    },
  },
];

const LITERATURE_RESULTS = [
  {
    product_id: 1,
    product_name: 'Specimen Alpha',
    literature: {
      applications: ['cross-linking'],
      methods: ['mass spectrometry'],
      references: [
        {
          pmid: '12345',
          title: 'A study on specimen alpha',
          source: 'Nature Methods',
          pubdate: '2024',
          authors: ['Curie M.', 'Röntgen W.'],
          doi: '10.1000/specimen',
          citation: 'Curie M., Röntgen W. (2024). A study on specimen alpha. Nature Methods. https://doi.org/10.1000/specimen',
        },
      ],
      protocols: [{ title: 'A study on specimen alpha', source: 'Nature Methods', pmid: '12345' }],
      matched_apps: [],
      matched_methods: [],
      unmatched_app_keywords: ['cross-linking'],
      unmatched_method_keywords: ['mass spectrometry'],
    },
  },
];

/** 拦截两个批量端点，返回固定信封 + 记录收到的 product_ids。
 *  ⚠ body 必须 JSON.stringify：传裸 object 时 Playwright 不会序列化，请求会永久挂起
 *    （实测踩过：组件无辜，是夹具的坑）。 */
async function stubBatchEndpoints(page, { fail = false } = {}) {
  const seen = { validate: [], literature: [] };
  await page.route('**/api/v1/products/batch-validate/', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    seen.validate.push(body.product_ids);
    if (fail) {
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'PubChem unavailable' }),
      });
    }
    return route.fulfill(envelope(VALIDATE_RESULTS));
  });
  await page.route('**/api/v1/products/batch-recommend-literature/', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}');
    seen.literature.push(body.product_ids);
    return route.fulfill(envelope(LITERATURE_RESULTS));
  });
  return seen;
}

/** 勾选的 id 应原样发给后端。id 由后端真实数据决定（本地库在 5000+），
 *  因此这里断言"形状 + 数量 + 唯一性"，不硬编码具体数字（硬编码会随库漂移而假失败）。 */
function expectIdList(ids, n) {
  expect(Array.isArray(ids), '请求体应带 product_ids 数组').toBe(true);
  expect(ids).toHaveLength(n);
  expect(ids.every((v) => typeof v === 'number' && Number.isInteger(v)), 'product_ids 应全为整数 id').toBe(true);
  expect(new Set(ids).size, 'product_ids 不应有重复').toBe(n);
}

/** 进产品列表页并等表格渲染完。 */
async function gotoProducts(page) {
  await page.goto(`${BASE_URL}/workspace/products`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.products-table tbody tr', { timeout: 20000 });
  await page.waitForTimeout(600);
}

/** 勾选前 N 行（点击行内 checkbox，不触发行点击导航）。 */
async function selectFirstRows(page, n) {
  const boxes = page.locator('.products-table tbody tr .col-check input[type="checkbox"]');
  for (let i = 0; i < n; i++) await boxes.nth(i).check();
  await page.waitForTimeout(300);
}

test.describe('@local-only @readonly 产品批量 AI 入口', () => {
  test('未勾选产品时，批量 AI 两个按钮都不出现', async ({ page }) => {
    test.setTimeout(90000);
    await loginAsStaff(page);
    await gotoProducts(page);

    await expect(page.locator(BTN_VALIDATE)).toHaveCount(0);
    await expect(page.locator(BTN_LITERATURE)).toHaveCount(0);
  });

  test('勾选产品后按钮出现，点击真的发出 batch-validate 请求（带 product_ids）', async ({ page }) => {
    test.setTimeout(90000);
    await loginAsStaff(page);
    const seen = await stubBatchEndpoints(page);
    await gotoProducts(page);
    await selectFirstRows(page, 2);

    await expect(page.locator(BTN_VALIDATE)).toBeVisible();
    await expect(page.locator(BTN_LITERATURE)).toBeVisible();

    await page.locator(BTN_VALIDATE).click();

    // 请求确实发出，且带上被勾选产品的 id
    await expect.poll(() => seen.validate.length, { timeout: 15000 }).toBeGreaterThan(0);
    expectIdList(seen.validate[0], 2);

    // 结果对话框出现，逐产品渲染
    await expect(page.locator(DIALOG)).toBeVisible();
    const rows = page.locator(`${DIALOG} [data-testid="batch-ai-row"]`);
    await expect(rows).toHaveCount(VALIDATE_RESULTS.length);
    await expect(page.locator(DIALOG)).toContainText('Specimen Alpha');
    await expect(page.locator(DIALOG)).toContainText('Specimen Beta');
    // overall_match=false / true 与 pubchem_cid 都要能看到
    await expect(page.locator(DIALOG)).toContainText('2244');
    await expect(page.locator(DIALOG)).toContainText('5793');
    // mismatches 非空行有专门视觉区分；空行没有
    await expect(rows.nth(0)).toHaveAttribute('data-has-mismatch', 'true');
    await expect(rows.nth(1)).toHaveAttribute('data-has-mismatch', 'false');
  });

  test('批量文献推荐：点击发出请求并渲染推荐文献', async ({ page }) => {
    test.setTimeout(90000);
    await loginAsStaff(page);
    const seen = await stubBatchEndpoints(page);
    await gotoProducts(page);
    await selectFirstRows(page, 1);

    await page.locator(BTN_LITERATURE).click();
    await expect.poll(() => seen.literature.length, { timeout: 15000 }).toBeGreaterThan(0);
    expectIdList(seen.literature[0], 1);

    await expect(page.locator(DIALOG)).toBeVisible();
    await expect(page.locator(`${DIALOG} [data-testid="batch-ai-row"]`)).toHaveCount(1);
    await expect(page.locator(DIALOG)).toContainText('A study on specimen alpha');
  });

  test('请求失败时给出可见提示，且按钮恢复可点（不静默）', async ({ page }) => {
    test.setTimeout(90000);
    await loginAsStaff(page);
    await stubBatchEndpoints(page, { fail: true });
    await gotoProducts(page);
    await selectFirstRows(page, 1);

    await page.locator(BTN_VALIDATE).click();
    // 失败必须有用户可见提示（toast / 对话框内的错误块）
    await expect(page.locator('.el-message, [data-testid="batch-ai-error"]').first()).toBeVisible();
    // 按钮恢复可点（loading 已解除）
    await expect(page.locator(BTN_VALIDATE)).toBeEnabled();
  });

  test('★ 权限：非 staff 的 procurement 即使勾选也看不到批量 AI 按钮', async ({ page }) => {
    test.setTimeout(90000);
    await loginAsProcurement(page);
    // 自证前提：确实是 procurement 且 is_staff=false（否则本用例无意义）
    await page.goto(`${BASE_URL}/workspace/products`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.products-table tbody tr', { timeout: 20000 });
    const auth = await page.evaluate(() => ({
      isStaff: localStorage.getItem('is_staff'),
      role: localStorage.getItem('role'),
    }));
    expect(auth.isStaff).toBe('false');
    expect(auth.role).toBe('procurement');

    await selectFirstRows(page, 2);
    // 后端是 IsAdminUser(=is_staff) ⇒ 非 staff 调了必 403 ⇒ 前端不给入口
    await expect(page.locator(BTN_VALIDATE)).toHaveCount(0);
    await expect(page.locator(BTN_LITERATURE)).toHaveCount(0);
    // 但既有批量操作仍在（证明是精准隐藏 AI 按钮，不是整块批量功能被关掉）
    await expect(page.getByRole('button', { name: 'Batch archive' })).toBeVisible();
  });
});