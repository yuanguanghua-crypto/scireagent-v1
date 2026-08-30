/**
 * AppLayout 72px 顶部留白视觉确认（P2 遗留 3）
 *
 * 背景：Step 3 顺手修复 — needsNavPad = isPublicPage() && path !== '/'
 * 统一为所有非 home public 页面加 padding-top:72px，防止 fixed PublicNav 遮挡内容。
 * 本次确认：①非 home public 页 .app-layout 带 public-nav-pad 且 padding-top=72px、
 *           ②home（/）不带 pad、③首屏顶部首个内容元素不被 PublicNav 遮挡。
 *
 * 运行（静态托管 dist，无需后端）：
 *   cd src_claude/frontend
 *   python -m http.server 8123 -d dist   （或任意静态服务器）
 *   BASE_URL=http://localhost:8123 npx playwright test e2e/applayout-navpad-check.spec.cjs --project=chromium
 */
const { test, expect } = require('@playwright/test');

const PUBLIC_NON_HOME = ['/applications', '/methods', '/products', '/about', '/search'];
const EXPECTED_PAD = 72;

test('非 home public 页：public-nav-pad 生效且 padding-top=72px，内容不被遮挡', async ({ page }) => {
  for (const path of PUBLIC_NON_HOME) {
    await page.goto(path);
    await page.waitForSelector('.app-layout');
    const probe = await page.evaluate(() => {
      const layout = document.querySelector('.app-layout');
      const content = document.querySelector('.app-layout .content-area');
      if (!layout || !content) return { ok: false, reason: 'no .app-layout/.content-area' };
      const cls = layout.classList.contains('public-nav-pad');
      const padTop = parseFloat(getComputedStyle(content).paddingTop); // 72px 加在 content-area 上
      // 找 content-area 内首个高度>0 的可视直接子元素（跳过 fixed PublicNav）
      const contentEls = content.children;
      let firstContent = null;
      for (const el of contentEls) {
        const r = el.getBoundingClientRect();
        if (r.height > 8 && r.width > 50) { firstContent = { y: Math.round(r.top), tag: el.tagName, cls: (el.className || '').toString().slice(0, 60) }; break; }
      }
      // 候选诊断：列出前 5 个满足条件的元素
      const diag = [];
      for (const el of document.querySelectorAll('.app-layout *')) {
        const r = el.getBoundingClientRect();
        if (r.height > 8 && r.width > 50) {
          diag.push({ y: Math.round(r.top), tag: el.tagName, cls: (el.className || '').toString().slice(0, 30) });
          if (diag.length >= 5) break;
        }
      }
      return { ok: cls && padTop === 72, cls, padTop, firstContent, diag };
    });
    expect(probe.ok, `${path}: public-nav-pad=${probe.cls} padTop=${probe.padTop}px (期望 72px)`).toBeTruthy();
    // 首个内容元素顶部应 ≥ 60px（72px padding 之下，不被 68px 高 fixed 导航遮挡）
    console.log(`${path} 诊断:`, JSON.stringify(probe.diag));
    expect(probe.firstContent?.y, `${path}: 首个内容元素 y=${probe.firstContent?.y}（应 ≥60）`).toBeGreaterThanOrEqual(60);
  }
});

test('home（/）：不带 public-nav-pad，无多余留白', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('.app-layout');
  const padTop = await page.evaluate(() => {
    const layout = document.querySelector('.app-layout');
    return {
      hasPad: layout.classList.contains('public-nav-pad'),
      padTop: parseFloat(getComputedStyle(layout).paddingTop),
    };
  });
  expect(padTop.hasPad).toBeFalsy();
  expect(padTop.padTop).toBeLessThan(40); // home 不引入 72px 大留白
});

test('页面无 console error / pageerror（防回归白屏）', async ({ page }) => {
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('/applications');
  await page.waitForSelector('.app-layout');
  // 静态托管无后端时 API 会 500/404（环境噪音，非页面 bug）——仅断言非网络类错误
  expect(errors.filter((e) => !e.includes('Failed to load resource') && !e.includes('AxiosError'))).toEqual([]);
});
