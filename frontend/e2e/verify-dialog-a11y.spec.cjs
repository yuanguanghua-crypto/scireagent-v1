/**
 * 验证弹窗无障碍能力（useDialogA11y 接入）：
 *   1. 打开弹窗时 .dialog-overlay 带 role="dialog" aria-modal="true" aria-labelledby
 *   2. 打开时焦点进入弹窗内首个可聚焦元素
 *   3. 按 ESC 关闭弹窗
 *   4. .missing-list 带 role="alert"
 *
 * 运行：cd frontend; npx playwright test e2e/verify-dialog-a11y.spec.cjs --reporter=line
 */
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const ADMIN_USER = process.env.E2E_USER || 'admin';
const ADMIN_PASS = process.env.E2E_PASS || 'AdminPass123!';

async function loginAsStaff(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);
  await Promise.all([
    page.waitForURL(/\/workspace/, { timeout: 15000 }),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
}

test.describe('弹窗无障碍能力', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page);
  });

  test('缺失字段弹窗：ARIA 属性 + role=alert + ESC 关闭 + focus 管理', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 记录触发按钮为当前焦点
    const saveBtn = page.locator('.form-actions button', { hasText: 'Save Draft' });
    await saveBtn.focus();
    await expect(saveBtn).toBeFocused();

    // 触发弹窗
    await saveBtn.click();
    await expect(page.locator('.dialog-overlay')).toBeVisible({ timeout: 5000 });

    // 1. ARIA 属性
    const overlay = page.locator('.dialog-overlay');
    await expect(overlay).toHaveAttribute('role', 'dialog');
    await expect(overlay).toHaveAttribute('aria-modal', 'true');
    await expect(overlay).toHaveAttribute('aria-labelledby', 'missing-title');

    // 2. focus 进入弹窗内（"去补充" 按钮是弹窗内唯一可聚焦元素）
    const confirmBtn = page.locator('.dialog-actions button', { hasText: '去补充' });
    await expect(confirmBtn).toBeFocused({ timeout: 3000 });

    // 3. .missing-list 带 role=alert
    await expect(page.locator('.missing-list')).toHaveAttribute('role', 'alert');

    // 4. ESC 关闭
    await page.keyboard.press('Escape');
    await expect(page.locator('.dialog-overlay')).toHaveCount(0);

    // 5. 焦点恢复到触发按钮
    await expect(saveBtn).toBeFocused({ timeout: 3000 });
  });

  test('GoalsPage 编辑弹窗：ARIA + ESC 关闭', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/goals`, { waitUntil: 'domcontentloaded' });
    // 等表格或空文本加载
    await page.waitForSelector('.entity-page', { timeout: 10000 });

    // 打开 New 弹窗
    await page.getByRole('button', { name: '+ New Goal' }).click();
    await expect(page.locator('.dialog-overlay')).toBeVisible({ timeout: 5000 });

    const overlay = page.locator('.dialog-overlay');
    await expect(overlay).toHaveAttribute('role', 'dialog');
    await expect(overlay).toHaveAttribute('aria-modal', 'true');
    await expect(overlay).toHaveAttribute('aria-labelledby', 'entity-editor-title');

    // ESC 关闭
    await page.keyboard.press('Escape');
    await expect(page.locator('.dialog-overlay')).toHaveCount(0);
  });
});
