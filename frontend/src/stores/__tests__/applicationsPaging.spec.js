/**
 * 应用列表的越界页收敛（A-176，2026-11-27）。
 *
 * ## 改前
 * `/applications` 点到末页之后（QA 实测第 1429 页）时，后端返回 404 `Invalid page.`，
 * 前端只把红字打在页面上，**卡片仍是上一页内容**。
 *
 * ## 为什么用单测
 * Element Plus 的 pager 按 `total` 渲染，**点不出范围外的页码** ⇒ 真机无法稳定复现
 * 这条分支，只能在 store 层直接喂一个 404。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const api = vi.hoisted(() => ({
  getApplications: vi.fn(),
  getApplication: vi.fn(),
  createApplication: vi.fn(),
  updateApplication: vi.fn(),
  deleteApplication: vi.fn(),
}))
// store 从 `@/api/applications` 导入（不是 api/knowledge）
vi.mock('@/api/applications', () => api)

import { useApplicationsStore } from '../applications'

const invalidPage = () => Object.assign(new Error('Invalid page.'), {
  response: { status: 404, data: { meta: { error: { message: 'Invalid page.' } } } },
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('applications store 越界页（A-176）', () => {
  it('越界页 ⇒ 回到最后一个有效页并重试，不把红字留在页面', async () => {
    const store = useApplicationsStore()
    // 先给一个已知总数（页大小 20 ⇒ 2 页）
    api.getApplications.mockResolvedValueOnce({
      data: [{ id: 1 }], meta: { pagination: { count: 40 } },
    })
    await store.fetchApplications()
    expect(store.pagination.total).toBe(40)

    // 请求越界页：先 404，重试时返回正常数据
    api.getApplications
      .mockRejectedValueOnce(invalidPage())
      .mockResolvedValueOnce({ data: [{ id: 2 }], meta: { pagination: { count: 40 } } })

    store.setPage(99)
    await store.fetchApplications({ page: 99 })

    expect(api.getApplications).toHaveBeenCalledTimes(3)   // 1 次正常 + 1 次 404 + 1 次重试
    expect(store.pagination.page).toBe(2)                   // 落到最后一个有效页
    expect(store.error, '不该把 404 当业务错误显示给用户').toBe(null)
    expect(store.applications).toEqual([{ id: 2 }])
  })

  it('非 Invalid page 的 404 仍照常抛错（不能吞掉真实错误）', async () => {
    const store = useApplicationsStore()
    api.getApplications.mockRejectedValueOnce(
      Object.assign(new Error('Not found'), {
        response: { status: 404, data: { detail: 'No such thing' } },
      }),
    )
    await expect(store.fetchApplications()).rejects.toBeTruthy()
    expect(store.error).toBeTruthy()
  })
})
