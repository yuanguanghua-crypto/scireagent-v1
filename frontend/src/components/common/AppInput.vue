<template>
  <div class="app-input" :class="{ 'app-input--error': error }">
    <!-- ★ 2026-10-20 a11y + 可测性：label 原来没有 for、el-input 没有 id ⇒
         ① 屏幕阅读器关联不上（靠 placeholder 勉强过 axe，但 placeholder 按 WCAG 不能替代 label）
         ② `getByLabel()` 定位不到 ⇒ E2E 只能用脆弱的 placeholder/CSS 选择器
         修一处，全站 39 个 AppInput 实例同时受益。 -->
    <label v-if="label" class="form-label" :for="inputId">{{ label }}</label>
    <el-input
      :id="inputId"
      :model-value="modelValue"
      :placeholder="placeholder"
      :type="type === 'textarea' ? 'textarea' : type"
      :size="size"
      :disabled="disabled"
      :readonly="readonly"
      :rows="type === 'textarea' ? rows : undefined"
      :maxlength="maxlength"
      @update:model-value="$emit('update:modelValue', $event)"
    >
      <template v-if="$slots.prepend" #prepend><slot name="prepend" /></template>
      <template v-if="$slots.append" #append><slot name="append" /></template>
    </el-input>
    <span v-if="hint && !error" class="form-hint">{{ hint }}</span>
    <span v-if="error" class="form-error">{{ error }}</span>
  </div>
</template>

<script setup>
import { useId } from 'vue'

// ★ 每个实例一个稳定唯一 id，用于 label[for] ↔ input[id] 关联（Vue 3.5+ useId）
const inputId = useId()
defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  type: {
    type: String,
    default: 'text',
    validator: v => ['text', 'number', 'email', 'password', 'textarea'].includes(v),
  },
  size: {
    type: String,
    default: 'md',
    validator: v => ['sm', 'md', 'lg'].includes(v),
  },
  disabled: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false },
  rows: { type: Number, default: 2 },
  error: { type: String, default: '' },
  hint: { type: String, default: '' },
  maxlength: { type: Number, default: undefined },
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.app-input { margin-bottom: 16px; }
.app-input .form-label { display: block; margin-bottom: 4px; font-size: 13px; font-weight: 500; color: var(--color-text-secondary); }
.app-input .form-hint { display: block; margin-top: 4px; font-size: 12px; color: var(--color-text-tertiary); }
.app-input .form-error { display: block; margin-top: 4px; font-size: 12px; color: var(--color-danger); }
</style>
