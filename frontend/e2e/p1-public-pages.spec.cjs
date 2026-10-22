/**
 * Batch 2 / P1-1 + P1-2 —— F1-10 静态页与 404、F1-5 知识实体状态 chips
 *
 * F1-10：三份法务/介绍文案硬编码在前端组件里（改一个字就要重新构建部署），
 *   此前只测过"能加载"，没有内容断言。改造文案时不会有任何告警。
 *
 * F1-5：`MethodIndex` / `ProtocolIndex` 的状态 chips 点击后**不筛数据**
 *   （`handleFilter` 不传 status）。这里把该缺陷**锁死**：
 *   断言"点了 chip 之后没有任何带 status= 的请求"，一旦有人修好，用例会红。
 */
const { test, expect } = require('@playwright/test');
const H = require('./helpers/probeAuth.cjs');

test.describe('@p1 @local-only F1-10 静态信息页与 404', () => {
  const cases = [
    ['/about', /SciReAgent/i, 500],
    ['/privacy', /Privacy/i, 300],
    ['/terms', /Terms/i, 300],
  ];

  for (const [path, re, minLen] of cases) {
    test(`${path} 有实质内容（不是空壳）`, async ({ page }) => {
      await page.goto(`${H.BASE}${path}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1200);
      const txt = await H.bodyText(page);
      expect(txt.length, `${path} 内容过短（${txt.length}），可能是空壳或渲染失败`)
        .toBeGreaterThan(minLen);
      expect(txt, `${path} 缺少期望关键词`).toMatch(re);
      // 不应被踢到登录页
      expect(page.url()).toContain(path);
    });
  }

  test('未匹配路径落到 404 页（不是白屏）', async ({ page }) => {
    await page.goto(`${H.BASE}/this-path-does-not-exist-probe`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    const txt = await H.bodyText(page);
    expect(txt.length, '404 页白屏').toBeGreaterThan(80);
    expect(txt, '404 页没有提示文案').toMatch(/404|not found|页面.*不存在/i);
  });
});

test.describe('@p1 @local-only F1-5 状态 chips 不筛数据（缺陷锁定）', () => {
  for (const [name, path, api] of [
    ['Methods', '/methods', '/api/v1/methods/'],
    ['Protocols', '/protocols', '/api/v1/protocols/'],
  ]) {
    test(`★ ${name} 点状态 chip 不会带 status 参数（当前缺陷）`, async ({ page }) => {
      const reqs = [];
      page.on('request', (r) => {
        if (r.url().includes(api)) reqs.push(r.url());
      });

      await page.goto(`${H.BASE}${path}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);
      const before = reqs.length;

      // 点"非默认"的状态 chip（Draft / Published / Superseded 之类）
      const chip = page.getByRole('button', { name: /^(Draft|Published|Superseded)$/i }).first();
      if (!(await chip.count())) test.skip(true, '找不到状态 chip（UI 可能改版）');
      await chip.click();
      await page.waitForTimeout(1800);

      const added = reqs.slice(before);
      for (const u of added) {
        expect(
          /[?&]status=/.test(u),
          `★ chip 开始真正筛数据了（请求带 status）：${u}\n` +
            '若这是修复，请更新说明书 §11.2 #12 与 flow_coverage_matrix 的 F1-5',
        ).toBe(false);
      }
    });
  }
});
