<script setup>
/**
 * ListTruncationHint —— 治理列表「静默截断」提示。
 * 仅在 API 总数大于当前实际渲染行数时出现，否则不渲染任何内容。
 * `count` 取自信封 `meta.pagination.count`，`shown` 为该页 `entities.length`。
 */
defineProps({
  count: { type: Number, default: 0 },
  shown: { type: Number, default: 0 },
})
</script>

<template>
  <p v-if="count && count > shown" class="truncation-hint" data-testid="truncation-hint">
    Showing first {{ shown }} of {{ count }} records
  </p>
</template>

<style scoped>
.truncation-hint {
  margin: 0 0 12px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--color-warning);
  background: var(--color-warning-light);
  border-radius: var(--radius-md);
}
</style>
