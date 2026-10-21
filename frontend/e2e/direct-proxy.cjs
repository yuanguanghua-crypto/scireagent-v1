#!/usr/bin/env node
/**
 * 本地「直连转发代理」—— 让 WebKit 绕开本机系统代理（FlClash 之类）跑测试。
 *
 * ## 为什么需要它（2026-10-21 实测）
 * 本机系统代理是 `127.0.0.1:7890`（FlClash），Windows 的 bypass 列表**已包含** `localhost;127.*`，
 * 但 **Playwright 的 Windows WebKit 页面的网络栈不遵循该 bypass** ——
 * 它把 `http://127.0.0.1:5173/@vite/client` 之类请求交给了 FlClash，拿回 **404**，
 * 于是 SPA 从不挂载（`#app` 长度 0），44 页冒烟全红。
 *
 * 对照（同一时刻、同一台机）：
 *   · `curl` / `page.request` 抓同一 URL → **200**
 *   · WebKit 页面 → **404**（13 个请求全挂）
 *   · WebKit + 本代理 → **`#app` 挂载 30329 字符、0 个失败请求**
 *
 * ## 做法
 * 起一个最小的 HTTP 转发代理（支持绝对 URI 与 CONNECT），**原样转发、不做任何拦截**。
 * 让 WebKit 显式走它 ⇒ 流量不进 FlClash，也不需要用户去关系统代理开关。
 * ⚠️ 它只在 127.0.0.1 上监听，仅供本机测试用，不对外。
 *
 * ## 用法
 * - 自动：`playwright.config.cjs` 在 `--project=webkit` 时把它作为 `webServer` 拉起（推荐）
 * - 手动：`node e2e/direct-proxy.cjs`，然后用 `E2E_DIRECT_PROXY=http://127.0.0.1:8130` 跑 webkit
 */
const http = require('http')
const net = require('net')

const PORT = Number(process.env.E2E_DIRECT_PROXY_PORT || 8130)
const HOST = '127.0.0.1'

const server = http.createServer((req, res) => {
  let target
  try {
    target = new URL(req.url)
  } catch {
    res.writeHead(400, { 'content-type': 'text/plain' })
    return res.end('direct-proxy: 只接受绝对 URI 形式的代理请求')
  }
  const upstream = http.request(
    {
      hostname: target.hostname,
      port: target.port || 80,
      path: target.pathname + target.search,
      method: req.method,
      headers: req.headers,
    },
    (upRes) => {
      res.writeHead(upRes.statusCode || 502, upRes.headers)
      upRes.pipe(res)
    },
  )
  upstream.on('error', (e) => {
    if (!res.headersSent) res.writeHead(502, { 'content-type': 'text/plain' })
    res.end(`direct-proxy upstream error: ${e.message}`)
  })
  req.pipe(upstream)
})

// HTTPS / WebSocket 走 CONNECT 隧道（本项目本地是 http，这里留作通用）
server.on('connect', (req, socket, head) => {
  const [host, port] = String(req.url).split(':')
  const upstream = net.connect(Number(port) || 443, host, () => {
    socket.write('HTTP/1.1 200 Connection Established\r\n\r\n')
    upstream.write(head)
    upstream.pipe(socket)
    socket.pipe(upstream)
  })
  upstream.on('error', () => socket.destroy())
  socket.on('error', () => upstream.destroy())
})

server.listen(PORT, HOST, () => {
  // Playwright 的 webServer 会等待该端口可连；这行只作本地手工启动时的提示
  console.log(`[direct-proxy] listening on http://${HOST}:${PORT}（仅本机，供 WebKit 绕开系统代理）`)
})
