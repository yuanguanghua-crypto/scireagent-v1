/**
 * 两个"展示型"组件的单测：`EmptyState` / `LoadingSpinner`。
 *
 * 它们没有复杂逻辑，但有**两条值得钉住的契约**：
 * ① `EmptyState` 的 `title` 有默认值（"No data"）—— 很多页面依赖它，改默认值会全站变文案；
 * ② `EmptyState` 的 `action` 插槽是 `v-if` 条件渲染 —— E2E 里大量断言
 *    「空态里有 Browse Products 出口」，插槽渲染错就会让那些用例静默失败。
 * 另外 `LoadingSpinner` 的全站 class `.spinner-text` 是 **a11y 扫描的等待锚点**
 * （`a11y.spec.cjs` 用 `waitForSelector('.spinner-text', {state:'detached'})` 等它消失），
 * 改类名会让 a11y 扫描在"加载中"那一帧采样，产生伪 serious 违规。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import EmptyState from '../EmptyState.vue'
import LoadingSpinner from '../LoadingSpinner.vue'

describe('EmptyState', () => {
  const mountIt = (props = {}, slots = {}) =>
    mount(EmptyState, { props, slots, global: { plugins: [ElementPlus] } })

  it('默认 title 是 "No data"（全站依赖这个默认值）', () => {
    const w = mountIt()
    expect(w.text()).toContain('No data')
    w.unmount()
  })

  it('title 可覆盖，description 在有值时渲染', () => {
    const w = mountIt({ title: 'No orders yet', description: 'You have no orders yet.' })
    expect(w.text()).toContain('No orders yet')
    expect(w.text()).toContain('You have no orders yet.')
    w.unmount()
  })

  it('description 为空时不渲染该段落', () => {
    const w = mountIt({ title: 'Only title', description: '' })
    expect(w.text()).toContain('Only title')
    expect(w.text()).not.toContain('You have no orders yet')
    w.unmount()
  })

  it('action 插槽有内容时渲染（E2E 的"出口按钮"靠它）', () => {
    const w = mountIt({ title: 'X' }, { action: '<a class="btn-primary">Browse Products</a>' })
    expect(w.find('.btn-primary').exists()).toBe(true)
    expect(w.text()).toContain('Browse Products')
    w.unmount()
  })

  it('无 action 插槽时不渲染多余节点', () => {
    const w = mountIt({ title: 'X' })
    expect(w.find('a').exists()).toBe(false)
    w.unmount()
  })
})

describe('LoadingSpinner', () => {
  it('渲染 .spinner-text（★ a11y 扫描的等待锚点，改类名会让扫描在加载帧采样）', () => {
    const w = mount(LoadingSpinner, { global: { plugins: [ElementPlus] } })
    expect(w.find('.spinner-text').exists()).toBe(true)
    w.unmount()
  })

  it('text 文案可覆盖', () => {
    const w = mount(LoadingSpinner, {
      props: { text: 'Loading orders...' },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).toContain('Loading orders...')
    w.unmount()
  })
})
