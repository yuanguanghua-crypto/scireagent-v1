/**
 * I 维补白（4/4）：`/workspace` 快捷入口 + `/workspace/knowledge-intake` 产品选择
 *
 * ## 为什么需要
 * `docs/e2e/INTERACTION_VERDICT.md` 里 `/workspace` 的「快捷入口」、`/workspace/knowledge-intake`
 * 的「产品下拉」都是 **✗ 无 spec**。
 *
 * ## 读码结论（选择器证据，含"描述过时"的纠正）
 * ### /workspace 快捷入口（`views/workspace/DashboardPage.vue`）
 * - `.actions-bar > router-link` 文案 `+ New Product` → `/workspace/products/new`（`:83-85`）
 * - `.gov-action`「去审核 →」→ `/workspace/verified`（`:150`，**仅当 `stats.verified_review > 0`**，
 *   属条件渲染 ⇒ 不作为本用例的必经项）
 * - `.recent-table tbody tr a` → `/workspace/products/<id>/edit`（`:196-200`，数据来自
 *   `GET /products/?page_size=10&ordering=-updated_at`，`:43-47`）
 * ⇒ 用**恒在**的 `+ New Product` 做主断言，用最近更新表格行做第二条入口（数据驱动）。
 *
 * ### /workspace/knowledge-intake「产品下拉」
 * ⚠️ 判定表写的是「产品下拉（AppSelect）」，**实际不是下拉组件**：
 *   `KnowledgeIntake.vue` 全文没有 AppSelect（`grep -rn AppSelect views/KnowledgeIntake.vue` 零命中；
 *   全站 14 个 AppSelect 实例都在 `ProductEditPage.vue`）。
 *   真实实现是**左侧产品列表 + 过滤输入框**：
 *     - `.ki-search`（`v-model="filterClass"`，`:196-200`）→ `filteredProducts` 计算属性
 *       （按 category_l1 / name / catalog_no 模糊匹配，`:77-84`）
 *     - `.ki-product-item`（`:202-211`）点击 → `selectProduct()`（`:87-105`）
 *     - 选中后右侧 `.ki-form-area` 渲染产品头 `.ki-product-header`（名称 / `.ki-catalog` / CAS，`:216-221`），
 *       列表项加 `.ki-active`（`:206`）—— 这就是"选中并回显"。
 * ⇒ 按真实控件测：能筛选、能选中、右侧回显 catalog + 名称、选中项高亮；并测"清空筛选可回退"。
 *
 * ## 纪律
 * - 全走 UI（真实点击 / 真实输入），不 evaluate 塞值
 * - 不断言绝对条数：只在"筛选前 vs 筛选后"做相对比较；产品条数用 >0 守卫（不是 ==N）
 * - 该页不写库（只读选择），无清理动作
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/workspace-entry-intake.spec.cjs --project=chromium --output=/tmp/pw-ui
 */

const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff } = require('./helpers/auth.cjs');

/** 知识录入页按 catalog 过滤的靶标（产品 23 / SC8003，dev 库唯一） */
const CATALOG = 'SC8003';

