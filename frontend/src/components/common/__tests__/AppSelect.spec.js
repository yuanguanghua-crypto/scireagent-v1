/**
 * `AppSelect` 组件单测 —— 重点是 **aria-label 透传**。
 *
 * ## 为什么这个组件必须用 aria-label（而不是 id）
 * 2026-10-21 修 D7 时实测过：Element Plus 的 `el-select` **不把 `id` 透传到内部
 * `<input role="combobox">`**（跟 `el-input` 吞 id 是同一个坑，见 AppInput.spec.js），
 * 但 **`aria-label` 会透传**。当时就是靠这一条把 ProductNew 的 a11y critical 降为 0。
 * ⇒ 这里把"aria-label 的三级回退"钉死，防止有人把它简化掉。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import AppSelect from '../AppSelect.vue'

const mountIt = (props = {}) =>
  mount(AppSelect, {
    props: { modelValue: '', options: [{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }], ...props },
    global: { plugins: [ElementPlus] },
  })

const sel = (w) => w.findComponent({ name: 'ElSelect' })
/**
 * ★ 可访问名要读**内部 combobox**，不是 `ElSelect` 的 props：
 *   `aria-label` 是 **attr**（props() 读不到），而 EP 会把它透传到
 *   `<input role="combobox">` 上 —— 实测有效（这正是 D7 修复能生效的原因）。
 */
const comboAria = (w) => w.find('input[role="combobox"]').attributes('aria-label')

describe('AppSelect', () => {
  it('有 label 时 aria-label = label（最高优先级）', () => {
    const w = mountIt({ label: 'Product Class', placeholder: 'Pick one' })
    expect(comboAria(w)).toBe('Product Class')
    w.unmount()
  })

  it('无 label 时退化到 placeholder', () => {
    const w = mountIt({ placeholder: 'Pick one' })
    expect(comboAria(w)).toBe('Pick one')
    w.unmount()
  })

  it('两者都没有时仍有可访问名（★ 由 EP 的默认值提供，实测是 "Please select"）', () => {
    const w = mountIt({})
    expect(comboAria(w)).toBe('Please select')
    w.unmount()
  })

  it('options 渲染成对应数量的 el-option', () => {
    const w = mountIt({ options: [{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }, { label: 'C', value: 'c' }] })
    expect(w.findAllComponents({ name: 'ElOption' })).toHaveLength(3)
    w.unmount()
  })

  it('options 为空数组时不崩', () => {
    const w = mountIt({ options: [] })
    expect(w.findAllComponents({ name: 'ElOption' })).toHaveLength(0)
    w.unmount()
  })

  it('option 的 disabled 透传', () => {
    const w = mountIt({ options: [{ label: 'A', value: 'a', disabled: true }] })
    expect(w.findComponent({ name: 'ElOption' }).props('disabled')).toBe(true)
    w.unmount()
  })

  it('label 作为视觉标签渲染', () => {
    const w = mountIt({ label: 'Category' })
    expect(w.find('label.form-label').text()).toBe('Category')
    w.unmount()
  })

  it('error 时渲染 .form-error 且根加 --error 类；hint 被隐藏', () => {
    const w = mountIt({ error: 'Required', hint: 'pick one' })
    expect(w.find('.form-error').text()).toBe('Required')
    expect(w.classes()).toContain('app-select--error')
    expect(w.find('.form-hint').exists()).toBe(false)
    w.unmount()
  })

  it('change 事件向上抛（父组件靠它触发筛选）', async () => {
    const w = mountIt()
    sel(w).vm.$emit('change', 'a')
    await w.vm.$nextTick()
    expect(w.emitted('change')[0][0]).toBe('a')
    w.unmount()
  })
})
