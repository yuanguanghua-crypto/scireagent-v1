/**
 * `ProductCard` 的「可售 / 不可售」两态 —— A-258 的前端契约（2026-11-18）。
 *
 * ## 为什么必须锁这一条
 * 收藏夹里会残留「先被收藏、后被下架」的商品：写入侧只拦「收藏**已归档**的商品」
 * （`queryset=Product.objects.filter(archived=False)`），拦不住「收藏**之后**才归档」。
 * 这类商品原本渲染成与在售完全一样的卡片，而 `retrieve` 对非 staff 的 archived 行抛 404
 * ⇒ 用户点进去得到一个 404，还以为站点坏了。
 *
 * ## 为什么断言「根节点是 div 而不是 a」
 * `pointer-events: none` 是**假禁用**：键盘 Tab 仍能聚焦、回车仍会导航。
 * 真正的不可点只能是「根本不渲染成链接」。这条断言就是防止有人日后把它改回 CSS 禁用。
 *
 * ⚠️ 基线（不可售时**必须**同时满足）：
 *   1. 根元素 tag = `div`（`<a>` 数量为 0）
 *   2. `aria-disabled="true"`
 *   3. 标题角标 = `Unavailable`，且**不再**渲染库存标签（`In Stock` 会误导）
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import ProductCard from '../ProductCard.vue'

const Blank = { template: '<div />' }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Blank },
      { path: '/products/:id', component: Blank },
    ],
  })
}

const PRODUCT = {
  id: 42,
  slug: 'atp-lithium-salt',
  name: 'ATP Lithium Salt',
  catalog_no: 'SC8042',
  cas: '51963-61-2',
  status: 'active',
  archived: false,
  inventory_status: 'in_stock',
  formula: 'C10H14N5O13P3Li',
  sku_summary: { count: 1, price_range: { min: '71.00', max: '71.00' } },
}

async function mountIt(productOverrides = {}, extraProps = {}) {
  const router = makeRouter()
  router.push('/')
  await router.isReady()
  return mount(ProductCard, {
    props: { product: { ...PRODUCT, ...productOverrides }, ...extraProps },
    global: { plugins: [ElementPlus, router] },
  })
}

describe('ProductCard 可售态（默认，不可回归）', () => {
  it('根节点是 <a>，href 指向 /products/:slug', async () => {
    const w = await mountIt()
    const root = w.find('[data-testid="product-card"]')
    expect(root.element.tagName).toBe('A')
    expect(root.attributes('href')).toContain('/products/atp-lithium-salt')
    w.unmount()
  })

  it('渲染库存标签而不是 Unavailable', async () => {
    const w = await mountIt()
    expect(w.text()).toContain('In Stock')
    expect(w.find('[data-testid="product-unavailable-badge"]').exists()).toBe(false)
    w.unmount()
  })

  it('没有 slug 时回退用 id 拼链接', async () => {
    const w = await mountIt({ slug: null })
    expect(w.find('[data-testid="product-card"]').attributes('href')).toContain('/products/42')
    w.unmount()
  })
})

describe('ProductCard 不可售态（A-258）', () => {
  it('根节点是 <div> —— 不渲染任何 <a>（真禁用，不是 pointer-events:none）', async () => {
    const w = await mountIt({ status: 'archived' }, { unavailable: true })
    const root = w.find('[data-testid="product-card"]')
    expect(root.element.tagName).toBe('DIV')
    expect(w.findAll('a').length).toBe(0)
    w.unmount()
  })

  it('带 aria-disabled="true"（读屏器能知道它不可用）', async () => {
    const w = await mountIt({ status: 'archived' }, { unavailable: true })
    expect(w.find('[data-testid="product-card"]').attributes('aria-disabled')).toBe('true')
    w.unmount()
  })

  it('角标显示 Unavailable，且不再显示 In Stock', async () => {
    const w = await mountIt({ status: 'archived' }, { unavailable: true })
    expect(w.find('[data-testid="product-unavailable-badge"]').text()).toBe('Unavailable')
    expect(w.text()).not.toContain('In Stock')
    w.unmount()
  })

  it('产品名与货号照常渲染（下架不等于信息消失）', async () => {
    const w = await mountIt({ status: 'archived' }, { unavailable: true })
    expect(w.text()).toContain('ATP Lithium Salt')
    expect(w.text()).toContain('SC8042')
    w.unmount()
  })
})
