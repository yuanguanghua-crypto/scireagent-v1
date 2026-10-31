<script setup>
import { formatDate, getStatusType, truncate } from '@/utils/helpers'
// cost_band / timeline 是枚举，后端回 `low` / `hours` 原始值，卡片用短标签
import { costBandShort, timelineShort } from '@/utils/methodSpecs'

const props = defineProps({
  method: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['click'])

function handleClick() {
  emit('click', props.method)
}
</script>

<template>
  <article
    class="card method-card"
    role="button"
    tabindex="0"
    :aria-label="`Method: ${method.name}`"
    @click="handleClick"
    @keydown.enter="handleClick"
  >
    <!-- Left accent bar - neutral color -->
    <div class="card-accent" aria-hidden="true"></div>

    <div class="card-body">
      <div class="card-header">
        <el-tag :type="getStatusType(method.status)" size="small" effect="light">
          {{ method.status }}
        </el-tag>
        <span v-if="method.is_step_tag" class="card-tag-step" title="This is a common step inside other methods, not a standalone protocol type">Step</span>
        <span class="card-badge">{{ method.protocol_count || 0 }} protocols</span>
      </div>

      <h3 class="card-title">{{ method.name }}</h3>
      <p class="card-description">{{ truncate(method.summary || method.purpose || method.description || '', 100) }}</p>

      <div class="card-footer">
        <span v-if="method.cost_band" class="card-tag">
          <span class="card-tag-icon" aria-hidden="true">$</span>
          {{ costBandShort(method.cost_band) }}
        </span>
        <span v-if="method.timeline" class="card-tag">
          <span class="card-tag-icon" aria-hidden="true">⏱</span>
          {{ timelineShort(method.timeline) }}
        </span>
        <span class="card-date">{{ formatDate(method.created_at) }}</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.method-card {
  cursor: pointer;
  display: flex;
  flex-direction: row;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  overflow: hidden;
  transition: box-shadow 0.2s var(--ease-out), border-color 0.2s var(--ease-out);
}

.method-card:hover {
  box-shadow: var(--shadow-card-hover);
  border-color: var(--color-border-hover);
}

.method-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.card-accent {
  width: 3px;
  flex-shrink: 0;
  background: var(--color-border);
  border-radius: 3px 0 0 3px;
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 16px 14px;
  min-width: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-tag-step {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--color-text-tertiary);
  background: var(--color-bg-subtle, #f3f4f6);
  border-radius: 4px;
  padding: 1px 6px;
}
.card-badge {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: 9999px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-description {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  margin-top: auto;
  border-top: 1px solid var(--color-border-light);
}

.card-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  padding: 2px 6px;
  border-radius: 4px;
}

.card-tag-icon {
  font-size: 10px;
}

.card-date {
  font-size: 11px;
  color: var(--color-text-tertiary);
  margin-left: auto;
}
</style>
