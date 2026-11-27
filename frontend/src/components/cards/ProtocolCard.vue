<script setup>
import { formatDate, getStatusType, truncate } from '@/utils/helpers'

const props = defineProps({
  protocol: {
    type: Object,
    required: true,
  },
  /**
   * 是否显示 status 标签（默认关）。
   *
   * ★ 2026-10-26：访客看到的协议全是 published（draft/superseded 已被后端过滤），
   *   这个标签对访客**零区分度**，还白占一个视觉位置。只有 staff 在按状态筛选
   *   （比如看 Draft）时才需要它来区分。所以改为默认不显示、由调用方按身份开启。
   */
  showStatus: {
    type: Boolean,
    default: false,
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
    <div class="card-accent" aria-hidden="true"></div>
    <div class="card-header">
      <span class="card-version">v{{ protocol.version }}</span>
      <el-tag v-if="showStatus" :type="getStatusType(protocol.status)" size="small">
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
/* ★ 2026-11-27（A-130）：这里原写 `display:flex; flex-direction:row`，而模板有
   **5 个子元素**（accent / header[版本] / title / description / footer[日期]）
   ⇒ 五个块被排成**一行**：版本在最左、标题居中、日期在最右，footer 的 `border-top`
   就变成一条**横穿文字的线**（截图可见，QA 报的"日期与标题、编号重叠"就是它）。
   修法：内容改回**竖向堆叠**（flex column），左侧色条改成**绝对定位**贴边 ——
   这样它不再参与流内布局，也就不需要把模板内容再包一层。
   ⚠️ 第一版试过两列 grid，结果内容列被压窄、标题逐词换行（更糟），已回退。 */
.protocol-card {
  position: relative;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px 20px 20px 28px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.card-accent {
  position: absolute;
  left: 12px;
  top: 20px;
  bottom: 20px;
  width: 3px;
  background: var(--color-border);
  border-radius: 3px;
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
