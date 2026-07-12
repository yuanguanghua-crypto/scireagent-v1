<script setup>
import { formatDate, getStatusType, truncate } from '@/utils/helpers'

const props = defineProps({
  application: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['click'])

function handleClick() {
  emit('click', props.application)
}
</script>

<template>
  <article
    class="card application-card"
    role="button"
    tabindex="0"
    :aria-label="`Application: ${application.name}`"
    @click="handleClick"
    @keydown.enter="handleClick"
  >
    <!-- Left accent - neutral color -->
    <div class="card-accent" aria-hidden="true"></div>

    <div class="card-body">
      <div class="card-header">
        <span
          v-if="application.category || application.research_goal_name"
          class="card-category"
        >
          {{ application.category || application.research_goal_name || 'General' }}
        </span>
        <el-tag :type="getStatusType(application.status)" size="small" effect="light">
          {{ application.status }}
        </el-tag>
      </div>

      <h3 class="card-title">{{ application.name }}</h3>
      <p class="card-description">{{ truncate(application.summary || application.description || '', 100) }}</p>

      <div class="card-footer">
        <span class="card-stat">
          <span class="card-stat-value">{{ application.method_count || 0 }}</span>
          <span class="card-stat-label">methods</span>
        </span>
        <span class="card-date">{{ formatDate(application.created_at) }}</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.application-card {
  cursor: pointer;
  display: flex;
  flex-direction: row;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  overflow: hidden;
  transition: box-shadow 0.2s var(--ease-out), border-color 0.2s var(--ease-out);
}

.application-card:hover {
  box-shadow: var(--shadow-card-hover);
  border-color: var(--color-border-hover);
}

.application-card:focus-visible {
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
  gap: 8px;
}

.card-category {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-tertiary);
  background: var(--color-bg);
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: 0.02em;
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
  justify-content: space-between;
  padding-top: 8px;
  margin-top: auto;
  border-top: 1px solid var(--color-border-light);
}

.card-stat {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.card-stat-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.card-stat-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.card-date {
  font-size: 11px;
  color: var(--color-text-tertiary);
}
</style>
