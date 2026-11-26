/**
 * 用户列表「谁能进后台」的可见性（S5 P-3 / A-092）。
 *
 * ## 缺陷
 * 本页把 role 字段显示成一个下拉，而下拉只有 4 个 role 值。
 * 但「能不能进后台」有三条**互相独立**的通道：
 *   a) `role='admin'`   b) `is_staff=True`   c) `is_superuser=True`
 * 生产实测（2026-11-26）：真正能进后台的 3 个账号 role **全是 researcher**
 * ⇒ 光看 role 下拉会得出"没有管理员"的错误结论，而选 admin 筛选又只能筛出
 *   唯一那个 role='admin' 的冒烟账号（smoke）。
 *
 * ## 本文件钉住
 * ① `is_staff` 的账号在列表里有 staff 标记；`is_superuser` 有 superuser 标记
 *    （两者都有时只显示更强的那个，不堆两个）；
 * ② 标记**不改变** role 下拉显示的原值（researcher 还是 researcher）——
 *    这两个是不同的东西，混在一起就又回到"看不出谁是管理员"的老问题；
 * ③ 筛选下拉的 admin 选项写明它包含 staff/superuser，
 *    这样「筛 admin 出来一个 researcher」在界面上自解释。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({
  getUsers: vi.fn(),
  patchUser: vi.fn(),
  verifyUserEmail: vi.fn(),
  sendUserPasswordReset: vi.fn(),
}))
vi.mock('@/api/system', () => api)

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { id: 999 } }),
}))

import UserManagementPage from '../UserManagementPage.vue'

function user(over = {}) {
  return {
    id: 1,
    username: 'u1',
    email: 'u1@example.com',
    role: 'researcher',
    is_active: true,
    email_verified: true,
    is_staff: false,
    is_superuser: false,
    date_joined: '2026-07-01T00:00:00Z',
    last_login: null,
    organization_name: '',
    ...over,
  }
}

function envelope(rows) {
  return {
    success: true,
    data: rows,
    meta: { pagination: { count: rows.length, page: 1, page_size: 200 } },
  }
}

async function mountWith(rows) {
  api.getUsers.mockResolvedValue(envelope(rows))
  const w = mount(UserManagementPage, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return w
}

function rowAt(w, i) {
  return w.findAll('tbody tr')[i]
}

describe('UserManagementPage — 后台权限标记（A-092）', () => {
  beforeEach(() => {
    api.getUsers.mockReset()
  })

  it('is_staff 账号显示 staff 标记', async () => {
    const w = await mountWith([user({ username: 'scire02', is_staff: true })])
    expect(rowAt(w, 0).text()).toContain('staff')
  })

  it('is_superuser 账号显示 superuser 标记', async () => {
    const w = await mountWith([user({ username: 'root', is_staff: true, is_superuser: true })])
    expect(rowAt(w, 0).text()).toContain('superuser')
  })

  it('两者都为真时只显示 superuser，不堆两个标记', async () => {
    const w = await mountWith([user({ username: 'root', is_staff: true, is_superuser: true })])
    const badges = rowAt(w, 0).findAll('.um-badge.staff, .um-badge.super')
    expect(badges.length).toBe(1)
    expect(badges[0].classes()).toContain('super')
  })

  it('普通研究员没有任何后台标记', async () => {
    const w = await mountWith([user({ username: 'plain' })])
    expect(rowAt(w, 0).findAll('.um-badge.staff, .um-badge.super').length).toBe(0)
  })

  it('标记不改变 role 下拉的原值（researcher 仍是 researcher）', async () => {
    const w = await mountWith([user({ username: 'scire02', role: 'researcher', is_staff: true })])
    const sel = rowAt(w, 0).find('select')
    expect(sel.element.value).toBe('researcher')
    // 但同时必须有 staff 标记 —— 否则「筛 admin 出 researcher」就解释不通了
    expect(rowAt(w, 0).text()).toContain('staff')
  })

  it('筛选下拉的 admin 选项写明包含 staff/superuser', async () => {
    const w = await mountWith([user()])
    const opts = w.findAll('.um-filters select')[0].findAll('option')
    const adminOpt = opts.find((o) => o.element.value === 'admin')
    expect(adminOpt).toBeTruthy()
    expect(adminOpt.text().toLowerCase()).toContain('staff')
    expect(adminOpt.text().toLowerCase()).toContain('superuser')
  })

  it('筛选下拉的其它选项保持原文', async () => {
    const w = await mountWith([user()])
    const opts = w.findAll('.um-filters select')[0].findAll('option')
    const resOpt = opts.find((o) => o.element.value === 'researcher')
    expect(resOpt.text()).toBe('researcher')
  })
})
