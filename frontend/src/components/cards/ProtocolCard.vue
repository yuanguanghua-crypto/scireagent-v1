<script setup>
import { formatDate, getStatusType, truncate } from '@/utils/helpers'

const props = defineProps({
  protocol: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['click'])

function handleClick() {
  emit('click', props.protocol)
}

function formatDuration(seconds) {
  if (!seconds) return null
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m === 0) return `${s}s`
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}
</script>

<template>
  <div
    class="card protocol-card"
    role="button"
    tabindex="0"
    :aria-label="`Protocol: ${protocol.name} v${protocol.version}`"
    @click="handleClick"
    @keydown.enter="handleClick"
  >
    <div class="card-header">
      <span class="card-version">v{{ protocol.version }}</span>
      <el-tag :type="getStatusType(protocol.status)" size="small">
        {{ protocol.status }}
      </el-tag>
    </div>

    <h3 class="card-title">{{ protocol.name }}</h3>
    <p class="card-description">{{ truncate(protocol.objective || protocol.description || '', 120) }}</p>

    <div class="card-footer">
      <span v-if="protocol.steps" class="card-meta">{{ protocol.steps.length }} steps</span>
      <span v-if="formatDuration(protocol.steps?.reduce((sum, s) => sum + (s.duration_seconds || 0), 0))" class="card-duration">
        {{ formatDuration(protocol.steps.reduce((sum, s) => sum + (s.duration_seconds || 0), 0)) }}
      </span>
      <span class="card-date">{{ formatDate(protocol.created_at) }}</span>
    </div>
  </div>
</template>

<style scoped>
.protocol-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 20px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.protocol-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.protocol-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-version {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-info);
  font-family: var(--font-mono);
}

.card-title {
  font-size: var(--text-card-title);
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  line-height: 1.4;
}

.card-description {
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  margin: 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border);
}

.card-meta,
.card-duration {
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
}

.card-date {
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  margin-left: auto;
}
</style>
