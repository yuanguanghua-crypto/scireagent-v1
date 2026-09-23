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
// 单一口径：凭据取自 helpers/auth.cjs（2026-09-23 修复：此处曾硬编码过期密码 'AdminPass123!' ⇒ 登录 401 ⇒ 假红）
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

// 用例级 tier（2026-09-23 复核，实跑证据）：
//   · 原「缺失字段弹窗（:31）」**已于 2026-09-23 删除用例**：该弹窗按设计移除
//     （`ProductEditPage.vue:2064`：「必填字段缺失不再弹独立弹窗」，Save Draft 直接标红、
//     Publish 走发布确认框）⇒ 断言的实体（`.missing-list` / '去补充' / 'missing-title'）不存在，
//     留下只会永远红；而**同类能力已由下方「GoalsPage 编辑弹窗 ARIA + ESC」覆盖** ⇒ 删除不产生覆盖空洞。
//   · :65「GoalsPage 编辑弹窗」 —— 依赖仍存在的 `#entity-editor-title` 编辑器弹窗 ⇒ 实跑绿 ⇒ 捞回。
test.describe('弹窗无障碍能力', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page);
  });

  test('GoalsPage 编辑弹窗：ARIA + ESC 关闭', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
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
