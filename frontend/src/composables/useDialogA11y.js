import { nextTick, onBeforeUnmount, watch } from 'vue'

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'textarea:not([disabled])',
  'input:not([disabled]):not([type="hidden"])', 'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * 为自定义 .dialog-overlay/.dialog 弹窗统一接入无障碍能力：
 *   - ARIA：dialog 容器加 role="dialog" aria-modal="true" aria-labelledby
 *   - ESC 关闭：按 Esc 调用 close()
 *   - focus 管理：打开时聚焦弹窗内首个可聚焦元素；关闭时还原焦点到触发元素
 *   - focus trap：Tab/Shift+Tab 在弹窗内循环，不跳到背后表单
 *
 * 不封装 AppDialog 组件——保持纯 CSS + template 路线。
 * 用法：
 *   const overlayRef = ref(null)
 *   useDialogA11y(showRef, overlayRef, { titleId: 'publish-title', close: () => showRef.value = false })
 *   <div v-if="show" ref="overlayRef" class="dialog-overlay" ...>
 *     <div class="dialog"><h3 id="publish-title">...</h3></div>
 *   </div>
 *
 * @param {import('vue').Ref<boolean>} openRef  控制弹窗显隐的 ref
 * @param {import('vue').Ref<HTMLElement|null>} overlayRef  指向 .dialog-overlay 元素的 ref
 * @param {{ titleId?: string, close: () => void }} opts
 */
export function useDialogA11y(openRef, overlayRef, opts) {
  const { close } = opts
  let lastFocused = null

  function getFocusable() {
    const overlay = overlayRef.value
    if (!overlay) return []
    return Array.from(overlay.querySelectorAll(FOCUSABLE))
      .filter(el => el.offsetParent !== null || el === document.activeElement)
  }

  function onKeydown(e) {
    if (!openRef.value) return
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
      return
    }
    if (e.key === 'Tab') {
      const focusable = getFocusable()
      if (!focusable.length) {
        e.preventDefault()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (e.shiftKey) {
        if (active === first || !overlayRef.value.contains(active)) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (active === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
  }

  function bind() {
    document.addEventListener('keydown', onKeydown, true)
  }
  function unbind() {
    document.removeEventListener('keydown', onKeydown, true)
  }

  watch(openRef, async (open) => {
    if (open) {
      lastFocused = document.activeElement
      bind()
      await nextTick()
      const focusable = getFocusable()
      if (focusable.length) focusable[0].focus()
      else overlayRef.value?.focus()
    } else {
      unbind()
      if (lastFocused && typeof lastFocused.focus === 'function') {
        lastFocused.focus()
        lastFocused = null
      }
    }
  })

  onBeforeUnmount(unbind)

  // 直接返回 attrs 对象，供模板 v-bind="dialogAttrs" 展开成单属性
  return opts.titleId
    ? { role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': opts.titleId, tabindex: '-1' }
    : { role: 'dialog', 'aria-modal': 'true', tabindex: '-1' }
}
