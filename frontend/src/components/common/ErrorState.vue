<script setup>
defineProps({
  title: {
    type: String,
    default: 'Something went wrong',
  },
  message: {
    type: String,
    default: 'An unexpected error occurred. Please try again.',
  },
  showRetry: {
    type: Boolean,
    default: true,
  },
})

defineEmits(['retry'])

import { AppButton } from './index'
</script>

<template>
  <div class="error-state">
    <div class="error-icon">
      <el-icon :size="48">
        <WarningFilled />
      </el-icon>
    </div>
    <h3 class="error-title">{{ title }}</h3>
    <p class="error-message">{{ message }}</p>
    <div class="error-actions">
      <AppButton v-if="showRetry" variant="primary" @click="$emit('retry')">
        <el-icon><RefreshRight /></el-icon>
        Try Again
      </AppButton>
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.error-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--color-danger-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-danger);
  margin-bottom: 16px;
}

.error-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 8px;
}

.error-message {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 20px;
  max-width: 400px;
  line-height: 1.5;
}

.error-actions {
  display: flex;
  gap: 8px;
}
</style>
