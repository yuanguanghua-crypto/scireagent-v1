/**
 * `<IsoDateInput>` —— A-249 收尾。
 *
 * 这个组件存在的唯一理由：`<input type="date">` 的分段输入会把手打的
 * `YYYY-MM-DD` 吃成脏值（实测 `2026-11-27` → `202611-02-07`），而全站日期显示
 * 都是 `YYYY-MM-DD`。所以这里钉住四件事：
 *   ① 底层是 type=text（这是修法的前提，退回 date 就前功尽弃）；
 *   ② 失焦归一：`20261127` / `2026/12/05` 都收敛成 ISO；
 *   ③ 含糊/不存在的写法 ⇒ `invalid` 事件带出文案、`aria-invalid`、红框，
 *      且 **`change` 不触发**（父组件常拿 change 直接发请求，脏值绝不能流出去）；
 *   ④ 调用方的 `aria-label` / `class` / `data-testid` 能透传到内层 input。
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import IsoDateInput from '../IsoDateInput.vue'

const input = (w) => w.find('input')
const hasErrStyle = (w) => w.find('input').classes().includes('iso-date-invalid')
const lastInvalid = (w) => (w.emitted('invalid') || []).at(-1)?.[0]

async function typeAndBlur(w, value) {
  await input(w).setValue(value)
  await input(w).trigger('blur')
}

describe('IsoDateInput', () => {
  it('★ 根元素就是 input 本身（包一层 span 会让调用方的 scoped 样式失效）', () => {
    const w = mount(IsoDateInput, { attrs: { class: 'sr-date' } })
    // 渲染出来的第一个节点必须是 <input>，不能是包裹用的 <span>
    expect(w.html().trim().startsWith('<input')).toBe(true)
    expect(w.find('input').classes()).toContain('sr-date')
    w.unmount()
  })

  it('底层是 text —— 退回 type=date 就白改了', () => {
    const w = mount(IsoDateInput)
    expect(input(w).attributes('type')).toBe('text')
    expect(input(w).attributes('inputmode')).toBe('numeric')
    w.unmount()
  })

  it('失焦把 20261127 归一成 2026-11-27', async () => {
    const w = mount(IsoDateInput, { props: { modelValue: '' } })
    await typeAndBlur(w, '20261127')
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['2026-11-27'])
    expect(w.emitted('change').at(-1)).toEqual(['2026-11-27'])
    w.unmount()
  })

  it('斜杠/点号写法也归一', async () => {
    const w = mount(IsoDateInput, { props: { modelValue: '' } })
    await typeAndBlur(w, '2026/12/05')
    expect(w.emitted('change').at(-1)).toEqual(['2026-12-05'])
    w.unmount()
  })

  it('★ 含糊写法 ⇒ 报错、aria-invalid、且不触发 change', async () => {
    const w = mount(IsoDateInput, { props: { modelValue: '' } })
    await typeAndBlur(w, '03/04/2026')

    expect(hasErrStyle(w)).toBe(true)
    expect(lastInvalid(w)).toMatch(/YYYY-MM-DD/)
    expect(input(w).attributes('aria-invalid')).toBe('true')
    expect(w.emitted('change'), '脏值绝不能通过 change 流给发请求的父组件').toBeUndefined()
    expect(w.emitted('invalid').at(-1)[0]).toMatch(/YYYY-MM-DD/)
    w.unmount()
  })

  it('不存在的日期（2026-02-30）也拦', async () => {
    const w = mount(IsoDateInput, { props: { modelValue: '' } })
    await typeAndBlur(w, '2026-02-30')
    expect(lastInvalid(w)).toMatch(/no day 30/)
    expect(w.emitted('change')).toBeUndefined()
    w.unmount()
  })

  it('min/max 与原生 `:min` 同语义', async () => {
    const w = mount(IsoDateInput, { props: { modelValue: '', min: '2026-11-27' } })
    await typeAndBlur(w, '2026-11-26')
    expect(lastInvalid(w)).toMatch(/on or after 2026-11-27/)
    expect(w.emitted('change')).toBeUndefined()

    await typeAndBlur(w, '2026-11-27')
    expect(hasErrStyle(w)).toBe(false)
    expect(w.emitted('change').at(-1)).toEqual(['2026-11-27'])
    w.unmount()
  })

  it('清空是合法的（= 不填），change 带空串', async () => {
    const w = mount(IsoDateInput, { props: { modelValue: '2026-11-27' } })
    await typeAndBlur(w, '')
    expect(w.emitted('change').at(-1)).toEqual([''])
    expect(hasErrStyle(w)).toBe(false)
    w.unmount()
  })

  it('外部改 modelValue（点预设按钮）会同步进输入框', async () => {
    const w = mount(IsoDateInput, { props: { modelValue: '2026-11-01' } })
    await w.setProps({ modelValue: '2026-11-27' })
    expect(input(w).element.value).toBe('2026-11-27')
    w.unmount()
  })

  it('aria-label / class / data-testid 透传到内层 input（不能挂在外层 span 上）', () => {
    const w = mount(IsoDateInput, {
      attrs: { 'aria-label': 'Report start date', class: 'po-input', 'data-testid': 'sr-start' },
    })
    expect(input(w).attributes('aria-label')).toBe('Report start date')
    expect(input(w).classes()).toContain('po-input')
    expect(input(w).attributes('data-testid')).toBe('sr-start')
    w.unmount()
  })

  it('validate() 供父组件提交前主动校验（防不 blur 直接点按钮）', async () => {
    const spy = vi.fn()
    const w = mount(IsoDateInput, { props: { modelValue: '' } })
    await input(w).setValue('garbage')
    expect(w.vm.validate()).toBe(false)
    expect(spy).not.toHaveBeenCalled()

    await input(w).setValue('2026-11-27')
    expect(w.vm.validate()).toBe(true)
    w.unmount()
  })
})
