const { defineConfig } = require('@playwright/test');

/**
 * ★ 生产（站点在 nginx Basic Auth 之后）所需的**第1 层**认证 —— 浏览器原生弹框那一层。
 *
 * 根因（2026-10-18 生产实测）：`https://scireagent.com/login` 返回
 *   `401 + WWW-Authenticate: Basic realm="SciReAgent Internal Test"`
 * 而本套 e2e 从未给**浏览器上下文**配 `httpCredentials` ⇒ 任何 `page.goto` 直接
 *   `net::ERR_INVALID_AUTH_CREDENTIALS`。
 * ⚠️ 这层与「应用层 Django 登录」是**两套独立口令**（见 deploy/CREDENTIALS.txt）：
 *   第 1 层 nginx Basic（弹框）→ 第 2 层 Django（登录页输入）。
 *   拿第 2 层口令填第 1 层 ⇒ 同样报 Invalid username or password。
 *   ⚠️ 因此**只设 `E2E_USER`/`E2E_PASS` 不足以跑生产**，必须同时给 `E2E_BASIC_*`。
 *
 * 本地 dev 无 nginx ⇒ 两个变量留空即可（此时不注入 httpCredentials，行为与从前一致）。
 */
const BASIC_USER = process.env.E2E_BASIC_USER || '';
const BASIC_PASS = process.env.E2E_BASIC_PASS || '';
// 仅在显式提供了第1 层凭据时注入 ⇒ 本地完全不受影响。
const httpCredentials =
  BASIC_USER && BASIC_PASS ? { username: BASIC_USER, password: BASIC_PASS } : undefined;

/**
 * 生产前置守卫：把「跑生产却漏配变量」从**跑到一半的诡异报错**变成**启动即拦**。
 *
 * 背景：`E2E_API_BASE` 若漏设，`helpers/api.cjs` 会静默回落到 `http://localhost:8000`
 * ⇒ 生产服务器上得到 `ECONNREFUSED ::1:8000`（实测，见 README「生产只读回归」）。
 * 这个回落对本地是**刻意**的，所以不能删；正确做法是「目标看起来是生产 却没配 API 地址」时**拒绝启动**。
 */
const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'

/**
 * ★ 2026-10-21：WebKit 绕开本机系统代理的办法 —— 本地「直连转发代理」。
 *
 * 背景（实测）：本机系统代理 127.0.0.1:7890（FlClash），Windows bypass 列表**已含** localhost/127.*，
 * 但 **Playwright 的 Windows WebKit 页面网络栈不遵循该 bypass** ⇒ 把 127.0.0.1:5173 的 ESM 请求
 * 交给 FlClash，拿回 404，SPA 从不挂载（#app 长度 0）。
 * 对照：同一时刻 curl / page.request → 200；WebKit 页面 → 404；**WebKit + 本代理 → #app 30329 字符、0 失败请求**。
 * ⇒ 起一个最小转发代理（`e2e/direct-proxy.cjs`，只听 127.0.0.1），让 WebKit 显式走它，不进 FlClash。
 * 好处：**用户不需要去关系统代理开关**，也不影响 Chromium/Firefox 的既有绿。
 *
 * 启用条件：本次跑批的目标里含 webkit（`--project=webkit`，或不指定 project 跑全部）。
 * 显式覆盖：E2E_DIRECT_PROXY=1 强制开 / =0 强制关。
 */
const DIRECT_PROXY_URL = process.env.E2E_DIRECT_PROXY_URL || 'http://127.0.0.1:8130'
const _projectArgs = process.argv.filter((a) => a.startsWith('--project'))
const _targetsWebkit = _projectArgs.length === 0 || _projectArgs.some((a) => a.includes('webkit'))
const USE_DIRECT_PROXY =
  process.env.E2E_DIRECT_PROXY === '0'
    ? false
    : process.env.E2E_DIRECT_PROXY === '1' || _targetsWebkit;
