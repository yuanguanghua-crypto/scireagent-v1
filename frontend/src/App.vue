<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'
import ResearchCartPanel from '@/components/navigation/ResearchCartPanel.vue'
</script>

<template>
  <AppLayout>
    <router-view />
  </AppLayout>
  <ResearchCartPanel />
</template>

<style>
/* Global styles handled by Tailwind + CSS variables */
</style>