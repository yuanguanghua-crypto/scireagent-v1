/**
 * useConfirm —— 页内确认对话框（替代 `window.confirm`）
 *
 * 为什么不用 `window.confirm`（2026-11-18 S4 实测归纳，四条都不是审美问题）：
 *   1. **阻塞主线程**：原生 confirm 弹出期间整个页面 JS 停摆，任何在途的
 *      loading / 轮询 / 过渡动画全部冻结。在本项目的「列表 + 行内按钮」场景里，
 *      用户点确认的瞬间其它按钮的 loading 态会僵在屏幕上。
 *   2. **不可样式化、不可本地化**：按钮文案由浏览器语言决定（中文系统上是
 *      「确定/取消」），而页面其余部分是中英混排的具体业务词语（「停用」
 *      「丢弃」）。同一个动作在两处叫两个名字，是操作语义的失真。
 *   3. **无法表达危险等级**：停用账号、丢弃待发邮件、发布对外合规结论
 *      这类不可逆动作，需要视觉上的危险色与「不可撤销」的措辞提示。
 *   4. **无痕、不可测**：原生弹框不进 DOM，e2e 与单测都断言不到，
 *      只能靠 `page.on('dialog')` 旁路 —— 那测的是"弹了框"，不是
 *      "取消后确实没写入"。
 *
 * 用法（**必须先有 `<ConfirmHost />` 在 App 根挂载**）：
 *   const { ask } = useConfirm()
 *   if (!(await ask({ title: '停用账号', message: '…', confirmText: '停用', danger: true }))) return
 *
 * 返回 Promise<boolean>：确认 → true；取消 / Esc / 点遮罩 → false。
 * 因此所有 `if (window.confirm(x)) doThing()` 都能一对一替换成
 * `if (await ask({...})) doThing()`，控制流不变。
 *
 * 并发：同一时刻只渲染一个对话框，后到的 ask 排队。这样即使用户连点两个
 * 危险按钮，也不会出现两个弹框叠在一起、第二个的 Promise 永远悬挂。
 */
import { reactive } from 'vue'

const DEFAULTS = {
  title: '请确认',
  message: '',
  confirmText: 'Confirm',
  cancelText: 'Cancel',
  danger: false,
}

// Host 渲染用的状态（只读语义，只由本模块与 settle 改写）
//
// ★ 2026-11-18（S4）：新增 `mode` —— 支持「文本输入」形态（`askText`），
//   用来替代 `window.prompt`。为什么要替代：原生 prompt 与 confirm 是同一批毛病
//   （阻塞主线程、不可样式化、不可测），但**更致命的一点**是它**取消时返回 `null`**，
//   而既有的两处调用方写的是 `window.prompt(...) || ''` / `?? ''`
//   ⇒ 取消与"留空确认"被压成同一个空串，**点取消反而会执行那个动作**
//   （拒绝付款凭证、拒绝 verified 结论）。`askText` 用 `null` 表示取消、
//   `''` 表示"确认但不填理由"，调用方才能把两者分开。
export const confirmState = reactive({
  ...DEFAULTS,
  visible: false,
  mode: 'confirm',      // 'confirm' | 'text'
  inputValue: '',
  placeholder: '',
})

let resolver = null
const queue = []

function present(opts) {
  const merged = { ...DEFAULTS, ...(opts || {}) }
  confirmState.title = merged.title
  confirmState.message = merged.message
  confirmState.confirmText = merged.confirmText
  confirmState.cancelText = merged.cancelText
  confirmState.danger = !!merged.danger
  confirmState.mode = merged.mode === 'text' ? 'text' : 'confirm'
  confirmState.inputValue = merged.defaultValue || ''
  confirmState.placeholder = merged.placeholder || ''
  confirmState.visible = true
}

/**
 * 弹出确认框。必须 `await`；返回布尔。
 * @param {{title?:string,message?:string,confirmText?:string,cancelText?:string,danger?:boolean}} opts
 * @returns {Promise<boolean>}
 */
export function askConfirm(opts) {
  return new Promise((resolve) => {
    if (resolver) {
      // 已有对话框在等 ⇒ 排队，等前一个结算后再present
      queue.push({ opts, resolve })
      return
    }
    resolver = resolve
    present(opts)
  })
}

/**
 * 弹出**带文本输入**的框（替代 `window.prompt`）。必须 `await`。
 *
 * 返回值语义（关键，别合并）：
 *   · `null`  ⇒ 用户取消 / Esc / 点遮罩 —— 调用方必须**什么都不做**；
 *   · `''`    ⇒ 用户确认但没填内容 —— 调用方照常执行，只是没有备注；
 *   · `'...'` ⇒ 用户确认并填了内容。
 *
 * @param {{title?:string,message?:string,placeholder?:string,defaultValue?:string,
 *          confirmText?:string,cancelText?:string,danger?:boolean}} opts
 * @returns {Promise<string|null>}
 */
export function askText(opts) {
  const withMode = { ...(opts || {}), mode: 'text' }
  return new Promise((resolve) => {
    if (resolver) {
      queue.push({ opts: withMode, resolve })
      return
    }
    resolver = resolve
    present(withMode)
  })
}

/**
 * 结算当前对话框。**幂等** —— 因为 `AppDialog` 在点遮罩/关闭按钮时
 * 会先 emit `update:visible=false` 再 emit `cancel`，两条路径都会调到这里；
 * 不做幂等就会 resolve 两次（第二次静默无效，但会把队列推进两步）。
 */
export function settleConfirm(result) {
  if (!resolver) return
  const done = resolver
  const wasText = confirmState.mode === 'text'
  resolver = null
  confirmState.visible = false
  // 文本模式：false/undefined/null 一律归为「取消」`null`，绝不退化成空串 ——
  // 否则调用方拿 `''` 继续执行，又回到 `window.prompt(...) || ''` 那个老坑。
  if (wasText) done(result === false || result == null ? null : String(result))
  else done(!!result)
  const next = queue.shift()
  if (next) {
    resolver = next.resolve
    present(next.opts)
  }
}

/** 供页面使用的最简接口 */
export function useConfirm() {
  return { ask: askConfirm, askText }
}

/** 仅供单测重置模块级状态 */
export function __resetConfirmForTest() {
  resolver = null
  queue.length = 0
  Object.assign(confirmState, { ...DEFAULTS, visible: false, mode: 'confirm', inputValue: '', placeholder: '' })
}
