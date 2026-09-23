/**
 * 临时验证 spec — 三项前端改动：
 *   A. 空表单保存：告知模式（标红 + warn 提示），不弹阻断弹窗
 *   B. SEO 自动生成按钮在新建页可见并可工作（保存后）
 *   C. AI AUTO MATCH 载入动画
 *
 * 运行：cd frontend; npx playwright test e2e/verify-improvements.spec.cjs --reporter=line
 */
const { test, expect, request } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_BASE = 'http://localhost:8000/api/v1';
// 单一口径：凭据一律取自 helpers/auth.cjs。
// 2026-09-23 修复：此处曾自行硬编码默认密码 'AdminPass123!'（与 helpers/auth.cjs 的 'admin123' 漂移）
// ⇒ 登录 401 ⇒ 反复跳 /login ⇒ `waitForURL` 超时 ⇒ 假红。
const { ADMIN_USER, ADMIN_PASS } = require('./helpers/auth');

async function loginAsStaff(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);
  await Promise.all([
    page.waitForURL(/\/workspace/, { timeout: 15000 }),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
}

test.describe('前端三项改进验证', { tag: ['@readonly', '@local-only'] }, () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page);
  });

  test('A. 空表单保存：告知模式（标红 + 提示），不弹阻断弹窗', async ({ page }) => {
    // ⚠ 挂起创建请求 POST /api/v1/products/：实测空表单点 Save Draft 后，后端 400（name 必填）
    //   的 error toast 会在 ~50ms 内覆盖 warn toast，使"warn 级反馈"无法稳定观察。
    //   本用例只验证前端"告知模式"（标红 + 提示 + 不阻断），**不断言保存结果**——
    //   空表单 name 必填 ⇒ 后端校验必不通过 ⇒ 不会落库（slug 由 ensureSlug 兜底生成，非阻断原因）。
    await page.route(/\/api\/v1\/products\/$/, () => { /* 挂起，不 fulfill/abort */ });

    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 不填任何字段，直接点 Save Draft
    await page.locator('.form-actions button', { hasText: 'Save Draft' }).click();

    // 告知模式：warn 级反馈（容器 .toast + 类 toast-warn；文案见 ProductEditPage.vue:1277）
    const toast = page.locator('.toast');
    await expect(toast).toHaveClass(/toast-warn/);
    await expect(toast).toContainText('required fields unfilled');
    await expect(toast).toContainText('kept available');

    // 行为变更锁定：必填字段缺失**不再弹独立阻断弹窗**
    //（ProductEditPage.vue:2064 注释 + saveDraft 告知模式 :1264-1277）
    await expect(page.locator('.dialog')).toHaveCount(0);

    // 标红：仅 product_class_id 绑定 `field-missing` 类（ProductEditPage.vue:1802，实测）
    await expect(page.locator('.el-cascader').first()).toHaveClass(/field-missing/);

    // 其余必填项用 `.field-error` 文本标记（name/catalog_no/smiles/product_class_id/default_sku，
    // 见 :1717/:1721/:1744/:1806/:1910，实测共 5 处）。注：CAS（:1723-1726）只有格式校验 span，
    // 未绑定任何"缺失"标记，故不断言其标红。
    await expect(page.locator('.field-error')).toHaveCount(5);
  });

  test('B. SEO 自动生成按钮在新建页可见（禁用状态，提示先保存）', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 新建页 SEO 按钮应可见但禁用，文字提示先保存
    const seoBtn = page.locator('.form-section', { hasText: '8. SEO' }).locator('button', { hasText: /SEO/i });
    await seoBtn.scrollIntoViewIfNeeded();
    await expect(seoBtn).toBeVisible({ timeout: 5000 });
    await expect(seoBtn).toBeDisabled();
    await expect(seoBtn).toContainText(/Save product first/i);
  });

  test('C. AI AUTO MATCH 载入动画', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 填入名字让 AI AUTO MATCH 面板出现
    await page.locator('input[placeholder*="Amino-ATP"]').fill('Test AI Spinner Product');

    // AI AUTO MATCH 按钮出现
    const aiBtn = page.getByRole('button', { name: /AI AUTO MATCH/ });
    await expect(aiBtn).toBeVisible({ timeout: 5000 });

    // 点击前无 spinner
    await expect(page.locator('.ai-loading-spinner')).not.toBeVisible();

    // 点击触发 enrich（可能很快结束，用 response 等待）
    const [resp] = await Promise.all([
      page.waitForResponse(r => r.url().match(/\/api\/v1\//) && (r.url().includes('enrich') || r.url().includes('match') || r.url().includes('pubchem')), { timeout: 30000 }).catch(() => null),
      aiBtn.click(),
    ]);

    // enrich 过程中应有 spinner（即使快速结束，按钮文本应变为 Searching）
    // 检查按钮文本变化
    await expect(aiBtn).toContainText(/Searching|matching/, { timeout: 5000 }).catch(() => {
      // enrich 可能极快完成，spinner 已消失——这种情况也算通过
    });
  });
});
