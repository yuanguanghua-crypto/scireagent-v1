/**
 * `DataPagination` 组件单测 —— props 映射与两个 emit 分支。
 *
 * ## 为什么值得测
 * 这个组件是 D2/D4/D5 修复的落点（`/orders`、`/ops/orders`、`/po/orders` 三处分页都用它）。
 * 它有一个**反直觉的关键设计**：`layout` 默认含 `sizes`，但三处调用方都**显式覆盖成不含 sizes**
 * —— 因为 Element Plus 的每页条数 select 没有可访问名，会引入 a11y critical（实测过两次）。
 * 所以这里要钉住"layout 能被覆盖且原样传下去"，否则将来有人"统一一下"就会把 a11y 打回去。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import DataPagination from '../DataPagination.vue'

const mountIt = (props = {}) =>
  mount(DataPagination, {
    props: { currentPage: 2, pageSize: 20, total: 120, ...props },
    global: { plugins: [ElementPlus] },
  })

const inner = (w) => w.findComponent({ name: 'ElPagination' })

describe('DataPagination', () => {
  it('把 currentPage / pageSize / total 映射到 el-pagination', () => {
    const w = mountIt({ currentPage: 3, pageSize: 50, total: 480 })
    const p = inner(w)
    expect(p.props('currentPage')).toBe(3)
    expect(p.props('pageSize')).toBe(50)
    expect(p.props('total')).toBe(480)
    w.unmount()
  })

  it('总数为 0 时不报错（空列表场景）', () => {
    const w = mountIt({ currentPage: 1, total: 0 })
    expect(inner(w).props('total')).toBe(0)
    w.unmount()
  })

  it('默认 layout 含 sizes，但**调用方可以覆盖掉它**（a11y 关键）', () => {
    const def = mountIt()
    expect(def.props('layout') || inner(def).props('layout')).toBeTruthy()
    def.unmount()

    const noSizes = mount(DataPagination, {
      props: {
        currentPage: 1, pageSize: 20, total: 100,
        layout: 'total, prev, pager, next',   // 三处调用方实际用的写法
      },
      global: { plugins: [ElementPlus] },
    })
    expect(inner(noSizes).props('layout')).toBe('total, prev, pager, next')
    noSizes.unmount()
  })

  it('点页码 ⇒ emit change({page}) 且带当前 pageSize', async () => {
    const w = mountIt()
    inner(w).vm.$emit('current-change', 4)
    await w.vm.$nextTick()
    const events = w.emitted('change')
    expect(events).toBeTruthy()
    expect(events[0][0]).toEqual({ page: 4, pageSize: 20 })
    expect(w.emitted('update:currentPage')[0][0]).toBe(4)
    w.unmount()
  })

  it('改每页条数 ⇒ 回到第 1 页（pageSize 变则页码必须重置）', async () => {
    const w = mountIt({ currentPage: 3 })
    inner(w).vm.$emit('size-change', 50)
    await w.vm.$nextTick()
    expect(w.emitted('update:pageSize')[0][0]).toBe(50)
    expect(w.emitted('change')[0][0]).toEqual({ page: 1, pageSize: 50 })
    w.unmount()
  })

  it('pageSizes 透传（可选每页条数由调用方决定）', () => {
    const w = mountIt({ pageSizes: [10, 20] })
    expect(inner(w).props('pageSizes')).toEqual([10, 20])
    w.unmount()
  })
})
