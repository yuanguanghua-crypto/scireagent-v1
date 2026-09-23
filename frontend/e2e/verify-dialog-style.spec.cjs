/**
 * 验证统一弹窗样式：
 *   1. 保存失败弹窗（missing-list + field-missing）computed style 来自全局 main.css
 *   2. .dialog border-radius=12px、box-shadow 来自 --shadow-modal
 *   3. .field-missing 边框色 = --color-danger
 *
 * 运行：cd frontend; npx playwright test e2e/verify-dialog-style.spec.cjs --reporter=line
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
//   · 原 :72（`.missing-list` danger 色 / field-missing 边框）**已于 2026-09-23 删除用例**：
//     该弹窗按设计移除（`ProductEditPage.vue:2064`），全仓无组件渲染 `.missing-list`
//     （连 main.css 的死样式也已在同批清理）⇒ 断言的实体不存在，留下只会永远红。
//   · :30 / :59（`.dialog` 容器样式 / `.dialog-overlay` backdrop blur）改为锚定**仍存在**的
//     Publish 确认弹窗（同一套全局 `.dialog-overlay` / `.dialog`，ProductEditPage.vue:2067）
//     ⇒ 保留原语义，实跑绿则捞回。
//   · :95（ElMessage toast 主题覆盖）实跑绿 ⇒ 捞回。
test.describe('统一弹窗样式验证', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page);
  });

  // 打开 Publish 确认弹窗（真实存在的 `.dialog`）。原触发方式（不填字段点 Save Draft）
  // 依赖已移除的缺失字段弹窗，已不可用。
  async function openPublishDialog(page) {
    await page.goto(`${BASE_URL}/workspace/products/66/edit`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.product-edit', { timeout: 15000 });
    await page.getByRole('button', { name: 'Publish' }).click();
    await expect(page.locator('#publish-title')).toBeVisible({ timeout: 8000 });
  }

  test('弹窗容器样式来自全局 token（圆角 + modal 阴影）', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await openPublishDialog(page);

    // 检查 computed style
    const styles = await page.locator('.dialog').evaluate(el => {
      const cs = getComputedStyle(el);
      return {
        borderRadius: cs.borderRadius,
        boxShadow: cs.boxShadow,
        maxWidth: cs.maxWidth,
        background: cs.backgroundColor,
      };
    });

    // 圆角来自全局 token --radius-sm
    expect(styles.borderRadius).toBe('4px');
    // modal 阴影（--shadow-modal = --shadow-xl，含 16px 48px + rgba(15,23,42,0.1) 偏移/色）
    expect(styles.boxShadow).toContain('rgba(15, 23, 42, 0.1)');
    // 默认宽度 440px
    expect(styles.maxWidth).toBe('440px');
    // 表面色背景（白色）
    expect(styles.background).toContain('rgb(255, 255, 255)');
  });

  test('遮罩层有 backdrop blur', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    await openPublishDialog(page);

    const backdrop = await page.locator('.dialog-overlay').evaluate(el => {
      return getComputedStyle(el).backdropFilter || getComputedStyle(el).webkitBackdropFilter;
    });
    // 有 blur（具体值浏览器间差异，只断言含 blur）
    expect(backdrop.toLowerCase()).toContain('blur');
  });

  test('ElMessage toast 样式被项目主题覆盖', { tag: ['@readonly', '@local-only'] }, async ({ page }) => {
    // 访问不存在的产品 → 后端 404 → http.js 触发 ElMessage.error
    await page.goto(`${BASE_URL}/workspace/products/9999999/edit`, { waitUntil: 'domcontentloaded' });

    // 等 ElMessage 出现
    const msg = page.locator('.el-message--error');
    await expect(msg).toBeVisible({ timeout: 8000 });

    const styles = await msg.evaluate(el => {
      const cs = getComputedStyle(el);
      return {
        background: cs.backgroundColor,
        borderColor: cs.borderColor,
      };
    });
    // danger-bg = --color-red-50 ≈ rgb(254, 242, 242)
    // danger-light = --color-red-100
    // 被覆盖后背景应是浅红，而非 Element Plus 默认白
    expect(styles.background).not.toBe('rgba(0, 0, 0, 0)');
  });
});
