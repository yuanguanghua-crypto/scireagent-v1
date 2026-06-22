<script setup>
/**
 * PageBridge — 详情页顶部深色渐变桥梁
 *
 * 承接首页 hero 深色，渐变融入内容浅色，缓解深→浅硬切。
 * 含极淡粒子剪影（呼应首页粒子网络 + footer）。
 * 被 ProductLayout 和各知识详情页复用。
 */
defineProps({
  height: { type: Number, default: 180 },
  overlap: { type: Number, default: 40 },
})
</script>

<template>
  <div
    class="page-bridge"
    :style="{ height: height + 'px', marginBottom: -overlap + 'px' }"
    aria-hidden="true"
  >
    <svg viewBox="0 0 1200 60" preserveAspectRatio="none">
      <g stroke="#5EEAD4" stroke-width="0.6" fill="none">
        <line x1="100" y1="30" x2="260" y2="20" opacity="0.18"/>
        <line x1="260" y1="20" x2="420" y2="38" opacity="0.20"/>
        <line x1="420" y1="38" x2="600" y2="24" opacity="0.16"/>
        <line x1="600" y1="24" x2="780" y2="40" opacity="0.18"/>
        <line x1="780" y1="40" x2="960" y2="22" opacity="0.20"/>
        <line x1="960" y1="22" x2="1120" y2="34" opacity="0.16"/>
      </g>
      <g>
        <circle cx="100" cy="30" r="1.4" fill="#5EEAD4" opacity="0.4"/>
        <circle cx="260" cy="20" r="1.2" fill="#99F6E4" opacity="0.35"/>
        <circle cx="420" cy="38" r="1.4" fill="#5EEAD4" opacity="0.4"/>
        <circle cx="600" cy="24" r="1" fill="#38BDF8" opacity="0.3"/>
        <circle cx="780" cy="40" r="1.4" fill="#5EEAD4" opacity="0.4"/>
        <circle cx="960" cy="22" r="1.2" fill="#B2B0FF" opacity="0.3"/>
        <circle cx="1120" cy="34" r="1.4" fill="#5EEAD4" opacity="0.4"/>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.page-bridge {
  width: 100%;
  background: linear-gradient(180deg, #0A1628 0%, #0F1F3D 45%, rgba(10, 22, 40, 0.12) 78%, transparent 100%);
  pointer-events: none;
}
.page-bridge svg {
  width: 100%;
  height: 100%;
  display: block;
  opacity: 0.55;
}
</style>
