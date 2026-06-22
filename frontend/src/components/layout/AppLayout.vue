<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
import PublicNav from './PublicNav.vue'

const route = useRoute()

// Public pages (no auth needed, transparent nav): Home, Login, Register, Product lists, Knowledge pages
const isPublicPage = () => route.meta?.nav === 'public'

// Workspace has its own sidebar via AdminLayout — hide nav entirely
const isWorkspace = () => route.path.startsWith('/workspace')
</script>

<template>
  <div class="app-layout" :class="{ 'layout-workspace': isWorkspace() }">
    <!-- Public pages: transparent fixed-top nav -->
    <PublicNav v-if="isPublicPage()" />

    <!-- Authenticated pages: full AppHeader -->
    <AppHeader v-else-if="!isWorkspace()" />

    <main class="content-area">
      <slot />
    </main>

    <AppFooter v-if="!isWorkspace()" />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--color-bg);
}

.layout-workspace {
  /* workspace handles its own layout */
}

.content-area {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
}

/* Public pages with transparent nav need no top padding — PublicNav is fixed overlay */
.public-layout .content-area {
  padding-top: 0;
}

@media (max-width: 768px) {
  .content-area {
    padding: 16px;
  }
}
</style>