async function openDashboard(page) {
  await loginAsStaff(page);
  await page.goto(`${BASE_URL}/workspace`, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.dashboard')).toBeVisible({ timeout: 20000 });
  // stats 请求完成后才渲染 v-else 主体（DashboardPage.vue:59-61）
  await expect(page.locator('.actions-bar')).toBeVisible({ timeout: 25000 });
}

test.describe('@workspace Dashboard 快捷入口', { tag: ['@readonly', '@local-only'] }, () => {
  test('「+ New Product」→ 跳 /workspace/products/new 并渲染新建表单', async ({ page }) => {
    await openDashboard(page);

    const newProduct = page.locator('.actions-bar a', { hasText: /New Product/i });
    await expect(newProduct, '快捷入口「+ New Product」应可见（DashboardPage.vue:84）').toBeVisible();
    await expect(newProduct).toHaveAttribute('href', /\/workspace\/products\/new$/);

    await newProduct.click();

    await expect(page).toHaveURL(/\/workspace\/products\/new$/, { timeout: 10000 });
    // 新建页关键元素：分节表单 + 保存按钮（ProductEditPage.vue:2015+ 各 .form-section、:2433 Save Draft）
    await expect(page.locator('.form-section').first()).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('button', { name: /Save Draft/i })).toBeVisible();
  });

  test('「Recently Updated」首行 → 跳该产品的编辑页', async ({ page }) => {
    await openDashboard(page);

    const rows = page.locator('.recent-table tbody tr');
    await expect(rows.first(), '最近更新表格应有数据（无数据则快捷入口无对象，属数据问题）')
      .toBeVisible({ timeout: 20000 });

    const link = rows.first().locator('a');
    const href = await link.getAttribute('href');
    expect(href, '行内链接应指向编辑页 /workspace/products/<id>/edit（DashboardPage.vue:199）')
      .toMatch(/^\/workspace\/products\/\d+\/edit$/);
    const productName = ((await link.textContent()) || '').trim();

    await link.click();

    await expect(page).toHaveURL(/\/workspace\/products\/\d+\/edit/, { timeout: 10000 });
    await expect(page.locator('.form-section').first()).toBeVisible({ timeout: 30000 });
    // 编辑页拿得到的是同一个产品：第 1 节 name 输入框（ProductEditPage.vue:2019）应回填该名字
    if (productName) {
      await expect(page.locator('input[placeholder="e.g. 2\'-Amino-ATP"]'))
        .toHaveValue(productName, { timeout: 20000 });
      console.log(`__E2E__ 从 Dashboard 进入编辑页：${productName}（${href}）`);
    }
  });
});

test.describe('@workspace 知识录入页产品选择', { tag: ['@readonly', '@local-only'] }, () => {
  test('产品列表可筛选 → 选中 → 右侧回显 catalog/名称且列表项高亮', async ({ page }) => {
    await loginAsStaff(page);
    await page.goto(`${BASE_URL}/workspace/knowledge-intake`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.ki-page')).toBeVisible({ timeout: 15000 });

    const items = page.locator('.ki-product-item');
    await expect(items.first(), '产品列表应加载出条目（GET /products/?page_size=200，KnowledgeIntake.vue:68）')
      .toBeVisible({ timeout: 25000 });
    const totalBefore = await items.count();
    expect(totalBefore, '产品列表应至少 1 条').toBeGreaterThan(0);

    // ① 筛选：输入 catalog ⇒ 列表收窄到该产品（相对比较，不写死条数）
    await page.locator('.ki-search').fill(CATALOG);
    await expect(items.first().locator('.ki-product-cat')).toHaveText(CATALOG, { timeout: 10000 });
    const narrowed = await items.count();
    expect(narrowed, `按「${CATALOG}」筛选后应比筛选前少`).toBeLessThan(totalBefore);

    const pickedName = ((await items.first().locator('.ki-product-name').textContent()) || '').trim();

    // ② 选中：点列表项 ⇒ 右侧表单出现（未选中时是 .ki-empty，KnowledgeIntake.vue:366-368）
    await items.first().click();
    await expect(page.locator('.ki-form-area')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.ki-empty')).toHaveCount(0);

    // ③ 回显：右侧产品头显示同一 cataog + 名称；列表项高亮 .ki-active（:206）
    await expect(page.locator('.ki-product-header .ki-catalog')).toHaveText(CATALOG);
    if (pickedName) {
      await expect(page.locator('.ki-product-header h2')).toHaveText(pickedName);
    }
    await expect(page.locator('.ki-product-item.ki-active')).toHaveCount(1);
    await expect(page.locator('.ki-product-item.ki-active')).toContainText(CATALOG);

    // ④ 回退：清空筛选 ⇒ 列表恢复（条数回升，相对断言）
    await page.locator('.ki-search').fill('');
    await expect.poll(async () => items.count(), { timeout: 10000 })
      .toBeGreaterThan(narrowed);
    // 已选中的产品在清空筛选后仍保持选中/高亮（不因重排丢失）
    await expect(page.locator('.ki-product-item.ki-active')).toContainText(CATALOG);
  });
});
