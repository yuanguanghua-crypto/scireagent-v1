/**
 * `ErrorBanner` 组件单测 —— 重点钉住 D10 那次**假绿**的根因。
 *
 * ## 为什么这个组件值得单测
 * 2026-10-21 修 D10 时，我把它写成 `v-if="message || title"`，而调用方传的是**固定 title**
 * ⇒ 横幅在**一切正常**的页面上也常显。而当时的 E2E **全绿** —— 因为它只断言"出错时出现"。
 * 是**视觉抽检截图**才发现的。这类"条件写反/多写一个 or"的问题，组件单测毫秒级就能拦住。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ErrorBanner from '../ErrorBanner.vue'

describe('ErrorBanner', () => {
  it('message 为空时不渲染（★ D10 回归：固定 title 不得让它常显）', () => {
    const w = mount(ErrorBanner, {
      props: { message: '', title: "Couldn't load orders.", kind: 'load' },
    })
    expect(w.find('.error-banner').exists()).toBe(false)
    w.unmount()
  })

  it('message 存在时渲染，且带上文案', () => {
    const w = mount(ErrorBanner, { props: { message: 'Injected failure' } })
    const el = w.find('.error-banner')
    expect(el.exists()).toBe(true)
    expect(el.text()).toContain('Injected failure')
    w.unmount()
  })

  it('title 只在有 message 时作为前缀出现', () => {
    const w = mount(ErrorBanner, {
      props: { message: 'boom', title: "Couldn't load orders." },
    })
    expect(w.find('.error-banner-title').text()).toBe("Couldn't load orders.")
    expect(w.text()).toContain('boom')
    w.unmount()
  })

  it('没有 title 时不渲染标题节点', () => {
    const w = mount(ErrorBanner, { props: { message: 'boom' } })
    expect(w.find('.error-banner-title').exists()).toBe(false)
    w.unmount()
  })

  it('kind 透传到 data-kind（E2E 靠它区分 load 与 action）', () => {
    const load = mount(ErrorBanner, { props: { message: 'x', kind: 'load' } })
    expect(load.find('.error-banner').attributes('data-kind')).toBe('load')
    load.unmount()

    const action = mount(ErrorBanner, { props: { message: 'x', kind: 'action' } })
    expect(action.find('.error-banner').attributes('data-kind')).toBe('action')
    action.unmount()
  })

  it('默认 kind 是 load', () => {
    const w = mount(ErrorBanner, { props: { message: 'x' } })
    expect(w.find('.error-banner').attributes('data-kind')).toBe('load')
    w.unmount()
  })

  it('有 role="alert" 让读屏软件播报', () => {
    const w = mount(ErrorBanner, { props: { message: 'x' } })
    expect(w.find('.error-banner').attributes('role')).toBe('alert')
    w.unmount()
  })

  it('message 变成空串时横幅消失（错误态可被清除）', async () => {
    const w = mount(ErrorBanner, { props: { message: 'boom' } })
    expect(w.find('.error-banner').exists()).toBe(true)
    await w.setProps({ message: '' })
    expect(w.find('.error-banner').exists()).toBe(false)
    w.unmount()
  })
})
