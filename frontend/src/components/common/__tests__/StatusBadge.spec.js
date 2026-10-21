/**
 * `StatusBadge` 组件单测 —— 状态→颜色的映射与本项目最常用的展示组件。
 *
 * 它被 20+ 页面用于展示订单/产品/发票状态，一旦映射写错（或 fallback 丢了），
 * 全站徽章会变成同一种灰 —— 而 E2E 只断言"文案对"，**看不出颜色错**。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '../StatusBadge.vue'

/**
 * 取圆点背景色（小写化便于比较）。
 * ⚠️ happy-dom **不做颜色规范化**：`background: #F59E0B` 会原样保留 hex，
 * 不像真浏览器那样变成 `rgb(245, 158, 11)` ⇒ 断言必须按 **hex** 写（初版按 rgb 写，3 条全红）。
 */
const dotBg = (w) => (w.find('.po-badge-dot').attributes('style') || '').toLowerCase()

describe('StatusBadge', () => {
  it('渲染根类 po-badge（E2E 的 `.po-badge` 选择器依赖它）', () => {
    const w = mount(StatusBadge, { props: { status: 'confirmed' } })
    expect(w.classes()).toContain('po-badge')
    w.unmount()
  })

  it('已知状态用语义色（po_received → amber #F59E0B）', () => {
    const w = mount(StatusBadge, { props: { status: 'po_received' } })
    expect(dotBg(w)).toContain('#f59e0b')
    w.unmount()
  })

  it('dotColor 优先级最高（覆盖状态映射）', () => {
    const w = mount(StatusBadge, { props: { status: 'paid', dotColor: '#123456' } })
    expect(dotBg(w)).toContain('#123456')
    w.unmount()
  })

  it('未知状态落到兜底灰 #9CA3AF（不会渲染成透明/无背景）', () => {
    const w = mount(StatusBadge, { props: { status: 'no-such-status' } })
    expect(dotBg(w)).toContain('#9ca3af')
    w.unmount()
  })

  it('label 优先于 status 转换结果', () => {
    const w = mount(StatusBadge, { props: { status: 'paid', label: '已付款' } })
    expect(w.text()).toContain('已付款')
    expect(w.text()).not.toContain('Paid')
    w.unmount()
  })

  it('无 label 时把 status 转成 Title Case（下划线变空格）', () => {
    const w = mount(StatusBadge, { props: { status: 'quote_pending' } })
    expect(w.text()).toContain('Quote Pending')
    w.unmount()
  })

  it('status 为空时仍渲染（不崩），文案为空', () => {
    const w = mount(StatusBadge, { props: { status: '' } })
    expect(w.find('.po-badge').exists()).toBe(true)
    expect(w.find('.po-badge-dot').exists()).toBe(true)
    w.unmount()
  })
})
