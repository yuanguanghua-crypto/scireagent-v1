/**
 * 前端**组件单测**配置（2026-10-21 新增）
 *
 * ## 为什么单独建配置，不复用 vite.config.js
 * `vite.config.js` 里挂了 `@tailwindcss/vite` 与 dev-server 代理，组件单测用不到这些，
 * 复用会拖慢启动、还可能因 tailwind 插件在 happy-dom 下的行为带来噪声。
 * ⇒ 这里只保留**编译 .vue 必需**的 `@vitejs/plugin-vue` + `@` 别名。
 *
 * ## 环境
 * `happy-dom`（比 jsdom 轻、快）。Element Plus 组件在 happy-dom 下可正常渲染，
 * 但对**依赖布局/计算样式**的断言（如元素实际宽高）不可靠 —— 这类仍归 E2E 的 V/R 维。
 *
 * ## 定位分工（别搞混）
 * | 层 | 工具 | 测什么 |
 * |---|---|---|
 * | 组件单测（本配置） | vitest + @vue/test-utils | props/emit/条件渲染/aria 与 DOM 契约，**毫秒级** |
 * | 页面 E2E | Playwright（854 例） | 真实浏览器里的操作与状态、跨引擎、a11y、响应式 |
 * ⇒ 组件单测**不替代** E2E；它拦的是"组件分支写漏了、可访问属性丢了"这类**快速可发现**的问题。
 */
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['src/**/__tests__/**/*.spec.js'],
    // 不开启 globals：显式 import { describe, it, expect }，避免与 Playwright 的语法混淆
    globals: false,
    reporters: ['default'],
  },
})
