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
  <footer class="site-footer">
    <div class="site-footer-inner">
      <span>© 2026 SciReAgent. All rights reserved.</span>
      <span class="site-footer-links">
        <router-link to="/privacy">Privacy Policy</router-link>
        <router-link to="/terms">Terms of Service</router-link>
      </span>
    </div>
  </footer>
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

  .site-footer {
    margin-top: auto;
    padding: 16px 24px;
    border-top: 1px solid #e5e7eb;
    font-size: 13px;
    color: #6b7280;
  }
  .site-footer-inner {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }
  .site-footer-links { display: flex; gap: 16px; }
  .site-footer-links a { color: #374151; text-decoration: none; }
  .site-footer-links a:hover { color: #2563eb; text-decoration: underline; }
  </style>