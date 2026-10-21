<template>
  <div class="app-input" :class="{ 'app-input--error': error }">
    <!-- ★ 2026-10-21 **二次修正（很重要）**：
         10-20 那版给 el-input 加 `:id` + `<label :for>`，以为就关联上了。
         组件单测实测发现：**Element Plus 的 `el-input` 会吞掉 `id`** ——
           · 内部 `<input class="el-input__inner">` 无 id
           · 连 `.el-input` 根 div 上也没有 id
         ⇒ `<label for="v-0">` 指向一个**不存在的元素**，等于孤儿 label，无障碍关联**并未生效**。
         实测对照（同一组件）：`aria-label` / `name` / `data-*` / `placeholder` **都能**透传到内部 input，
         唯独 `id` 不能 ⇒ 所以改走 **aria-label**。
         ⚠️ 影响面：全站 39 个 AppInput 实例里，**只有 CheckoutPage 的 7 个传了 label**
           （其余 32 个在 ProductEditPage，多用外层 `<label>…<AppInput/></label>` 包裹式关联，那是有效的）。
         而这 7 个此前从未被 a11y 扫到 —— 因为扫 `/checkout` 时购物车是空的、表单不渲染（扫描条件不对）。
         `:id` 仍保留（无害，将来 EP 支持自动生效）；`for` 去掉（避免指向不存在目标的误导）。 -->
    <label v-if="label" class="form-label">{{ label }}</label>
    <el-input
      :id="inputId"
      :aria-label="label || placeholder || undefined"
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
