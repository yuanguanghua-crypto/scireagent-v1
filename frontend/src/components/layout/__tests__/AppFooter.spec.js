/**
 * ★ 2026-11-27（A-105 / A-106）页脚回归锁。
 *
 * A-105（P1）：页脚 Documentation / API Reference / Support 三个链接的 href 全是 `#`
 *   —— 点 Documentation 页面与 URL 都不动。仓库里没有 /docs、/api-reference、/support
 *   任何路由，这三项是**永久死链**，已删除。本测试锁住「页脚链接必须指向真实路由」。
 *
 * A-106（P1）：页面上叠了**两个**页脚 —— AppLayout 里的 AppFooter（深色、
 *   "SciReagent"、三项 `#` 链接）与 App.vue 里的 `.site-footer`（浅色、
 *   "SciReAgent"、Privacy/Terms）。两者品牌拼写还不一样。
 *   现在页脚只由 AppFooter 承担，App.vue 不再渲染 `<footer>`。本测试锁住这两点：
 *     ① App.vue 源码里不出现 `<footer`（防止双页脚回归）；
 *     ② 页脚品牌只写 "SciReagent"（仓库主流写法：SITE_NAME / index.html / og:* 共 19 处）。
 *
 * 注：QA 报的「About 页眉 ABOUT SCIREAGENT 拼写不一致」经核为**误判** ——
 * `'SciReagent'.toUpperCase() === 'SCIREAGENT'` 与 `'SciReAgent'.toUpperCase()` 同形，
 * 大写形态无法区分两者，故不是缺陷，本测试也不再对大写形态做约束。
 */
import { describe, it, expect } from 'vitest'
import { mount, RouterLinkStub } from '@vue/test-utils'
import AppFooter from '@/components/layout/AppFooter.vue'
import appSource from '@/App.vue?raw'

function mountFooter() {
  return mount(AppFooter, { global: { stubs: { RouterLink: RouterLinkStub } } })
}

describe('AppFooter（A-105 / A-106）', () => {
  it('品牌写法与全站一致：只有 SciReagent，没有 SciReAgent', () => {
    const text = mountFooter().text()
    expect(text).toContain('SciReagent')
    expect(text).not.toContain('SciReAgent')
  })

  it('版权年份取当前年', () => {
    expect(mountFooter().text()).toContain(String(new Date().getFullYear()))
  })

  it('页脚不出现已删除的三个死链文案', () => {
    const text = mountFooter().text()
    expect(text).not.toContain('Documentation')
    expect(text).not.toContain('API Reference')
    expect(text).not.toContain('Support')
  })

  it('页脚里没有指向 "#" 的死链（A-105 回归锁）', () => {
    // 死链有两种形态：`<a href="#">` 与「根本不是链接」的假入口。
    // 这里锁住两件事：不存在 href="#" 的锚点，且页脚里的可点项全部是 RouterLink。
    const w = mountFooter()
    expect(w.findAll('a[href="#"]')).toHaveLength(0)
    const anchors = w.findAll('a')
    const routerLinks = w.findAllComponents(RouterLinkStub)
    expect(anchors.length).toBe(routerLinks.length)
  })

  it('页脚每个链接都指向真实路由（且不是 "#"）', () => {
    const tos = mountFooter()
      .findAllComponents(RouterLinkStub)
      .map((c) => c.props('to'))
    expect(tos.length).toBeGreaterThan(0)
    for (const to of tos) {
      expect(typeof to).toBe('string')
      expect(to).not.toBe('#')
      expect(to).toMatch(/^\//)
    }
  })

  it('页脚链接集合就是隐私政策与条款两项', () => {
    const tos = mountFooter()
      .findAllComponents(RouterLinkStub)
      .map((c) => c.props('to'))
    expect(tos).toEqual(['/privacy', '/terms'])
  })

  it('App.vue 不再渲染第二个页脚（A-106 双页脚回归锁）', () => {
    // 只认标签本身；注释里提到 `<footer>` 的历史说明不算
    const withoutComments = appSource.replace(/<!--[\s\S]*?-->/g, '')
    expect(withoutComments).not.toMatch(/<footer[\s>]/)
  })
})
