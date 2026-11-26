/**
 * useConfirm / ConfirmHost 单测（S4 丙族）
 *
 * 覆盖点都是**踩过或极易踩**的：
 *  1. ask 返回 Promise，且未结算前一直 pending（若宿主缺失，调用方会静默卡死）
 *  2. confirm → true / cancel → false
 *  3. settle 幂等（AppDialog 在点遮罩时会先 emit update:visible 再 emit cancel，
 *     两条路径都会结算；不幂等就会把队列推进两步）
 *  4. 并发排队：第二个 ask 不能覆盖第一个，必须等第一个结算
 *  5. 危险等级透传
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import {
  askConfirm, askText, settleConfirm, confirmState, __resetConfirmForTest,
} from '@/composables/useConfirm'
import ConfirmHost from '@/components/common/ConfirmHost.vue'

beforeEach(() => {
  __resetConfirmForTest()
})

describe('useConfirm 状态机', () => {
  it('ask 后状态置为可见并带上文案', async () => {
    const p = askConfirm({ title: '停用账号', message: '确定？', confirmText: '停用' })
    expect(confirmState.visible).toBe(true)
    expect(confirmState.title).toBe('停用账号')
    expect(confirmState.message).toBe('确定？')
    expect(confirmState.confirmText).toBe('停用')
    settleConfirm(true)
    await p
  })

  it('未结算前 Promise 保持 pending', async () => {
    let done = false
    askConfirm({ message: 'x' }).then(() => { done = true })
    await Promise.resolve()
    await Promise.resolve()
    expect(done).toBe(false)
    settleConfirm(false)
    await Promise.resolve()
  })

  it('confirm → true，cancel → false', async () => {
    const p1 = askConfirm({ message: 'a' })
    settleConfirm(true)
    await expect(p1).resolves.toBe(true)

    const p2 = askConfirm({ message: 'b' })
    settleConfirm(false)
    await expect(p2).resolves.toBe(false)
  })

  it('settle 幂等：连调两次只结算一次，且不误推进队列', async () => {
    const p1 = askConfirm({ message: 'first' })
    const p2 = askConfirm({ message: 'second' }) // 排队
    expect(confirmState.message).toBe('first')

    settleConfirm(true)
    await expect(p1).resolves.toBe(true)
    // 队列已推进到第二个
    expect(confirmState.visible).toBe(true)
    expect(confirmState.message).toBe('second')

    // 模拟 AppDialog 的「update:visible=false → cancel」重复触发
    settleConfirm(false)
    settleConfirm(false)

    await expect(p2).resolves.toBe(false)
    expect(confirmState.visible).toBe(false)
  })

  it('并发排队：第二个 ask 不覆盖第一个', async () => {
    const p1 = askConfirm({ message: 'first', danger: false })
    const p2 = askConfirm({ message: 'second', danger: true })

    expect(confirmState.message).toBe('first')
    expect(confirmState.danger).toBe(false)

    settleConfirm(true)
    await expect(p1).resolves.toBe(true)

    expect(confirmState.message).toBe('second')
    expect(confirmState.danger).toBe(true)

    settleConfirm(true)
    await expect(p2).resolves.toBe(true)
  })

  it('无参数时用默认文案，不抛错', async () => {
    const p = askConfirm()
    expect(confirmState.title).toBe('请确认')
    expect(confirmState.confirmText).toBe('Confirm')
    settleConfirm(false)
    await expect(p).resolves.toBe(false)
  })

  it('结算后清空 visible，避免遮罩残留挡住页面', async () => {
    const p = askConfirm({ message: 'x' })
    expect(confirmState.visible).toBe(true)
    settleConfirm(true)
    await p
    expect(confirmState.visible).toBe(false)
  })
})

describe('ConfirmHost', () => {
  it('渲染消息并把「确认」点击转成 true', async () => {
    const wrapper = mount(ConfirmHost, { attachTo: document.body })
    const p = askConfirm({ title: 'T', message: '要删吗？', confirmText: '删除', danger: true })
    await wrapper.vm.$nextTick()

    expect(document.body.textContent).toContain('要删吗？')
    expect(document.body.textContent).toContain('删除')

    // ★ 用 testid 而非文本：一度把 data-testid 挂在 <AppDialog>（Teleport 根）上，
    //   被 Vue 静默丢弃，只剩一条 warning —— 那种"选择器永远匹配不到"的坑
    //   靠文本断言掩盖不了。这里必须断言 testid 真的在 DOM 里。
    const confirmBtn = document.querySelector('[data-testid="confirm-ok"]')
    expect(confirmBtn).toBeTruthy()
    expect(confirmBtn.textContent.trim()).toBe('删除')
    confirmBtn.click()

    await expect(p).resolves.toBe(true)
    wrapper.unmount()
  })

  it('取消按钮返回 false', async () => {
    const wrapper = mount(ConfirmHost, { attachTo: document.body })
    const p = askConfirm({ message: '要删吗？', cancelText: '算了' })
    await wrapper.vm.$nextTick()

    const cancelBtn = document.querySelector('[data-testid="confirm-cancel"]')
    expect(cancelBtn).toBeTruthy()
    expect(cancelBtn.textContent.trim()).toBe('算了')
    cancelBtn.click()

    await expect(p).resolves.toBe(false)
    wrapper.unmount()
  })

  it('消息里的 \\n 分段不会被吞（white-space: pre-line 的前提）', async () => {
    const wrapper = mount(ConfirmHost, { attachTo: document.body })
    const p = askConfirm({ message: '第一行\n\n第二行' })
    await wrapper.vm.$nextTick()

    const msg = document.querySelector('[data-testid="confirm-message"]')
    expect(msg.textContent).toContain('第一行')
    expect(msg.textContent).toContain('第二行')
    // 换行必须保留在文本节点里，否则 pre-line 也无从渲染
    expect(msg.textContent.includes('\n')).toBe(true)

    settleConfirm(false)
    await expect(p).resolves.toBe(false)
    wrapper.unmount()
  })
})

/* ───────────────────────── askText（A-116 同轮 / `window.prompt` 替代） ─────────────────────────
 *
 * 核心判据只有一条，但它是**整个替换的理由**：
 *   原生 prompt 取消返回 `null`，而两处旧调用方写的是
 *   `window.prompt(...) || ''` / `?? ''` ⇒ **取消被压成空串，动作照样执行**
 *   （拒绝付款凭证 / 拒绝 verified 结论 —— 点取消反而拒了）。
 * 所以 `null`（取消）与 `''`（确认但留空）必须能被调用方区分开。
 */
