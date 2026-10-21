#!/usr/bin/env node
/**
 * E2E 环境前置自检（preflight）—— 2026-10-21 新增
 *
 * ## 为什么需要它
 * 这套 E2E 曾多次把**环境问题**当成**应用问题**：
 *   · 后端没起 ⇒ 一堆 "element not found"，看起来像前端 bug
 *   · 5173 被别的服务占了 ⇒ 页面「白屏」，看不出是被顶掉了
 *   · 本机系统代理（FlClash 之类）接管 127.0.0.1 ⇒ WebKit 拿到 404，而 curl 是 200
 *   · index.html 曾引 Google Fonts 外链 ⇒ 网络一抖页面加载就超时，报成随机的用例失败
 * ⇒ 跑批前先跑这个，把"环境不行"和"代码不行"分开。**FAIL 就别跑测试了，先把环境修好。**
 *
 * ## 判定口径
 * | 级别 | 含义 | 退出码 |
 * |---|---|---|
 * | FAIL | 必须修，否则测试结果无意义 | 1 |
 * | WARN | 可能影响某些引擎/用例，但仍可跑 | 0 |
 * | PASS | 正常 | 0 |
 *
 * 用法：node e2e/preflight.cjs         （或 npm run test:e2e:preflight）
 *      node e2e/preflight.cjs --strict  （WARN 也算失败，正式跑批/发版前用）
 */
const http = require('http')
const https = require('https')
const fs = require('fs')
const net = require('net')
const path = require('path')

const FRONT = process.env.BASE_URL || 'http://localhost:5173'
const BACK = process.env.E2E_API_BASE || 'http://localhost:8000'
const STRICT = process.argv.includes('--strict')

const rows = []
function add(level, name, detail) {
  rows.push({ level, name, detail })
}

/** 简单 GET，返回 { status, body, ms } 或抛错 */
function get(url, timeout = 8000) {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith('https') ? https : http
    const t0 = Date.now()
    const req = lib.get(url, { timeout }, (res) => {
      let body = ''
      res.setEncoding('utf8')
      res.on('data', (c) => { body += c })
      res.on('end', () => resolve({ status: res.statusCode, body, ms: Date.now() - t0 }))
    })
    req.on('timeout', () => { req.destroy(new Error(`超时 ${timeout}ms`)) })
    req.on('error', reject)
  })
}

/** 端口是否在监听（用于探测本机代理端口） */
function portOpen(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const s = new net.Socket()
    const done = (v) => { s.destroy(); resolve(v) }
    s.setTimeout(600)
    s.once('connect', () => done(true))
    s.once('timeout', () => done(false))
    s.once('error', () => done(false))
    s.connect(port, host)
  })
}

;(async () => {
  // ① 后端
  try {
    const r = await get(`${BACK}/api/v1/products/?page_size=1`)
    const okJson = (() => { try { JSON.parse(r.body); return true } catch { return false } })()
    if (r.status === 200 && okJson) {
      add(r.ms > 3000 ? 'WARN' : 'PASS', `后端 ${BACK}`, `${r.status} ${r.ms}ms  JSON ok`)
    } else {
      add('FAIL', `后端 ${BACK}`, `HTTP ${r.status}，返回不是预期 JSON（${r.body.slice(0, 60)}）`)
    }
  } catch (e) {
    add('FAIL', `后端 ${BACK}`, `不可达：${String(e.message).split('\n')[0]}`)
  }

  // ② 前端（必须确认是 **vite dev server**，而不是别的服务占了 5173）
  try {
    const r = await get(`${FRONT}/`)
    const hasApp = r.body.includes('id="app"')
    const isVite = r.body.includes('@vite/client')
    if (r.status !== 200) {
      add('FAIL', `前端 ${FRONT}`, `HTTP ${r.status}`)
    } else if (!hasApp) {
      add('FAIL', `前端 ${FRONT}`, '200 但没有 <div id="app">，可能被别的服务占了')
    } else if (!isVite) {
      add('WARN', `前端 ${FRONT}`, '200 且含 #app，但没看到 @vite/client（不是 dev server？生产构建请另测）')
    } else {
      add(r.ms > 3000 ? 'WARN' : 'PASS', `前端 ${FRONT}`, `${r.status} ${r.ms}ms  vite ok`)
    }
  } catch (e) {
    add('FAIL', `前端 ${FRONT}`, `不可达：${String(e.message).split('\n')[0]}`)
  }

  // ③ 外网字体依赖（源码 + dist 都查；dist 是生产上传源，容易忘记重建）
  const fontRefs = []
  for (const rel of ['index.html', 'dist/index.html']) {
    const p = path.join(__dirname, '..', rel)
    if (!fs.existsSync(p)) continue
    const txt = fs.readFileSync(p, 'utf8')
    if (/fonts\.googleapis|fonts\.gstatic/.test(txt)) fontRefs.push(rel)
  }
  if (fontRefs.length === 0) {
    add('PASS', '外网字体依赖', '0 处（已自托管 src/assets/fonts）')
  } else if (fontRefs.includes('index.html')) {
    add('FAIL', '外网字体依赖', `源码仍引 Google Fonts：${fontRefs.join(', ')}（会因网络抖动造成 flake）`)
  } else {
    add('WARN', '外网字体依赖', `源码已自托管，但 ${fontRefs.join(', ')} 仍是外链 ⇒ 生产产物未重建`)
  }

  // ④ 本机代理端口（WebKit 的本地请求会被它接管；Chromium/Firefox 已各自规避）
  const proxyPorts = [7890, 7891, 1080, 10809]
  const listening = []
  for (const port of proxyPorts) {
    if (await portOpen(port)) listening.push(port)
  }
  if (listening.length === 0) {
    add('PASS', '本机代理端口', '未检测到常见代理端口在监听')
  } else {
    add('WARN', '本机代理端口', `检测到 ${listening.join(', ')} 在监听 ⇒ 跑 --project=webkit 前建议关掉系统代理`)
  }

  // ⑤ 测试数据库残留（会撞 pre-commit 的变异演练，也会让 pytest 报 database is locked）
  const staleDb = path.join(__dirname, '..', '..', 'backend', 'test_db.sqlite3')
  if (fs.existsSync(staleDb)) {
    add('WARN', '后端测试库残留', 'backend/test_db.sqlite3 存在 ⇒ 跑 pytest 前建议先移开（否则可能 database is locked）')
  } else {
    add('PASS', '后端测试库残留', '无残留')
  }

  // ── 输出 ──
  const icon = { PASS: '✓', WARN: '!', FAIL: '✗' }
  const nFail = rows.filter((r) => r.level === 'FAIL').length
  const nWarn = rows.filter((r) => r.level === 'WARN').length
  const nPass = rows.filter((r) => r.level === 'PASS').length
  const nameW = Math.max(...rows.map((r) => r.name.length)) + 2

  console.log('\nE2E 环境自检（跑批前先过这个）')
  console.log('─'.repeat(72))
  for (const r of rows) {
    console.log(`${icon[r.level]} ${r.level.padEnd(4)} ${r.name.padEnd(nameW)} ${r.detail}`)
  }
  console.log('─'.repeat(72))
  console.log(`结果：${nPass} PASS / ${nWarn} WARN / ${nFail} FAIL`)

  if (nFail > 0) {
    console.log('⇒ 环境不合格，先修环境再跑测试（否则测试结果会被误读成代码问题）\n')
    process.exit(1)
  }
  if (STRICT && nWarn > 0) {
    console.log('⇒ --strict 模式下 WARN 也算失败\n')
    process.exit(1)
  }
  console.log('⇒ 可以开跑\n')
})()
