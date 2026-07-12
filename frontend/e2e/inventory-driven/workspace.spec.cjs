/**
 * 阶段 3 — Workspace 研究员穷举（inventory-driven/workspace.spec.cjs）
 *
 * 覆盖 §4 阶段3：Dashboard / ProductsPage / ProductEditPage / 五个知识管理页
 * (Apps/Methods/Protocols/Goals/References) / KnowledgeIntake 的主流程交互。
 * 选择器以真实源码为准（已逐页读取 AdminLayout/DashboardPage/ProductsPage/
 * ProductEditPage/AppsPage/MethodsPage/ProtocolsPage/GoalsPage/ReferencesPage/
 * KnowledgeIntake）：
 *  - 列表：原生 `<table>`(`.entity-table`/`.products-table`/`.recent-table`)。
 *  - 弹层：自定义 `<div class="dialog-overlay">` + `#entity-editor-title` / `#publish-title`。
 *  - Toast：管理页 save 失败用 `toast.error`→ElMessage(`.el-message--error`)；
 *    ProductEditPage 用自定义 `div.toast.toast-success`；KnowledgeIntake 用 `.ki-toast`。
 *  - 写操作隔离：管理页"新建"经 UI 真实创建后，按唯一名从 API 列表查 id 并 DELETE 清理。
 *
 * 运行：
 *   cd src_claude/frontend
 *   npx playwright test e2e/inventory-driven/workspace.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('../helpers/auth');
const { attachConsoleErrorCollector } = require('../helpers/console');
const { apiContext } = require('../helpers/api');

const CONSOLE_WHITELIST = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation'];

function gotoPage(page, path) {
  return page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded' });
}

// 从已登录页面的 localStorage 读取 token（用于 API 清理）。
// 注意：auth.cjs 导出的是 getToken(request,user,pass)（需要 request fixture），
// 这里直接在 page 上下文读 localStorage.token 更轻量。
async function pageGetToken(page) {
  return page.evaluate(() => localStorage.getItem('token'));
}

// 按唯一名/标题从 API 列表查出并删除（尽力清理，失败不阻断）。
async function cleanupEntity(page, ep, uniqueName) {
  const token = await pageGetToken(page);
  if (!token) return;
  const ctx = await apiContext(token);
  try {
    const resp = await ctx.get(`/${ep}/`, { params: { page_size: 500 } });
    const body = await resp.json().catch(() => ({}));
    const list = Array.isArray(body) ? body : (body?.data?.results || body?.results || []);
    for (const e of list) {
      if (e.name === uniqueName || e.title === uniqueName) {
        await ctx.delete(`/${ep}/${e.id}/`).catch(() => {});
      }
    }
  } catch (e) { /* ignore */ }
  finally { await ctx.dispose().catch(() => {}); }
}

