import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { execSync } from 'child_process'

// ── 构建来源标记（2026-10-20 新增）────────────────────────────────────────
// 为什么需要：`docs/CLAIMS.md` 的 C8 要回答「生产前端产物是不是 HEAD 构建的」。
// 原先的判据是「在生产机上 rebuild，与线上 dist 逐文件 diff」，但它假设**构建可复现**——
// 实测不成立：同源码连续两次构建，Tailwind v4 生成的 CSS 每次都差几百字节
// （421115 vs 420430），CSS hash 一变，引用它的入口 JS 也变，167 个文件全部改名。
// ⇒ 逐文件 diff 只会随机红，证明不了任何事。
//
// 改成把「构建时的 commit」写进产物本身，判据就变成一行 grep：
//   从生产 dist/index.html 取出 meta[name=build-commit] 的值，与 git HEAD 比对。
// 这直接回答「这份产物是哪个 commit 构建的」，且**完全不受构建不确定性影响**。
//
// 优先读 BUILD_COMMIT 环境变量（CI / 显式部署时可传），否则回退到 git。
function resolveBuildCommit() {
  if (process.env.BUILD_COMMIT) return String(process.env.BUILD_COMMIT).trim()
  try {
    return execSync('git rev-parse --short HEAD', {
      cwd: __dirname,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim()
  } catch {
    // 拿不到就显式写 unknown —— 不要伪造一个看起来像 hash 的值
    return 'unknown'
  }
}

const BUILD_COMMIT = resolveBuildCommit()

/** 把 commit 注入 index.html 的 <meta>：不会被 minify 掉，脚本 grep 也最简单 */
function injectBuildCommit() {
  return {
    name: 'inject-build-commit',
    transformIndexHtml(html) {
      return html.replace(
        '</head>',
        `  <meta name="build-commit" content="${BUILD_COMMIT}" />\n</head>`,
      )
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    injectBuildCommit(),
  ],
  // 也暴露给源码（main.js 里打日志 / 调试面板可用）
  define: {
    __BUILD_COMMIT__: JSON.stringify(BUILD_COMMIT),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    // ★ v4.1 DEV-8：主包拆分 — vendor 库独立 chunk，业务代码变更时浏览器缓存命中 vendor
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-element': ['element-plus'],
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
          'vendor-http': ['axios'],
        },
      },
    },
  },
  server: {
    // host:true 让 vite 监听所有网卡(含 127.0.0.1 与 [::1]),
    // 消除浏览器把 localhost 解析成 IPv4 时连不上仅 IPv6 监听的 dev server 的问题。
    host: true,
    port: 5173,
    proxy: {
      // 强制 IPv4, 避免 Node 把 localhost 解析成 [::1] 后转发到
      // 只监听 127.0.0.1 的 Django(runserver 默认 IPv4)导致 ECONNREFUSED。
      '/api': {
        // ★ 2026-10-21：可用 VITE_API_PROXY 指向另一套后端（空库演练 / CI 多用例隔离）
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api/v1': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})