<template>
  <div class="app-input" :class="{ 'app-input--error': error }">
    <label v-if="label" class="form-label">{{ label }}</label>
    <el-input
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
