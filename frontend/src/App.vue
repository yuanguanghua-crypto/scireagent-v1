<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'
import ResearchCartPanel from '@/components/navigation/ResearchCartPanel.vue'
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
</style>