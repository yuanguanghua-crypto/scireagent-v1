<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'
import ResearchCartPanel from '@/components/navigation/ResearchCartPanel.vue'
import ConfirmHost from '@/components/common/ConfirmHost.vue'
</script>

<template>
  <AppLayout>
    <router-view v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </router-view>
  </AppLayout>
  <ResearchCartPanel />
  <!-- ★ 2026-11-18（S4）：全局确认框宿主。必须常驻在根部 —— 任何页面
       `await ask(...)` 都指向它；缺了它 Promise 永远不结算（点了没反应）。 -->
  <ConfirmHost />
  <!-- ★ 2026-11-27（A-106）：这里原本还有一个 `.site-footer`（浅色、写 "SciReAgent"、
       只带 Privacy/Terms），与 AppLayout 里的 AppFooter 叠成**双页脚**。
       页脚统一由 AppFooter 承担（单个、深色、品牌写法与全站一致），此处不再重复渲染。 -->
</template>

<style>
/* Global styles handled by Tailwind + CSS variables */

/* Page transition (route switching) */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
  .page-leave-to {
    opacity: 0;
    transform: translateY(-4px);
  }

  /* ★ 2026-11-27（A-106）：`.site-footer*` 一组样式随双页脚一并删除（页脚只剩 AppFooter）。 */
  </style>