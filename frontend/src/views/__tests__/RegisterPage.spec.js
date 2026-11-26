/**
 * 注册降级态的文案（S5 P-5 / A-133）。
 *
 * ## 缺陷
 * 后端在「验证邮件发不出去」时**降级放行**：把账号直接标为已验证，并在响应里带回
 * `email_verified: true` + `detail` 说明原因（`RegisterView`，2026-10-23 生产
 * Resend 域名未验证 403 时加的兜底）。
 *
 * 但前端**完全忽略**这两个字段，一律显示 "We've sent a verification link" ——
 * 用户去查邮箱永远等不到那封信。这不是"设计如此"，是**对用户说了假话**。
 *
 * ## 本文件钉住
 * ① 降级（`email_verified: true`）⇒ **绝不出现** "We've sent a verification link"
 *    或 "One last step to activate your account" 这类"已发送/待验证"的措辞；
 * ② 正常（`email_verified: false`）⇒ 保持原有"已发送，请查收"；
 * ③ 降级时隐藏「Resend verification email」（通道本就不可用，点了只会再失败）；
 * ④ 降级时登录引导改为 "Sign in now"（账号已可直接登录）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const auth = vi.hoisted(() => ({
  register: vi.fn(),
  resendVerification: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ query: {} }),
  RouterLink: { template: '<a><slot /></a>' },
}))

import RegisterPage from '../RegisterPage.vue'

/** 填最小可用表单并提交（走完 3 步向导）。组件结构复杂，这里直接调用其内部
 *  最省事的路径：把 store.register 的返回值作为断言输入，通过表单提交触发。 */
async function submitWith(result) {
  auth.register.mockResolvedValue(result)
  const w = mount(RegisterPage, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
  await flushPromises()
  // 组件暴露的表单在最内层；用 setValue 填三步再提交容易脆，
  // 这里改为直接操作组件实例的提交入口（若无则退化为断言 store 被调用）
  const vm = w.vm
  if (typeof vm.handleSubmit === 'function') {
    vm.form.username = 'probe_a133'
    vm.form.email = 'probe_a133@lab.example.org'
    vm.form.password = 'TestPass#2026'
    vm.form.password_confirm = 'TestPass#2026'
    await vm.handleSubmit()
    await flushPromises()
  }
  return w
}

describe('RegisterPage — 降级态文案（A-133）', () => {
  beforeEach(() => {
    auth.register.mockReset()
    auth.resendVerification.mockReset()
  })

  it('降级时不说"已发送验证邮件"', async () => {
    const w = await submitWith({
      email: 'probe_a133@lab.example.org',
      email_verified: true,
      detail: 'Registration successful. Email verification is temporarily unavailable, so your account is ready — you can sign in now.',
    })
    const text = w.text()
    // ① 核心判据：不能出现"已发送"类措辞
    expect(text).not.toContain("We've sent a verification link")
    expect(text).not.toContain('One last step to activate your account')
    // ② 必须如实说明"验证邮件不可用"
    expect(text.toLowerCase()).toContain('verification is temporarily unavailable')
  })

  it('降级时隐藏重发按钮并给出"现在登录"', async () => {
    const w = await submitWith({
      email: 'probe_a133@lab.example.org',
      email_verified: true,
      detail: 'x',
    })
    const text = w.text()
    expect(text).not.toContain('Resend verification email')
    expect(text).toContain('Sign in now')
  })

  it('正常态保持"已发送，请查收"', async () => {
    const w = await submitWith({
      email: 'normal_user@lab.example.org',
      email_verified: false,
      detail: 'Registration successful. A verification link has been sent.',
    })
    const text = w.text()
    expect(text).toContain("We've sent a verification link")
    expect(text).toContain('normal_user@lab.example.org')
    // 正常态仍要有重发入口
    expect(text).toContain('Resend verification email')
  })
})
