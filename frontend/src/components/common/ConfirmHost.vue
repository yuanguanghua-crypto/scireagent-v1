<template>
  <!-- ★ 2026-11-18（S4 / 丙族）：全局唯一的确认框宿主。
       挂在 App 根，任何页面 `await ask(...)` 都复用这一个实例。
       没有它，`askConfirm()` 的 Promise 会永远悬挂 —— 调用方的后续代码
       （写库、发请求）既不会执行也不会报错，表现为"点了没反应"。

       ⚠️ 不要把 `data-testid` 挂在 `<AppDialog>` 上：它的根是 `<Teleport>`，
       Vue 会丢弃透传属性并只留一条 warning（实测），e2e 选择器会静默失效。
       所以 footer 用**具名插槽自渲染**两个按钮，testid 才真实落在 DOM 上。 -->
  <AppDialog
    :visible="confirmState.visible"
    :title="confirmState.title"
    :variant="confirmState.danger ? 'danger' : 'default'"
    title-id="confirm-dialog-title"
    @cancel="onCancel"
    @update:visible="onVisibleChange"
  >
    <p class="confirm-message" data-testid="confirm-message">{{ confirmState.message }}</p>

    <!-- ★ 2026-11-18（S4）：`askText` 的输入框 —— 替代 `window.prompt`。
         取消语义（`settleConfirm(false)` ⇒ resolve `null`）见 useConfirm.js 的注释：
         原生 prompt 取消返回 `null`，而旧调用方写 `|| ''` 把它压成空串，
         于是"点取消"反而执行了动作。 -->
    <input
      v-if="confirmState.mode === 'text'"
      ref="textInput"
      v-model="confirmState.inputValue"
      class="confirm-input"
      type="text"
      data-testid="confirm-input"
      :placeholder="confirmState.placeholder"
      @keyup.enter="onConfirm"
    />

    <template #footer>
      <AppButton
        variant="ghost"
        data-testid="confirm-cancel"
        @click="onCancel"
      >{{ confirmState.cancelText }}</AppButton>
      <AppButton
        :variant="confirmState.danger ? 'danger' : 'primary'"
        data-testid="confirm-ok"
        @click="onConfirm"
      >{{ confirmState.confirmText }}</AppButton>
    </template>
  </AppDialog>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import AppDialog from './AppDialog.vue'
import AppButton from './AppButton.vue'
import { confirmState, settleConfirm } from '@/composables/useConfirm'

const textInput = ref(null)

// 文本模式弹出来后自动聚焦 —— 否则用户得多点一次才开始打字（原生 prompt 是自动聚焦的，
// 少了这一步就是"换了个更差的交互"）。
watch(() => confirmState.visible, async (v) => {
  if (!v || confirmState.mode !== 'text') return
  await nextTick()
  textInput.value?.focus()
})

function onConfirm() {
  settleConfirm(confirmState.mode === 'text' ? confirmState.inputValue : true)
}

function onCancel() {
  // 文本模式由 settleConfirm 统一折算成 `null`（= 取消），调用方据此中止动作
  settleConfirm(false)
}

// 点遮罩 / 点右上角 × 都会走这里。`AppDialog` 的 emit 顺序是
// update:visible(false) → cancel，所以这里结算后 onCancel 会是空操作（settle 幂等）。
function onVisibleChange(v) {
  if (!v) settleConfirm(false)
}
</script>

<style scoped>
.confirm-message {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--color-text-secondary);
  /* 调用方常带 \n 分段的补充说明（如"这会绕过邮箱验证"），
     不保留换行会挤成一整段、丢掉强调效果。 */
  white-space: pre-line;
}
/* ★ 2026-11-18（S4）：`askText` 输入框 */
.confirm-input {
  display: block;
  width: 100%;
  margin-top: 12px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 6px);
  font-size: 14px;
  font-family: var(--font-sans);
  color: var(--color-text);
  background: var(--color-surface);
  box-sizing: border-box;
}
.confirm-input:focus {
  outline: none;
  border-color: var(--color-primary);
}
</style>
