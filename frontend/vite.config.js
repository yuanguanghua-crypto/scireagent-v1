import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
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
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api/v1': {
        target: 'http://127.0.0.1:8000',
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