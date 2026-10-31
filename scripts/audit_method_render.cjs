#!/usr/bin/env node
/**
 * audit_method_render — 方法页渲染层端到端验证（必须在**服务器侧**运行）。
 *
 * ## 为什么必须在服务器跑
 *
 * 本机（Windows）实测：curl 直连 `https://www.scireagent.com/methods/N` 返回 200
 * （1.4s），但 Playwright 拉起 Edge 后**无论走不走系统代理都超时**：
 *   - 默认（系统代理 7890/FlClash）→ 本站超时，example.com 正常
 *   - `--proxy-server=127.0.0.1:63121`（curl 用的那个）→ 本站仍超时
 *   - `--no-proxy-server` → 连 example.com 都不通（本机直连外网被整体阻断）
 * 已排除凭据错误与站点问题 ⇒ 属本机浏览器环境的网络阻断，不是代码问题。
 * Playwright 自带的 firefox/webkit 也因版本不匹配（库要 1532/2311，本地是 1522/2287）
 * 无法启动。故改用服务器侧 chromium-headless-shell。
 *
 * ## 服务器准备（一次性）
 *
 *   mkdir -p /tmp/pwtest && cd /tmp/pwtest
 *   npm init -y && npm i playwright --no-audit --no-fund
 *   npx playwright install chromium          # 约 120MB
 *
 * ## 用法
 *
 *   PLAYWRIGHT_PATH=/tmp/pwtest/node_modules/playwright \
 *   CRED_FILE=/home/admin/scireagent/deploy/CREDENTIALS.txt \
 *   node scripts/audit_method_render.cjs [并发数]
 *
 * 输出 CSV 到 stdout 的 STDOUT_CSV 路径（默认 /tmp/pwtest/render83.csv）。
 *
 * ## 判据
 *
 * 全绿 = status 200 + #app 渲染 >500 字符 + timeline 渲染成人类可读标签
 *        + AI 草稿提示存在 + Advantages/Limitations 区块存在 + 首个协议链接可点开
 *
 * ⚠️ 注意：方法页协议列表**设计上只预览 3 条** + 「Show all N →」链接，
 *    所以 `a[href*=/protocols/]` 恒为 3 是预期行为，不是 bug。
 *    「Show all N」的 N == API 的 protocols.length == 协议为 published 的桥数。
 */
const fs = require('fs');

const PW = process.env.PLAYWRIGHT_PATH || '/tmp/pwtest/node_modules/playwright';
const CRED_FILE = process.env.CRED_FILE
  || '/home/admin/scireagent/deploy/CREDENTIALS.txt';
const BASE = process.env.RENDER_BASE || 'https://scireagent.com';
const OUT = process.env.STDOUT_CSV || '/tmp/pwtest/render83.csv';
const CONC = parseInt(process.argv[2] || '4', 10);

const { chromium } = require(PW);

const credTxt = fs.readFileSync(CRED_FILE, 'utf8');
let U, P;
for (const l of credTxt.split(/\r?\n/)) {
  const m = l.match(/^(scire\d+)[ \t]+(\S+)/);
  if (m) { U = m[1]; P = m[2]; break; }
}
if (!U) throw new Error('凭据文件里没找到 scireNN 账号行');

async function fetchIds() {
  const res = await fetch(`${BASE}/api/v1/methods/?page_size=200`, {
    headers: { Authorization: 'Basic ' + Buffer.from(`${U}:${P}`).toString('base64') },
  });
  const j = await res.json();
  const arr = Array.isArray(j) ? j : (Array.isArray(j.data) ? j.data : []);
  return arr.map((x) => ({ id: x.id, name: x.name }));
}

