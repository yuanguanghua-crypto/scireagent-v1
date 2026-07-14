/**
 * TDD E2E — 问题1：产品详情页应优先显示 Word 提取的结构图（structure_image），
 * 而非用 SMILES 渲染的图。
 *
 * 前置：
 *  - 部署后的站点可访问（BASE_URL，默认 https://scireagent.com）
 *  - 目标产品已发布且库中有 structure_image（PRODUCT_SLUG 指定）
 *
 * 验证：详情页 .pd-structure-box 内出现 img.pd-structure-img，
 *       其 src 以 data:image 开头（即 Word 提取的 PNG，而非 SMILES 渲染）。
 */
const { test, expect } = require('@playwright/test');

const SLUG = process.env.PRODUCT_SLUG || '5-propargylamino-ctp';

test.describe('Product detail shows Word structure_image (priority over SMILES)', () => {
  test('structure box renders img.pd-structure-img with data URI', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

    await page.goto(`/products/${SLUG}`, { waitUntil: 'networkidle' });

    const box = page.locator('.pd-structure-box');
    await expect(box).toBeVisible({ timeout: 15000 });

    // 关键断言：不应只显示 SMILES 文本占位，而应出现 Word 结构图 <img>
    const img = box.locator('img.pd-structure-img');
    await expect(img).toBeVisible({ timeout: 15000 });

    const src = await img.getAttribute('src');
    expect(src, 'structure_image 必须是 data:image/... PNG').toMatch(/^data:image\//);

    // 不应出现“No structure”占位（结构图已显示）
    await expect(box.locator('.pd-svg-placeholder:has-text("No structure")')).toHaveCount(0);

    // 无运行时 JS 错误
    expect(errors, `页面存在 JS 错误: ${errors.join(' | ')}`).toHaveLength(0);
  });
});