const API_BASE = process.env.E2E_API_BASE || '';
const isProdTarget = /scireagent\.com|^https?:\/\/(?!localhost|127\.0\.0\.1)/.test(BASE_URL);

if (isProdTarget) {
  const missing = [];
  if (!API_BASE) missing.push('E2E_API_BASE=https://scireagent.com');
  if (!BASIC_USER) missing.push('E2E_BASIC_USER=<nginx 第1层账号>');
  if (!BASIC_PASS) missing.push('E2E_BASIC_PASS=<nginx 第1层口令>');
  // 第2 层（应用层 Django 登录）也必须**显式**给：仓库里的默认值（admin/admin123 等）
  // 在生产同样有效（实测），但"默认口令能登进生产"本身就是隐患 ⇒ 生产一律要求显式注入。
  if (!process.env.E2E_USER) missing.push('E2E_USER=<应用层 staff 账号>');
  if (!process.env.E2E_PASS) missing.push('E2E_PASS=<应用层 staff 口令>');
  if (missing.length) {
    throw new Error(
      '[生产前置守卫] 目标是生产但缺少必需环境变量，已拒绝启动（避免跑到一半才报 ECONNREFUSED / ' +
        'ERR_INVALID_AUTH_CREDENTIALS 这类看不懂的错）：\n  - ' +
        missing.join('\n  - ') +
        '\n口令来源见服务器 deploy/CREDENTIALS.txt（**不在仓库内**）。本地跑请勿设置 BASE_URL。',
    );
  }
}

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

  // ★ 每次运行用**唯一**产物目录，别用固定的 `test-results`。
  //
  // 原因（2026-10-22 实测）：Playwright 每次启动会自己 `rm -rf <outputDir>`，这个删除
  // 经过本机 node 的 safe-delete 钩子；该目录累计 >50 个文件就抛
  // `SAFE_DELETE_BULK_CONFIRM_REQUIRED` ⇒ **一个用例都没跑**就以 FAIL 退出
  // （日志只有 1~9 秒、堆栈在 wrappedPromisesRm，看着像"测试挂了"，其实是环境拦截）。
  //
  // 用唯一目录后 Playwright 无需删除任何已存在的目录，问题从根上消失。
  // 代价：历史产物会累积 —— `test-artifacts/` 已进 .gitignore，定期清即可；
  // 也可用 `PW_OUTPUT` 显式指定（CI / run_all_tests.py 就是这么做的）。
  outputDir: process.env.PW_OUTPUT
    || require('path').join('test-artifacts', `${Date.now()}-${process.pid}`),
  // 跑 webkit 时自动拉起本地直连代理（Playwright 会等端口可连；已存在则复用）
  ...(USE_DIRECT_PROXY
    ? {
        webServer: [
          {
            command: 'node e2e/direct-proxy.cjs',
            port: Number(DIRECT_PROXY_URL.split(':').pop()) || 8130,
            reuseExistingServer: true,
            timeout: 20000,
            stdout: 'ignore',
            stderr: 'pipe',
          },
        ],
      }
    : {}),
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
    baseURL: BASE_URL,
    headless: true,
    viewport: { width: 1280, height: 720 },
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    // ★ 第1 层 nginx Basic（仅生产注入；本地为 undefined ⇒ 行为不变）。
    //放在全局 `use` 而非单个 spec ⇒ `@prod-ok` 用例不必各自重复 test.use({httpCredentials})。
    ...(httpCredentials ? { httpCredentials } : {}),
  },
  projects: [
    {
      name: 'chromium',
      // 2026-09-23：本机已装 Playwright bundled 浏览器（ms-playwright 下现有 firefox-1522 / webkit-2287）；
      // chromium 仍走系统已装的 Microsoft Edge（channel: 'msedge'）——它稳定可用，暂不切换成 bundled chromium。
      // 运行：npx playwright test --project=chromium
      // ★ 可用 PW_CHANNEL 环境变量覆盖；**空串可显式清空 channel** ⇒ 走自带 bundled chromium。
      //   ⚠️ 2026-10-18 实测修正：原写法 `process.env.PW_CHANNEL || 'msedge'` 让
      //      `PW_CHANNEL=''`（空串）**回落到 'msedge'**，与注释宣称的"清空 channel"**相反**
      //      （实测生产机 channel="msedge" 仍启动 Edge 155.0.4283.45）。
      //      ⇒ 改为：变量**存在**（哪怕是空串）就按其值解析；空串 ⇒ undefined ⇒ bundled chromium。
      //         不存在（未设）⇒ 保持 'msedge'（本地开发默认，行为不变）。
      use: {
        browserName: 'chromium',
        channel: 'PW_CHANNEL' in process.env
          ? (process.env.PW_CHANNEL || undefined)
          : 'msedge',
      },
    },
    // 阶段 9 启用（需先 npx playwright install firefox webkit）：
    //
    // ★ 2026-10-21 根因更正（推翻了 `e2e/GATE.md` §8.1 的旧结论）：
    //   旧文档写「`Vite dev server(5173)` + Playwright Firefox/WebKit 这条路走不通：
    //   FF 下所有模块加载报错」，并据此判定跨浏览器闸门「待投入 / 要靠 dist+preview 绕」。
    //   **实测真因不是 dev server，而是本机的系统代理**（FlClash 之类）：
    //     ├ 症状：`/@vite/client` 与 `/src/main.js` 返回 **404**、`NS_ERROR_CORRUPTED_CONTENT`，
    //     │        `#app` innerHTML 长度 = **0**（SPA 从未挂载）
    //     ├ 对照 1：同一 URL 用 `curl`（含 Firefox UA）⇒ **200 text/javascript**（服务端没问题）
    //     ├ 对照 2：Chromium（走 channel=msedge）⇒ 正常挂载（Playwright 启动时未继承系统代理）
    //     ├ 对照 3：Firefox 加 `network.proxy.type=0` ⇒ `#app` 挂载 **30329 字符、失败请求 0**
    //     └ ⇒ 请求是被**系统代理**接走后返回 404，dev server 本身完全正常。
    //   ⇒ 所以 **Firefox 只要关掉代理就能用**，无需改走 preview/dist。
    //
    // ⚠️ WebKit 另说（★ 2026-10-21 **已解决**，推翻本条原结论）：
    //   原写「WK 无法绕开系统代理、只能换环境」—— 实测过重：
    //     · `proxy: { server: 'direct://' }` 确实报 `Could not resolve proxy name`（不认该 scheme）
    //     · 但 WK 页面网络栈**不读**系统 bypass（这才是 404 的真因），
    //       而它**认** Playwright 显式传入的 `proxy`
    //   ⇒ 给它指一个本地「直连转发代理」（下方 `UseDirectProxy` 条件）即可，**无需用户关系统代理**。
    //   实测：默认 #app=0 / 13 个 404；走直连代理 #app=30329、0 失败请求。
    {
      name: 'firefox',
      use: {
        browserName: 'firefox',
        // 0 = 直接连接（不使用系统代理）。**这是 FF 能跑通的唯一关键开关**。
        // ⚠️ 必须放 `launchOptions`：`firefoxUserPrefs` **不是** TestOptions 的顶层键，
        //    写成 `use: { firefoxUserPrefs }` 会被**静默忽略**（实测：改完仍然
        //    `#app` 长度 0、`.hero-title` element not found，与未改一模一样）。
        launchOptions: {
          firefoxUserPrefs: { 'network.proxy.type': 0 },
        },
      },
    },
    {
      name: 'webkit',
      use: {
        browserName: 'webkit',
        // 仅当本次跑批含 webkit 时才注入（见文件头 USE_DIRECT_PROXY 说明）
        ...(USE_DIRECT_PROXY ? { proxy: { server: DIRECT_PROXY_URL } } : {}),
      },
    },
  ],
});
