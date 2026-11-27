<script setup>
/**
 * `<IsoDateInput>` —— 日期输入的统一实现（A-249 收尾）。
 *
 * ## 为什么要它
 * 全站原先有 9 个 `<input type="date">`。实测（Edge/zh-CN，真实浏览器）：
 *
 *     手打 `2026-11-27`  ⇒  value 变成 `202611-02-07`
 *     手打 `11272026`    ⇒  value 变成 `""`
 *
 * 因为 `type=date` 是**分段输入**，`-` 不推进分段，浏览器按 locale 把数字塞进
 * 年/月/日；值一旦变脏，用户原意已丢失、无法事后修正。而全站日期**显示**都是
 * `YYYY-MM-DD`，运营照屏幕格式打就是打不进去。
 *
 * ## ★ 为什么根元素必须是 input 本身（踩过）
 * 第一版把 input 包在 `<span>` 里，结果调用方写的 `class="po-input sr-date"`
 * 里那条 **scoped** 规则（`.sr-date { width: 150px }`）**不生效** —— Vue 的 scoped
 * 样式只会把父组件的 scope id 加到子组件的**根元素**上，包一层就等于把 caller 的
 * 样式全废掉，宽度回落到全局 `.po-input { width:100% }`（实测 217px vs 预期 150px）。
 * 所以：**根节点 = input**，class / aria-label / data-testid 全部原样透传；
 * 错误文案通过 `@invalid` 抛给调用方，由各页自己的错误位渲染。
 *
 * ## 契约
 * - `v-model` 始终是「归一后的 ISO 字符串或空串」；空串表示"不填"。
 * - `@change` 只在**归一成功后**触发（空也算成功），所以父组件可以安全地拿它发请求
 *   —— 不会像原生 `type=date` 那样在用户改年份的中途触发。
 * - `@invalid(msg)`：空串表示恢复合法；非空时父组件可据此禁用提交或显示错误。
 * - 非法写法**不猜**：`03/04/2026` 到底是 3 月 4 日还是 4 月 3 日 → 报错。
 */
import { ref, watch } from 'vue'
import { normalizeIsoDate } from '@/utils/isoDate'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  modelValue: { type: String, default: '' },
  /** 最小可选日期（ISO）。留空则不校验下限。 */
  min: { type: String, default: '' },
  /** 最大可选日期（ISO）。留空则不校验上限。 */
  max: { type: String, default: '' },
  placeholder: { type: String, default: 'YYYY-MM-DD' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'change', 'invalid'])

const text = ref(props.modelValue || '')
const error = ref('')

// 外部改了值（如点"最近 30 天"预设）⇒ 同步进输入框
watch(() => props.modelValue, (v) => {
  if ((v || '') !== text.value) {
    text.value = v || ''
    error.value = ''
  }
})

function setError(msg) {
  if (error.value !== msg) {
    error.value = msg
    emit('invalid', msg)
  }
}

/** 输入过程中只同步原文；归一放在失焦/回车，避免用户打一半就被改写 */
function onInput(e) {
  text.value = e.target.value
  emit('update:modelValue', text.value)
  setError('')
}

function commit() {
  const r = normalizeIsoDate(text.value)
  if (!r.ok) {
    setError(r.error)
    return
  }
  // 上下限：与原生 `:min` 同语义（ISO 字符串直接比大小即等价）
  if (r.value && props.min && r.value < props.min) {
    setError(`Must be on or after ${props.min}.`)
    return
  }
  if (r.value && props.max && r.value > props.max) {
    setError(`Must be on or before ${props.max}.`)
    return
  }
  text.value = r.value
  setError('')
  emit('update:modelValue', r.value)
  emit('change', r.value)
}

defineExpose({
  /** 父组件提交前可主动校验一次（防"打完直接点按钮"绕过 blur） */
  validate() {
    commit()
    return !error.value
  },
})
</script>

<template>
  <input
    :value="text"
    type="text"
    inputmode="numeric"
    autocomplete="off"
    :placeholder="placeholder"
    :disabled="disabled"
    :class="{ 'iso-date-invalid': !!error }"
    :aria-invalid="error ? 'true' : undefined"
    :title="error || undefined"
    @input="onInput"
    @blur="commit"
    @keyup.enter="commit"
    v-bind="$attrs"
  />
</template>

<style scoped>
/* 只做"错了"的视觉标记，不改布局尺寸 —— 尺寸由调用方的 class 决定 */
.iso-date-invalid {
  border-color: #dc2626 !important;
  box-shadow: 0 0 0 1px #dc2626 inset;
}
</style>