test.describe('阶段3 Workspace 研究员穷举', () => {

  // ============ 守卫：匿名访问 /workspace → 登录页 ============
  test('Guard: 匿名 /workspace → /login?redirect=/workspace', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await gotoPage(page, '/workspace');
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    expect(page.url()).toContain('redirect=');
    expect(errors).toEqual([]);
  });

  // ============ Dashboard ============
  test('Dashboard: 统计卡片/快捷入口/知识图谱/近期表渲染', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: '+ New Product' })).toBeVisible();
    await expect(page.getByText('Knowledge Graph')).toBeVisible();
    // 近期表或空态二选一
    const recentOrEmpty = page.locator('.recent-table, .empty-state').first();
    await expect(recentOrEmpty).toBeVisible();
    expect(errors).toEqual([]);
  });

  // ============ ProductsPage ============
  test('Products: 列表渲染 + 可排序表头切换排序指示', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    const nameHeader = page.locator('th.sortable', { hasText: 'Name' });
    await nameHeader.click();
    await expect(nameHeader).toContainText(/[▲▼]/, { timeout: 5000 });
    expect(errors).toEqual([]);
  });

  test('Products: 状态过滤下拉切换（计数文案更新，无报错）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    const statusSelect = page.locator('.filter-select').first();
    await statusSelect.selectOption('active');
    await expect(page.locator('.filter-count')).toContainText(/products/, { timeout: 5000 });
    expect(errors).toEqual([]);
  });

  test('Products: 勾选行 → Batch Link 弹层打开 → 取消关闭', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    await page.locator('.products-table tbody tr').first().locator('.col-check input').check();
    await page.getByRole('button', { name: 'Batch Link' }).click();
    await expect(page.getByText(/selected products to a knowledge chain/)).toBeVisible({ timeout: 5000 });
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByText(/selected products to a knowledge chain/)).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test('Products: 操作菜单 → 下架 → 确认弹层打开 → 取消', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    // 先过滤 active，确保第一行可下架（archived 行的“下架”按钮不渲染）
    await page.locator('.filter-select').first().selectOption('active');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    await page.locator('.products-table tbody tr').first().locator('.menu-trigger').click();
    await page.getByRole('button', { name: '下架' }).click();
    await expect(page.locator('#archive-title')).toBeVisible({ timeout: 5000 });
    await page.getByRole('button', { name: '取消' }).click();
    await expect(page.locator('#archive-title')).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test('Products: 操作菜单 → 删除 → 确认弹层 + 勾选框门控删除按钮', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    await page.locator('.products-table tbody tr').first().locator('.menu-trigger').click();
    await page.getByRole('button', { name: '删除' }).click();
    await expect(page.getByText('确认删除')).toBeVisible({ timeout: 5000 });
    const deleteBtn = page.getByRole('button', { name: '永久删除' });
    await expect(deleteBtn).toBeDisabled();
    await page.locator('.confirm-check input[type="checkbox"]').check();
    await expect(deleteBtn).toBeEnabled();
    await page.getByRole('button', { name: '取消' }).click();
    await expect(page.getByText('确认删除')).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  // ============ ProductEditPage ============
  test('ProductEdit: 从列表进入编辑页 → 表单(Name/完整度条)渲染', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    await page.locator('.products-table tbody tr').first().locator('.col-name').click();
    await expect(page).toHaveURL(/\/workspace\/products\/\d+\/edit/, { timeout: 10000 });
    await expect(page.locator('.product-edit')).toBeVisible();
    await expect(page.locator('input[placeholder*="Amino-ATP"]').first()).toBeVisible();
    await expect(page.locator('.completeness-bar').first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('ProductEdit: 点击 Save Draft → 自定义 toast-success（幂等重存，不污染）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    await page.locator('.products-table tbody tr').first().locator('.col-name').click();
    await expect(page.locator('.product-edit')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Save Draft' }).click();
    await expect(page.locator('.toast-success, .toast').first()).toBeVisible({ timeout: 8000 });
    expect(errors).toEqual([]);
  });

  test('ProductEdit: 点击 Publish → 确认弹层打开（不实际发布，避免状态变更）→ 取消', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/products');
    await expect(page.locator('.products-table tbody tr').first()).toBeVisible({ timeout: 10000 });
    await page.locator('.products-table tbody tr').first().locator('.col-name').click();
    await expect(page.locator('.product-edit')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Publish' }).click();
      await expect(page.locator('#publish-title')).toBeVisible({ timeout: 5000 });
      await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.locator('#publish-title')).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  // ============ 五个知识管理页 ============
  const pages = [
    { key: 'goals', path: '/workspace/goals', ep: 'research-goals', newBtn: '+ New Goal', editorTitle: 'New Research Goal', field: 'name', fillLabel: 'Name' },
    { key: 'apps', path: '/workspace/applications', ep: 'applications', newBtn: '+ New Application', editorTitle: 'New Application', field: 'name', fillLabel: 'Name' },
    { key: 'methods', path: '/workspace/methods', ep: 'methods', newBtn: '+ New Method', editorTitle: 'New Method', field: 'name', fillLabel: 'Name' },
    { key: 'protocols', path: '/workspace/protocols', ep: 'protocols', newBtn: '+ New Protocol', editorTitle: 'New Protocol', field: 'name', fillLabel: 'Name' },
    { key: 'references', path: '/workspace/references', ep: 'references', newBtn: '+ New Reference', editorTitle: 'New Reference', field: 'title', fillLabel: 'Title' },
  ];

  for (const p of pages) {
    test(`Knowledge(${p.key}): 列表渲染 + 打开编辑器 + 空名保存 → .el-message--error`, async ({ page }) => {
      const errors = attachConsoleErrorCollector(page, { whitelist: [...CONSOLE_WHITELIST, 'Failed to load resource'] });
      const unique = `__e2e_${p.key}_${Date.now()}__`;
      await loginAsStaff(page);
      await gotoPage(page, p.path);
      await expect(page.locator('.entity-table tbody tr, .empty-state').first()).toBeVisible({ timeout: 10000 });
      await page.getByRole('button', { name: p.newBtn }).click();
      await expect(page.locator('#entity-editor-title')).toHaveText(p.editorTitle, { timeout: 5000 });
      await expect(page.locator('.dialog-overlay input.input-full').first()).toBeVisible();
      // 空名直接保存 → 后端 400 → toast.error(ElMessage)
      await page.getByRole('button', { name: 'Save' }).click();
      await expect(page.locator('.el-message--error').first()).toBeVisible({ timeout: 8000 });
      await page.getByRole('button', { name: 'Cancel' }).click();
      await expect(page.locator('#entity-editor-title')).toHaveCount(0);
      expect(errors).toEqual([]);
    });

    test(`Knowledge(${p.key}): 新建（真实写）→ 列表出现 → API 清理`, async ({ page }) => {
      const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
      const unique = `__e2e_${p.key}_${Date.now()}__`;
      await loginAsStaff(page);
      await gotoPage(page, p.path);
      await expect(page.locator('.entity-table tbody tr, .empty-state').first()).toBeVisible({ timeout: 10000 });
      await page.getByRole('button', { name: p.newBtn }).click();
      await expect(page.locator('#entity-editor-title')).toHaveText(p.editorTitle, { timeout: 5000 });
      await page.locator('.dialog-overlay input.input-full').first().fill(unique);
      await page.getByRole('button', { name: 'Save' }).click();
      // 弹层关闭 + 新行出现
      await expect(page.locator('#entity-editor-title')).toHaveCount(0, { timeout: 8000 });
      await expect(page.locator('.entity-table tbody tr', { hasText: unique }).first()).toBeVisible({ timeout: 8000 });
      await cleanupEntity(page, p.ep, unique);
      expect(errors).toEqual([]);
    });
  }

  // ============ KnowledgeIntake ============
  test('KnowledgeIntake: 产品列表渲染 → 选产品 → 表单区 + 切换 chip（不提交，避免写库）', async ({ page }) => {
    const errors = attachConsoleErrorCollector(page, { whitelist: CONSOLE_WHITELIST });
    await loginAsStaff(page);
    await gotoPage(page, '/workspace/knowledge-intake');
    await expect(page.locator('.ki-product-item').first()).toBeVisible({ timeout: 10000 });
    await page.locator('.ki-product-item').first().click();
    await expect(page.locator('.ki-form-area')).toBeVisible({ timeout: 5000 });
    const chip = page.locator('.ki-chip').first();
    await chip.click();
    await expect(chip).toHaveClass(/ki-chip-active/);
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
    expect(errors).toEqual([]);
  });
});
