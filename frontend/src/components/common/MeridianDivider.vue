<script setup>
/**
 * MeridianDivider — 贝塞尔经络分隔线（缓慢波动版）
 *
 * 用 SVG SMIL <animate> 驱动 path 形状在多个波形间缓慢循环，
 * 两条线不同相位 + 散点呼吸，营造水流/呼吸感。
 * 零 JS、声明式；prefers-reduced-motion 下禁用动画。
 */
defineProps({
  flip: { type: Boolean, default: false },
  height: { type: Number, default: 48 },
  accent: { type: String, default: '#5EEAD4' },
})
</script>

<template>
  <div
    class="meridian-divider"
    :class="{ flip }"
    :style="{ height: height + 'px' }"
    aria-hidden="true"
  >
    <svg viewBox="0 0 1200 48" preserveAspectRatio="none">
      <defs>
        <linearGradient id="md-grad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#0A1628" stop-opacity="0.12" />
          <stop offset="0.5" :stop-color="accent" stop-opacity="0.28" />
          <stop offset="1" stop-color="#38BDF8" stop-opacity="0" />
        </linearGradient>
      </defs>

      <!-- 主经络线：缓慢波动（16s 循环）-->
      <path stroke="url(#md-grad)" stroke-width="1" fill="none">
        <animate
          attributeName="d"
          values="
            M0,28 C200,10 380,42 600,22 S1000,34 1200,14;
            M0,30 C200,14 380,38 600,26 S1000,30 1200,18;
            M0,26 C200,8 380,44 600,20 S1000,36 1200,12;
            M0,28 C200,10 380,42 600,22 S1000,34 1200,14"
          dur="16s"
          repeatCount="indefinite"
          calcMode="spline"
          keyTimes="0;0.33;0.66;1"
          keySplines="0.4 0 0.6 1;0.4 0 0.6 1;0.4 0 0.6 1"
        />
      </path>

      <!-- 辅经络线：不同相位（20s 循环）-->
      <path stroke="url(#md-grad)" stroke-width="0.8" fill="none" opacity="0.5">
        <animate
          attributeName="d"
          values="
            M0,36 C240,24 440,38 680,28 S1040,22 1200,30;
            M0,34 C240,28 440,34 680,30 S1040,26 1200,34;
            M0,38 C240,20 440,42 680,26 S1040,18 1200,26;
            M0,36 C240,24 440,38 680,28 S1040,22 1200,30"
          dur="20s"
          repeatCount="indefinite"
          calcMode="spline"
          keyTimes="0;0.33;0.66;1"
          keySplines="0.4 0 0.6 1;0.4 0 0.6 1;0.4 0 0.6 1"
        />
      </path>

      <!-- 散点星点：缓慢呼吸 -->
      <circle :fill="accent">
        <animate attributeName="cx" values="180;200;180" dur="14s" repeatCount="indefinite" />
        <animate attributeName="cy" values="22;26;22" dur="14s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.5;0.2;0.5" dur="5s" repeatCount="indefinite" />
        <set attributeName="r" to="1.5" />
      </circle>
      <circle fill="#8FE8FF">
        <animate attributeName="cx" values="520;540;520" dur="18s" repeatCount="indefinite" />
        <animate attributeName="cy" values="34;30;34" dur="18s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.45;0.18;0.45" dur="6s" repeatCount="indefinite" />
        <set attributeName="r" to="1" />
      </circle>
      <circle :fill="accent">
        <animate attributeName="cx" values="860;840;860" dur="16s" repeatCount="indefinite" />
        <animate attributeName="cy" values="18;22;18" dur="16s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.5;0.2;0.5" dur="5.5s" repeatCount="indefinite" />
        <set attributeName="r" to="1.2" />
      </circle>
      <circle fill="#B2B0FF">
        <animate attributeName="cx" values="1080;1060;1080" dur="20s" repeatCount="indefinite" />
        <animate attributeName="cy" values="28;32;28" dur="20s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.4;0.15;0.4" dur="6.5s" repeatCount="indefinite" />
        <set attributeName="r" to="1" />
      </circle>
    </svg>
  </div>
</template>

<style scoped>
.meridian-divider {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  pointer-events: none;
}
.meridian-divider svg {
  width: 100%;
  height: 100%;
  display: block;
}
.flip svg { transform: scaleY(-1); }

/* prefers-reduced-motion：停止所有 SMIL 动画 */
@media (prefers-reduced-motion: reduce) {
  .meridian-divider :deep(animate) { display: none; }
}
</style>