describe('askText：取消与留空必须可区分', () => {
  it('★ 取消 ⇒ null（不是空串）', async () => {
    const p = askText({ message: 'reject?' })
    settleConfirm(false)
    await expect(p).resolves.toBe(null)
  })

  it('确认且没输入 ⇒ 空串（照常执行，只是没有理由）', async () => {
    const p = askText({ message: 'reject?' })
    settleConfirm(confirmState.inputValue)
    await expect(p).resolves.toBe('')
  })

  it('确认并输入 ⇒ 原样返回该字符串', async () => {
    const p = askText({ message: 'reject?', defaultValue: 'wrong amount' })
    settleConfirm(confirmState.inputValue)
    await expect(p).resolves.toBe('wrong amount')
  })

  it('defaultValue 预填到输入框', () => {
    askText({ message: 'x', defaultValue: '预填内容' })
    expect(confirmState.inputValue).toBe('预填内容')
    settleConfirm(false)
  })

  it('文本模式下 mode 为 text，确认模式仍是 confirm（互不串台）', async () => {
    const p1 = askConfirm({ message: 'confirm one' })
    expect(confirmState.mode).toBe('confirm')
    const p2 = askText({ message: 'text one' })     // 排队
    settleConfirm(true)
    await expect(p1).resolves.toBe(true)
    // 队列推进后必须是文本模式，且输入框已按新参数重置
    expect(confirmState.mode).toBe('text')
    settleConfirm(false)
    await expect(p2).resolves.toBe(null)
  })

  it('★ 文本模式按 Esc/遮罩（settle false）不得退化成空串', async () => {
    const p = askText({ message: 'x', defaultValue: '已填了一半' })
    settleConfirm(false)
    await expect(p).resolves.toBe(null)
  })

  it('ConfirmHost 文本模式渲染输入框，点确认返回输入值', async () => {
    const wrapper = mount(ConfirmHost, { attachTo: document.body })
    const p = askText({ message: 'why?', placeholder: 'Optional reason…' })
    await wrapper.vm.$nextTick()

    const input = document.querySelector('[data-testid="confirm-input"]')
    expect(input, '★ askText 没有渲染输入框 ⇒ 退化成只能确认/取消').toBeTruthy()
    expect(input.getAttribute('placeholder')).toBe('Optional reason…')
    input.value = 'duplicate payment'
    input.dispatchEvent(new Event('input'))
    await wrapper.vm.$nextTick()

    document.querySelector('[data-testid="confirm-ok"]').click()
    await expect(p).resolves.toBe('duplicate payment')
    wrapper.unmount()
  })

  it('确认模式不渲染输入框（别让普通确认框多出一个空输入）', async () => {
    const wrapper = mount(ConfirmHost, { attachTo: document.body })
    const p = askConfirm({ message: 'sure?' })
    await wrapper.vm.$nextTick()
    expect(document.querySelector('[data-testid="confirm-input"]')).toBeNull()
    settleConfirm(true)
    await p
    wrapper.unmount()
  })
})
