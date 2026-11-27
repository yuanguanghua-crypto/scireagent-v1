/**
 * 设置页 Account 栏三处口径（S7 认证/设置桶，2026-11-27）。
 *
 * - **A-238**：五个标签页里**完全没有**邮箱验证状态，而登录对未验证账号是硬拦（403）
 *   —— 用户看不到自己卡在哪一步。补一行 `Email verification`。
 * - **A-185**：注册页选 "Independent Researcher" 落库是 `role='researcher'`，
 *   差别只在**有没有组织**。无组织时如实显示 Independent Researcher，
 *   不再笼统 "Researcher" 让人以为选择没生效。
 * - **顺带**：`user.organization` 是外键 **id**（不是对象），原实现读 `org.name`
 *   恒 undefined ⇒ Organization 一栏**对所有用户**都显示 "None"。
 *   序列化器早就带 `organization_name`，改用它。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const state = vi.hoisted(() => ({ user: null }))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: state.user,
    isOrgAdmin: !!state.user?.is_org_admin,
    isAuthenticated: true,
    isStaff: false,
  }),
}))

import SettingsPage from '@/views/SettingsPage.vue'

async function mountAccount(user) {
  state.user = user
  const w = mount(SettingsPage, { global: { stubs: { 'router-link': true } } })
  // 切到 Account 标签（必须 await：面板是 v-if，不等待则读到空 DOM）
  const tab = w.findAll('button').find((b) => b.text().trim() === 'Account')
  await tab.trigger('click')
  return w
}

function rows(w) {
  const out = {}
  for (const r of w.findAll('.info-row')) {
    const label = r.find('.info-label').text().trim()
    out[label] = r.find('.info-value').text().replace(/\s+/g, ' ').trim()
  }
  return out
}

beforeEach(() => {
  state.user = null
})

describe('A-238 邮箱验证状态', () => {
  it('已验证 → Verified', async () => {
    const w = await mountAccount({
      username: 'u', email: 'u@x.com', role: 'researcher',
      email_verified: true, organization: null, organization_name: null,
    })
    expect(rows(w)['Email verification']).toBe('Verified')
  })

  it('未验证 → Not verified', async () => {
    const w = await mountAccount({
      username: 'u', email: 'u@x.com', role: 'researcher',
      email_verified: false, organization: null, organization_name: null,
    })
    expect(rows(w)['Email verification']).toBe('Not verified')
  })
})

describe('A-185 Role 与注册选择', () => {
  it('无组织的研究员 → Independent Researcher', async () => {
    const w = await mountAccount({
      username: 'u', role: 'researcher', email_verified: true,
      organization: null, organization_name: null,
    })
    expect(rows(w)['Role']).toContain('Independent Researcher')
  })

  it('有组织的研究员 → Researcher（团队身份）', async () => {
    const w = await mountAccount({
      username: 'u', role: 'researcher', email_verified: true,
      organization: 4, organization_name: 'E2E Customer Org',
    })
    expect(rows(w)['Role']).toContain('Researcher')
    expect(rows(w)['Role']).not.toContain('Independent')
  })
})

describe('Organization 一栏读 organization_name（不是 org.name）', () => {
  it('有组织时显示机构名，而不是 None', async () => {
    const w = await mountAccount({
      username: 'u', role: 'researcher', email_verified: true,
      organization: 4, organization_name: 'E2E Customer Org',
    })
    expect(rows(w)['Organization']).toBe('E2E Customer Org')
  })

  it('无组织时显示 None', async () => {
    const w = await mountAccount({
      username: 'u', role: 'researcher', email_verified: true,
      organization: null, organization_name: null,
    })
    expect(rows(w)['Organization']).toBe('None')
  })
})
