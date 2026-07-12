<script setup>
/**
 * PageBridge — 详情页顶部极淡渐变桥梁
 *
 * 极简的 emerald 渐变色带，承接首页氛围，
 * 淡到几乎不可见，仅提供微妙的视觉过渡。
 */
defineProps({
  height: { type: Number, default: 24 },
})
</script>

<template>
  <div
    class="page-bridge"
    :style="{ height: height + 'px' }"
    aria-hidden="true"
  />
</template>

<style scoped>
.page-bridge {
  width: 100%;
  background: linear-gradient(180deg,
    rgba(5, 150, 105, 0.04) 0%,
    transparent 100%
  );
  pointer-events: none;
}
</style>
