/**
 * 购物车 / 结账 5 条修复的回归锁（S7 购物车桶，2026-11-27）。
 *
 * | 编号 | 病 | 这里锁什么 |
 * |---|---|---|
 * | A-143 | /cart 商品名是纯文本 h3，点了不动 | 名称必须是 RouterLink，且指向 `/products/<slug>` |
 * | A-143 连带 | 序列化器字段是 `product_cas`，页面读 `item.cas` ⇒ CAS 标签从没渲染过 | CAS 标签按 `product_cas` 出现 |
 * | A-178 | 商品行完全没有图 | 真结构式渲染缩略图；`Structure rendering requires…` 占位卡**不当图** |
 * | A-125 | 访客点 Place Order 被瞬移登录页、全程无解释 | 访客点击→提示 + 跳 `/login?redirect=/checkout`；按钮下常驻门槛说明 |
 * | A-135 | 结账摘要缺 SKU 与小计行 | 摘要出现 SKU 码与 Subtotal 行 |
 * | A-136 | 结账页 PO Number 预填上一张（甚至已取消）订单的 PO 号 | 资料里有 default_po_number 也不预填 |
 * | A-148 | 直接访问 /checkout 先闪「空购物车」 | loading 期间只出 LoadingSpinner，不出 EmptyState |
 *
 * ## 为什么 mock 到 store/api 这一层
 * 这些断言全部落在**页面如何消费数据**上（字段名、链接、空态分支），
 * 真实 store 会连带发请求，换不来额外信号；真正需要"真的跑一遍"的部分
 * 已用 dev 真机（msedge）逐条验过，见当日记忆。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { RouterLinkStub } from '@vue/test-utils'

const state = vi.hoisted(() => ({
  basket: null,
  authed: false,
  push: null,
  toast: null,
}))

vi.mock('@/stores/basket', () => ({ useBasketStore: () => state.basket }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ isAuthenticated: state.authed, user: null, role: '', organization: null }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: state.push }) }))
vi.mock('@/components/common', () => ({
  AppButton: {
    name: 'AppButton',
    props: ['variant', 'size', 'nativeType', 'loading'],
    emits: ['click'],
    template: '<button class="stub-btn" @click="$emit(\'click\')"><slot /></button>',
  },
  AppInput: {
    name: 'AppInput',
    props: ['modelValue', 'label', 'placeholder', 'type', 'rows', 'error'],
    emits: ['update:modelValue'],
    template:
      '<label class="stub-input"><span class="stub-label">{{ label }}</span>' +
      '<input :value="modelValue" :placeholder="placeholder" :type="type || \'text\'" ' +
      '@input="$emit(\'update:modelValue\', $event.target.value)" /></label>',
  },
  LoadingSpinner: { name: 'LoadingSpinner', template: '<div class="stub-loading"></div>' },
  EmptyState: {
    name: 'EmptyState',
    template: '<div class="stub-empty"><slot name="action" /></div>',
  },
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/api/orders', () => ({ checkout: vi.fn() }))
vi.mock('@/api/auth', () => ({ updateProfile: vi.fn(async () => ({})) }))

import { toast } from '@/components/common'
import CartPage from '@/views/CartPage.vue'
import CheckoutPage from '@/views/CheckoutPage.vue'

const REAL_SVG = '<svg viewBox="0 0 10 10"><path d="M0 0L10 10"/></svg>'
const PLACEHOLDER_SVG = '<svg viewBox="0 0 400 300"><text>Structure rendering requires RDKit.js</text></svg>'

function makeItem(over = {}) {
  return {
    id: 1,
    product: 27,
    product_name: 'Fluorescein-12-UTP',
    product_slug: 'sc8007-fluorescein-12-utp',
    product_cas: '134367-01-4',
    product_structure_svg: '',
    sku: 47,
    sku_code: 'SC8007-1',
    pack_size: '10 μL',
    unit_price: '99.00',
    currency: 'USD',
    quantity: 1,
    subtotal: '99.00',
    ...over,
  }
}

function basketStore({ items = [], loading = false } = {}) {
  const total = items.reduce((s, i) => s + Number(i.subtotal || 0), 0)
  return {
    items,
    loading,
    total: total ? total.toFixed(2) : '0.00',
    count: items.reduce((s, i) => s + i.quantity, 0),
    computedTotal: total,
    loadBasket: vi.fn(async () => {}),
    updateQuantity: vi.fn(),
    removeItem: vi.fn(),
    clearBasket: vi.fn(),
  }
}

function mountCart() {
  return mount(CartPage, {
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

function mountCheckout() {
  return mount(CheckoutPage, {
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

beforeEach(() => {
  state.push = vi.fn()
  state.authed = false
  vi.clearAllMocks()
})

describe('A-143 /cart 商品名可点回详情', () => {
  it('名称是 RouterLink 且指向产品 slug', () => {
    state.basket = basketStore({ items: [makeItem()] })
    const w = mountCart()
    // 锚点存在 ⇒ 确实是链接而不是纯文本；`to` 只能从组件 props 取
    // （RouterLinkStub 不写 href，DOMWrapper 也没有 props()）
    expect(w.find('.cart-item-name a').exists()).toBe(true)
    const link = w.findComponent(RouterLinkStub)
    expect(link.props('to')).toBe('/products/sc8007-fluorescein-12-utp')
  })

  it('没有 slug 时退回数字 id（不出现死链）', () => {
    state.basket = basketStore({ items: [makeItem({ product_slug: '' })] })
    const w = mountCart()
    expect(w.findComponent(RouterLinkStub).props('to')).toBe('/products/27')
  })

  it('CAS 标签读的是序列化器的 product_cas 字段', () => {
    state.basket = basketStore({ items: [makeItem()] })
    const tags = mountCart().findAll('.meta-tag').map((t) => t.text())
    expect(tags).toContain('CAS: 134367-01-4')
  })
})

describe('A-178 /cart 商品行缩略图', () => {
  it('真结构式 → 渲染 SVG', () => {
    state.basket = basketStore({ items: [makeItem({ product_structure_svg: REAL_SVG })] })
    const w = mountCart()
    expect(w.find('.cart-item-thumb-svg svg').exists()).toBe(true)
  })

  it('「Structure rendering requires…」占位卡不当图（只留中性图标）', () => {
    state.basket = basketStore({ items: [makeItem({ product_structure_svg: PLACEHOLDER_SVG })] })
    const w = mountCart()
    expect(w.find('.cart-item-thumb-svg').exists()).toBe(false)
    expect(w.find('.cart-item-thumb svg').exists()).toBe(true) // 图标仍在
    expect(w.find('.cart-item-thumb').text()).not.toContain('RDKit')
  })
})

describe('A-125 访客下单门槛要有说明', () => {
  it('访客点 Place Order → 先提示再跳登录页（带 redirect）', async () => {
    state.authed = false
    state.basket = basketStore({ items: [makeItem()] })
    const w = mountCart()
    const placeOrder = w.findAll('button').find((b) => b.text() === 'Place Order')
    await placeOrder.trigger('click')
    expect(toast.info).toHaveBeenCalled()
    expect(state.push).toHaveBeenCalledWith({ path: '/login', query: { redirect: '/checkout' } })
  })

  it('页面常驻一句门槛说明（访客可见、登录用户不显示）', () => {
    state.basket = basketStore({ items: [makeItem()] })
    state.authed = false
    expect(mountCart().find('.summary-note').exists()).toBe(true)

    state.authed = true
    expect(mountCart().find('.summary-note').exists()).toBe(false)
  })
})

describe('A-135 结账摘要要有 SKU 与小计行', () => {
  it('摘要行含 SKU 码，尾部有 Subtotal 与 Total', () => {
    state.basket = basketStore({ items: [makeItem()] })
    const w = mountCheckout()
    expect(w.find('.summary-item-sku').text()).toBe('SC8007-1')
    expect(w.find('.summary-subtotal').text()).toContain('Subtotal')
    expect(w.find('.summary-subtotal').text()).toContain('99.00')
    expect(w.find('.summary-total').text()).toContain('Total')
  })
})

describe('A-136 PO Number 不再预填', () => {
  it('即使资料里留着 default_po_number，PO 输入框初始为空', () => {
    state.basket = basketStore({ items: [makeItem()] })
    const w = mountCheckout()
    const po = w.find('input[placeholder="PO-2026-00123"]')
    expect(po.exists()).toBe(true)
    expect(po.element.value).toBe('')
  })
})

describe('A-148 /checkout 加载期不得先闪空购物车', () => {
  it('loading 中只出 LoadingSpinner，不出 EmptyState', () => {
    state.basket = basketStore({ items: [], loading: true })
    const w = mountCheckout()
    expect(w.find('.stub-loading').exists()).toBe(true)
    expect(w.find('.stub-empty').exists()).toBe(false)
  })

  it('加载完成且真的为空时才出 EmptyState', () => {
    state.basket = basketStore({ items: [], loading: false })
    const w = mountCheckout()
    expect(w.find('.stub-loading').exists()).toBe(false)
    expect(w.find('.stub-empty').exists()).toBe(true)
  })
})
