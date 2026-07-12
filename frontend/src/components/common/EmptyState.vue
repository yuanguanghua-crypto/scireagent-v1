<script setup>
defineProps({
  title: {
    type: String,
    default: 'No data',
  },
  description: {
    type: String,
    default: '',
  },
  icon: {
    type: String,
    default: 'Document',
  },
})

defineEmits(['action'])
</script>

<template>
  <div class="empty-state">
    <div class="empty-icon">
      <el-icon :size="48">
        <component :is="icon" />
      </el-icon>
    </div>
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-description">{{ description }}</p>
    <div class="empty-action">
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.empty-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  margin-bottom: 16px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 8px;
}

.empty-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 20px;
  max-width: 360px;
  line-height: 1.5;
}

.empty-action {
  display: flex;
  gap: 8px;
}
</style>