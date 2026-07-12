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
      use: { browserName: 'chromium' },
    },
    // 阶段 9 启用（需先 npx playwright install firefox webkit）：
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
  ],
});