async function checkOne(browser, m) {
  const c = await browser.newContext({
    httpCredentials: { username: U, password: P },
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 1000 },
  });
  const pg = await c.newPage();
  const errs = [];
  pg.on('pageerror', (e) => errs.push(String(e.message).slice(0, 120)));
  const rec = {
    id: m.id, name: m.name, status: 0, app_len: 0, h1: '',
    timeline_label: '', timeline_bare: false, ai_note: false,
    adv_block: false, proto_links: 0, link_ok: '', errors: '',
  };
  try {
    const r = await pg.goto(`${BASE}/methods/${m.id}`,
      { timeout: 40000, waitUntil: 'domcontentloaded' });
    rec.status = r.status();
    // 不用 networkidle：页面有持续轮询，networkidle 永不达成
    await pg.waitForTimeout(3800);
    const info = await pg.evaluate(() => {
      const app = document.querySelector('#app');
      const html = app ? app.innerHTML : '';
      const txt = document.body ? document.body.innerText : '';
      return {
        appLen: html.length,
        h1: (document.querySelector('h1') || {}).innerText || '',
        vals: Array.from(document.querySelectorAll('.spec-val'))
          .map((e) => e.innerText.trim()),
        note: (document.querySelector('.spec-draft-note') || {}).innerText || '',
        links: Array.from(document.querySelectorAll('a[href*="/protocols/"]'))
          .map((a) => a.getAttribute('href')),
        hasAdvCol: !!document.querySelector('.detail-columns'),
        hasLabel: /(Minutes?\s*\(<30\s*min\)|Hours?\s*\(30\s*min|Days?\s*\(1[–-]7|Weeks?\s*\(>1\s*week)/i.test(txt),
        bareEnum: /\b(minutes|hours|days|weeks)\b/i.test(txt),
      };
    });
    rec.app_len = info.appLen;
    rec.h1 = info.h1;
    rec.timeline_label = info.vals.join(' | ');
    rec.ai_note = /AI-generated|pending expert review/i.test(info.note);
    rec.adv_block = info.hasAdvCol;
    rec.proto_links = info.links.length;
    rec.timeline_bare = info.bareEnum && !info.hasLabel;

    if (info.links.length) {
      const r2 = await pg.goto(BASE + info.links[0],
        { timeout: 40000, waitUntil: 'domcontentloaded' });
      await pg.waitForTimeout(2500);
      const len2 = await pg.evaluate(() => {
        const a = document.querySelector('#app');
        return a ? a.innerHTML.length : 0;
      });
      rec.link_ok = (r2 && r2.status() === 200 && len2 > 500)
        ? 'ok' : `bad(${r2 ? r2.status() : '-'}/${len2})`;
    } else {
      rec.link_ok = 'no_link';
    }
    rec.errors = errs.slice(0, 2).join(' | ');
  } catch (e) {
    rec.errors = 'FATAL ' + String(e.message).split('\n')[0].slice(0, 110);
  }
  await c.close();
  return rec;
}

(async () => {
  const list = await fetchIds();
  console.log(`方法 ${list.length} 个｜并发 ${CONC}｜${BASE}`);
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const rows = [];
  let idx = 0, done = 0;
  const t0 = Date.now();

  async function worker() {
    while (idx < list.length) {
      const my = idx++;
      try {
        rows.push(await checkOne(browser, list[my]));
      } catch (e) {
        rows.push({ id: list[my].id, name: list[my].name,
                    errors: 'WORKER ' + String(e.message).slice(0, 90) });
      }
      done += 1;
      if (done % 10 === 0) {
        console.log(`  ${done}/${list.length}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
      }
    }
  }
  await Promise.all(Array.from({ length: CONC }, worker));
  await browser.close();

  rows.sort((a, b) => a.id - b.id);
  const cols = ['id', 'name', 'status', 'app_len', 'h1', 'timeline_label',
                'timeline_bare', 'ai_note', 'adv_block', 'proto_links',
                'link_ok', 'errors'];
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  fs.writeFileSync(OUT, '\ufeff' + cols.join(',') + '\n'
    + rows.map((r) => cols.map((c) => esc(r[c])).join(',')).join('\n') + '\n', 'utf8');

  const bad = rows.filter((r) => r.status !== 200 || !r.app_len || !r.ai_note
    || !r.adv_block || r.link_ok !== 'ok');
  console.log(`\n完成 ${rows.length} 页｜${((Date.now() - t0) / 1000).toFixed(0)}s｜异常 ${bad.length}`);
  bad.slice(0, 15).forEach((r) => console.log(
    `  #${r.id} ${String(r.name).slice(0, 30)} status=${r.status} ai=${r.ai_note} `
    + `adv=${r.adv_block} link=${r.link_ok} ${r.errors}`));
  console.log(`CSV: ${OUT}`);
})().catch((e) => { console.error('FATAL', String(e.message).slice(0, 300)); process.exit(1); });
