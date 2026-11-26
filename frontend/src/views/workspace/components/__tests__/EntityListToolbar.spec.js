/**
 * `EntityListToolbar` 单测 —— 三个控件的 emit 契约（S4 / A-066 + A-014）。
 *
 * ## 为什么值得测
 * 这里有一个**只在关掉开关时才会走到**的分支：`showDrafts=false` 时必须**顺带**把
 * `status` 清空。漏掉它的后果不是报错，而是「开关关着、筛选还停在 archived」⇒
 * 查询变成 `status=archived` 且不带 include_unpublished，后端先按方案 B 筛成
 * 公开态、再按 archived 筛 ⇒ **空表**。用户看到的是"这页没数据了"，没人会想到
 * 是残留的筛选态。E2E 只在真实点击序列里能撞上，单测里一行就能钉死。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import EntityListToolbar from '../EntityListToolbar.vue'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'active' },
  { value: 'draft', label: 'draft' },
]

const mountIt = (props = {}) =>
  mount(EntityListToolbar, {
    props: { statusOptions: STATUS_OPTIONS, ...props },
    global: { plugins: [ElementPlus] },
  })

const toggle = (w) => w.find('[data-testid="show-drafts-toggle"]')

describe('EntityListToolbar', () => {
  it('勾选 Show drafts ⇒ 抛 update:showDrafts(true) 并立刻触发一次 submit', async () => {
    const w = mountIt()
    await toggle(w).setValue(true)
    expect(w.emitted('update:showDrafts')[0]).toEqual([true])
    expect(w.emitted('submit')).toHaveLength(1)
  })

  it('★ 取消勾选 ⇒ 除 update:showDrafts(false) 外还必须抛 update:status("")', async () => {
    const w = mountIt({ showDrafts: true, status: 'archived' })
    await toggle(w).setValue(false)
    expect(w.emitted('update:showDrafts')[0]).toEqual([false])
    // 关键：不清空的话会变成「关着开关却按 archived 筛」⇒ 空表
    expect(w.emitted('update:status')[0]).toEqual([''])
  })

  it('状态下拉只在 showDrafts 为真时渲染（关着时没有可筛的状态）', async () => {
    const off = mountIt({ showDrafts: false })
    expect(off.findComponent({ name: 'ElSelect' }).exists()).toBe(false)

    const on = mountIt({ showDrafts: true })
    expect(on.findComponent({ name: 'ElSelect' }).exists()).toBe(true)
  })

  it('状态下拉的选项来自 statusOptions（标签与值都透传）', () => {
    const w = mountIt({ showDrafts: true })
    const items = w.findAllComponents({ name: 'ElOption' })
    expect(items.map((o) => o.props('value'))).toEqual(['', 'active', 'draft'])
    expect(items.map((o) => o.props('label'))).toEqual(['All statuses', 'active', 'draft'])
  })

  it('搜索框输入 ⇒ update:search；回车 ⇒ submit', async () => {
    const w = mountIt()
    const input = w.find('input')
    await input.setValue('kinase')
    expect(w.emitted('update:search')[0]).toEqual(['kinase'])
    await input.trigger('keyup.enter')
    expect(w.emitted('submit')).toHaveLength(1)
  })

  it('search 是受控 prop：不在组件内自持状态（父组件才是唯一真相源）', () => {
    const w = mountIt({ search: 'abc' })
    expect(w.find('input').element.value).toBe('abc')
  })
})
