<script setup>
defineProps({
  size: {
    type: String,
    default: 'medium',
    validator: (val) => ['small', 'medium', 'large'].includes(val),
  },
  text: {
    type: String,
    default: 'Loading...',
  },
  fullscreen: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <div
    class="loading-spinner"
    :class="[
      `size-${size}`,
      { 'is-fullscreen': fullscreen },
    ]"
  >
    <div class="spinner-container">
      <div class="spinner"></div>
      <p v-if="text" class="spinner-text">{{ text }}</p>
    </div>
  </div>
</template>

<style scoped>
.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.loading-spinner.is-fullscreen {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.85);
  z-index: 9999;
  backdrop-filter: blur(2px);
}

.spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.spinner {
  border-radius: 50%;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  animation: spin 0.8s linear infinite;
}

.size-small .spinner {
  width: 20px;
  height: 20px;
  border-width: 2px;
}

.size-medium .spinner {
  width: 32px;
  height: 32px;
}

.size-large .spinner {
  width: 48px;
  height: 48px;
  border-width: 4px;
}

.spinner-text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>