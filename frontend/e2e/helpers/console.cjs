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
function attachConsoleErrorCollector(page, { whitelist = [] } = {}) {
  const errors = [];
  const onConsole = (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (!whitelist.some((w) => text.includes(w))) errors.push(text);
    }
  };
  const onPageError = (err) => errors.push(`PAGEERROR: ${err.message}`);
  page.on('console', onConsole);
  page.on('pageerror', onPageError);
  return errors;
}

module.exports = { attachConsoleErrorCollector };
