<template>
  <div class="app-select" :class="{ 'app-select--error': error }">
    <label v-if="label" class="form-label">{{ label }}</label>
    <el-select
      :model-value="modelValue"
      :placeholder="placeholder"
      :size="size"
      :disabled="disabled"
      :clearable="clearable"
      @update:model-value="$emit('update:modelValue', $event)"
      @change="$emit('change', $event)"
    >
      <el-option
        v-for="opt in options"
        :key="opt.value"
        :label="opt.label"
        :value="opt.value"
        :disabled="opt.disabled"
      />
    </el-select>
    <span v-if="hint && !error" class="form-hint">{{ hint }}</span>
    <span v-if="error" class="form-error">{{ error }}</span>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: 'Please select' },
  options: {
    type: Array,
    default: () => [],
  },
  size: {
    type: String,
    default: 'md',
    validator: v => ['sm', 'md', 'lg'].includes(v),
  },
  disabled: { type: Boolean, default: false },
  clearable: { type: Boolean, default: false },
  error: { type: String, default: '' },
  hint: { type: String, default: '' },
})

defineEmits(['update:modelValue', 'change'])
</script>

<style scoped>
.app-select { margin-bottom: 16px; }
.app-select .form-label { display: block; margin-bottom: 4px; font-size: 13px; font-weight: 500; color: var(--color-text-secondary); }
.app-select .form-hint { display: block; margin-top: 4px; font-size: 12px; color: var(--color-text-tertiary); }
.app-select .form-error { display: block; margin-top: 4px; font-size: 12px; color: var(--color-danger); }
</style>
