// Feasibility probe: launch chromium headless, load the app, print title, close.
const { chromium } = require('playwright')

;(async () => {
  const browser = await chromium.launch()
  const page = await browser.newPage()
  await page.goto('http://localhost:5173/')
  console.log('TITLE:', await page.title())
  await browser.close()
  console.log('PROBE_OK')
})().catch((e) => {
  console.error('PROBE_FAILED:', e.message)
  process.exit(1)
})
