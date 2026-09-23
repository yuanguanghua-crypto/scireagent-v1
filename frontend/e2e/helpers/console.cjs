/**
 * Console / PageError 错误雷达
 * 每 spec 在 beforeEach 挂上收集器，afterEach 断言数组为空。
 * 这是白屏 / 运行时异常的早期雷达 —— 任何未捕获异常都会在冒烟阶段暴露。
 *
 * 用法：
 *   const { attachConsoleErrorCollector } = require('./helpers/console');
 *   const errors = attachConsoleErrorCollector(page);
 *   // ... 测试 ...
 *   expect(errors).toEqual([]);
 */

/**
 * 外部字体 CDN 中和器（2026-09-23 新增）
 *
 * 根因（已实测，3/3 稳定复现）：应用 CSS 引用了 Google Fonts，而**本机无外网**
 * ⇒ `fonts.gstatic.com` 的 .woff2 请求以 `net::ERR_CONNECTION_CLOSED` 失败
 * ⇒ 浏览器打出一条**不带 URL 的** console error
 *    `Failed to load resource: net::ERR_CONNECTION_CLOSED`
 * ⇒ 被本收集器捕获 ⇒ `expect(errors).toEqual([])` 随机失败（失败条数 2/3/4/5 波动）。
 *
 * 处置：**不**放宽消息白名单（那会把真正的网络/资源失败一并掩盖），而是把这两个
 * 外部域名在测试期**直接以空 200 应答** ⇒ 浏览器不再产生任何错误，CSS 落回系统字体。
 * 这是**加法式**修复：不改变任何断言语义，只消除环境噪声。
 */
const EXTERNAL_FONT_RE = /^https:\/\/fonts\.(googleapis|gstatic)\.com\//
function stubExternalFonts(page) {
  try {
    return page.route(EXTERNAL_FONT_RE, (route) =>
      route.fulfill({ status: 200, contentType: 'text/css', body: '' }))
  } catch (e) {
    return Promise.resolve()
  }
}

function attachConsoleErrorCollector(page, { whitelist = [] } = {}) {
  stubExternalFonts(page)
  const errors = []
  const onConsole = (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text()
      if (!whitelist.some((w) => text.includes(w))) errors.push(text)
    }
  }
  const onPageError = (err) => errors.push(`PAGEERROR: ${err.message}`)
  page.on('console', onConsole)
  page.on('pageerror', onPageError)
  return errors
}

module.exports = { attachConsoleErrorCollector, stubExternalFonts }
