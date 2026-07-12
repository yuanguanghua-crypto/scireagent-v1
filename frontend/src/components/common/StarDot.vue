<script setup>
/**
 * StarDot — 可复用静态/微动星点（全站视觉词汇）
 *
 * 用于：StatsBar 角落、section 标题装饰、CategoryPills dot、知识页 icon 等。
 * Phase 2 跨页面血脉的核心复用单元。
 */
defineProps({
  size: { type: Number, default: 4 },
  color: { type: String, default: '#8FE8FF' },
  glow: { type: Boolean, default: true },   // 是否带光晕
  pulse: { type: Boolean, default: false }, // 是否呼吸闪烁
})
</script>

<template>
  <span
    class="star-dot"
    :class="{ pulse, glow }"
    :style="{ '--sz': size + 'px', '--c': color }"
    aria-hidden="true"
  >
    <span class="star-dot__core"></span>
  </span>
</template>

<style scoped>
.star-dot {
  position: relative;
  display: inline-block;
  width: var(--sz);
  height: var(--sz);
  flex-shrink: 0;
}
.star-dot__core {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--c);
}
.star-dot.glow .star-dot__core {
  box-shadow:
    0 0 calc(var(--sz) * 1.2) var(--c),
    0 0 calc(var(--sz) * 2.4) color-mix(in srgb, var(--c) 40%, transparent);
}
.star-dot.pulse .star-dot__core {
  animation: star-dot-pulse 2.6s ease-in-out infinite;
}
@keyframes star-dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.45; transform: scale(0.82); }
}
@media (prefers-reduced-motion: reduce) {
  .star-dot.pulse .star-dot__core { animation: none; }
}
</style>
