const { defineConfig } = require('@playwright/test');

/**
 * SciReAgent 前端 E2E 配置
 *
 * 运行前提：后端 :8000 + 前端 :5173 已启动。
 *
 * 浏览器策略：
 *  - 当前环境仅安装 Chromium（ms-playwright 缓存仅有 chromium-*）。
 *  - 跨浏览器（firefox / webkit）项目在【阶段 9】启用，需先
 *    `npx playwright install firefox webkit`（沙箱外/CI 执行）。
 *  - 阶段 0 仅 chromium，保证默认 `npx playwright test` 可跑绿。
 *
 * 视口：默认桌面 1280×720；响应式专项（阶段 8）用 test.use({ viewport }) 覆盖。
 */
module.exports = defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.cjs',
  timeout: 45000,
  expect: { timeout: 10000 },
  retries: 1,
  // ★ 必须串行（2026-09-22 实测教训）：本套 spec 共用**同一个本地 dev 库**，
  //   而大量用例用 `snapshotDb()` 做「表计数 Δ」断言（只读零写入 / 审计 Δ+1 / Δ0）。
  //   默认并行 workers 会让 A 用例的夹具增删落进 B 用例的 before/after 窗口
  //   ⇒ 假失败（实测：单跑 14+6 全过，并行跑出现 Δ+1 / Δ-1 / Δ+2）。
  //   ⇒ 任何依赖 DB 快照 Δ 的断言都要求串行；此处统一锁死为 1 worker。
  workers: 1,
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    headless: true,
    viewport: { width: 1280, height: 720 },
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      // 2026-09-23：本机已装 Playwright bundled 浏览器（ms-playwright 下现有 firefox-1522 / webkit-2287）；
      // chromium 仍走系统已装的 Microsoft Edge（channel: 'msedge'）——它稳定可用，暂不切换成 bundled chromium。
      // 运行：npx playwright test --project=chromium
      use: { browserName: 'chromium', channel: 'msedge' },
    },
    // 阶段 9 启用（需先 npx playwright install firefox webkit）：
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
  ],
});
