/**
 * `AppInput` 组件单测 —— 重点钉住 a11y 的 `label[for] ↔ input[id]` 关联。
 *
 * ## 背景（2026-10-20 修的那批 a11y）
 * 这个组件有 **39 个实例**。修之前 `label` 没有 `for`、`el-input` 没有 `id`
 * ⇒ 屏幕阅读器关联不上、`getByLabel()` 也定位不到（E2E 只能靠脆弱的 placeholder）。
 *
 * ## 这段注释是**本文件最大的价值**：它记下了一次"以为修好了、其实没修"（2026-10-21 单测发现）
 * 10-20 那版给 `el-input` 加 `:id`、给 `<label>` 加 `:for`，**看起来**就关联上了。
 * 但实测 Element Plus 的 `el-input` **会吞掉 `id`**：内部 `<input>` 没有 id，`.el-input` 根 div 也没有
 * ⇒ `<label for="v-0">` 指向不存在的元素 = 孤儿 label，无障碍关联根本没生效。
 * 同一组对照实验：`aria-label` / `name` / `data-*` / `placeholder` **都能**透传到内部 input，唯独 `id` 不能。
 * ⇒ 正确修法是 **aria-label**（本文件下方断言它），并**保留一条"id 不透传"的事实断言**：
 *   哪天 EP 开始透传 id，那条会红，提示我们"可以改回 id 路线了"。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import AppInput from '../AppInput.vue'

const mountIt = (props = {}) =>
  mount(AppInput, { props: { modelValue: '', ...props }, global: { plugins: [ElementPlus] } })

describe('AppInput', () => {
  it('label 文案渲染出来（视觉标签）', () => {
    const w = mountIt({ label: 'Product Name' })
    expect(w.find('label').text()).toBe('Product Name')
    w.unmount()
  })

  it('★ a11y 关联走 aria-label：内部 input 的 aria-label === label 文案', () => {
    const w = mountIt({ label: 'Product Name' })
    expect(w.find('input').attributes('aria-label')).toBe('Product Name')
    w.unmount()
  })

  it('无 label 时退化到 placeholder 作 aria-label', () => {
    const w = mountIt({ placeholder: 'Search...' })
    expect(w.find('input').attributes('aria-label')).toBe('Search...')
    w.unmount()
  })

  it('label 与 placeholder 都没有时不给 aria-label（避免空名污染）', () => {
    const w = mountIt({})
    expect(w.find('input').attributes('aria-label')).toBeUndefined()
    w.unmount()
  })

  it('★ 事实断言：EP 的 el-input **不透传 id**（若此条变红，说明 EP 行为变了、可改回 id 路线）', () => {
    const w = mountIt({ label: 'X' })
    expect(w.find('input').attributes('id')).toBeUndefined()
    w.unmount()
  })

  it('不再渲染 label[for]（避免指向不存在元素造成孤儿 label）', () => {
    const w = mountIt({ label: 'X' })
    expect(w.find('label').attributes('for')).toBeUndefined()
    w.unmount()
  })

  it('两个实例的 aria-label 各自独立（同页不会串台）', () => {
    const a = mountIt({ label: 'A' })
    const b = mountIt({ label: 'B' })
    expect(a.find('input').attributes('aria-label')).toBe('A')
    expect(b.find('input').attributes('aria-label')).toBe('B')
    a.unmount(); b.unmount()
  })

  it('没有 label 时不渲染 label 节点', () => {
    const w = mountIt({ placeholder: 'x' })
    expect(w.find('label').exists()).toBe(false)
    w.unmount()
  })

  it('placeholder 透传到内部 input', () => {
    const w = mountIt({ placeholder: 'Search...' })
    expect(w.find('input').attributes('placeholder')).toBe('Search...')
    w.unmount()
  })

  it('error 时渲染 .form-error，并给根元素加 --error 类', () => {
    const w = mountIt({ error: 'Required' })
    expect(w.find('.form-error').text()).toBe('Required')
    expect(w.classes()).toContain('app-input--error')
    w.unmount()
  })

  it('hint 只在无 error 时显示（两者互斥，避免同时显示矛盾提示）', () => {
    const withHint = mountIt({ hint: 'max 50 chars' })
    expect(withHint.find('.form-hint').text()).toBe('max 50 chars')
    withHint.unmount()

    const both = mountIt({ hint: 'max 50 chars', error: 'Required' })
    expect(both.find('.form-hint').exists()).toBe(false)
    expect(both.find('.form-error').exists()).toBe(true)
    both.unmount()
  })

  it('输入触发 update:modelValue（受控组件的双向绑定）', async () => {
    const w = mountIt()
    await w.find('input').setValue('hello')
    const ev = w.emitted('update:modelValue')
    expect(ev).toBeTruthy()
    expect(ev[0][0]).toBe('hello')
    w.unmount()
  })

  it('modelValue 反映到内部 input 显示', () => {
    const w = mountIt({ modelValue: 'XyZ' })
    expect(w.find('input').element.value).toBe('XyZ')
    w.unmount()
  })

  it('type="textarea" 渲染成 textarea 而非 input', () => {
    const w = mountIt({ type: 'textarea' })
    expect(w.find('textarea').exists()).toBe(true)
    w.unmount()
  })
})
