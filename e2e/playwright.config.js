// Playwright config for SciReAgent E2E walkthrough.
// Dev server is assumed already running at http://localhost:5173 (Vite, IPv6 ::1).
// We do NOT start/stop it here (no webServer) to avoid touching the running app.
const { defineConfig } = require('@playwright/test')

module.exports = defineConfig({
  testDir: './tests',
  timeout: 90000,
  expect: { timeout: 20000 },
  // Absorb transient Chromium-on-Windows worker crashes (STATUS_ACCESS_VIOLATION
  // 0xC0000005) so an infra flake never masks a real result. A genuine failure
  // (e.g. the gap③ backend source bug) still fails on every retry.
  retries: 2,
  fullyParallel: false,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'test-results.json' }],
  ],
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    actionTimeout: 12000,
    // Hardening for sandboxed / container Chromium:
    // - --no-sandbox / --disable-setuid-sandbox: avoid permission denials
    // - --disable-dev-shm-usage: avoid "/dev/shm too small" crashes that
    //   surface as "Target page, context or browser has been closed"
    // - --disable-gpu: avoid GPU-process access-violation crashes on Windows
    launchOptions: {
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    },
  },
})
