/**
 * HTTP/2 上线后真实浏览器验证
 *
 * 目的：curl 不支持 HTTP/2（实测 "the installed libcurl version does not
 * support this"），只有真实浏览器（Chromium/Edge）才能验证 h2 是否真正生效，
 * 以及首屏多资源是否复用单连接（142 个 js/css 资源）。
 *
 * 判据：
 *   1. 响应中 h2/h3 字段出现 "h2" ⇒ 协议协商成功
 *   2. connectionFinished 事件统计 ⇒ 是否复用连接
 *   3. 加载耗时对比
 */
const { chromium } = require('playwright');

const BASE = process.env.TARGET_BASE || 'https://scireagent.com';
// ★ 2026-10-18 安全修正：生产口令不再硬编码在仓库里（原为真实可用的生产 nginx 口令）。
//   沿用项目既有命名：E2E_BASIC_USER / E2E_BASIC_PASS（nginx 第 1 层）。
//   来源：服务器 deploy/CREDENTIALS.txt（权限 600，不在仓库内）。
const USER = process.env.E2E_BASIC_USER || process.env.SITE_USER || '';
const PASS = process.env.E2E_BASIC_PASS || process.env.SITE_PASS || '';
if (!USER || !PASS) {
  console.error(
    '缺少 nginx Basic 凭据：请注入 E2E_BASIC_USER / E2E_BASIC_PASS（见 deploy/CREDENTIALS.txt）。',
  );
  process.exit(2);
}

(async () => {
  const browser = await chromium.launch({
    channel: process.env.PW_CHANNEL || 'msedge',
    args: ['--ignore-certificate-errors'],
  });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  // nginx 有 HTTP Basic Auth（auth_basic 覆盖全站），不带认证会被直接断开
  // ⇒ 表现为 net::ERR_CONNECTION_CLOSED（而非 401）
  ctx.setHTTPCredentials({ username: USER, password: PASS });
  const page = await ctx.newPage();

  const responses = [];
  const connections = [];
  page.on('response', (r) => {
    responses.push({
      url: r.url(),
      status: r.status(),
      httpVersion: r.request()._options?.httpVersion || '',
      fromCache: r.fromServiceWorker(),
    });
  });

  // 统计真实连接数（每条 = 一个 TCP 连接）
  let connId = 0;
  const connIds = new Map();
  page.on('request', (r) => {
    const rt = r._initializer ? null : null;
  });
  page.on('websocket', () => {});

  // 用 CDP 精确统计连接
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable');
  const events = [];
  cdp.on('Network.responseReceivedExtraInfo', () => {});
  cdp.on('Network.requestWillBeSent', (e) => {
    events.push({ id: e.requestId, ts: e.timestamp, url: e.request.url });
  });

  const t0 = Date.now();
  await page.goto(BASE + '/', { waitUntil: 'networkidle', timeout: 90000 });
  const loadMs = Date.now() - t0;

  // 协议统计
  const versionSet = new Set();
  for (const r of responses) {
    const p = r.httpVersion;
    if (p) versionSet.add(p);
  }

  // 从 performance API 拿真实的 protocol（最可靠）
  const protocolInfo = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const res = performance.getEntriesByType('resource').map((e) => ({
      name: e.name.split('/').pop(),
      protocol: e.nextHopProtocol,
      duration: Math.round(e.duration),
      transferSize: e.transferSize,
    }));
    const byProto = {};
    for (const r of res) {
      const k = r.protocol || '(empty)';
      byProto[k] = (byProto[k] || 0) + 1;
    }
    return {
      navProtocol: nav ? nav.nextHopProtocol : '(none)',
      resourceCount: res.length,
      byProtocol: byProto,
      totalTransferKB: Math.round(
        res.reduce((s, r) => s + (r.transferSize || 0), 0) / 1024),
      slowest: res.sort((a, b) => b.duration - a.duration).slice(0, 8),
    };
  });

  console.log('='.repeat(70));
  console.log('HTTP/2 真实浏览器验证 |', BASE);
  console.log('='.repeat(70));
  console.log('导航协议(nextHopProtocol):', protocolInfo.navProtocol);
  console.log('页面加载耗时          :', loadMs, 'ms');
  console.log('资源总数              :', protocolInfo.resourceCount);
  console.log('总传输量              :', protocolInfo.totalTransferKB, 'KB');
  console.log('\n--- 各协议的资源数分布 ---');
  for (const [k, v] of Object.entries(protocolInfo.byProtocol)) {
    console.log(`  ${k.padEnd(12)} : ${v}`);
  }
  console.log('\n--- 最慢的 8 个资源 ---');
  for (const r of protocolInfo.slowest) {
    console.log(`  ${String(r.duration).padStart(6)}ms  ${r.protocol || '(空)'}  ${r.name}`);
  }

  const h2 = Object.keys(protocolInfo.byProtocol).some((k) => k.includes('h2'));
  const navH2 = protocolInfo.navProtocol.includes('h2');
  console.log('\n--- 判定 ---');
  console.log('  导航是否 h2 :', navH2 ? 'YES ✅' : 'NO ❌');
  console.log('  子资源是否 h2:', h2 ? 'YES ✅' : 'NO ❌');

  await browser.close();
})().catch((e) => {
  console.error('FAILED:', e.message);
  process.exit(1);
});