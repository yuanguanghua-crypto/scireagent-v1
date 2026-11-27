/**
 * 401 处置分流（A-169，2026-11-27）。
 *
 * ## 病
 * 拦截器对**所有** 401 一律 `ElMessage.error('Session expired')` +
 * `window.location.href = '/login'`。可登录接口对"密码错"也返回 401，
 * 于是用户点 Sign In 后页面被**整页刷新**：LoginPage 里那条
 * "Incorrect username or password" 连同组件状态一起被冲掉，屏幕上什么都没有。
 * （QA Batch 15 两轮实测：后端 401、DOM 里 .auth-error-banner 全程为空。）
 *
 * ## 口径
 * 凭据类端点（login/register/reset/verify/…）的 401 是**业务答案**，
 * 交给页面自己渲染；其余端点的 401 才是会话过期，照旧跳登录。
 *
 * ⚠️ 这里直接取拦截器的 rejected 处理器来测——它是纯函数式的一层，
 * 用 axios 假 adapter 反而要绕更多圈子。`handlers` 是 axios 的公开结构之一，
 * 若将来升级 axios 改了形状，本用例会**立刻炸**而不是静默放过。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn(), success: vi.fn() } }))

import { ElMessage } from 'element-plus'
import http from '@/utils/http'

const rejected = (() => {
  const handlers = http.interceptors.response.handlers
  const h = handlers[handlers.length - 1]
  return h.rejected
})()

function err401(url) {
  return {
    config: { url },
    response: { status: 401, data: { success: false, meta: { error: { detail: 'Invalid username or password' } } } },
  }
}

beforeEach(() => {
  ElMessage.error.mockClear()
})

describe('A-169 凭据端点的 401 不弹"会话过期"、不整页跳转', () => {
  for (const path of ['/auth/login', '/auth/register', '/auth/reset-password', '/auth/verify-email']) {
    it(`${path} 的 401 交给调用方处理`, async () => {
      await expect(rejected(err401(path))).rejects.toBeTruthy()
      const said = ElMessage.error.mock.calls.map((c) => String(c[0]))
      expect(said.some((m) => m.includes('Session expired'))).toBe(false)
      expect(said).toHaveLength(0)
    })
  }

  it('普通业务端点的 401 仍然提示会话过期', async () => {
    await expect(rejected(err401('/orders/38/'))).rejects.toBeTruthy()
    const said = ElMessage.error.mock.calls.map((c) => String(c[0]))
    expect(said.some((m) => m.includes('Session expired'))).toBe(true)
  })
})
